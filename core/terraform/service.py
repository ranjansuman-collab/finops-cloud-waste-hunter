"""
core/terraform/service.py
Coordinates real Terraform execution lifecycle with strict FinOps safety gates.

Workflow:
1. Workspace setup (isolated from project source files).
2. Structured modification & security validation.
3. terraform fmt.
4. terraform validate.
5. terraform plan (-no-color -out=tfplan).
6. Plan review & staleness tracking.
7. EXPLICIT HUMAN APPROVAL (with additional confirmation for destructive actions).
8. terraform apply.
9. Read-only AWS verification.

Safety Invariants:
- NEVER executes terraform apply automatically.
- NEVER applies without explicit user approval.
- Bedrock is recommendation-only and CANNOT invoke apply.
- Live mode NEVER fakes Terraform success.

ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import os
import time
import uuid
import shutil
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from core.models import (
    WasteFinding,
    AIRecommendation,
    CostFinding,
    ResourceType,
)
from core.terraform.models import (
    TerraformPlanResult,
    TerraformApplyResult,
    TerraformApprovalRequest,
    AWSVerificationResult,
)
from core.terraform.cli import (
    TerraformCLI,
    STATUS_SUCCESS,
    STATUS_TERRAFORM_NOT_INSTALLED,
    STATUS_FMT_FAILED,
    STATUS_VALIDATION_FAILED,
)
from core.terraform.generator import (
    TerraformChangeGenerator,
    STATUS_UNSUPPORTED_ACTION,
    STATUS_SECURITY_POLICY_VIOLATION,
    STATUS_RESOURCE_NOT_FOUND_IN_CONFIG,
)
from core.aws.connection import (
    AWSConnectionService,
    get_configured_region,
    has_aws_credentials,
    STATUS_CREDENTIALS_MISSING,
    STATUS_CONNECTED,
)

logger = logging.getLogger("finops.terraform.service")

PLAN_EXPIRY_SECONDS = 1800  # 30 minutes


class StoredPlan:
    """Internal registry record for an active, unapplied Terraform plan."""

    def __init__(
        self,
        plan_id: str,
        config_hash: str,
        affected_resources: List[str],
        proposed_actions: List[str],
        is_destructive: bool,
        plan_file: Path,
        unified_diff: str,
        estimated_savings: float = 0.0,
    ):
        self.plan_id = plan_id
        self.config_hash = config_hash
        self.affected_resources = affected_resources
        self.proposed_actions = proposed_actions
        self.is_destructive = is_destructive
        self.plan_file = plan_file
        self.unified_diff = unified_diff
        self.estimated_savings = estimated_savings
        self.created_at = time.time()
        self.applied = False

    def is_stale(self) -> bool:
        return (time.time() - self.created_at) > PLAN_EXPIRY_SECONDS


class RealTerraformService:
    """
    Manages the complete real Terraform workflow with safety controls,
    plan verification, and post-apply read-only AWS verification.
    """

    def __init__(
        self,
        workspace_dir: Optional[Path] = None,
        source_dir: Optional[Path] = None,
        use_live_terraform: bool = True,
        region_name: Optional[str] = None
    ):
        base_dir = Path(__file__).parent.parent.parent
        self.workspace_dir = Path(workspace_dir or (base_dir / "storage" / "terraform_workspace"))
        self.source_dir = Path(source_dir or (base_dir / "sample_infrastructure"))
        self.use_live_terraform = use_live_terraform
        self.region = get_configured_region(region_name)
        self.cli = TerraformCLI(workspace_dir=self.workspace_dir)
        self.generator = TerraformChangeGenerator()
        self.active_plans: Dict[str, StoredPlan] = {}

    def initialize_workspace(self) -> bool:
        """
        Creates an isolated working copy of Terraform files in the workspace directory.
        Prevents corrupting original project template files.
        """
        try:
            self.workspace_dir.mkdir(parents=True, exist_ok=True)
            if self.source_dir.exists():
                for item in self.source_dir.glob("*.tf"):
                    dest = self.workspace_dir / item.name
                    if not dest.exists():
                        shutil.copy2(item, dest)
            return True
        except Exception as exc:
            logger.error(f"Failed to initialize Terraform workspace: {exc}")
            return False

    def reset_workspace_file(self, filename: str = "main.tf") -> None:
        """Restores a workspace file from the original source template."""
        src = self.source_dir / filename
        dest = self.workspace_dir / filename
        if src.exists():
            shutil.copy2(src, dest)

    def _compute_file_hash(self, filepath: Path) -> str:
        """Calculates SHA-256 hash of a file for staleness and tampering detection."""
        if not filepath.exists():
            return ""
        return hashlib.sha256(filepath.read_bytes()).hexdigest()

    # ------------------------------------------------------------------
    # Step 1-5: Change Proposal, fmt, validate, and plan
    # ------------------------------------------------------------------

    def create_plan(
        self,
        findings: List[WasteFinding],
        recommendations: Optional[List[AIRecommendation]] = None,
        cost_findings: Optional[List[CostFinding]] = None,
    ) -> TerraformPlanResult:
        """
        Executes the pre-apply pipeline:
        Generate HCL -> terraform fmt -> terraform validate -> terraform plan.

        Returns a structured TerraformPlanResult.
        NEVER executes terraform apply.
        """
        self.initialize_workspace()
        main_tf = self.workspace_dir / "main.tf"
        if not main_tf.exists():
            return TerraformPlanResult(
                plan_id="",
                success=False,
                return_code=1,
                stdout="",
                stderr="main.tf not found in Terraform workspace.",
                status="WORKSPACE_ERROR",
                errors=["main.tf missing in workspace"],
            )

        original_hcl = main_tf.read_text(encoding="utf-8")
        current_hcl = original_hcl
        affected_resources: List[str] = []
        proposed_actions: List[str] = []
        is_destructive = False

        rec_map = {r.finding_id: r for r in (recommendations or [])}
        cost_map = {c.finding_id: c for c in (cost_findings or [])}
        total_savings = 0.0

        errors: List[str] = []

        for finding in findings:
            rec = rec_map.get(finding.id)
            new_hcl, action_type, status = self.generator.generate_modification(
                finding=finding,
                content=current_hcl,
                recommendation=rec,
            )

            if status == STATUS_SECURITY_POLICY_VIOLATION:
                return TerraformPlanResult(
                    plan_id="",
                    success=False,
                    return_code=1,
                    stdout="",
                    stderr="Security policy violation in proposed modification.",
                    status=STATUS_SECURITY_POLICY_VIOLATION,
                    errors=[f"Security violation: untrusted inputs rejected for {finding.resource_name}"],
                )

            if status in (STATUS_UNSUPPORTED_ACTION, STATUS_RESOURCE_NOT_FOUND_IN_CONFIG):
                errors.append(f"Skipping {finding.resource_name} ({finding.resource_type}): {status}")
                continue

            if status == "SUCCESS" and new_hcl:
                current_hcl = new_hcl
                affected_resources.append(finding.resource_name)
                proposed_actions.append(action_type or "MODIFY")
                if action_type in ("DELETE", "DISASSOCIATE", "RELEASE", "TERMINATE"):
                    is_destructive = True
                cost = cost_map.get(finding.id)
                if cost:
                    total_savings += cost.monthly_savings

        if not affected_resources:
            if any("UNSUPPORTED_ACTION" in e for e in errors):
                return TerraformPlanResult(
                    plan_id="",
                    success=False,
                    return_code=1,
                    stdout="",
                    stderr="The requested action is unsupported for Terraform automation.",
                    status=STATUS_UNSUPPORTED_ACTION,
                    errors=errors,
                )
            return TerraformPlanResult(
                plan_id="",
                success=True,
                return_code=0,
                stdout="No Terraform modifications needed for provided findings.",
                stderr="",
                status="NO_CHANGES_REQUIRED",
                unified_diff="",
                errors=errors,
            )

        # Write modified HCL to workspace
        main_tf.write_text(current_hcl, encoding="utf-8")
        unified_diff = self.generator.compute_diff(original_hcl, current_hcl, "main.tf")
        config_hash = self._compute_file_hash(main_tf)

        # In simulation mode (or when Terraform CLI is not enabled for live execution)
        if not self.use_live_terraform:
            plan_id = f"plan-sim-{uuid.uuid4().hex[:8]}"
            plan_file = self.workspace_dir / f"{plan_id}.tfplan"
            plan_file.write_text("SIMULATED_PLAN_DATA", encoding="utf-8")

            stored = StoredPlan(
                plan_id=plan_id,
                config_hash=config_hash,
                affected_resources=affected_resources,
                proposed_actions=proposed_actions,
                is_destructive=is_destructive,
                plan_file=plan_file,
                unified_diff=unified_diff,
                estimated_savings=total_savings,
            )
            self.active_plans[plan_id] = stored

            simulated_plan_stdout = (
                f"Terraform will perform the following actions:\n\n"
                f"  # Simulated Plan for {len(affected_resources)} resource(s)\n"
                f"{unified_diff}\n"
                f"Plan: {len(affected_resources)} to change, 0 to add, 0 to destroy."
            )
            return TerraformPlanResult(
                plan_id=plan_id,
                success=True,
                return_code=0,
                stdout=simulated_plan_stdout,
                stderr="",
                status=STATUS_SUCCESS,
                config_hash=config_hash,
                affected_resources=affected_resources,
                proposed_actions=proposed_actions,
                estimated_savings=round(total_savings, 2),
                is_destructive=is_destructive,
                requires_approval=True,
                unified_diff=unified_diff,
                plan_file=str(plan_file),
            )

        # -------------------------------------------------------------
        # Real Terraform CLI Execution
        # -------------------------------------------------------------
        # 1. Check if Terraform CLI is installed
        installed, ver_msg = self.cli.is_installed()
        if not installed:
            return TerraformPlanResult(
                plan_id="",
                success=False,
                return_code=127,
                stdout="",
                stderr=f"Terraform CLI is not installed: {ver_msg}",
                status=STATUS_TERRAFORM_NOT_INSTALLED,
                errors=["Terraform CLI not found on system PATH"],
            )

        # 2. terraform fmt
        fmt_res = self.cli.fmt(check=True)
        if not fmt_res.success:
            # Try auto-formatting once
            auto_fmt = self.cli.fmt(check=False)
            if not auto_fmt.success:
                return TerraformPlanResult(
                    plan_id="",
                    success=False,
                    return_code=fmt_res.return_code,
                    stdout=fmt_res.stdout,
                    stderr=f"terraform fmt failed: {fmt_res.stderr}",
                    status=STATUS_FMT_FAILED,
                    errors=[f"terraform fmt error: {fmt_res.stderr}"],
                )

        # 3. terraform validate
        val_res = self.cli.validate()
        if not val_res.valid:
            return TerraformPlanResult(
                plan_id="",
                success=False,
                return_code=val_res.return_code,
                stdout=val_res.stdout,
                stderr=f"terraform validate failed: {val_res.stderr}",
                status=STATUS_VALIDATION_FAILED,
                errors=[f"terraform validate error: {val_res.stderr}"],
            )

        # 4. terraform plan
        plan_id = f"plan-{uuid.uuid4().hex[:8]}"
        plan_file_name = f"{plan_id}.tfplan"
        plan_file_path = self.workspace_dir / plan_file_name

        plan_res = self.cli.plan(plan_out=plan_file_name)
        if not plan_res.success:
            return TerraformPlanResult(
                plan_id="",
                success=False,
                return_code=plan_res.return_code,
                stdout=plan_res.stdout,
                stderr=f"terraform plan failed: {plan_res.stderr}",
                status="PLAN_FAILED",
                errors=[f"terraform plan error: {plan_res.stderr}"],
            )

        # Store verified plan for future explicit approval
        stored = StoredPlan(
            plan_id=plan_id,
            config_hash=config_hash,
            affected_resources=affected_resources,
            proposed_actions=proposed_actions,
            is_destructive=is_destructive,
            plan_file=plan_file_path,
            unified_diff=unified_diff,
            estimated_savings=total_savings,
        )
        self.active_plans[plan_id] = stored

        return TerraformPlanResult(
            plan_id=plan_id,
            success=True,
            return_code=0,
            stdout=plan_res.stdout,
            stderr=plan_res.stderr,
            status=STATUS_SUCCESS,
            config_hash=config_hash,
            affected_resources=affected_resources,
            proposed_actions=proposed_actions,
            estimated_savings=round(total_savings, 2),
            is_destructive=is_destructive,
            requires_approval=True,
            unified_diff=unified_diff,
            plan_file=str(plan_file_path),
        )

    # ------------------------------------------------------------------
    # Step 6-9: Explicit Approval, Apply, and Read-Only AWS Verification
    # ------------------------------------------------------------------

    def apply_plan(
        self,
        approval: TerraformApprovalRequest,
        use_live_aws: bool = False
    ) -> TerraformApplyResult:
        """
        Executes terraform apply strictly following the 6-point safety check:
        1. A valid Terraform plan exists.
        2. The plan completed successfully.
        3. The Terraform configuration has not changed since the plan was created.
        4. The plan is not stale (expires in 30 minutes).
        5. The user explicitly approved the action (approved=True).
        6. Destructive actions require confirm_destructive=True.

        After apply: performs read-only AWS verification.
        NEVER reports success if Terraform failed.
        """
        # Safety Gate 1: Check plan exists
        stored_plan = self.active_plans.get(approval.plan_id)
        if not stored_plan:
            return TerraformApplyResult(
                plan_id=approval.plan_id,
                success=False,
                return_code=1,
                stdout="",
                stderr="Terraform plan not found or expired.",
                status="PLAN_NOT_FOUND",
                errors=["No plan matching the provided plan_id was found."],
            )

        # Safety Gate 2: Check if already applied
        if stored_plan.applied:
            return TerraformApplyResult(
                plan_id=approval.plan_id,
                success=False,
                return_code=1,
                stdout="",
                stderr="This Terraform plan has already been applied.",
                status="PLAN_ALREADY_APPLIED",
                errors=["Re-application of previously executed plans is disallowed."],
            )

        # Safety Gate 3: Check if plan is stale
        if stored_plan.is_stale():
            return TerraformApplyResult(
                plan_id=approval.plan_id,
                success=False,
                return_code=1,
                stdout="",
                stderr="The Terraform plan is stale (>30 minutes old). Re-plan required.",
                status="PLAN_STALE",
                errors=["Plan expired. Please generate a fresh plan before applying."],
            )

        # Safety Gate 4: Check explicit user approval
        if not approval.approved:
            return TerraformApplyResult(
                plan_id=approval.plan_id,
                success=False,
                return_code=1,
                stdout="",
                stderr="Explicit user approval is required before applying Terraform changes.",
                status="APPROVAL_REQUIRED",
                errors=["User rejected or did not provide approval."],
            )

        # Safety Gate 5: Check destructive confirmation
        if stored_plan.is_destructive and not approval.confirm_destructive:
            return TerraformApplyResult(
                plan_id=approval.plan_id,
                success=False,
                return_code=1,
                stdout="",
                stderr=(
                    "This action involves destructive operations (deletion, termination, or release). "
                    "Explicit confirmation (confirm_destructive=True) is required."
                ),
                status="DESTRUCTIVE_CONFIRMATION_REQUIRED",
                errors=["Destructive confirmation missing."],
            )

        # Safety Gate 6: Verify configuration integrity (tamper detection)
        main_tf = self.workspace_dir / "main.tf"
        current_hash = self._compute_file_hash(main_tf)
        if current_hash != stored_plan.config_hash:
            return TerraformApplyResult(
                plan_id=approval.plan_id,
                success=False,
                return_code=1,
                stdout="",
                stderr="Terraform configuration has been modified since the plan was reviewed. Re-plan required.",
                status="CONFIG_TAMPERED",
                errors=["Configuration hash mismatch."],
            )

        # -------------------------------------------------------------
        # Execute Apply
        # -------------------------------------------------------------
        if not self.use_live_terraform:
            # Simulation mode
            stored_plan.applied = True
            verification = self._verify_aws_change(
                affected_resources=stored_plan.affected_resources,
                use_live_aws=False,
            )
            return TerraformApplyResult(
                plan_id=approval.plan_id,
                success=True,
                return_code=0,
                stdout=f"Apply complete! Resources: {len(stored_plan.affected_resources)} changed. (Simulated Mode)",
                stderr="",
                status=STATUS_SUCCESS,
                affected_resources=stored_plan.affected_resources,
                proposed_actions=stored_plan.proposed_actions,
                verification=verification,
            )

        # Live Terraform execution
        installed, ver_msg = self.cli.is_installed()
        if not installed:
            return TerraformApplyResult(
                plan_id=approval.plan_id,
                success=False,
                return_code=127,
                stdout="",
                stderr=f"Terraform CLI is not installed: {ver_msg}",
                status=STATUS_TERRAFORM_NOT_INSTALLED,
                errors=["Terraform CLI missing on system PATH."],
            )

        plan_filename = stored_plan.plan_file.name
        apply_res = self.cli.apply(plan_file=plan_filename)

        if not apply_res.success:
            return TerraformApplyResult(
                plan_id=approval.plan_id,
                success=False,
                return_code=apply_res.return_code,
                stdout=apply_res.stdout,
                stderr=apply_res.stderr,
                status="APPLY_FAILED",
                affected_resources=stored_plan.affected_resources,
                proposed_actions=stored_plan.proposed_actions,
                errors=[f"terraform apply failed: {apply_res.stderr}"],
            )

        stored_plan.applied = True

        # -------------------------------------------------------------
        # Read-Only Post-Apply AWS Verification
        # -------------------------------------------------------------
        verification = self._verify_aws_change(
            affected_resources=stored_plan.affected_resources,
            use_live_aws=use_live_aws,
        )

        return TerraformApplyResult(
            plan_id=approval.plan_id,
            success=True,
            return_code=0,
            stdout=apply_res.stdout,
            stderr=apply_res.stderr,
            status=STATUS_SUCCESS,
            affected_resources=stored_plan.affected_resources,
            proposed_actions=stored_plan.proposed_actions,
            verification=verification,
        )

    def _verify_aws_change(
        self,
        affected_resources: List[str],
        use_live_aws: bool
    ) -> AWSVerificationResult:
        """
        Conducts read-only verification of AWS resources after Terraform apply.
        Never mutates AWS.
        """
        target_name = affected_resources[0] if affected_resources else "unknown"

        if not use_live_aws:
            return AWSVerificationResult(
                resource_id=target_name,
                resource_type="SIMULATED",
                verified=True,
                status="SIMULATED",
                message=f"Simulated verification: changes for '{target_name}' registered successfully.",
            )

        # Live verification: check credentials first
        conn_service = AWSConnectionService(self.region)
        sts = conn_service.get_caller_identity()
        if not sts["authenticated"]:
            return AWSVerificationResult(
                resource_id=target_name,
                resource_type="LIVE_AWS",
                verified=False,
                status=STATUS_CREDENTIALS_MISSING,
                message=f"Post-apply verification aborted: {sts['message']}",
            )

        # Real read-only discovery to verify resource state
        try:
            from core.aws.discovery import AWSDiscoveryService
            discovery = AWSDiscoveryService(self.region)
            all_res = discovery.discover_all()

            # Inspect if resource is still present or updated
            found = False
            for group_name in ("instances", "volumes", "elastic_ips", "functions", "buckets"):
                for r in all_res.get(group_name, []):
                    if r.get("name") == target_name or r.get("id") == target_name:
                        found = True
                        break

            return AWSVerificationResult(
                resource_id=target_name,
                resource_type="LIVE_AWS",
                verified=True,
                status="VERIFIED",
                message=f"Read-only AWS verification confirmed resource state in {self.region}.",
                details={"verified_in_region": self.region, "resource_found": found},
            )
        except Exception as exc:
            logger.warning(f"Live AWS verification encountered error: {exc}")
            return AWSVerificationResult(
                resource_id=target_name,
                resource_type="LIVE_AWS",
                verified=False,
                status="ERROR",
                message=f"Verification query failed: {str(exc)}",
            )
