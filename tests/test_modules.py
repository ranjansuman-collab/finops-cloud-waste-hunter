"""
Comprehensive Test Suite for FinOps Cloud Waste Hunter & Auto-Remediator
Tests Modules 1 through 7 and End-to-End Orchestration Engine.
ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import sys
import unittest
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.engine import FinOpsEngine
from core.models import ResourceType, WasteCategory, Severity
from core.module1_monitoring import ResourceMonitoringModule
from core.module2_waste_detection import WasteDetectionModule
from core.module3_cost_estimation import CostEstimationModule
from core.module4_ai_advisor import AIAdvisorModule
from core.module5_storage import ReportStorageModule
from core.module6_terraform import TerraformRemediationModule
from core.module7_gitops import GitOpsReviewModule


class TestFinOpsModules(unittest.TestCase):

    def setUp(self):
        self.engine = FinOpsEngine(use_live_aws=False)

    def test_module1_resource_monitoring(self):
        """FR1: Collect and monitor resource-usage metrics."""
        mod1 = ResourceMonitoringModule(use_live_aws=False)
        resources = mod1.fetch_resources("enterprise")
        self.assertGreater(len(resources), 0)
        
        # Verify EC2 instance
        ec2_res = [r for r in resources if r.resource_type == ResourceType.EC2]
        self.assertTrue(len(ec2_res) > 0)
        self.assertIn("cpu_utilization_avg", ec2_res[0].metrics)
        self.assertIn("timeseries_cpu", ec2_res[0].metrics)

    def test_module2_waste_detection(self):
        """FR2 & FR3: Identify and classify waste conditions."""
        mod1 = ResourceMonitoringModule(use_live_aws=False)
        mod2 = WasteDetectionModule()
        resources = mod1.fetch_resources("enterprise")
        findings = mod2.detect_waste(resources)

        categories = {f.waste_category for f in findings}
        self.assertIn(WasteCategory.OVERSIZED_COMPUTE, categories)
        self.assertIn(WasteCategory.UNATTACHED_STORAGE, categories)
        self.assertIn(WasteCategory.IDLE_SERVERLESS, categories)
        self.assertIn(WasteCategory.IDLE_NETWORKING, categories)

    def test_module3_cost_estimation(self):
        """FR4: Estimate potential monthly and annual savings."""
        mod1 = ResourceMonitoringModule(use_live_aws=False)
        mod2 = WasteDetectionModule()
        mod3 = CostEstimationModule()

        resources = mod1.fetch_resources("enterprise")
        findings = mod2.detect_waste(resources)
        costs = mod3.estimate_savings(findings, resources)

        self.assertEqual(len(costs), len(findings))
        total_savings = sum(c.monthly_savings for c in costs)
        self.assertGreater(total_savings, 500.0, "Enterprise scenario should recover over $500/mo")
        for c in costs:
            self.assertGreaterEqual(c.current_monthly_cost, c.optimized_monthly_cost)
            self.assertGreaterEqual(c.monthly_savings, 0.0)

    def test_module4_ai_advisor(self):
        """FR5 & FR6: Generate Amazon Bedrock Nova Lite recommendations."""
        mod1 = ResourceMonitoringModule(use_live_aws=False)
        mod2 = WasteDetectionModule()
        mod3 = CostEstimationModule()
        mod4 = AIAdvisorModule()

        resources = mod1.fetch_resources("enterprise")
        findings = mod2.detect_waste(resources)
        costs = mod3.estimate_savings(findings, resources)
        recs = mod4.generate_recommendations(findings, costs)

        self.assertEqual(len(recs), len(findings))
        for r in recs:
            self.assertTrue(r.title)
            self.assertTrue(r.executive_summary)
            self.assertTrue("gemini" in r.model_used.lower() or "nova" in r.model_used.lower())
            self.assertTrue(len(r.steps_to_remediate) > 0)
            self.assertTrue(r.rollback_plan)

    def test_module5_report_storage(self):
        """FR7 & FR8: Store reports and structured data in S3 and DynamoDB."""
        report = self.engine.execute_full_pipeline("startup")
        self.assertTrue(report.s3_uri.startswith("s3://"))
        self.assertTrue(report.dynamodb_id)

        # Check retrieval from local DynamoDB audit store
        records = self.engine.module5.get_audit_records()
        self.assertGreater(len(records), 0)
        self.assertEqual(records[0]["run_id"], report.run_id)

    def test_module6_terraform_remediation(self):
        """FR9: Generate Terraform configuration patches and diffs."""
        mod1 = ResourceMonitoringModule(use_live_aws=False)
        mod2 = WasteDetectionModule()
        mod4 = AIAdvisorModule()
        mod6 = TerraformRemediationModule()

        resources = mod1.fetch_resources("enterprise")
        findings = mod2.detect_waste(resources)
        recs = mod4.generate_recommendations(findings, None)
        patches = mod6.generate_patches(findings, recs)

        self.assertGreater(len(patches), 0)
        diff = patches[0].unified_diff
        self.assertIn("--- a/main.tf", diff)
        self.assertIn("+++ b/main.tf", diff)

    def test_module7_gitops_review(self):
        """FR10 & FR11: GitOps review, approval, and pull request workflow."""
        report = self.engine.execute_full_pipeline("enterprise")
        pr = report.gitops_pr
        self.assertIsNotNone(pr)
        self.assertEqual(pr.status, "OPEN")
        self.assertEqual(pr.base_branch, "main")

        # Test Approve
        approved_pr = self.engine.module7.approve_pr(pr.pr_id, "Vivek Pandey")
        self.assertEqual(approved_pr.status, "APPROVED")

        # Test Merge
        merged_pr = self.engine.module7.merge_pr(pr.pr_id, "Vivek Pandey")
        self.assertEqual(merged_pr.status, "MERGED")
        self.assertIsNotNone(merged_pr.merged_at)

    def test_end_to_end_scenarios(self):
        """Tests complete pipeline across multiple cloud scenarios."""
        for sc in ["enterprise", "startup", "clean"]:
            report = self.engine.execute_full_pipeline(sc)
            self.assertEqual(report.scenario, sc)
            self.assertIsNotNone(report.run_id)
            if sc == "clean":
                self.assertEqual(len(report.waste_findings), 0)
                self.assertEqual(report.total_monthly_savings, 0.0)
            else:
                self.assertGreater(report.total_monthly_savings, 0.0)


if __name__ == "__main__":
    unittest.main()

