"""
FinOps Cloud Waste Hunter & Auto-Remediator
Real AWS Resource Discovery Service
Performs read-only discovery of EC2, EBS, Elastic IP, Lambda, and S3 resources
using Boto3 paginators, handling per-service permissions without synthetic fallbacks.

ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError

from core.models import CloudResource, ResourceType
from core.aws.connection import (
    AWSConnectionService,
    get_aws_session,
    get_configured_region,
    classify_aws_error,
    STATUS_CONNECTED,
    STATUS_CREDENTIALS_MISSING,
    STATUS_NO_PERMISSION,
    STATUS_ERROR
)

logger = logging.getLogger("finops.aws.discovery")


class AWSDiscoveryError(Exception):
    """Raised when real AWS discovery fails fundamentally (e.g. missing credentials)."""
    pass


class AWSDiscoveryService:
    """
    Executes read-only discovery across AWS services using the standard Boto3 credential chain.
    Transforms raw AWS API payloads into standardized CloudResource models.
    """

    def __init__(self, region_name: Optional[str] = None):
        self.region = get_configured_region(region_name)
        self.conn_service = AWSConnectionService(self.region)

    def discover_ec2_instances(self, session: boto3.Session) -> Tuple[List[CloudResource], Dict[str, Any]]:
        """Discovers EC2 instances with pagination, state, AZ, and attached block devices."""
        resources: List[CloudResource] = []
        status: Dict[str, Any] = {"status": STATUS_CONNECTED, "count": 0, "message": "OK"}

        try:
            ec2 = session.client("ec2", region_name=self.region)
            paginator = ec2.get_paginator("describe_instances")

            for page in paginator.paginate():
                for reservation in page.get("Reservations", []):
                    for inst in reservation.get("Instances", []):
                        inst_id = inst.get("InstanceId", "unknown")
                        state = inst.get("State", {}).get("Name", "unknown")
                        inst_type = inst.get("InstanceType", "unknown")
                        az = inst.get("Placement", {}).get("AvailabilityZone", self.region)
                        tags = {t["Key"]: t["Value"] for t in inst.get("Tags", []) if "Key" in t and "Value" in t}
                        name = tags.get("Name", inst_id)

                        launch_time = inst.get("LaunchTime")
                        launch_str = launch_time.isoformat() if hasattr(launch_time, "isoformat") else str(launch_time or "")

                        # Extract attached EBS volume mappings
                        attached_ebs = []
                        for bdm in inst.get("BlockDeviceMappings", []):
                            ebs_info = bdm.get("Ebs", {})
                            vol_id = ebs_info.get("VolumeId")
                            if vol_id:
                                attach_time = ebs_info.get("AttachTime")
                                attached_ebs.append({
                                    "volume_id": vol_id,
                                    "device_name": bdm.get("DeviceName", ""),
                                    "status": ebs_info.get("Status", "attached"),
                                    "delete_on_termination": ebs_info.get("DeleteOnTermination", False),
                                    "attach_time": attach_time.isoformat() if hasattr(attach_time, "isoformat") else str(attach_time or "")
                                })

                        specs = {
                            "instance_type": inst_type,
                            "platform": inst.get("PlatformDetails", inst.get("Platform", "Linux/UNIX")),
                            "availability_zone": az,
                            "launch_time": launch_str,
                            "attached_ebs_volumes": attached_ebs,
                            "vpc_id": inst.get("VpcId"),
                            "subnet_id": inst.get("SubnetId"),
                            "private_ip": inst.get("PrivateIpAddress"),
                            "public_ip": inst.get("PublicIpAddress"),
                            "architecture": inst.get("Architecture", "x86_64"),
                            "hypervisor": inst.get("Hypervisor", "xen")
                        }

                        # Metrics mapping established for Checkpoint 4 CloudWatch retrieval
                        metrics = {
                            "metrics_mapping": {
                                "namespace": "AWS/EC2",
                                "metric_name": "CPUUtilization",
                                "dimension_name": "InstanceId",
                                "dimension_value": inst_id
                            }
                        }

                        resources.append(
                            CloudResource(
                                id=inst_id,
                                name=name,
                                resource_type=ResourceType.EC2,
                                region=self.region,
                                state=state,
                                specs=specs,
                                tags=tags,
                                metrics=metrics,
                                created_at=launch_str
                            )
                        )

            status["count"] = len(resources)
            status["message"] = f"Discovered {len(resources)} EC2 instance(s)."
        except Exception as exc:
            st, msg = classify_aws_error(exc)
            status = {"status": st, "count": 0, "message": msg}
            logger.warning(f"EC2 discovery error: {msg}")

        return resources, status

    def discover_ebs_volumes(self, session: boto3.Session) -> Tuple[List[CloudResource], Dict[str, Any]]:
        """Discovers EBS volumes with pagination, size, type, attachment, and encryption details."""
        resources: List[CloudResource] = []
        status: Dict[str, Any] = {"status": STATUS_CONNECTED, "count": 0, "message": "OK"}

        try:
            ec2 = session.client("ec2", region_name=self.region)
            paginator = ec2.get_paginator("describe_volumes")

            for page in paginator.paginate():
                for vol in page.get("Volumes", []):
                    vol_id = vol.get("VolumeId", "unknown")
                    state = vol.get("State", "unknown")
                    vol_type = vol.get("VolumeType", "gp3")
                    size_gb = vol.get("Size", 0)
                    az = vol.get("AvailabilityZone", self.region)
                    encrypted = vol.get("Encrypted", False)
                    tags = {t["Key"]: t["Value"] for t in vol.get("Tags", []) if "Key" in t and "Value" in t}
                    name = tags.get("Name", vol_id)

                    create_time = vol.get("CreateTime")
                    create_str = create_time.isoformat() if hasattr(create_time, "isoformat") else str(create_time or "")

                    attachments = vol.get("Attachments", [])
                    is_unattached = len(attachments) == 0

                    attachment_details = []
                    for att in attachments:
                        att_time = att.get("AttachTime")
                        attachment_details.append({
                            "instance_id": att.get("InstanceId"),
                            "device": att.get("Device"),
                            "state": att.get("State"),
                            "delete_on_termination": att.get("DeleteOnTermination", False),
                            "attach_time": att_time.isoformat() if hasattr(att_time, "isoformat") else str(att_time or "")
                        })

                    specs = {
                        "volume_type": vol_type,
                        "size_gb": size_gb,
                        "availability_zone": az,
                        "encrypted": encrypted,
                        "kms_key_id": vol.get("KmsKeyId"),
                        "iops": vol.get("Iops"),
                        "throughput_mbps": vol.get("Throughput"),
                        "is_unattached": is_unattached,
                        "attachments": attachment_details
                    }

                    # Metrics mapping established for Checkpoint 4 CloudWatch retrieval
                    metrics = {
                        "attachment_status": "unattached" if is_unattached else "attached",
                        "metrics_mapping": {
                            "namespace": "AWS/EBS",
                            "metric_name": "VolumeReadOps",
                            "dimension_name": "VolumeId",
                            "dimension_value": vol_id
                        }
                    }

                    resources.append(
                        CloudResource(
                            id=vol_id,
                            name=name,
                            resource_type=ResourceType.EBS,
                            region=self.region,
                            state=state,
                            specs=specs,
                            tags=tags,
                            metrics=metrics,
                            created_at=create_str
                        )
                    )

            status["count"] = len(resources)
            status["message"] = f"Discovered {len(resources)} EBS volume(s)."
        except Exception as exc:
            st, msg = classify_aws_error(exc)
            status = {"status": st, "count": 0, "message": msg}
            logger.warning(f"EBS discovery error: {msg}")

        return resources, status

    def discover_elastic_ips(self, session: boto3.Session) -> Tuple[List[CloudResource], Dict[str, Any]]:
        """Discovers Elastic IP addresses and association states."""
        resources: List[CloudResource] = []
        status: Dict[str, Any] = {"status": STATUS_CONNECTED, "count": 0, "message": "OK"}

        try:
            ec2 = session.client("ec2", region_name=self.region)
            resp = ec2.describe_addresses()

            for addr in resp.get("Addresses", []):
                alloc_id = addr.get("AllocationId", addr.get("PublicIp", "unknown"))
                public_ip = addr.get("PublicIp", "unknown")
                assoc_id = addr.get("AssociationId")
                inst_id = addr.get("InstanceId")
                eni_id = addr.get("NetworkInterfaceId")
                is_associated = bool(assoc_id or inst_id or eni_id)
                state = "associated" if is_associated else "unassociated"

                tags = {t["Key"]: t["Value"] for t in addr.get("Tags", []) if "Key" in t and "Value" in t}
                name = tags.get("Name", f"eip-{public_ip}")

                specs = {
                    "allocation_id": alloc_id,
                    "public_ip": public_ip,
                    "domain": addr.get("Domain", "vpc"),
                    "instance_id": inst_id,
                    "association_id": assoc_id,
                    "network_interface_id": eni_id,
                    "network_interface_owner_id": addr.get("NetworkInterfaceOwnerId"),
                    "is_associated": is_associated
                }

                metrics = {
                    "days_unassociated": 0 if is_associated else 1,
                    "is_associated": is_associated
                }

                resources.append(
                    CloudResource(
                        id=alloc_id,
                        name=name,
                        resource_type=ResourceType.EIP,
                        region=self.region,
                        state=state,
                        specs=specs,
                        tags=tags,
                        metrics=metrics
                    )
                )

            status["count"] = len(resources)
            status["message"] = f"Discovered {len(resources)} Elastic IP(s)."
        except Exception as exc:
            st, msg = classify_aws_error(exc)
            status = {"status": st, "count": 0, "message": msg}
            logger.warning(f"EIP discovery error: {msg}")

        return resources, status

    def discover_lambda_functions(self, session: boto3.Session) -> Tuple[List[CloudResource], Dict[str, Any]]:
        """Discovers Lambda functions with pagination, memory, runtime, timeout, and ARN."""
        resources: List[CloudResource] = []
        status: Dict[str, Any] = {"status": STATUS_CONNECTED, "count": 0, "message": "OK"}

        try:
            lam = session.client("lambda", region_name=self.region)
            paginator = lam.get_paginator("list_functions")

            for page in paginator.paginate():
                for fn in page.get("Functions", []):
                    fn_name = fn.get("FunctionName", "unknown")
                    arn = fn.get("FunctionArn", fn_name)
                    runtime = fn.get("Runtime", "unknown")
                    memory_mb = fn.get("MemorySize", 128)
                    timeout = fn.get("Timeout", 3)
                    last_mod = fn.get("LastModified", "")
                    code_size = fn.get("CodeSize", 0)

                    # Read tags if available
                    tags: Dict[str, str] = {}
                    try:
                        tag_resp = lam.list_tags(Resource=arn)
                        tags = tag_resp.get("Tags", {})
                    except Exception:
                        pass

                    specs = {
                        "runtime": runtime,
                        "memory_mb": memory_mb,
                        "timeout_seconds": timeout,
                        "last_modified": last_mod,
                        "code_size_bytes": code_size,
                        "handler": fn.get("Handler"),
                        "role": fn.get("Role"),
                        "package_type": fn.get("PackageType", "Zip"),
                        "architectures": fn.get("Architectures", ["x86_64"])
                    }

                    # Metrics mapping established for Checkpoint 4 CloudWatch retrieval
                    metrics = {
                        "metrics_mapping": {
                            "namespace": "AWS/Lambda",
                            "metric_name": "Invocations",
                            "dimension_name": "FunctionName",
                            "dimension_value": fn_name
                        }
                    }

                    resources.append(
                        CloudResource(
                            id=arn,
                            name=fn_name,
                            resource_type=ResourceType.LAMBDA,
                            region=self.region,
                            state="active",
                            specs=specs,
                            tags=tags,
                            metrics=metrics,
                            created_at=last_mod
                        )
                    )

            status["count"] = len(resources)
            status["message"] = f"Discovered {len(resources)} Lambda function(s)."
        except Exception as exc:
            st, msg = classify_aws_error(exc)
            status = {"status": st, "count": 0, "message": msg}
            logger.warning(f"Lambda discovery error: {msg}")

        return resources, status

    def discover_s3_buckets(self, session: boto3.Session) -> Tuple[List[CloudResource], Dict[str, Any]]:
        """
        Discovers S3 buckets metadata strictly without downloading or inspecting object contents.
        Queries bucket location where accessible.
        """
        resources: List[CloudResource] = []
        status: Dict[str, Any] = {"status": STATUS_CONNECTED, "count": 0, "message": "OK"}

        try:
            s3 = session.client("s3", region_name=self.region)
            resp = s3.list_buckets()

            for b in resp.get("Buckets", []):
                name = b.get("Name", "unknown")
                created = b.get("CreationDate")
                created_str = created.isoformat() if hasattr(created, "isoformat") else str(created or "")

                bucket_region = self.region
                try:
                    loc_resp = s3.get_bucket_location(Bucket=name)
                    loc = loc_resp.get("LocationConstraint")
                    if loc is None or loc == "":
                        bucket_region = "us-east-1"
                    else:
                        bucket_region = loc
                except Exception:
                    pass

                specs = {
                    "bucket_name": name,
                    "creation_date": created_str,
                    "bucket_region": bucket_region
                }

                # Metrics mapping established for Checkpoint 4 CloudWatch retrieval
                metrics = {
                    "metrics_mapping": {
                        "namespace": "AWS/S3",
                        "metric_name": "BucketSizeBytes",
                        "dimension_name": "BucketName",
                        "dimension_value": name
                    }
                }

                resources.append(
                    CloudResource(
                        id=f"arn:aws:s3:::{name}",
                        name=name,
                        resource_type=ResourceType.S3,
                        region=bucket_region,
                        state="available",
                        specs=specs,
                        tags={},
                        metrics=metrics,
                        created_at=created_str
                    )
                )

            status["count"] = len(resources)
            status["message"] = f"Discovered {len(resources)} S3 bucket(s)."
        except Exception as exc:
            st, msg = classify_aws_error(exc)
            status = {"status": st, "count": 0, "message": msg}
            logger.warning(f"S3 discovery error: {msg}")

        return resources, status

    def discover_all(self, region_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Coordinates full read-only AWS resource discovery across all target services.
        Guarantees:
        - If credentials are missing, returns an explicit error without falling back to fake resources.
        - If a service encounters AccessDenied, records the service error and continues others.
        - Discovered resources are returned with empty arrays if none exist.
        """
        if region_name:
            self.region = get_configured_region(region_name)
            self.conn_service = AWSConnectionService(self.region)

        now_iso = datetime.now(timezone.utc).isoformat()
        session = get_aws_session(self.region)

        # 1. Verify STS Identity
        caller_identity = self.conn_service.get_caller_identity(session)
        if not caller_identity["authenticated"]:
            err_status = caller_identity["status"]
            err_msg = caller_identity["message"]
            return {
                "account_id": None,
                "arn": None,
                "region": self.region,
                "discovery_timestamp": now_iso,
                "is_real_aws": True,
                "status": err_status,
                "resources": {},
                "all_resources": [],
                "resource_counts": {"ec2": 0, "ebs": 0, "eip": 0, "lambda": 0, "s3": 0, "total": 0},
                "service_statuses": {
                    "ec2": {"status": err_status, "count": 0, "message": err_msg},
                    "ebs": {"status": err_status, "count": 0, "message": err_msg},
                    "eip": {"status": err_status, "count": 0, "message": err_msg},
                    "lambda": {"status": err_status, "count": 0, "message": err_msg},
                    "s3": {"status": err_status, "count": 0, "message": err_msg}
                },
                "errors": [err_msg],
                "summary": f"Discovery aborted: {err_msg}"
            }

        # 2. Execute discovery per service
        ec2_resources, ec2_status = self.discover_ec2_instances(session)
        ebs_resources, ebs_status = self.discover_ebs_volumes(session)
        eip_resources, eip_status = self.discover_elastic_ips(session)
        lam_resources, lam_status = self.discover_lambda_functions(session)
        s3_resources, s3_status = self.discover_s3_buckets(session)

        grouped = {
            "ec2": [r.model_dump() for r in ec2_resources],
            "ebs": [r.model_dump() for r in ebs_resources],
            "eip": [r.model_dump() for r in eip_resources],
            "lambda": [r.model_dump() for r in lam_resources],
            "s3": [r.model_dump() for r in s3_resources]
        }

        all_models = ec2_resources + ebs_resources + eip_resources + lam_resources + s3_resources

        counts = {
            "ec2": len(ec2_resources),
            "ebs": len(ebs_resources),
            "eip": len(eip_resources),
            "lambda": len(lam_resources),
            "s3": len(s3_resources),
            "total": len(all_models)
        }

        service_statuses = {
            "ec2": ec2_status,
            "ebs": ebs_status,
            "eip": eip_status,
            "lambda": lam_status,
            "s3": s3_status
        }

        errors = [
            f"{s.upper()}: {info['message']}"
            for s, info in service_statuses.items()
            if info["status"] != STATUS_CONNECTED
        ]

        return {
            "account_id": caller_identity["account_id"],
            "arn": caller_identity["arn"],
            "region": self.region,
            "discovery_timestamp": now_iso,
            "is_real_aws": True,
            "status": STATUS_CONNECTED,
            "resources": grouped,
            "all_resources": [r.model_dump() for r in all_models],
            "resource_counts": counts,
            "service_statuses": service_statuses,
            "errors": errors,
            "summary": f"Discovered {counts['total']} real AWS resource(s) in {self.region} for account {caller_identity['account_id']}."
        }
