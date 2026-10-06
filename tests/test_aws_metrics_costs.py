"""
Unit Tests for Real CloudWatch Metrics, Cost Explorer & Waste Analysis (Mocked)
Tests metric collection, Cost Explorer spend retrieval, transparent estimation labeling,
and waste detection accuracy without synthetic fallbacks or live mutations.

ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from datetime import datetime, timezone
from botocore.exceptions import ClientError, NoCredentialsError

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.models import CloudResource, ResourceType, WasteCategory
from core.aws.metrics import AWSMetricsService
from core.aws.costs import AWSCostService
from core.module2_waste_detection import WasteDetectionModule
from core.module3_cost_estimation import CostEstimationModule
from core.aws.connection import (
    STATUS_CONNECTED,
    STATUS_NO_PERMISSION,
    STATUS_NOT_AVAILABLE,
    STATUS_CREDENTIALS_MISSING
)


class TestAWSMetricsAndCosts(unittest.TestCase):

    def test_cloudwatch_ec2_metric_retrieval(self):
        """CloudWatch service correctly calculates averages, maxima, and sums from datapoints."""
        mock_cw = MagicMock()
        mock_cw.get_metric_statistics.return_value = {
            "Datapoints": [
                {"Timestamp": datetime(2026, 9, 20, 1, 0, tzinfo=timezone.utc), "Average": 4.2, "Maximum": 8.1, "Minimum": 2.0},
                {"Timestamp": datetime(2026, 9, 20, 2, 0, tzinfo=timezone.utc), "Average": 3.8, "Maximum": 6.5, "Minimum": 1.5}
            ]
        }

        service = AWSMetricsService(region_name="ap-southeast-2")
        result = service.fetch_metric_statistics(
            cw_client=mock_cw,
            namespace="AWS/EC2",
            metric_name="CPUUtilization",
            dimension_name="InstanceId",
            dimension_value="i-0123456789abcdef0",
            start_time=datetime(2026, 9, 15, tzinfo=timezone.utc),
            end_time=datetime(2026, 9, 20, tzinfo=timezone.utc)
        )

        self.assertTrue(result["has_data"])
        self.assertEqual(result["datapoints_count"], 2)
        self.assertEqual(result["summary"]["average"], 4.0)
        self.assertEqual(result["summary"]["maximum"], 8.1)
        self.assertEqual(result["summary"]["minimum"], 1.5)

    def test_cloudwatch_missing_metric_data_does_not_invent_values(self):
        """When CloudWatch has no datapoints, summary values remain None without invented metrics."""
        mock_cw = MagicMock()
        mock_cw.get_metric_statistics.return_value = {"Datapoints": []}

        service = AWSMetricsService(region_name="ap-southeast-2")
        result = service.fetch_metric_statistics(
            cw_client=mock_cw,
            namespace="AWS/EC2",
            metric_name="CPUUtilization",
            dimension_name="InstanceId",
            dimension_value="i-nodata",
            start_time=datetime(2026, 9, 15, tzinfo=timezone.utc),
            end_time=datetime(2026, 9, 20, tzinfo=timezone.utc)
        )

        self.assertFalse(result["has_data"])
        self.assertEqual(result["datapoints_count"], 0)
        self.assertIsNone(result["summary"]["average"])
        self.assertIsNone(result["summary"]["maximum"])

    def test_cloudwatch_permission_error_handling(self):
        """AccessDenied from CloudWatch is mapped cleanly without crashing."""
        mock_cw = MagicMock()
        mock_cw.get_metric_statistics.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "User lacks cloudwatch:GetMetricStatistics"}},
            "GetMetricStatistics"
        )

        service = AWSMetricsService(region_name="ap-southeast-2")
        result = service.fetch_metric_statistics(
            cw_client=mock_cw,
            namespace="AWS/Lambda",
            metric_name="Invocations",
            dimension_name="FunctionName",
            dimension_value="my-fn",
            start_time=datetime(2026, 9, 15, tzinfo=timezone.utc),
            end_time=datetime(2026, 9, 20, tzinfo=timezone.utc)
        )

        self.assertEqual(result["status"], STATUS_NO_PERMISSION)
        self.assertFalse(result["has_data"])
        self.assertIn("lacks cloudwatch", result["error"])

    @patch("core.aws.costs.get_aws_session")
    def test_cost_explorer_spend_retrieval(self, mock_get_session):
        """Cost Explorer successfully groups spending by service and sums total cost."""
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {"Keys": ["Amazon Elastic Compute Cloud - Compute"], "Metrics": {"UnblendedCost": {"Amount": "145.50", "Unit": "USD"}}},
                        {"Keys": ["Amazon Elastic Block Store"], "Metrics": {"UnblendedCost": {"Amount": "32.00", "Unit": "USD"}}},
                        {"Keys": ["AWS Lambda"], "Metrics": {"UnblendedCost": {"Amount": "4.50", "Unit": "USD"}}}
                    ]
                }
            ]
        }
        mock_session = MagicMock()
        mock_session.client.return_value = mock_ce
        mock_get_session.return_value = mock_session

        service = AWSCostService(region_name="ap-southeast-2")
        result = service.get_actual_costs(session=mock_session, days=30)

        self.assertEqual(result["status"], STATUS_CONNECTED)
        self.assertTrue(result["has_actual_costs"])
        self.assertEqual(result["total_cost"], 182.00)
        self.assertEqual(result["currency"], "USD")
        self.assertIn("Amazon Elastic Compute Cloud - Compute", result["service_costs"])
        self.assertEqual(result["service_costs"]["Amazon Elastic Compute Cloud - Compute"], 145.50)

    @patch("core.aws.costs.get_aws_session")
    def test_cost_explorer_disabled_or_unavailable(self, mock_get_session):
        """DataUnavailableException reports NOT_AVAILABLE cleanly with descriptive message."""
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.side_effect = ClientError(
            {"Error": {"Code": "DataUnavailableException", "Message": "Cost Explorer is not enabled for this account."}},
            "GetCostAndUsage"
        )
        mock_session = MagicMock()
        mock_session.client.return_value = mock_ce
        mock_get_session.return_value = mock_session

        service = AWSCostService(region_name="ap-southeast-2")
        result = service.get_actual_costs(session=mock_session)

        self.assertEqual(result["status"], STATUS_NOT_AVAILABLE)
        self.assertFalse(result["has_actual_costs"])
        self.assertIn("Cost Explorer is not enabled", result["message"])

    def test_waste_detection_with_real_metrics_and_no_false_positives(self):
        """Waste detection flags underutilized EC2 and idle Lambda, but does not flag missing metrics."""
        detector = WasteDetectionModule()

        # 1. Underutilized running EC2 with real CloudWatch metrics
        res_underutilized = CloudResource(
            id="i-underutilized",
            name="worker-idle",
            resource_type=ResourceType.EC2,
            region="ap-southeast-2",
            state="running",
            specs={"instance_type": "c5.2xlarge", "vcpus": 8, "ram_gb": 16},
            tags={"Name": "worker-idle"},
            metrics={"cpu_utilization_avg": 3.2, "cpu_utilization_max": 7.0, "has_real_metrics": True}
        )

        # 2. Running EC2 with NO metric data available (must NOT be labeled as waste)
        res_no_metrics = CloudResource(
            id="i-no-metrics",
            name="new-instance",
            resource_type=ResourceType.EC2,
            region="ap-southeast-2",
            state="running",
            specs={"instance_type": "c5.2xlarge"},
            tags={"Name": "new-instance"},
            metrics={"cpu_utilization_avg": None, "has_real_metrics": False}
        )

        # 3. Stopped EC2 instance
        res_stopped = CloudResource(
            id="i-stopped",
            name="old-staging",
            resource_type=ResourceType.EC2,
            region="ap-southeast-2",
            state="stopped",
            specs={"instance_type": "t3.large"},
            tags={"Name": "old-staging"},
            metrics={}
        )

        # 4. Unattached EBS volume
        res_unattached_ebs = CloudResource(
            id="vol-unattached",
            name="orphaned-ebs",
            resource_type=ResourceType.EBS,
            region="ap-southeast-2",
            state="available",
            specs={"size_gb": 100, "volume_type": "gp3", "is_unattached": True},
            tags={"Name": "orphaned-ebs"},
            metrics={"attachment_status": "unattached"}
        )

        # 5. Lambda with 0 invocations from CloudWatch
        res_idle_lambda = CloudResource(
            id="arn:aws:lambda:ap-southeast-2:123:function:dormant-hook",
            name="dormant-hook",
            resource_type=ResourceType.LAMBDA,
            region="ap-southeast-2",
            state="active",
            specs={"memory_mb": 256, "runtime": "python3.11"},
            tags={},
            metrics={"invocations_period_sum": 0, "has_real_metrics": True}
        )

        # 6. Lambda with None invocations (missing data - must NOT be labeled as waste)
        res_unmonitored_lambda = CloudResource(
            id="arn:aws:lambda:ap-southeast-2:123:function:unmonitored",
            name="unmonitored",
            resource_type=ResourceType.LAMBDA,
            region="ap-southeast-2",
            state="active",
            specs={"memory_mb": 256},
            tags={},
            metrics={"invocations_period_sum": None}
        )

        findings = detector.detect_waste([
            res_underutilized,
            res_no_metrics,
            res_stopped,
            res_unattached_ebs,
            res_idle_lambda,
            res_unmonitored_lambda
        ])

        found_ids = {f.resource_id for f in findings}

        # Assertions
        self.assertIn("i-underutilized", found_ids)
        self.assertIn("i-stopped", found_ids)
        self.assertIn("vol-unattached", found_ids)
        self.assertIn("arn:aws:lambda:ap-southeast-2:123:function:dormant-hook", found_ids)

        # Crucial check: resources without metrics must NOT be labeled as waste
        self.assertNotIn("i-no-metrics", found_ids)
        self.assertNotIn("arn:aws:lambda:ap-southeast-2:123:function:unmonitored", found_ids)

    def test_savings_estimation_transparent_labeling_in_real_mode(self):
        """In real AWS mode, pricing breakdowns clearly disclose model estimation and Cost Explorer context."""
        estimator = CostEstimationModule()
        res = CloudResource(
            id="i-test-downsize",
            name="analytics-node",
            resource_type=ResourceType.EC2,
            region="ap-southeast-2",
            state="running",
            specs={"instance_type": "c5.2xlarge", "vcpus": 8, "ram_gb": 16},
            metrics={"cpu_utilization_avg": 4.5, "cpu_utilization_max": 9.0}
        )

        detector = WasteDetectionModule()
        findings = detector.detect_waste([res])
        self.assertEqual(len(findings), 1)

        ce_data = {
            "has_actual_costs": True,
            "service_costs": {"Amazon Elastic Compute Cloud - Compute": 320.00}
        }

        # Real AWS mode estimation
        cost_findings = estimator.estimate_savings(
            findings=findings,
            resources=[res],
            cost_explorer_data=ce_data,
            is_real_aws=True
        )

        self.assertEqual(len(cost_findings), 1)
        cf = cost_findings[0]
        self.assertIn("[ESTIMATED SAVINGS MODEL]", cf.pricing_breakdown)
        self.assertIn("Actual AWS EC2 Service Spend: $320.00/mo", cf.pricing_breakdown)
        self.assertIn("Assumption: regional AWS on-demand rates", cf.pricing_breakdown)
        self.assertGreater(cf.monthly_savings, 0.0)

    def test_api_metrics_endpoint(self):
        """FastAPI GET /api/aws/metrics returns valid metrics structure."""
        from fastapi.testclient import TestClient
        from app.server import app

        client = TestClient(app)
        res = client.get("/api/aws/metrics?region=ap-southeast-2&window_days=7")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("status", data)
        self.assertIn("window_days", data)
        self.assertEqual(data["window_days"], 7)
        self.assertIn("resource_metrics", data)

    def test_api_costs_endpoint(self):
        """FastAPI GET /api/aws/costs returns valid cost structure with limitations."""
        from fastapi.testclient import TestClient
        from app.server import app

        client = TestClient(app)
        res = client.get("/api/aws/costs?region=ap-southeast-2&days=14")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("status", data)
        self.assertIn("total_cost", data)
        self.assertIn("service_costs", data)
        self.assertIn("limitations_and_assumptions", data)


if __name__ == "__main__":
    unittest.main()
