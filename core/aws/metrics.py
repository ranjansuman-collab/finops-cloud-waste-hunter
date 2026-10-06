"""
FinOps Cloud Waste Hunter & Auto-Remediator
Real CloudWatch Metrics Collection Service
Collects utilization metrics for discovered AWS resources (EC2, EBS, Lambda)
using CloudWatch get_metric_statistics with configurable evaluation periods.

ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
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

logger = logging.getLogger("finops.aws.metrics")


class AWSMetricsService:
    """
    Retrieves real CloudWatch telemetry for discovered resources.
    Never invents or fabricates missing metric data.
    """

    METRIC_SPECS = {
        ResourceType.EC2: [
            {"namespace": "AWS/EC2", "metric": "CPUUtilization", "stats": ["Average", "Maximum", "Minimum"], "unit": "Percent"},
            {"namespace": "AWS/EC2", "metric": "NetworkIn", "stats": ["Average", "Sum"], "unit": "Bytes"},
            {"namespace": "AWS/EC2", "metric": "NetworkOut", "stats": ["Average", "Sum"], "unit": "Bytes"},
            {"namespace": "AWS/EC2", "metric": "DiskReadOps", "stats": ["Sum", "Average"], "unit": "Count"},
            {"namespace": "AWS/EC2", "metric": "DiskWriteOps", "stats": ["Sum", "Average"], "unit": "Count"}
        ],
        ResourceType.EBS: [
            {"namespace": "AWS/EBS", "metric": "VolumeReadOps", "stats": ["Sum", "Average"], "unit": "Count"},
            {"namespace": "AWS/EBS", "metric": "VolumeWriteOps", "stats": ["Sum", "Average"], "unit": "Count"},
            {"namespace": "AWS/EBS", "metric": "VolumeIdleTime", "stats": ["Sum", "Average"], "unit": "Seconds"}
        ],
        ResourceType.LAMBDA: [
            {"namespace": "AWS/Lambda", "metric": "Invocations", "stats": ["Sum"], "unit": "Count"},
            {"namespace": "AWS/Lambda", "metric": "Errors", "stats": ["Sum"], "unit": "Count"},
            {"namespace": "AWS/Lambda", "metric": "Duration", "stats": ["Average", "Maximum"], "unit": "Milliseconds"},
            {"namespace": "AWS/Lambda", "metric": "Throttles", "stats": ["Sum"], "unit": "Count"}
        ]
    }

    def __init__(self, region_name: Optional[str] = None):
        self.region = get_configured_region(region_name)
        self.conn_service = AWSConnectionService(self.region)

    def fetch_metric_statistics(
        self,
        cw_client: Any,
        namespace: str,
        metric_name: str,
        dimension_name: str,
        dimension_value: str,
        start_time: datetime,
        end_time: datetime,
        period_seconds: int = 3600,
        statistics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Queries CloudWatch get_metric_statistics for a specific dimension.
        Returns datapoints and statistical summaries, or empty structure if no data exists.
        """
        stats_to_query = statistics or ["Average", "Maximum", "Minimum", "Sum"]
        try:
            resp = cw_client.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=[{"Name": dimension_name, "Value": dimension_value}],
                StartTime=start_time,
                EndTime=end_time,
                Period=period_seconds,
                Statistics=stats_to_query
            )

            raw_datapoints = resp.get("Datapoints", [])
            # Sort datapoints chronologically
            sorted_points = sorted(raw_datapoints, key=lambda d: d.get("Timestamp", datetime.min))

            datapoint_records = []
            avg_vals = []
            max_vals = []
            min_vals = []
            sum_vals = []

            for p in sorted_points:
                ts = p.get("Timestamp")
                ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
                rec = {"timestamp": ts_str}
                for s in stats_to_query:
                    if s in p:
                        rec[s.lower()] = round(float(p[s]), 3)
                datapoint_records.append(rec)

                if "Average" in p:
                    avg_vals.append(float(p["Average"]))
                if "Maximum" in p:
                    max_vals.append(float(p["Maximum"]))
                if "Minimum" in p:
                    min_vals.append(float(p["Minimum"]))
                if "Sum" in p:
                    sum_vals.append(float(p["Sum"]))

            has_data = len(datapoint_records) > 0
            return {
                "metric_name": metric_name,
                "namespace": namespace,
                "has_data": has_data,
                "datapoints_count": len(datapoint_records),
                "datapoints": datapoint_records,
                "summary": {
                    "average": round(sum(avg_vals) / len(avg_vals), 3) if avg_vals else None,
                    "maximum": round(max(max_vals), 3) if max_vals else None,
                    "minimum": round(min(min_vals), 3) if min_vals else None,
                    "sum": round(sum(sum_vals), 3) if sum_vals else None
                },
                "status": "SUCCESS"
            }
        except Exception as exc:
            st, msg = classify_aws_error(exc)
            logger.warning(f"Error fetching metric {metric_name} for {dimension_value}: {msg}")
            return {
                "metric_name": metric_name,
                "namespace": namespace,
                "has_data": False,
                "datapoints_count": 0,
                "datapoints": [],
                "summary": {"average": None, "maximum": None, "minimum": None, "sum": None},
                "status": st,
                "error": msg
            }

    def collect_metrics_for_resources(
        self,
        resources: List[CloudResource],
        session: Optional[boto3.Session] = None,
        window_days: int = 14
    ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
        """
        Iterates over discovered resources and retrieves their respective CloudWatch metrics.
        Enriches resource.metrics in-place with real metrics data.
        Returns:
            (resource_metrics_map, status_dict)
        """
        sess = session or get_aws_session(self.region)
        resource_metrics: Dict[str, Dict[str, Any]] = {}
        status = {"status": STATUS_CONNECTED, "collected_count": 0, "errors": []}

        try:
            cw = sess.client("cloudwatch", region_name=self.region)
        except Exception as exc:
            st, msg = classify_aws_error(exc)
            return {}, {"status": st, "collected_count": 0, "errors": [msg]}

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=window_days)
        # Select period: hourly (3600) for <= 14 days, otherwise 86400 (daily)
        period_seconds = 3600 if window_days <= 14 else 86400

        for res in resources:
            r_type = res.resource_type
            specs_list = self.METRIC_SPECS.get(r_type, [])
            if not specs_list:
                continue

            # Determine dimension identifier
            if r_type == ResourceType.EC2:
                dim_name = "InstanceId"
                dim_val = res.id
            elif r_type == ResourceType.EBS:
                dim_name = "VolumeId"
                dim_val = res.id
            elif r_type == ResourceType.LAMBDA:
                dim_name = "FunctionName"
                dim_val = res.name
            else:
                continue

            res_entry: Dict[str, Any] = {
                "resource_id": res.id,
                "resource_name": res.name,
                "resource_type": r_type.value,
                "window_days": window_days,
                "metrics": {}
            }

            for spec in specs_list:
                m_name = spec["metric"]
                metric_result = self.fetch_metric_statistics(
                    cw_client=cw,
                    namespace=spec["namespace"],
                    metric_name=m_name,
                    dimension_name=dim_name,
                    dimension_value=dim_val,
                    start_time=start_time,
                    end_time=end_time,
                    period_seconds=period_seconds,
                    statistics=spec["stats"]
                )
                res_entry["metrics"][m_name] = metric_result

                # Propagate specific summaries to resource.metrics for waste detection
                if metric_result.get("has_data"):
                    summary = metric_result["summary"]
                    if r_type == ResourceType.EC2 and m_name == "CPUUtilization":
                        res.metrics["cpu_utilization_avg"] = summary["average"]
                        res.metrics["cpu_utilization_max"] = summary["maximum"]
                        res.metrics["cpu_utilization_min"] = summary["minimum"]
                        res.metrics["has_real_metrics"] = True
                    elif r_type == ResourceType.LAMBDA and m_name == "Invocations":
                        res.metrics["invocations_period_sum"] = summary["sum"]
                        res.metrics["has_real_metrics"] = True
                    elif r_type == ResourceType.EBS and m_name == "VolumeReadOps":
                        res.metrics["read_ops_sum"] = summary["sum"]
                        res.metrics["has_real_metrics"] = True

            resource_metrics[res.id] = res_entry
            status["collected_count"] += 1

        return resource_metrics, status

    def get_all_metrics(
        self,
        resources: Optional[List[CloudResource]] = None,
        region_name: Optional[str] = None,
        window_days: int = 14
    ) -> Dict[str, Any]:
        """
        Coordinates full metrics retrieval for resources. If resources not passed,
        discovers resources first using AWSDiscoveryService.
        """
        if region_name:
            self.region = get_configured_region(region_name)
            self.conn_service = AWSConnectionService(self.region)

        session = get_aws_session(self.region)
        caller_identity = self.conn_service.get_caller_identity(session)

        now_iso = datetime.now(timezone.utc).isoformat()
        if not caller_identity["authenticated"]:
            err_status = caller_identity["status"]
            err_msg = caller_identity["message"]
            return {
                "account_id": None,
                "arn": None,
                "region": self.region,
                "timestamp": now_iso,
                "is_real_aws": True,
                "status": err_status,
                "window_days": window_days,
                "resource_metrics": {},
                "metric_errors": [err_msg],
                "summary": f"CloudWatch metrics collection aborted: {err_msg}"
            }

        target_resources = resources
        if target_resources is None:
            from core.aws.discovery import AWSDiscoveryService
            discovery = AWSDiscoveryService(region_name=self.region)
            disc_result = discovery.discover_all()
            target_resources = [CloudResource(**r) for r in disc_result.get("all_resources", [])]

        metrics_map, status_info = self.collect_metrics_for_resources(
            resources=target_resources,
            session=session,
            window_days=window_days
        )

        return {
            "account_id": caller_identity["account_id"],
            "arn": caller_identity["arn"],
            "region": self.region,
            "timestamp": now_iso,
            "is_real_aws": True,
            "status": status_info["status"],
            "window_days": window_days,
            "resource_metrics": metrics_map,
            "metric_errors": status_info.get("errors", []),
            "summary": f"Collected CloudWatch metrics across {len(metrics_map)} resources in {self.region} over {window_days} days."
        }
