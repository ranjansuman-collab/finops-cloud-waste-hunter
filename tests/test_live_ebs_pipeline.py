"""
Unit and regression tests for live AWS EBS discovery, monitoring, waste detection,
and Bedrock error handling.

Verifies:
1. Real unattached EBS volume is properly retained in inventory and detected as waste.
2. Missing metrics for unattached EBS are represented as None, not fabricated as zero.
3. When Bedrock encounters account verification errors (e.g. ValidationException: Operation not allowed),
   the pipeline preserves monitored resources, waste findings, cost findings, and surfaces the exact
   Bedrock error without crashing.
4. Demo/simulation mode remains isolated and functional.
"""

import unittest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError

from core.models import ResourceType, Severity, WasteCategory, CloudResource
from core.module1_monitoring import ResourceMonitoringModule
from core.module2_waste_detection import WasteDetectionModule
from core.module3_cost_estimation import CostEstimationModule
from core.engine import FinOpsEngine
from core.aws.connection import STATUS_ACCOUNT_VERIFICATION_REQUIRED


class TestLiveEBSPipeline(unittest.TestCase):

    def test_unattached_ebs_waste_detection_with_none_metrics(self):
        """Unattached EBS volume must be detected as waste even when CloudWatch metrics are unavailable/None."""
        resource = CloudResource(
            id="vol-095e4086520c65b70",
            name="vol-095e4086520c65b70",
            resource_type=ResourceType.EBS,
            region="ap-southeast-2",
            state="available",
            specs={
                "volume_type": "gp3",
                "size_gb": 1,
                "availability_zone": "ap-southeast-2a",
                "encrypted": False,
                "kms_key_id": None,
                "iops": 3000,
                "throughput_mbps": 125,
                "is_unattached": True,
                "attachments": []
            },
            tags={},
            metrics={
                "attachment_status": "unattached",
                "read_ops_sum": None,
                "has_real_metrics": False,
                "days_unattached": None
            }
        )

        detector = WasteDetectionModule()
        findings = detector.detect_waste([resource])

        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f.resource_id, "vol-095e4086520c65b70")
        self.assertEqual(f.waste_category, WasteCategory.UNATTACHED_STORAGE)
        self.assertEqual(f.severity, Severity.HIGH)
        self.assertIsNone(f.metrics_summary.get("days_unattached"))
        self.assertIsNone(f.metrics_summary.get("read_ops_sum"))

        # Cost estimation
        estimator = CostEstimationModule()
        costs = estimator.estimate_savings(findings, [resource], is_real_aws=True)
        self.assertEqual(len(costs), 1)
        self.assertGreater(costs[0].monthly_savings, 0.0)

    @patch("core.aws.metrics.AWSMetricsService.collect_metrics_for_resources")
    @patch("core.aws.costs.AWSCostService.get_actual_costs")
    @patch("core.aws.discovery.AWSDiscoveryService.discover_all")
    @patch("core.gemini_advisor.GeminiAdvisorService.get_client")
    def test_pipeline_preserves_monitored_resources_on_ai_advisor_error(
        self, mock_gemini_client, mock_discover_all, mock_get_costs, mock_collect_metrics
    ):
        """
        When Gemini fails (e.g. invalid API key / NO_PERMISSION),
        the pipeline must NOT crash with 500 error and discard monitored resources.
        It must retain monitored resources, waste findings, cost findings, and record the exact AI error.
        """
        # Mock discovery returning 1 real EBS volume
        mock_discover_all.return_value = {
            "status": "CONNECTED",
            "account_id": "105456916922",
            "arn": "arn:aws:iam::105456916922:root",
            "all_resources": [
                {
                    "id": "vol-095e4086520c65b70",
                    "name": "vol-095e4086520c65b70",
                    "resource_type": "EBS",
                    "region": "ap-southeast-2",
                    "state": "available",
                    "specs": {
                        "volume_type": "gp3",
                        "size_gb": 1,
                        "is_unattached": True,
                        "attachments": []
                    },
                    "tags": {},
                    "metrics": {
                        "attachment_status": "unattached",
                        "read_ops_sum": None,
                        "has_real_metrics": False
                    }
                }
            ]
        }

        mock_get_costs.return_value = None
        mock_collect_metrics.return_value = ({}, {"status": "CONNECTED", "collected_count": 1, "errors": []})

        mock_gemini_client.return_value = (None, {
            "status": "NO_PERMISSION",
            "message": "Gemini authentication failed: API key expired or unauthorized"
        })

        engine = FinOpsEngine(use_live_aws=True)
        with patch("core.aws.connection.has_aws_credentials", return_value=True):
            report = engine.execute_full_pipeline(use_live_aws=True, region_name="ap-southeast-2")

        # Monitored resources and waste findings must be intact
        self.assertEqual(len(report.monitored_resources), 1)
        self.assertEqual(report.monitored_resources[0].id, "vol-095e4086520c65b70")
        self.assertEqual(len(report.waste_findings), 1)
        self.assertEqual(report.waste_findings[0].resource_id, "vol-095e4086520c65b70")
        self.assertEqual(len(report.cost_findings), 1)

        # AI recommendations are empty because of the error, but the error is explicitly surfaced
        self.assertEqual(len(report.ai_recommendations), 0)
        self.assertEqual(report.ai_status, "NO_PERMISSION")
        self.assertIn("API key expired", report.ai_error)
        self.assertIn(report.ai_error, report.errors)

    def test_simulation_mode_still_works_unaffected(self):
        """Simulation mode with enterprise scenario must continue functioning with full recommendations."""
        engine = FinOpsEngine(use_live_aws=False)
        report = engine.execute_full_pipeline(scenario_id="enterprise", use_live_aws=False)

        self.assertGreater(len(report.monitored_resources), 0)
        self.assertGreater(len(report.waste_findings), 0)
        self.assertGreater(len(report.ai_recommendations), 0)
        self.assertIsNone(report.bedrock_error)

    @patch("core.aws.metrics.AWSMetricsService.collect_metrics_for_resources")
    @patch("core.aws.costs.AWSCostService.get_actual_costs")
    @patch("core.aws.discovery.AWSDiscoveryService.discover_all")
    @patch("core.gemini_advisor.GeminiAdvisorService.analyze_finding")
    def test_live_unmanaged_ebs_produces_remediation_patch_and_plan(
        self, mock_gemini_rec, mock_discover_all, mock_get_costs, mock_collect_metrics
    ):
        """
        A real discovered unattached EBS volume not present in sample_infrastructure/main.tf
        must produce a valid Terraform remediation patch with diff, and generate a valid plan artifact.
        """
        from core.models import AIRecommendation

        mock_discover_all.return_value = {
            "status": "CONNECTED",
            "account_id": "105456916922",
            "arn": "arn:aws:iam::105456916922:root",
            "all_resources": [
                {
                    "id": "vol-095e4086520c65b70",
                    "name": "vol-095e4086520c65b70",
                    "resource_type": "EBS",
                    "region": "ap-southeast-2",
                    "state": "available",
                    "specs": {
                        "volume_type": "gp3",
                        "size_gb": 1,
                        "is_unattached": True,
                        "attachments": []
                    },
                    "tags": {},
                    "metrics": {
                        "attachment_status": "unattached",
                        "read_ops_sum": None,
                        "has_real_metrics": False
                    }
                }
            ]
        }
        mock_get_costs.return_value = None
        mock_collect_metrics.return_value = ({}, {"status": "CONNECTED", "collected_count": 1, "errors": []})

        # Gemini returns structured recommendation with safe Terraform HCL
        gemini_rec = AIRecommendation(
            finding_id="waste-ebs-20c65b70",
            resource_id="vol-095e4086520c65b70",
            resource_name="vol-095e4086520c65b70",
            title="Delete Unattached EBS Volume vol-095e4086520c65b70",
            executive_summary="Remove unattached EBS volume to prevent idle storage waste.",
            risk_level="Low Risk",
            rationale="Volume is unattached with 0 I/O operations.",
            steps_to_remediate=["Create final snapshot if needed", "Delete the volume via Terraform/API"],
            rollback_plan="Restore from snapshot if required.",
            confidence_score=0.98,
            estimated_monthly_savings=0.08,
            action_type="DELETE",
            proposed_action="SNAPSHOT_AND_DELETE",
            terraform_hcl="# Safe deletion: ensure volume is destroyed\n# Resource unattached in ap-southeast-2\n",
            terraform_explanation="Remove volume block from Terraform configuration.",
            model_used="gemini-3.5-flash-lite"
        )
        mock_gemini_rec.return_value = (gemini_rec, {"status": "SUCCESS", "model_used": "gemini-3.5-flash-lite"})

        engine = FinOpsEngine(use_live_aws=True)
        with patch("core.aws.connection.has_aws_credentials", return_value=True):
            report = engine.execute_full_pipeline(use_live_aws=True, region_name="ap-southeast-2")

        # Must have 1 waste finding, 1 AI recommendation, and 1 Terraform patch
        self.assertEqual(len(report.waste_findings), 1)
        self.assertEqual(len(report.ai_recommendations), 1)
        self.assertEqual(len(report.terraform_patches), 1)

        patch_obj = report.terraform_patches[0]
        self.assertEqual(patch_obj.action_type, "DELETE")
        self.assertIn("vol_095e4086520c65b70", patch_obj.unified_diff)
        self.assertIn("-resource \"aws_ebs_volume\"", patch_obj.unified_diff)

        # Terraform plan artifact must be present with valid hash and status
        self.assertEqual(report.terraform_plan_status, "SUCCESS")
        self.assertTrue(report.terraform_plan_id.startswith("plan-"))
        self.assertEqual(len(report.terraform_plan_hash), 64)  # SHA-256
        self.assertIsNotNone(report.terraform_plan_file)

    def test_gemini_hcl_security_validation(self):
        """Test that validate_untrusted_input enforces strict HCL security rules."""
        from core.terraform.generator import validate_untrusted_input
        from core.models import WasteFinding, AIRecommendation

        finding = WasteFinding(
            id="waste-ebs-test",
            resource_id="vol-095e4086520c65b70",
            resource_name="vol-095e4086520c65b70",
            resource_type=ResourceType.EBS,
            waste_category=WasteCategory.UNATTACHED_STORAGE,
            severity=Severity.HIGH,
            description="Unattached EBS volume",
            recommended_specs="Delete unattached volume",
            current_specs="1 GiB gp3 unattached",
            metrics_summary={}
        )

        # Safe input
        safe_rec = AIRecommendation(
            finding_id="waste-ebs-test",
            resource_id="vol-095e4086520c65b70",
            resource_name="vol-095e4086520c65b70",
            title="Safe EBS Clean",
            executive_summary="Safe summary",
            risk_level="Low Risk",
            rationale="Safe rationale",
            steps_to_remediate=["Step 1"],
            rollback_plan="Rollback",
            confidence_score=0.9,
            action_type="DELETE",
            terraform_hcl="# Safe comment\n",
            model_used="gemini-3.5-flash-lite"
        )
        valid, err = validate_untrusted_input(finding, safe_rec)
        self.assertTrue(valid)
        self.assertEqual(err, "OK")

        # Unsafe provisioner injection
        unsafe_rec1 = AIRecommendation(
            finding_id="waste-ebs-test",
            resource_id="vol-095e4086520c65b70",
            resource_name="vol-095e4086520c65b70",
            title="Unsafe",
            executive_summary="Unsafe",
            risk_level="Low Risk",
            rationale="Unsafe",
            steps_to_remediate=["Step 1"],
            rollback_plan="Rollback",
            confidence_score=0.9,
            action_type="DELETE",
            terraform_hcl='resource "aws_ebs_volume" "test" {\n  provisioner "local-exec" {\n    command = "rm -rf /"\n  }\n}',
            model_used="gemini-3.5-flash-lite"
        )
        valid, err = validate_untrusted_input(finding, unsafe_rec1)
        self.assertFalse(valid)
        self.assertEqual(err, "SECURITY_POLICY_VIOLATION")

        # Unsafe token / credential leak pattern
        unsafe_rec2 = AIRecommendation(
            finding_id="waste-ebs-test",
            resource_id="vol-095e4086520c65b70",
            resource_name="vol-095e4086520c65b70",
            title="Unsafe",
            executive_summary="Unsafe",
            risk_level="Low Risk",
            rationale="Unsafe",
            steps_to_remediate=["Step 1"],
            rollback_plan="Rollback",
            confidence_score=0.9,
            action_type="DELETE",
            terraform_hcl='variable "secret" { default = "token = 123" }',
            model_used="gemini-3.5-flash-lite"
        )
        valid, err = validate_untrusted_input(finding, unsafe_rec2)
        self.assertFalse(valid)
        self.assertEqual(err, "SECURITY_POLICY_VIOLATION")

        # Unbalanced braces syntax rejection
        unsafe_rec3 = AIRecommendation(
            finding_id="waste-ebs-test",
            resource_id="vol-095e4086520c65b70",
            resource_name="vol-095e4086520c65b70",
            title="Unsafe",
            executive_summary="Unsafe",
            risk_level="Low Risk",
            rationale="Unsafe",
            steps_to_remediate=["Step 1"],
            rollback_plan="Rollback",
            confidence_score=0.9,
            action_type="DELETE",
            terraform_hcl='resource "aws_ebs_volume" "test" {\n  size = 10\n',
            model_used="gemini-3.5-flash-lite"
        )
        valid, err = validate_untrusted_input(finding, unsafe_rec3)
        self.assertFalse(valid)
        self.assertEqual(err, "SECURITY_POLICY_VIOLATION")

    @patch("core.aws.metrics.AWSMetricsService.collect_metrics_for_resources")
    @patch("core.aws.costs.AWSCostService.get_actual_costs")
    @patch("core.aws.discovery.AWSDiscoveryService.discover_all")
    @patch("core.gemini_advisor.GeminiAdvisorService.analyze_finding")
    def test_gemini_failure_never_produces_fake_patch(
        self, mock_gemini_rec, mock_discover_all, mock_get_costs, mock_collect_metrics
    ):
        """
        When Gemini fails on live resources, the pipeline must NOT produce a fake patch
        or report successful remediation.
        """
        mock_discover_all.return_value = {
            "status": "CONNECTED",
            "account_id": "105456916922",
            "arn": "arn:aws:iam::105456916922:root",
            "all_resources": [
                {
                    "id": "vol-095e4086520c65b70",
                    "name": "vol-095e4086520c65b70",
                    "resource_type": "EBS",
                    "region": "ap-southeast-2",
                    "state": "available",
                    "specs": {"volume_type": "gp3", "size_gb": 1, "is_unattached": True, "attachments": []},
                    "tags": {},
                    "metrics": {"attachment_status": "unattached", "read_ops_sum": None, "has_real_metrics": False}
                }
            ]
        }
        mock_get_costs.return_value = None
        mock_collect_metrics.return_value = ({}, {"status": "CONNECTED", "collected_count": 1, "errors": []})
        mock_gemini_rec.return_value = (None, {"status": "RATE_LIMITED", "message": "Resource exhausted (quota exceeded)"})

        engine = FinOpsEngine(use_live_aws=True)
        with patch("core.aws.connection.has_aws_credentials", return_value=True):
            report = engine.execute_full_pipeline(use_live_aws=True, region_name="ap-southeast-2")

        # Waste findings exist, but 0 fake recommendations and 0 fake patches
        self.assertEqual(len(report.waste_findings), 1)
        self.assertEqual(len(report.ai_recommendations), 0)
        self.assertEqual(len(report.terraform_patches), 0)
        self.assertIn("quota exceeded", report.ai_error)
