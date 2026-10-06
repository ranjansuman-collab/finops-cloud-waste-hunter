"""
Module 3: Cost & Savings Estimation
Calculates current spend, optimized spend, monthly/annual savings, and carbon reduction metrics.
ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

from typing import List, Dict, Tuple
from core.models import (
    WasteFinding,
    CloudResource,
    CostFinding,
    ResourceType
)


class CostEstimationModule:
    """
    Implements FR4:
    FinOps pricing engine that models current vs optimized AWS cloud expenditure.
    """

    HOURS_PER_MONTH = 720

    # Standard AWS On-Demand Hourly Rates (us-east-1)
    EC2_HOURLY_PRICING: Dict[str, float] = {
        "c5.4xlarge": 0.6800,
        "c5.2xlarge": 0.3400,
        "c5.xlarge": 0.1700,
        "c5.large": 0.0850,
        "m5.2xlarge": 0.3840,
        "m5.xlarge": 0.1920,
        "m5.large": 0.0960,
        "t3.2xlarge": 0.3328,
        "t3.xlarge": 0.1664,
        "t3.large": 0.0832,
        "t3.medium": 0.0416,
        "t3.small": 0.0208,
        "t3.micro": 0.0104,
    }

    # EBS Monthly GB Pricing
    EBS_GB_MONTHLY_PRICING: Dict[str, float] = {
        "gp3": 0.08,
        "gp2": 0.10,
        "io2": 0.125,
        "st1": 0.045,
    }

    # Unassociated Elastic IP hourly penalty
    EIP_HOURLY_PENALTY: float = 0.005

    # NAT Gateway baseline hourly fee
    NAT_GATEWAY_HOURLY: float = 0.045

    def estimate_savings(
        self,
        findings: List[WasteFinding],
        resources: List[CloudResource],
        cost_explorer_data: Optional[Dict[str, Any]] = None,
        is_real_aws: bool = False
    ) -> List[CostFinding]:
        res_map = {r.id: r for r in resources}
        cost_findings: List[CostFinding] = []

        service_costs = {}
        if is_real_aws and cost_explorer_data and cost_explorer_data.get("has_actual_costs"):
            service_costs = cost_explorer_data.get("service_costs", {})

        for finding in findings:
            res = res_map.get(finding.resource_id)
            if not res:
                continue

            current_cost, opt_cost, breakdown, co2e = self._compute_cost_delta(finding, res)

            # In real AWS mode, clearly label calculated estimates and record assumptions
            if is_real_aws:
                service_key_map = {
                    ResourceType.EC2: "Amazon Elastic Compute Cloud - Compute",
                    ResourceType.EBS: "Amazon Elastic Block Store",
                    ResourceType.LAMBDA: "AWS Lambda",
                    ResourceType.EIP: "Amazon Elastic Compute Cloud - Compute",
                    ResourceType.S3: "Amazon Simple Storage Service"
                }
                ce_name = service_key_map.get(res.resource_type, "")
                actual_spend = service_costs.get(ce_name)
                spend_note = f" (Actual AWS {res.resource_type.value} Service Spend: ${actual_spend:.2f}/mo)" if actual_spend is not None else ""
                breakdown = f"[ESTIMATED SAVINGS MODEL]{spend_note} {breakdown} [Assumption: regional AWS on-demand rates; exact resource attribution requires Cost Allocation Tags]"

            monthly_savings = max(0.0, current_cost - opt_cost)
            annualized = monthly_savings * 12

            cost_findings.append(
                CostFinding(
                    finding_id=finding.id,
                    resource_id=res.id,
                    resource_name=res.name,
                    resource_type=res.resource_type,
                    current_monthly_cost=round(current_cost, 2),
                    optimized_monthly_cost=round(opt_cost, 2),
                    monthly_savings=round(monthly_savings, 2),
                    annualized_savings=round(annualized, 2),
                    carbon_savings_kg_co2e=round(co2e, 2),
                    pricing_breakdown=breakdown
                )
            )

        return cost_findings

    def _compute_cost_delta(
        self,
        finding: WasteFinding,
        res: CloudResource
    ) -> Tuple[float, float, str, float]:
        """Returns (current_monthly, optimized_monthly, breakdown_text, carbon_kg_co2e)."""
        r_type = res.resource_type

        # 1. EC2 Compute Rightsizing & Stopped Instances
        if r_type == ResourceType.EC2:
            current_type = res.specs.get("instance_type", "t3.medium")

            # Handle stopped EC2 instances
            if res.state == "stopped" or "stopped" in finding.id:
                # Stopped compute costs $0/hr, but root disk storage is charged (typical 30GB gp3 root volume)
                root_vol_gb = 30
                vol_cost = root_vol_gb * self.EBS_GB_MONTHLY_PRICING.get("gp3", 0.08)
                breakdown = f"Stopped {current_type} incurring ~{root_vol_gb} GB root volume storage (${vol_cost:.2f}/mo)"
                return vol_cost, 0.0, breakdown, 0.5

            rec_type = finding.metrics_summary.get("recommended_instance_type", "t3.medium")

            curr_rate = self.EC2_HOURLY_PRICING.get(current_type, 0.10)
            opt_rate = self.EC2_HOURLY_PRICING.get(rec_type, 0.0416)

            curr_monthly = curr_rate * self.HOURS_PER_MONTH
            opt_monthly = opt_rate * self.HOURS_PER_MONTH
            breakdown = f"{current_type} (${curr_rate:.4f}/hr) downsized to {rec_type} (${opt_rate:.4f}/hr)"
            vcpus_freed = max(2, res.specs.get("vcpus", 8) - 2)
            carbon = vcpus_freed * 0.025 * self.HOURS_PER_MONTH * 0.4
            return curr_monthly, opt_monthly, breakdown, carbon

        # 2. EBS Unattached Volume
        elif r_type == ResourceType.EBS:
            vol_type = res.specs.get("volume_type", "gp3")
            size_gb = res.specs.get("size_gb", 100)
            rate_per_gb = self.EBS_GB_MONTHLY_PRICING.get(vol_type, 0.08)

            curr_monthly = size_gb * rate_per_gb
            opt_monthly = 0.0  # Deleted/Snapshotted
            breakdown = f"{size_gb} GB @ ${rate_per_gb:.2f}/GB-mo ({vol_type}) unattached"
            carbon = size_gb * 0.005  # Storage energy footprint
            return curr_monthly, opt_monthly, breakdown, carbon

        # 3. Idle Serverless Lambda
        elif r_type == ResourceType.LAMBDA:
            prov_concurrency = res.specs.get("provisioned_concurrency", 0)
            mem_mb = res.specs.get("memory_mb", 512)
            # Prov concurrency rate ~$0.0000041667/GB-sec
            prov_cost = prov_concurrency * (mem_mb / 1024.0) * 0.0000041667 * 2592000
            base_cost = 2.50  # Storage and minimal retention fees
            curr_monthly = prov_cost + base_cost
            opt_monthly = 0.0
            breakdown = f"{prov_concurrency} prov. concurrency units + cold storage allocation"
            carbon = 0.8
            return curr_monthly, opt_monthly, breakdown, carbon

        # 4. Unassociated Elastic IP
        elif r_type == ResourceType.EIP:
            curr_monthly = self.EIP_HOURLY_PENALTY * self.HOURS_PER_MONTH
            opt_monthly = 0.0
            breakdown = f"AWS unassociated IPv4 address fee ($0.005/hr * 720h)"
            carbon = 0.1
            return curr_monthly, opt_monthly, breakdown, carbon

        # 5. Idle NAT Gateway
        elif r_type == ResourceType.NAT_GATEWAY:
            curr_monthly = self.NAT_GATEWAY_HOURLY * self.HOURS_PER_MONTH
            opt_monthly = 0.0
            breakdown = f"Dedicated NAT Gateway baseline reservation ($0.045/hr * 720h)"
            carbon = 12.0
            return curr_monthly, opt_monthly, breakdown, carbon

        return 0.0, 0.0, "Standard resource", 0.0
