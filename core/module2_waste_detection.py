"""
Module 2: Waste Detection
Detects unattached storage, idle serverless functions, oversized resources, and networking waste.
ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import uuid
from typing import List
from core.models import (
    CloudResource,
    ResourceType,
    WasteFinding,
    WasteCategory,
    Severity
)


class WasteDetectionModule:
    """
    Implements FR2 & FR3:
    Detects and classifies cloud waste across Compute, Storage, Serverless, and Networking.
    """

    # Recommendation mappings for rightsizing
    DOWNGRADE_MAP = {
        "c5.4xlarge": "c5.large",
        "c5.2xlarge": "c5.large",
        "c5.xlarge": "c5.large",
        "m5.2xlarge": "m5.large",
        "m5.xlarge": "t3.medium",
        "t3.2xlarge": "t3.medium",
        "t3.xlarge": "t3.medium",
        "t3.large": "t3.small",
    }

    def detect_waste(self, resources: List[CloudResource]) -> List[WasteFinding]:
        findings: List[WasteFinding] = []

        for res in resources:
            if res.resource_type == ResourceType.EBS:
                finding = self._check_ebs_waste(res)
                if finding:
                    findings.append(finding)

            elif res.resource_type == ResourceType.LAMBDA:
                finding = self._check_lambda_waste(res)
                if finding:
                    findings.append(finding)

            elif res.resource_type == ResourceType.EC2:
                finding = self._check_ec2_waste(res)
                if finding:
                    findings.append(finding)

            elif res.resource_type == ResourceType.EIP:
                finding = self._check_eip_waste(res)
                if finding:
                    findings.append(finding)

            elif res.resource_type == ResourceType.NAT_GATEWAY:
                finding = self._check_nat_waste(res)
                if finding:
                    findings.append(finding)

        return findings

    def _check_ebs_waste(self, res: CloudResource) -> WasteFinding | None:
        metrics = res.metrics
        specs = res.specs
        days_unattached = metrics.get("days_unattached", 0)
        is_unattached = (
            specs.get("is_unattached") is True or
            res.state == "available" or
            metrics.get("attachment_status") == "unattached" or
            days_unattached > 0
        )

        # Flag unattached volumes in either real AWS or simulation (where days >= 7)
        if is_unattached:
            size_gb = specs.get("size_gb", 0)
            vol_type = specs.get("volume_type", "gp3")
            days_label = f" for {days_unattached} days" if days_unattached > 0 else ""
            severity = Severity.CRITICAL if (size_gb >= 500 or days_unattached >= 30) else Severity.HIGH

            return WasteFinding(
                id=f"waste-ebs-{res.id[-8:]}",
                resource_id=res.id,
                resource_name=res.name,
                resource_type=ResourceType.EBS,
                waste_category=WasteCategory.UNATTACHED_STORAGE,
                severity=severity,
                description=(
                    f"EBS Volume '{res.name}' ({size_gb} GB {vol_type}) is currently unattached{days_label}, "
                    f"accruing dormant provisioned storage charges without compute attachment."
                ),
                current_specs=f"{size_gb} GB {vol_type} (Unattached)",
                recommended_specs="Snapshot & Terminate Volume (Reclaim 100% Cost)",
                confidence_score=0.99,
                metrics_summary={
                    "days_unattached": days_unattached,
                    "size_gb": size_gb,
                    "volume_type": vol_type,
                    "is_unattached": True
                }
            )
        return None

    def _check_lambda_waste(self, res: CloudResource) -> WasteFinding | None:
        metrics = res.metrics
        invocations = metrics.get("invocations_30d")
        if invocations is None:
            invocations = metrics.get("invocations_period_sum")

        # Do not label as waste if metrics were not available or never collected
        if invocations is None:
            return None

        last_invoked_days = metrics.get("last_invoked_days_ago", 0)
        prov_concurrency = res.specs.get("provisioned_concurrency", 0)

        if invocations == 0:
            severity = Severity.HIGH if prov_concurrency > 0 else Severity.MEDIUM
            desc = (
                f"Serverless Lambda '{res.name}' has 0 invocations over the evaluated period."
            )
            if prov_concurrency > 0:
                desc += f" It maintains {prov_concurrency} provisioned concurrency units incurring 24/7 idle fees."

            return WasteFinding(
                id=f"waste-lmb-{res.name[:8]}-{uuid.uuid4().hex[:4]}",
                resource_id=res.id,
                resource_name=res.name,
                resource_type=ResourceType.LAMBDA,
                waste_category=WasteCategory.IDLE_SERVERLESS,
                severity=severity,
                description=desc,
                current_specs=f"{res.specs.get('memory_mb', 128)}MB | {prov_concurrency} Prov. Concurrency",
                recommended_specs="Deprecate & Remove Concurrency / Delete Function",
                confidence_score=0.96,
                metrics_summary={
                    "invocations": invocations,
                    "last_invoked_days": last_invoked_days,
                    "provisioned_concurrency": prov_concurrency
                }
            )
        return None

    def _check_ec2_waste(self, res: CloudResource) -> WasteFinding | None:
        inst_type = res.specs.get("instance_type", "t3.micro")

        # Stopped instances incur persistent EBS storage and IP allocation fees
        if res.state == "stopped":
            return WasteFinding(
                id=f"waste-ec2-stopped-{res.id[-8:]}",
                resource_id=res.id,
                resource_name=res.name,
                resource_type=ResourceType.EC2,
                waste_category=WasteCategory.OVERSIZED_COMPUTE,
                severity=Severity.MEDIUM,
                description=(
                    f"EC2 Instance '{res.name}' ({inst_type}) is in 'stopped' state while continuing to incur "
                    f"underlying EBS volume storage reservation costs."
                ),
                current_specs=f"{inst_type} (Stopped)",
                recommended_specs="Snapshot EBS root volume and Terminate stopped instance if decommissioned",
                confidence_score=0.95,
                metrics_summary={"state": "stopped", "instance_type": inst_type}
            )

        if res.state != "running":
            return None

        metrics = res.metrics
        cpu_avg = metrics.get("cpu_utilization_avg")
        cpu_max = metrics.get("cpu_utilization_max", 100.0)

        # Do not label as waste if CPU metrics are unavailable
        if cpu_avg is None:
            return None

        # Flag if avg CPU is below 10% and peak is below 20%
        if cpu_avg < 10.0 and cpu_max < 20.0:
            recommended_type = self.DOWNGRADE_MAP.get(inst_type, "t3.medium")
            if recommended_type != inst_type:
                severity = Severity.CRITICAL if ("4xlarge" in inst_type or "2xlarge" in inst_type) else Severity.HIGH
                return WasteFinding(
                    id=f"waste-ec2-{res.id[-8:]}",
                    resource_id=res.id,
                    resource_name=res.name,
                    resource_type=ResourceType.EC2,
                    waste_category=WasteCategory.OVERSIZED_COMPUTE,
                    severity=severity,
                    description=(
                        f"EC2 Instance '{res.name}' ({inst_type}) is severely underutilized with "
                        f"average CPU of {cpu_avg}% (peak: {cpu_max}%) over the evaluation period."
                    ),
                    current_specs=f"{inst_type} ({res.specs.get('vcpus', '?')} vCPU, {res.specs.get('ram_gb', '?')}GB RAM)",
                    recommended_specs=f"Downsize to {recommended_type} (Right-sizing)",
                    confidence_score=0.98,
                    metrics_summary={
                        "cpu_utilization_avg": cpu_avg,
                        "cpu_utilization_max": cpu_max,
                        "memory_utilization_avg": metrics.get("memory_utilization_avg", 0),
                        "recommended_instance_type": recommended_type
                    }
                )
        return None

    def _check_eip_waste(self, res: CloudResource) -> WasteFinding | None:
        days = res.metrics.get("days_unassociated", 0)
        is_unassoc = (
            res.state == "unassociated" or
            res.specs.get("is_associated") is False or
            days > 0
        )
        if is_unassoc:
            return WasteFinding(
                id=f"waste-eip-{res.id[-8:]}",
                resource_id=res.id,
                resource_name=res.name,
                resource_type=ResourceType.EIP,
                waste_category=WasteCategory.IDLE_NETWORKING,
                severity=Severity.MEDIUM,
                description=(
                    f"Elastic IP '{res.specs.get('public_ip', res.id)}' is allocated but not associated "
                    f"with any running instance, incurring AWS unassociated IPv4 address fees."
                ),
                current_specs=f"Allocated Static IPv4: {res.specs.get('public_ip', res.id)}",
                recommended_specs="Release unassociated Elastic IP address",
                confidence_score=1.0,
                metrics_summary={"days_unassociated": days}
            )
        return None

    def _check_nat_waste(self, res: CloudResource) -> WasteFinding | None:
        metrics = res.metrics
        mb_transferred = metrics.get("bytes_processed_30d_mb", 100.0)
        if mb_transferred < 10.0:
            return WasteFinding(
                id=f"waste-nat-{res.id[-8:]}",
                resource_id=res.id,
                resource_name=res.name,
                resource_type=ResourceType.NAT_GATEWAY,
                waste_category=WasteCategory.IDLE_NETWORKING,
                severity=Severity.HIGH,
                description=(
                    f"NAT Gateway '{res.name}' processed only {mb_transferred} MB in 30 days while incurring "
                    f"continuous hourly baseline gateway reservation fees."
                ),
                current_specs=f"NAT Gateway in {res.specs.get('subnet_id', 'VPC')}",
                recommended_specs="Decommission NAT Gateway / Consolidate into Shared NAT",
                confidence_score=0.94,
                metrics_summary={"bytes_processed_mb": mb_transferred}
            )
        return None
