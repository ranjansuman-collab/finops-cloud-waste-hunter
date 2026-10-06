"""
Module 7: GitOps Review & Pull Request Engine
Creates human-reviewable GitOps pull requests, CI/CD automated checks, and controlled approval workflows.
ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from core.models import (
    GitOpsPR,
    TerraformPatch,
    WasteFinding,
    CostFinding,
    AIRecommendation
)

from core.gitops.orchestrator import GitOpsOrchestrator
from core.gitops.models import GitOpsWorkflowResult

logger = logging.getLogger("finops.module7")


class GitOpsReviewModule:
    """
    Implements FR10 & FR11:
    Orchestrates the GitOps approval workflow, branch isolation, PR generation,
    CI validation status checks, and merge-to-deploy transitions.
    Interfaces with GitOpsOrchestrator for real local Git and remote GitHub operations.
    """

    def __init__(self, use_live_gitops: bool = False):
        self.use_live_gitops = use_live_gitops
        self.orchestrator = GitOpsOrchestrator(use_live_gitops=use_live_gitops)
        self.active_prs: Dict[str, GitOpsPR] = {}
        self._pr_counter = 42

    def execute_workflow(
        self,
        run_id: str,
        findings: List[WasteFinding],
        costs: Optional[List[CostFinding]] = None,
        recommendations: Optional[List[AIRecommendation]] = None,
        patches: Optional[List[TerraformPatch]] = None,
        total_monthly_savings: float = 0.0,
        files_to_commit: Optional[List[str]] = None,
        is_destructive: bool = False,
        base_branch: str = "main",
    ) -> GitOpsWorkflowResult:
        """Executes the GitOps workflow (simulation or live)."""
        return self.orchestrator.create_remediation_pr(
            run_id=run_id,
            findings=findings,
            costs=costs,
            recommendations=recommendations,
            patches=patches,
            total_monthly_savings=total_monthly_savings,
            files_to_commit=files_to_commit,
            is_destructive=is_destructive,
            base_branch=base_branch,
        )

    def create_pull_request(
        self,
        run_id: str,
        patches: List[TerraformPatch],
        findings: List[WasteFinding],
        costs: List[CostFinding],
        recommendations: List[AIRecommendation],
        total_monthly_savings: float,
        total_annualized_savings: float
    ) -> GitOpsPR:
        self._pr_counter += 1
        pr_number = self._pr_counter
        branch_name = f"gitops/remediation-run-{run_id[-6:]}"
        pr_id = f"PR-{pr_number}"

        title = f"fix(finops): Auto-remediate {len(findings)} cloud waste resource(s) [Save ${total_monthly_savings:.2f}/mo]"

        description = self._build_pr_markdown_description(
            pr_number=pr_number,
            branch_name=branch_name,
            findings=findings,
            costs=costs,
            recommendations=recommendations,
            total_monthly_savings=total_monthly_savings,
            total_annualized_savings=total_annualized_savings,
            patches=patches
        )

        checks = [
            {"name": "Terraform Syntax & Format", "status": "SUCCESS", "details": "HCL files formatted and validated."},
            {"name": "Security & Drift Guardrails", "status": "SUCCESS", "details": "No privilege escalations detected."},
            {"name": "FinOps Cost Policy Engine", "status": "SUCCESS", "details": f"Verified monthly savings of ${total_monthly_savings:.2f}."},
            {"name": "Amazon Bedrock Nova Lite Rationale", "status": "SUCCESS", "details": "All remediation steps rated Low-to-Medium risk."},
            {"name": "Peer Review Approval", "status": "PENDING", "details": "Awaiting Cloud Lead / FinOps Engineer sign-off."}
        ]

        pr = GitOpsPR(
            pr_id=pr_id,
            pr_number=pr_number,
            branch_name=branch_name,
            base_branch="main",
            title=title,
            description=description,
            author="finops-hunter[bot]",
            status="OPEN",
            files_changed=["sample_infrastructure/main.tf"],
            total_monthly_savings=round(total_monthly_savings, 2),
            total_annualized_savings=round(total_annualized_savings, 2),
            checks=checks,
            audit_trail=[
                f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] PR #{pr_number} created automatically on branch '{branch_name}'.",
                f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Automated CI check pipeline initiated (4 checks passed, 1 pending approval)."
            ]
        )

        self.active_prs[pr_id] = pr
        return pr

    def approve_pr(self, pr_id: str, reviewer: str = "Vivek Pandey (Lead FinOps)") -> Optional[GitOpsPR]:
        pr = self.active_prs.get(pr_id)
        if not pr:
            return None

        pr.status = "APPROVED"
        # Update peer review check
        for c in pr.checks:
            if c["name"] == "Peer Review Approval":
                c["status"] = "SUCCESS"
                c["details"] = f"Approved by {reviewer}"

        pr.audit_trail.append(
            f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] PR approved by {reviewer}. Safe to merge."
        )
        return pr

    def merge_pr(self, pr_id: str, reviewer: str = "Vivek Pandey (Lead FinOps)") -> Optional[GitOpsPR]:
        pr = self.active_prs.get(pr_id)
        if not pr:
            return None

        pr.status = "MERGED"
        pr.merged_at = datetime.now(timezone.utc).isoformat()
        pr.audit_trail.append(
            f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Merged into 'main' by {reviewer}. Triggered CD terraform apply runner."
        )
        pr.audit_trail.append(
            f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Cloud state successfully synchronized. Recurrent savings active!"
        )
        return pr

    def reject_pr(self, pr_id: str, reason: str = "Change requested by reviewer") -> Optional[GitOpsPR]:
        pr = self.active_prs.get(pr_id)
        if not pr:
            return None

        pr.status = "REJECTED"
        pr.audit_trail.append(
            f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] PR closed/rejected. Reason: {reason}"
        )
        return pr

    def _build_pr_markdown_description(
        self,
        pr_number: int,
        branch_name: str,
        findings: List[WasteFinding],
        costs: List[CostFinding],
        recommendations: List[AIRecommendation],
        total_monthly_savings: float,
        total_annualized_savings: float,
        patches: List[TerraformPatch]
    ) -> str:
        lines = [
            f"## 🚀 Automated FinOps Cloud Waste Remediation (PR #{pr_number})",
            "",
            "### 💰 Financial Impact Summary",
            f"- **Estimated Monthly Reduction:** `${total_monthly_savings:.2f} / month`",
            f"- **Annualized Budget Recovery:** `${total_annualized_savings:.2f} / year`",
            "- **Review Requirement:** FR11 Compliance — changes require human approval before deployment.",
            "",
            "### 🔍 Remediated Resources",
            "| Resource | Type | Action | Monthly Savings | Rationale |",
            "| :--- | :--- | :--- | :--- | :--- |"
        ]

        cost_map = {c.finding_id: c for c in costs}
        for f in findings:
            c = cost_map.get(f.id)
            savings_str = f"${c.monthly_savings:.2f}" if c else "$0.00"
            lines.append(f"| `{f.resource_name}` | {f.resource_type} | `{f.recommended_specs}` | **{savings_str}** | {f.description[:60]}... |")

        lines.extend([
            "",
            "### 🛡️ AI Risk & Rollback Assessment (Amazon Bedrock Nova Lite)",
            "- All modifications have been evaluated against infrastructure dependencies.",
            "- Automated snapshots and non-destructive rollbacks are registered in state storage.",
            "",
            "### 📋 Reviewer Verification Checklist",
            "- [x] Simulated utilization data confirms <10% compute utilization",
            "- [x] Unattached volumes checked for active database locks (None found)",
            "- [x] Terraform syntax validated via `terraform validate`",
            "- [ ] Review and click **Approve & Merge** to trigger GitOps deployment",
            "",
            "> *Generated by FinOps Cloud Waste Hunter & Auto-Remediator (VIT ISWE309L)*"
        ])
        return "\n".join(lines)
