"""
Unit Tests for Real AWS Resource Discovery Service (Mocked)
Tests read-only discovery of EC2, EBS, EIP, Lambda, and S3 resources,
pagination handling, permission isolation, and strict no-fallback behavior in live AWS mode.

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

from core.models import ResourceType
from core.aws.discovery import AWSDiscoveryService, AWSDiscoveryError
from core.module1_monitoring import ResourceMonitoringModule
from core.aws.connection import (
    STATUS_CONNECTED,
    STATUS_NO_PERMISSION,
    STATUS_CREDENTIALS_MISSING
)


class TestAWSDiscoveryService(unittest.TestCase):

    def test_discover_ec2_instances_with_pagination(self):
        """EC2 discovery correctly processes multiple pages and extracts attachments & tags."""
        mock_session = MagicMock()
        mock_ec2 = MagicMock()
        mock_paginator = MagicMock()

        page1 = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0aaa111bbb222ccc3",
                            "InstanceType": "t3.large",
                            "State": {"Name": "running"},
                            "Placement": {"AvailabilityZone": "ap-southeast-2a"},
                            "LaunchTime": datetime(2026, 9, 15, 10, 0, 0, tzinfo=timezone.utc),
                            "Tags": [{"Key": "Name", "Value": "api-gateway-prod"}, {"Key": "Env", "Value": "Prod"}],
                            "BlockDeviceMappings": [
                                {
                                    "DeviceName": "/dev/xvda",
                                    "Ebs": {"VolumeId": "vol-0123456789abcdef0", "Status": "attached"}
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        page2 = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0ddd444eee555fff6",
                            "InstanceType": "m5.xlarge",
                            "State": {"Name": "stopped"},
                            "Placement": {"AvailabilityZone": "ap-southeast-2b"},
                            "LaunchTime": datetime(2026, 9, 10, 8, 30, 0, tzinfo=timezone.utc),
                            "Tags": [{"Key": "Name", "Value": "worker-stopped"}],
                            "BlockDeviceMappings": []
                        }
                    ]
                }
            ]
        }

        mock_paginator.paginate.return_value = [page1, page2]
        mock_ec2.get_paginator.return_value = mock_paginator
        mock_session.client.return_value = mock_ec2

        discovery = AWSDiscoveryService(region_name="ap-southeast-2")
        resources, status = discovery.discover_ec2_instances(mock_session)

        self.assertEqual(status["status"], STATUS_CONNECTED)
        self.assertEqual(len(resources), 2)
        self.assertEqual(resources[0].id, "i-0aaa111bbb222ccc3")
        self.assertEqual(resources[0].name, "api-gateway-prod")
        self.assertEqual(resources[0].resource_type, ResourceType.EC2)
        self.assertEqual(resources[0].state, "running")
        self.assertEqual(resources[0].specs["availability_zone"], "ap-southeast-2a")
        self.assertEqual(len(resources[0].specs["attached_ebs_volumes"]), 1)
        self.assertEqual(resources[0].specs["attached_ebs_volumes"][0]["volume_id"], "vol-0123456789abcdef0")

        # Metric mapping established
        self.assertEqual(resources[0].metrics["metrics_mapping"]["metric_name"], "CPUUtilization")
        self.assertEqual(resources[1].id, "i-0ddd444eee555fff6")
        self.assertEqual(resources[1].state, "stopped")

    def test_discover_ebs_volumes_and_unattached_state(self):
        """EBS discovery identifies unattached vs attached volumes with size and encryption."""
        mock_session = MagicMock()
        mock_ec2 = MagicMock()
        mock_paginator = MagicMock()

        page = {
            "Volumes": [
                {
                    "VolumeId": "vol-attached01",
                    "VolumeType": "gp3",
                    "Size": 100,
                    "State": "in-use",
                    "AvailabilityZone": "ap-southeast-2a",
                    "Encrypted": True,
                    "Tags": [{"Key": "Name", "Value": "db-disk"}],
                    "Attachments": [{"InstanceId": "i-01234", "Device": "/dev/sda1", "State": "attached"}]
                },
                {
                    "VolumeId": "vol-orphan02",
                    "VolumeType": "gp2",
                    "Size": 500,
                    "State": "available",
                    "AvailabilityZone": "ap-southeast-2a",
                    "Encrypted": False,
                    "Tags": [{"Key": "Name", "Value": "abandoned-backup"}],
                    "Attachments": []
                }
            ]
        }

        mock_paginator.paginate.return_value = [page]
        mock_ec2.get_paginator.return_value = mock_paginator
        mock_session.client.return_value = mock_ec2

        discovery = AWSDiscoveryService(region_name="ap-southeast-2")
        resources, status = discovery.discover_ebs_volumes(mock_session)

        self.assertEqual(status["status"], STATUS_CONNECTED)
        self.assertEqual(len(resources), 2)

        attached = resources[0]
        self.assertFalse(attached.specs["is_unattached"])
        self.assertEqual(attached.metrics["attachment_status"], "attached")

        orphan = resources[1]
        self.assertTrue(orphan.specs["is_unattached"])
        self.assertEqual(orphan.metrics["attachment_status"], "unattached")
        self.assertEqual(orphan.specs["size_gb"], 500)

    def test_discover_elastic_ips(self):
        """Elastic IP discovery detects associated vs unassociated addresses."""
        mock_session = MagicMock()
        mock_ec2 = MagicMock()

        mock_ec2.describe_addresses.return_value = {
            "Addresses": [
                {
                    "AllocationId": "eipalloc-assoc01",
                    "PublicIp": "13.239.10.20",
                    "InstanceId": "i-0987654321",
                    "AssociationId": "eipassoc-011223344",
                    "Domain": "vpc",
                    "Tags": [{"Key": "Name", "Value": "nat-gateway-eip"}]
                },
                {
                    "AllocationId": "eipalloc-idle02",
                    "PublicIp": "52.64.88.99",
                    "Domain": "vpc",
                    "Tags": []
                }
            ]
        }
        mock_session.client.return_value = mock_ec2

        discovery = AWSDiscoveryService(region_name="ap-southeast-2")
        resources, status = discovery.discover_elastic_ips(mock_session)

        self.assertEqual(status["status"], STATUS_CONNECTED)
        self.assertEqual(len(resources), 2)
        self.assertEqual(resources[0].state, "associated")
        self.assertEqual(resources[1].state, "unassociated")
        self.assertFalse(resources[1].specs["is_associated"])

    def test_discover_lambda_functions(self):
        """Lambda discovery extracts runtime, memory, code size, and tags."""
        mock_session = MagicMock()
        mock_lam = MagicMock()
        mock_paginator = MagicMock()

        page = {
            "Functions": [
                {
                    "FunctionName": "image-processor",
                    "FunctionArn": "arn:aws:lambda:ap-southeast-2:123456789012:function:image-processor",
                    "Runtime": "python3.11",
                    "MemorySize": 512,
                    "Timeout": 30,
                    "LastModified": "2026-09-01T12:00:00.000+0000",
                    "CodeSize": 1048576,
                    "Handler": "handler.lambda_handler",
                    "Role": "arn:aws:iam::123456789012:role/lambda-role"
                }
            ]
        }
        mock_paginator.paginate.return_value = [page]
        mock_lam.get_paginator.return_value = mock_paginator
        mock_lam.list_tags.return_value = {"Tags": {"Project": "Thumbnails"}}
        mock_session.client.return_value = mock_lam

        discovery = AWSDiscoveryService(region_name="ap-southeast-2")
        resources, status = discovery.discover_lambda_functions(mock_session)

        self.assertEqual(status["status"], STATUS_CONNECTED)
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].name, "image-processor")
        self.assertEqual(resources[0].specs["runtime"], "python3.11")
        self.assertEqual(resources[0].specs["memory_mb"], 512)
        self.assertEqual(resources[0].tags.get("Project"), "Thumbnails")

    def test_discover_s3_buckets_read_only_metadata(self):
        """S3 discovery retrieves bucket metadata without downloading objects."""
        mock_session = MagicMock()
        mock_s3 = MagicMock()

        mock_s3.list_buckets.return_value = {
            "Buckets": [
                {"Name": "finops-data-bucket-ap2", "CreationDate": datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)},
                {"Name": "finops-us-east-archive", "CreationDate": datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)}
            ]
        }

        def get_loc_effect(Bucket):
            if Bucket == "finops-data-bucket-ap2":
                return {"LocationConstraint": "ap-southeast-2"}
            return {"LocationConstraint": None}

        mock_s3.get_bucket_location.side_effect = get_loc_effect
        mock_session.client.return_value = mock_s3

        discovery = AWSDiscoveryService(region_name="ap-southeast-2")
        resources, status = discovery.discover_s3_buckets(mock_session)

        self.assertEqual(status["status"], STATUS_CONNECTED)
        self.assertEqual(len(resources), 2)
        self.assertEqual(resources[0].name, "finops-data-bucket-ap2")
        self.assertEqual(resources[0].region, "ap-southeast-2")
        self.assertEqual(resources[1].name, "finops-us-east-archive")
        self.assertEqual(resources[1].region, "us-east-1")
        # Ensure no download or get_object was called
        self.assertFalse(hasattr(mock_s3, "get_object") and mock_s3.get_object.called)

    @patch("core.aws.discovery.get_aws_session")
    def test_permission_error_isolation(self, mock_get_session):
        """AccessDenied on Lambda does not crash EC2 or EBS discovery."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "555666777888",
            "Arn": "arn:aws:iam::555666777888:user/auditor",
            "UserId": "AIDAAUDITOR"
        }

        mock_ec2 = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"Reservations": []}]
        mock_ec2.get_paginator.return_value = mock_paginator
        mock_ec2.describe_addresses.return_value = {"Addresses": []}

        mock_lam = MagicMock()
        mock_lam.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "User is not authorized to perform lambda:ListFunctions"}},
            "ListFunctions"
        )

        mock_s3 = MagicMock()
        mock_s3.list_buckets.return_value = {"Buckets": []}

        def client_side_effect(service, region_name=None):
            if service == "sts":
                return mock_sts
            elif service == "ec2":
                return mock_ec2
            elif service == "lambda":
                return mock_lam
            elif service == "s3":
                return mock_s3
            return MagicMock()

        mock_session.client.side_effect = client_side_effect

        discovery = AWSDiscoveryService(region_name="ap-southeast-2")
        result = discovery.discover_all()

        self.assertEqual(result["status"], STATUS_CONNECTED)
        self.assertEqual(result["account_id"], "555666777888")
        self.assertEqual(result["service_statuses"]["ec2"]["status"], STATUS_CONNECTED)
        self.assertEqual(result["service_statuses"]["lambda"]["status"], STATUS_NO_PERMISSION)
        self.assertIn("User is not authorized", result["service_statuses"]["lambda"]["message"])
        self.assertTrue(len(result["errors"]) > 0)

    @patch("core.aws.discovery.get_aws_session")
    def test_missing_credentials_returns_clear_error_no_fake_fallback(self, mock_get_session):
        """When credentials are missing, discovery returns clear unauthenticated state and no fake resources."""
        mock_session = MagicMock()
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = NoCredentialsError()
        mock_session.client.return_value = mock_sts
        mock_get_session.return_value = mock_session

        discovery = AWSDiscoveryService(region_name="ap-southeast-2")
        result = discovery.discover_all()

        self.assertTrue(result["is_real_aws"])
        self.assertEqual(result["status"], STATUS_CREDENTIALS_MISSING)
        self.assertEqual(result["resource_counts"]["total"], 0)
        self.assertEqual(len(result["all_resources"]), 0)

    @patch("core.aws.connection.has_aws_credentials", return_value=False)
    def test_module1_real_mode_raises_error_when_credentials_missing(self, mock_has_creds):
        """ResourceMonitoringModule in live AWS mode raises AWSDiscoveryError instead of returning fake data."""
        mod1 = ResourceMonitoringModule(use_live_aws=True, region_name="ap-southeast-2")
        with self.assertRaises(AWSDiscoveryError) as ctx:
            mod1.fetch_resources()
        self.assertIn("AWS credentials missing", str(ctx.exception))

    def test_module1_simulation_mode_still_works(self):
        """ResourceMonitoringModule in simulation mode still returns scenario data correctly."""
        mod1 = ResourceMonitoringModule(use_live_aws=False)
        resources = mod1.fetch_resources("enterprise")
        self.assertGreater(len(resources), 0)
        self.assertEqual(resources[0].resource_type, ResourceType.EC2)

    def test_api_resources_endpoint(self):
        """FastAPI GET /api/aws/resources returns valid discovery response structure."""
        from fastapi.testclient import TestClient
        from app.server import app

        client = TestClient(app)
        response = client.get("/api/aws/resources?region=ap-southeast-2")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("status", data)
        self.assertIn("is_real_aws", data)
        self.assertTrue(data["is_real_aws"])
        self.assertIn("resources", data)
        self.assertIn("resource_counts", data)
        self.assertIn("service_statuses", data)


if __name__ == "__main__":
    unittest.main()
