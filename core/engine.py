"""
FinOps Orchestration Engine
Coordinates the entire 7-module lifecycle:
Module 1: Resource Monitoring
Module 2: Waste Detection
Module 3: Cost & Savings Estimation
Module 4: AI Recommendation (Google Gemini)
Module 5: Report Storage (Amazon S3 & DynamoDB)
Module 6: Terraform Remediation
Module 7: GitOps Review

ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import os
import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from core.models import PipelineReport
from core.gemini_advisor import DEFAULT_GEMINI_MODEL
from core.module1_monitoring import ResourceMonitoringModule
from core.module2_waste_detection import WasteDetectionModule
from core.module3_cost_estimation import CostEstimationModule
from core.module4_ai_advisor import AIAdvisorModule
from core.module5_storage import ReportStorageModule
from core.module6_terraform import TerraformRemediationModule
from core.module7_gitops import GitOpsReviewModule

logger = logging.getLogger("finops.engine")


class FinOpsEngine:
    def __init__(self, use_live_aws: bool = False, use_live_terraform: bool = False):
        self.module1 = ResourceMonitoringModule(use_live_aws=use_live_aws)
        self.module2 = WasteDetectionModule()
        self.module3 = CostEstimationModule()
        self.module4 = AIAdvisorModule(use_live_aws=use_live_aws)
        self.module5 = ReportStorageModule()
        self.module6 = TerraformRemediationModule(use_live_terraform=use_live_terraform)
        self.module7 = GitOpsReviewModule()
        self.last_report: Optional[PipelineReport] = None

    @property
    def terraform_service(self):
        return self.module6.real_service

    def execute_full_pipeline(
        self,
        scenario_id: str = "enterprise",
        use_live_aws: Optional[bool] = None,
        region_name: Optional[str] = None,
        use_live_terraform: Optional[bool] = None,
    ) -> PipelineReport:
        if use_live_aws is not None:
            self.module1.use_live_aws = use_live_aws
            self.module4.use_live_aws = use_live_aws
        if use_live_terraform is not None:
            self.module6.real_service.use_live_terraform = use_live_terraform
        if region_name:
            self.module1.region_name = region_name
            self.module4.region_name = region_name
            self.module6.real_service.region = region_name

        run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}"

        is_live = self.module1.use_live_aws
        if is_live:
            scenario_id = "live-aws"

        # Step 1: Resource Monitoring
        resources = self.module1.fetch_resources(scenario_id)

        # In live AWS mode: retrieve real CloudWatch metrics & Cost Explorer spend
        ce_data = None
        if is_live:
            from core.aws.metrics import AWSMetricsService
            from core.aws.costs import AWSCostService

            metrics_service = AWSMetricsService(region_name=self.module1.region_name)
            metrics_service.collect_metrics_for_resources(resources=resources)

            cost_service = AWSCostService(region_name=self.module1.region_name)
            ce_data = cost_service.get_actual_costs()

        # Step 2: Waste Detection (uses real CloudWatch metrics in live mode)
        waste_findings = self.module2.detect_waste(resources)

        # Step 3: Cost & Savings Estimation (clearly marks estimates in live mode)
        cost_findings = self.module3.estimate_savings(
            findings=waste_findings,
            resources=resources,
            cost_explorer_data=ce_data,
            is_real_aws=is_live
        )

        total_current = sum(c.current_monthly_cost for c in cost_findings)
        total_optimized = sum(c.optimized_monthly_cost for c in cost_findings)
        total_monthly_savings = sum(c.monthly_savings for c in cost_findings)
        total_annualized_savings = sum(c.annualized_savings for c in cost_findings)
        total_carbon = sum(c.carbon_savings_kg_co2e for c in cost_findings)

        cost_map = {c.finding_id: c for c in cost_findings}
        for finding in waste_findings:
            if finding.id in cost_map:
                finding.estimated_monthly_savings = cost_map[finding.id].monthly_savings
                finding.estimated_monthly_waste = cost_map[finding.id].monthly_savings

        # Step 4: AI Recommendations
        # In LIVE mode this delegates to GeminiAdvisorService.
        # If Gemini encounters an error (e.g. missing API key, rate limit, quota, invalid key),
        # preserve the exact error on the report rather than aborting the pipeline and
        # discarding the discovered resources, waste findings, cost models, and remediation patches.
        ai_recommendations = []
        ai_status = None
        ai_error = None
        try:
            ai_recommendations = self.module4.generate_recommendations(waste_findings, cost_findings)
            for rec in ai_recommendations:
                if rec.finding_id in cost_map:
                    rec.estimated_monthly_savings = cost_map[rec.finding_id].monthly_savings
        except Exception as b_err:
            err_str = str(b_err)
            if err_str.startswith("GEMINI_ERROR:") or err_str.startswith("BEDROCK_ERROR:"):
                parts = err_str.split(":", 2)
                ai_status = parts[1] if len(parts) > 1 else "ERROR"
                ai_error = parts[2] if len(parts) > 2 else err_str
            else:
                ai_status = "ERROR"
                ai_error = err_str
            logger.warning(f"AI advisor unavailable in pipeline ({ai_status}): {ai_error}")

        # Step 6: Terraform Remediation Patches & Plan Generation
        terraform_patches = self.module6.generate_patches(waste_findings, ai_recommendations)
        plan_res = None
        if waste_findings:
            try:
                plan_res = self.terraform_service.create_plan(
                    findings=waste_findings,
                    recommendations=ai_recommendations,
                    cost_findings=cost_findings
                )
            except Exception as tf_plan_err:
                logger.error(f"Failed to create Terraform plan in pipeline: {tf_plan_err}")

        # Step 7: GitOps Pull Request & Review
        gitops_pr = None
        if waste_findings:
            gitops_pr = self.module7.create_pull_request(
                run_id=run_id,
                patches=terraform_patches,
                findings=waste_findings,
                costs=cost_findings,
                recommendations=ai_recommendations,
                total_monthly_savings=total_monthly_savings,
                total_annualized_savings=total_annualized_savings
            )

        report = PipelineReport(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            scenario=scenario_id,
            monitored_resources=resources,
            waste_findings=waste_findings,
            cost_findings=cost_findings,
            total_current_monthly_cost=round(total_current, 2),
            total_optimized_monthly_cost=round(total_optimized, 2),
            total_monthly_savings=round(total_monthly_savings, 2),
            total_annualized_savings=round(total_annualized_savings, 2),
            total_carbon_savings_kg=round(total_carbon, 2),
            ai_recommendations=ai_recommendations,
            terraform_patches=terraform_patches,
            terraform_plan_id=plan_res.plan_id if plan_res else None,
            terraform_plan_file=str(plan_res.plan_file) if (plan_res and plan_res.plan_file) else None,
            terraform_plan_status=plan_res.status if plan_res else None,
            terraform_plan_stdout=plan_res.stdout if plan_res else None,
            terraform_plan_stderr=plan_res.stderr if plan_res else None,
            terraform_plan_hash=plan_res.config_hash if plan_res else None,
            terraform_plan_result=plan_res.model_dump() if plan_res else None,
            gitops_pr=gitops_pr,
            is_real_aws=is_live,
            ai_status=ai_status,
            ai_error=ai_error,
            bedrock_status=ai_status,
            bedrock_error=ai_error,
            errors=[ai_error] if ai_error else []
        )

        # Step 5: S3 & DynamoDB Storage
        storage_meta = self.module5.store_pipeline_run(report.model_dump())
        report.s3_uri = storage_meta.get("s3_uri", "")
        report.dynamodb_id = storage_meta.get("dynamodb_id", "")

        self.last_report = report
        return report

    def get_module_data(
        self,
        module_num: int,
        scenario_id: str = "enterprise",
        use_live_aws: Optional[bool] = None,
        region_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Supports inspecting operations individually for module-wise demonstration."""
        if not self.last_report:
            self.execute_full_pipeline(scenario_id, use_live_aws=use_live_aws, region_name=region_name)
        report = self.last_report

        if module_num == 1:
            return {
                "module": 1,
                "title": "Resource Monitoring",
                "count": len(report.monitored_resources),
                "data": [r.model_dump() for r in report.monitored_resources]
            }
        elif module_num == 2:
            return {
                "module": 2,
                "title": "Waste Detection",
                "count": len(report.waste_findings),
                "data": [w.model_dump() for w in report.waste_findings]
            }
        elif module_num == 3:
            return {
                "module": 3,
                "title": "Cost & Savings Estimation",
                "total_monthly_savings": report.total_monthly_savings,
                "total_annualized_savings": report.total_annualized_savings,
                "total_carbon_savings_kg": report.total_carbon_savings_kg,
                "data": [c.model_dump() for c in report.cost_findings]
            }
        elif module_num == 4:
            return {
                "module": 4,
                "title": "AI Recommendation (Google Gemini)",
                "model": os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
                "ai_status": report.ai_status,
                "ai_error": report.ai_error,
                "bedrock_status": report.bedrock_status,
                "bedrock_error": report.bedrock_error,
                "data": [r.model_dump() for r in report.ai_recommendations]
            }
        elif module_num == 5:
            return {
                "module": 5,
                "title": "Report Storage (Amazon S3 & DynamoDB)",
                "s3_uri": report.s3_uri,
                "dynamodb_id": report.dynamodb_id,
                "audit_history": self.module5.get_audit_records()
            }
        elif module_num == 6:
            return {
                "module": 6,
                "title": "Terraform Remediation",
                "patches_count": len(report.terraform_patches),
                "data": [p.model_dump() for p in report.terraform_patches],
                "plan_id": report.terraform_plan_id,
                "plan_status": report.terraform_plan_status,
                "plan_file": report.terraform_plan_file,
                "plan_result": report.terraform_plan_result,
            }
        elif module_num == 7:
            return {
                "module": 7,
                "title": "GitOps Review & Pull Requests",
                "pr": report.gitops_pr.model_dump() if report.gitops_pr else None,
                "active_prs": {k: v.model_dump() for k, v in self.module7.active_prs.items()}
            }
        return {"error": "Invalid module number"}
