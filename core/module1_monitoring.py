"""
Module 1: Resource Monitoring
Collects resource-utilisation information from simulated cloud infrastructure and AWS CloudWatch.
ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from core.models import CloudResource, ResourceType
from data.scenarios import get_scenario_resources, SCENARIOS

logger = logging.getLogger("finops.module1")


class ResourceMonitoringModule:
    """
    Module 1 collects cloud resource utilization metrics and inventory.
    Implements FR1: Collect and monitor resource-usage metrics from simulated cloud infrastructure.
    """

    def __init__(self, use_live_aws: bool = False, region_name: Optional[str] = None):
        self.use_live_aws = use_live_aws
        self.region_name = region_name

    def _check_aws_credentials(self) -> bool:
        from core.aws.connection import has_aws_credentials
        return has_aws_credentials()

    def fetch_resources(self, scenario_id: str = "enterprise") -> List[CloudResource]:
        """
        Polls infrastructure resources. In live AWS mode, polls real EC2/EBS/Lambda/CloudWatch.
        In simulation mode, loads high-fidelity scenario telemetry.
        """
        if self.use_live_aws:
            return self._fetch_live_aws_resources()
        return self._fetch_simulated_resources(scenario_id)

    def _fetch_simulated_resources(self, scenario_id: str) -> List[CloudResource]:
        resources = get_scenario_resources(scenario_id)
        # Enrich telemetry with current collection timestamp
        now = datetime.now(timezone.utc).isoformat()
        for res in resources:
            if not res.created_at:
                res.created_at = now
            # Synthetic 7-day metric timeseries for chart rendering
            res.metrics["timeseries_cpu"] = self._generate_timeseries(
                res.metrics.get("cpu_utilization_avg", 10.0), variance=4.0
            )
        return resources

    def _generate_timeseries(self, base_val: float, variance: float = 3.0) -> List[Dict[str, Any]]:
        """Generates realistic 7-point sparkline timeseries for dashboards."""
        import random
        points = []
        random.seed(int(base_val * 10))
        for i in range(7):
            jitter = (random.random() - 0.5) * variance
            val = max(0.5, round(base_val + jitter, 2))
            points.append({"day": f"D-{7-i}", "value": val})
        return points

    def _fetch_live_aws_resources(self) -> List[CloudResource]:
        """
        Connects via AWSDiscoveryService to discover live AWS resources across EC2, EBS, EIP, Lambda, and S3.
        Raises AWSDiscoveryError if credentials are missing or STS fails.
        Never silently substitutes fake enterprise data in live AWS mode.
        """
        from core.aws.discovery import AWSDiscoveryService, AWSDiscoveryError
        from core.aws.connection import has_aws_credentials

        if not has_aws_credentials():
            raise AWSDiscoveryError("AWS credentials missing. Cannot discover live AWS resources.")

        discovery = AWSDiscoveryService(region_name=self.region_name)
        result = discovery.discover_all()

        if result.get("status") != "CONNECTED":
            err_msg = result.get("summary") or "AWS authentication/discovery failed"
            raise AWSDiscoveryError(err_msg)

        all_dicts = result.get("all_resources", [])
        return [CloudResource(**r) for r in all_dicts]

