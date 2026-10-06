"""
Unit Tests for AWS Connection & Authentication Service (Mocked)
Tests standard credential resolution, STS verification, error classification,
and individual service health probes without calling real AWS APIs.

ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    PartialCredentialsError,
    EndpointConnectionError
)

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.aws.connection import (
    AWSConnectionService,
    get_configured_region,
    has_aws_credentials,
    classify_aws_error,
    DEFAULT_AWS_REGION,
    STATUS_CONNECTED,
    STATUS_NO_PERMISSION,
    STATUS_ACCOUNT_VERIFICATION_REQUIRED,
    STATUS_NOT_AVAILABLE,
    STATUS_CREDENTIALS_MISSING,
    STATUS_ERROR
)


class TestAWSConnectionService(unittest.TestCase):

    def test_default_region_resolution(self):
        """Region resolution defaults to ap-southeast-2 unless overridden."""
        with patch.dict("os.environ", {}, clear=True):
            region = get_configured_region()
            self.assertEqual(region, "ap-southeast-2")

    def test_configured_region_environment_precedence(self):
        """Environment variables override default region in priority order."""
        with patch.dict("os.environ", {"AWS_DEFAULT_REGION": "us-west-2"}):
            self.assertEqual(get_configured_region(), "us-west-2")

        with patch.dict("os.environ", {"AWS_REGION": "eu-central-1", "AWS_DEFAULT_REGION": "us-west-2"}):
            self.assertEqual(get_configured_region(), "eu-central-1")

        with patch.dict("os.environ", {"FINOPS_AWS_REGION": "ap-southeast-2", "AWS_REGION": "eu-central-1"}):
            self.assertEqual(get_configured_region(), "ap-southeast-2")

        # Explicit parameter takes highest precedence
        self.assertEqual(get_configured_region("us-east-1"), "us-east-1")

    def test_classify_aws_error_credentials_missing(self):
        """NoCredentialsError maps to CREDENTIALS_MISSING."""
        status, _ = classify_aws_error(NoCredentialsError())
        self.assertEqual(status, STATUS_CREDENTIALS_MISSING)

        status_part, _ = classify_aws_error(PartialCredentialsError(provider="env", cred_var="AWS_SECRET_ACCESS_KEY"))
        self.assertEqual(status_part, STATUS_CREDENTIALS_MISSING)

    def test_classify_aws_error_permissions(self):
        """AccessDenied and UnauthorizedOperation map to NO_PERMISSION."""
        err_response = {"Error": {"Code": "AccessDenied", "Message": "User is not authorized"}}
        status, _ = classify_aws_error(ClientError(err_response, "DescribeInstances"))
        self.assertEqual(status, STATUS_NO_PERMISSION)

        err_unauth = {"Error": {"Code": "UnauthorizedOperation", "Message": "You are not authorized"}}
        status_unauth, _ = classify_aws_error(ClientError(err_unauth, "DescribeRegions"))
        self.assertEqual(status_unauth, STATUS_NO_PERMISSION)

    def test_classify_aws_error_account_verification(self):
        """Account verification and subscription errors map to ACCOUNT_VERIFICATION_REQUIRED."""
        err_verif = {
            "Error": {
                "Code": "AccountVerificationRequiredException",
                "Message": "Your AWS account must be verified before accessing Amazon Bedrock foundation models."
            }
        }
        status, msg = classify_aws_error(ClientError(err_verif, "ListFoundationModels"))
        self.assertEqual(status, STATUS_ACCOUNT_VERIFICATION_REQUIRED)
        self.assertIn("verified", msg.lower())

        err_opt_in = {
            "Error": {
                "Code": "OptInRequired",
                "Message": "You are not subscribed to this service."
            }
        }
        status_opt, _ = classify_aws_error(ClientError(err_opt_in, "GetDimensionValues"))
        self.assertEqual(status_opt, STATUS_ACCOUNT_VERIFICATION_REQUIRED)

    def test_classify_aws_error_service_not_available(self):
        """Region unsupported or disabled service maps to NOT_AVAILABLE."""
        err_data = {
            "Error": {
                "Code": "DataUnavailableException",
                "Message": "Cost Explorer is not enabled for this account."
            }
        }
        status, _ = classify_aws_error(ClientError(err_data, "GetDimensionValues"))
        self.assertEqual(status, STATUS_NOT_AVAILABLE)

        status_conn, _ = classify_aws_error(EndpointConnectionError(endpoint_url="https://bedrock.ap-invalid.amazonaws.com"))
        self.assertEqual(status_conn, STATUS_NOT_AVAILABLE)

    @patch("core.aws.connection.get_aws_session")
    def test_sts_get_caller_identity_success(self, mock_get_session):
        """STS get_caller_identity returns authenticated details."""
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/finops-auditor",
            "UserId": "AIDA12345678EXAMPLE"
        }
        mock_session = MagicMock()
        mock_session.client.return_value = mock_sts
        mock_get_session.return_value = mock_session

        service = AWSConnectionService(region_name="ap-southeast-2")
        result = service.get_caller_identity(mock_session)

        self.assertTrue(result["authenticated"])
        self.assertEqual(result["status"], STATUS_CONNECTED)
        self.assertEqual(result["account_id"], "123456789012")
        self.assertEqual(result["arn"], "arn:aws:iam::123456789012:user/finops-auditor")
        self.assertEqual(result["region"], "ap-southeast-2")

    @patch("core.aws.connection.get_aws_session")
    def test_sts_get_caller_identity_missing_credentials(self, mock_get_session):
        """STS failure with NoCredentialsError returns CREDENTIALS_MISSING."""
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = NoCredentialsError()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_sts
        mock_get_session.return_value = mock_session

        service = AWSConnectionService(region_name="ap-southeast-2")
        result = service.get_caller_identity(mock_session)

        self.assertFalse(result["authenticated"])
        self.assertEqual(result["status"], STATUS_CREDENTIALS_MISSING)
        self.assertIsNone(result["account_id"])

    @patch("core.aws.connection.get_aws_session")
    def test_full_status_when_authenticated(self, mock_get_session):
        """Full status check probes all 5 services when STS succeeds."""
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "987654321098",
            "Arn": "arn:aws:iam::987654321098:role/FinOpsAdmin",
            "UserId": "AROA987654321EXAMPLE"
        }

        mock_ec2 = MagicMock()
        mock_ec2.describe_regions.return_value = {"Regions": [{"RegionName": "ap-southeast-2"}]}

        mock_cw = MagicMock()
        mock_cw.list_metrics.return_value = {"Metrics": []}

        mock_s3 = MagicMock()
        mock_s3.list_buckets.return_value = {"Buckets": []}

        mock_ce = MagicMock()
        mock_ce.get_dimension_values.return_value = {"DimensionValues": []}

        mock_bedrock = MagicMock()
        mock_bedrock.list_foundation_models.return_value = {"modelSummaries": []}

        def client_side_effect(service_name, region_name=None):
            if service_name == "sts":
                return mock_sts
            elif service_name == "ec2":
                return mock_ec2
            elif service_name == "cloudwatch":
                return mock_cw
            elif service_name == "s3":
                return mock_s3
            elif service_name == "ce":
                return mock_ce
            elif service_name == "bedrock":
                return mock_bedrock
            raise ValueError(f"Unknown service: {service_name}")

        mock_session = MagicMock()
        mock_session.client.side_effect = client_side_effect
        mock_get_session.return_value = mock_session

        service = AWSConnectionService(region_name="ap-southeast-2")
        status = service.get_full_status()

        self.assertEqual(status["status"], STATUS_CONNECTED)
        self.assertEqual(status["account_id"], "987654321098")
        self.assertEqual(status["region"], "ap-southeast-2")
        for s_name in ["ec2", "cloudwatch", "s3", "cost_explorer", "bedrock"]:
            self.assertEqual(status["services"][s_name]["status"], STATUS_CONNECTED)

    @patch("core.aws.connection.get_aws_session")
    def test_bedrock_account_verification_reported_accurately(self, mock_get_session):
        """Bedrock account verification error is preserved without fake fallback."""
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "111222333444",
            "Arn": "arn:aws:iam::111222333444:user/test",
            "UserId": "AIDATEST"
        }

        mock_bedrock = MagicMock()
        mock_bedrock.list_foundation_models.side_effect = ClientError(
            {"Error": {"Code": "AccountVerificationRequiredException", "Message": "Account verification required"}},
            "ListFoundationModels"
        )

        mock_session = MagicMock()
        mock_session.client.side_effect = lambda svc, region_name=None: mock_sts if svc == "sts" else (
            mock_bedrock if svc == "bedrock" else MagicMock()
        )
        mock_get_session.return_value = mock_session

        service = AWSConnectionService(region_name="ap-southeast-2")
        status = service.get_full_status()

        self.assertEqual(status["status"], STATUS_CONNECTED)
        self.assertEqual(status["services"]["bedrock"]["status"], STATUS_ACCOUNT_VERIFICATION_REQUIRED)
        self.assertIn("Account verification required", status["services"]["bedrock"]["message"])

    def test_api_status_endpoint(self):
        """FastAPI /api/aws/status endpoint returns valid status structure."""
        from fastapi.testclient import TestClient
        from app.server import app

        client = TestClient(app)
        response = client.get("/api/aws/status?region=ap-southeast-2")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("services", data)
        self.assertIn("region", data)
        self.assertEqual(data["region"], "ap-southeast-2")
        for svc in ["ec2", "cloudwatch", "s3", "cost_explorer", "bedrock"]:
            self.assertIn(svc, data["services"])


if __name__ == "__main__":
    unittest.main()
