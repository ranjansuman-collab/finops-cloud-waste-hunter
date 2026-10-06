"""
FinOps Cloud Waste Hunter & Auto-Remediator
Real AWS Cost Explorer Integration Service
Queries AWS Cost Explorer read-only APIs for actual service and region expenditure.
Clearly distinguishes actual account spend from estimated per-resource pricing models.

ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta
import boto3
from botocore.exceptions import ClientError

from core.aws.connection import (
    AWSConnectionService,
    get_aws_session,
    get_configured_region,
    classify_aws_error,
    STATUS_CONNECTED,
    STATUS_CREDENTIALS_MISSING,
    STATUS_NO_PERMISSION,
    STATUS_NOT_AVAILABLE,
    STATUS_ERROR
)

logger = logging.getLogger("finops.aws.costs")


class AWSCostService:
    """
    Retrieves actual AWS historical billing data from AWS Cost Explorer.
    Maintains rigorous separation between actual reported spend and calculated estimates.
    """

    def __init__(self, region_name: Optional[str] = None):
        self.region = get_configured_region(region_name)
        self.conn_service = AWSConnectionService(self.region)

    def get_actual_costs(
        self,
        session: Optional[boto3.Session] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Queries AWS Cost Explorer get_cost_and_usage grouped by SERVICE.
        Returns:
            Dict containing total spend, service breakdown, date range, and currency.
        """
        sess = session or get_aws_session(self.region)
        now = datetime.now(timezone.utc).date()
        start_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")

        # Ensure valid start and end dates for Cost Explorer
        if start_date >= end_date:
            start_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")

        try:
            # Cost Explorer endpoint is global (us-east-1)
            ce = sess.client("ce", region_name="us-east-1")
            resp = ce.get_cost_and_usage(
                TimePeriod={"Start": start_date, "End": end_date},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
                GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}]
            )

            service_costs: Dict[str, float] = {}
            total_cost = 0.0
            currency = "USD"

            results_by_time = resp.get("ResultsByTime", [])
            for period in results_by_time:
                for group in period.get("Groups", []):
                    keys = group.get("Keys", [])
                    service_name = keys[0] if keys else "Unknown Service"
                    metrics = group.get("Metrics", {})
                    unblended = metrics.get("UnblendedCost", {})
                    amount = float(unblended.get("Amount", 0.0))
                    currency = unblended.get("Unit", "USD")

                    service_costs[service_name] = round(service_costs.get(service_name, 0.0) + amount, 2)
                    total_cost += amount

            # Sort services by highest spend descending
            sorted_services = dict(sorted(service_costs.items(), key=lambda item: item[1], reverse=True))

            return {
                "status": STATUS_CONNECTED,
                "has_actual_costs": True,
                "total_cost": round(total_cost, 2),
                "currency": currency,
                "date_range": {"start": start_date, "end": end_date, "days": days},
                "service_costs": sorted_services,
                "message": f"Retrieved actual AWS costs for {len(sorted_services)} service(s) totaling ${total_cost:.2f} {currency}."
            }
        except Exception as exc:
            st, msg = classify_aws_error(exc)
            logger.warning(f"Cost Explorer error: {msg}")
            return {
                "status": st,
                "has_actual_costs": False,
                "total_cost": 0.0,
                "currency": "USD",
                "date_range": {"start": start_date, "end": end_date, "days": days},
                "service_costs": {},
                "message": msg
            }

    def get_full_cost_report(
        self,
        region_name: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Coordinates caller authentication and cost data retrieval with transparent limitation disclosures.
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
                "date_range": {"days": days},
                "total_cost": 0.0,
                "service_costs": {},
                "currency": "USD",
                "limitations_and_assumptions": [
                    "AWS credentials not available to query Cost Explorer."
                ],
                "errors": [err_msg],
                "summary": f"Cost retrieval aborted: {err_msg}"
            }

        cost_result = self.get_actual_costs(session=session, days=days)

        limitations = [
            "AWS Cost Explorer provides account and service-level cost aggregations.",
            "Per-resource cost attribution is estimated using AWS published regional on-demand rates unless AWS Cost Allocation Tags are activated."
        ]

        if not cost_result["has_actual_costs"]:
            limitations.append(f"Actual Cost Explorer data unavailable: {cost_result['message']}.")

        errors = []
        if cost_result["status"] != STATUS_CONNECTED:
            errors.append(cost_result["message"])

        return {
            "account_id": caller_identity["account_id"],
            "arn": caller_identity["arn"],
            "region": self.region,
            "timestamp": now_iso,
            "is_real_aws": True,
            "status": cost_result["status"],
            "date_range": cost_result["date_range"],
            "total_cost": cost_result["total_cost"],
            "service_costs": cost_result["service_costs"],
            "currency": cost_result["currency"],
            "limitations_and_assumptions": limitations,
            "errors": errors,
            "summary": cost_result["message"]
        }
