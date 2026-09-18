"""
Module 5: Report Storage & Audit Ledger
Stores structured waste detection data and reports using Amazon S3 and Amazon DynamoDB.
ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("finops.module5")


class ReportStorageModule:
    """
    Implements FR7 & FR8:
    Generates and persists audit reports to S3 and registers audit records into DynamoDB.
    Supports both simulated local persistence and live AWS S3/DynamoDB sync.
    """

    def __init__(self, base_dir: str = None):
        if not base_dir:
            base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage")
        self.base_dir = Path(base_dir)
        self.s3_dir = self.base_dir / "s3_bucket" / "reports"
        self.dynamodb_dir = self.base_dir / "dynamodb"

        self.s3_dir.mkdir(parents=True, exist_ok=True)
        self.dynamodb_dir.mkdir(parents=True, exist_ok=True)

        self.db_file = self.dynamodb_dir / "finops_audit_table.json"
        if not self.db_file.exists():
            self.db_file.write_text("[]", encoding="utf-8")

        self.s3_client = self._init_boto3_client("s3")
        self.dynamodb_client = self._init_boto3_client("dynamodb")

    def _init_boto3_client(self, service: str):
        if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
            try:
                import boto3
                return boto3.client(service)
            except Exception as e:
                logger.warning(f"Failed to initialize live AWS {service} client: {e}")
        return None

    def store_pipeline_run(self, report_data: Dict[str, Any]) -> Dict[str, str]:
        run_id = report_data.get("run_id", f"run-{int(datetime.now(timezone.utc).timestamp())}")
        timestamp = report_data.get("timestamp", datetime.now(timezone.utc).isoformat())

        # 1. S3 Storage (JSON + Markdown)
        s3_json_filename = f"finops-audit-{run_id}.json"
        s3_md_filename = f"finops-report-{run_id}.md"

        json_path = self.s3_dir / s3_json_filename
        json_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")

        md_content = self._generate_markdown_report(report_data)
        md_path = self.s3_dir / s3_md_filename
        md_path.write_text(md_content, encoding="utf-8")

        s3_uri = f"s3://finops-waste-hunter-reports/{s3_json_filename}"

        # If live S3 client is configured, upload
        if self.s3_client and os.getenv("FINOPS_S3_BUCKET"):
            try:
                bucket = os.getenv("FINOPS_S3_BUCKET")
                self.s3_client.put_object(
                    Bucket=bucket,
                    Key=f"reports/{s3_json_filename}",
                    Body=json.dumps(report_data, indent=2)
                )
                logger.info(f"Report synced to live S3 bucket: {bucket}")
            except Exception as e:
                logger.warning(f"Could not upload to live S3: {e}")

        # 2. DynamoDB Storage (Structured Audit Record)
        audit_record = {
            "run_id": run_id,
            "timestamp": timestamp,
            "scenario": report_data.get("scenario", "default"),
            "total_findings": len(report_data.get("waste_findings", [])),
            "monthly_savings": report_data.get("total_monthly_savings", 0.0),
            "annualized_savings": report_data.get("total_annualized_savings", 0.0),
            "carbon_savings_kg": report_data.get("total_carbon_savings_kg", 0.0),
            "gitops_pr_number": report_data.get("gitops_pr", {}).get("pr_number") if report_data.get("gitops_pr") else None,
            "gitops_status": report_data.get("gitops_pr", {}).get("status", "N/A") if report_data.get("gitops_pr") else "N/A",
            "s3_json_key": s3_json_filename,
            "s3_uri": s3_uri
        }

        self._save_to_dynamodb_store(audit_record)

        # If live DynamoDB client is configured, put item
        if self.dynamodb_client and os.getenv("FINOPS_DYNAMODB_TABLE"):
            try:
                table = os.getenv("FINOPS_DYNAMODB_TABLE")
                self.dynamodb_client.put_item(
                    TableName=table,
                    Item={
                        "run_id": {"S": run_id},
                        "timestamp": {"S": timestamp},
                        "monthly_savings": {"N": str(audit_record["monthly_savings"])},
                        "total_findings": {"N": str(audit_record["total_findings"])}
                    }
                )
            except Exception as e:
                logger.warning(f"Could not write to live DynamoDB: {e}")

        return {
            "s3_uri": s3_uri,
            "s3_local_path": str(json_path),
            "s3_md_path": str(md_path),
            "dynamodb_id": run_id
        }

    def _save_to_dynamodb_store(self, record: Dict[str, Any]):
        try:
            records = json.loads(self.db_file.read_text(encoding="utf-8"))
        except Exception:
            records = []
        records.insert(0, record)
        # Keep latest 50 runs in local DynamoDB ledger
        records = records[:50]
        self.db_file.write_text(json.dumps(records, indent=2), encoding="utf-8")

    def get_audit_records(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.db_file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def get_report_by_id(self, run_id: str) -> Optional[Dict[str, Any]]:
        path = self.s3_dir / f"finops-audit-{run_id}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def _generate_markdown_report(self, data: Dict[str, Any]) -> str:
        findings = data.get("waste_findings", [])
        recs = data.get("ai_recommendations", [])
        monthly_sav = data.get("total_monthly_savings", 0.0)
        annual_sav = data.get("total_annualized_savings", 0.0)
        carbon_sav = data.get("total_carbon_savings_kg", 0.0)

        lines = [
            "# FinOps Cloud Waste Hunter & Auto-Remediator Audit Report",
            "**Course Project Review-1** | ISWE309L Cloud Computing",
            "**Project Team**: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)",
            f"**Execution Timestamp**: `{data.get('timestamp')}`",
            f"**Run ID**: `{data.get('run_id')}`",
            "",
            "## Executive Summary",
            f"- **Total Monthly Projected Savings**: **${monthly_sav:.2f} / month**",
            f"- **Total Annualized Projected Savings**: **${annual_sav:.2f} / year**",
            f"- **Projected Carbon Footprint Reduction**: **{carbon_sav:.2f} kg CO2e**",
            f"- **Total Inefficiencies Detected**: **{len(findings)} resource(s)**",
            "",
            "## Detected Waste Findings & AI Remediation Plans",
            "| Resource | Type | Category | Severity | Current Specs | Recommended Action |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |"
        ]

        for f in findings:
            lines.append(
                f"| `{f.get('resource_name')}` | {f.get('resource_type')} | {f.get('waste_category')} | "
                f"{f.get('severity')} | {f.get('current_specs')} | {f.get('recommended_specs')} |"
            )

        lines.append("")
        lines.append("## Amazon Bedrock Nova Lite Rationale")
        for r in recs:
            lines.append(f"### {r.get('title')} ({r.get('risk_level')})")
            lines.append(f"- **Summary**: {r.get('executive_summary')}")
            lines.append(f"- **Rationale**: {r.get('rationale')}")
            lines.append("- **Action Steps**:")
            for s in r.get("steps_to_remediate", []):
                lines.append(f"  1. {s}")
            lines.append(f"- **Rollback Procedure**: {r.get('rollback_plan')}")
            lines.append("")

        lines.append("---")
        lines.append("*Generated automatically by FinOps Cloud Waste Hunter & Auto-Remediator engine.*")
        return "\n".join(lines)
