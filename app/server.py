"""
FinOps Web Application & REST API Server (FastAPI)
Provides real-time interactive UI and module-by-module demonstration endpoints.
ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import os
import json
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from core.engine import FinOpsEngine
from data.scenarios import SCENARIOS

app = FastAPI(
    title="FinOps Cloud Waste Hunter & Auto-Remediator",
    description="Automated cloud waste detection, Google Gemini AI recommendation, and GitOps Terraform remediation.",
    version="1.0.0"
)

# Initialize engine
engine = FinOpsEngine(use_live_aws=False)

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


class PipelineRunRequest(BaseModel):
    scenario: str = "enterprise"
    use_live_aws: bool = False
    region: Optional[str] = None


class PRActionRequest(BaseModel):
    reviewer: str = "Vivek Pandey (Lead FinOps Engineer)"
    reason: Optional[str] = None


class AdvisorRequest(BaseModel):
    """
    Configuration accepted by POST /api/aws/advisor.
    The endpoint always obtains live evidence from the real AWS pipeline itself;
    the frontend cannot inject arbitrary findings.
    """
    region: Optional[str] = None
    model_id: Optional[str] = None
    window_days: int = 14   # CloudWatch metrics window


class TerraformPlanApiRequest(BaseModel):
    scenario: Optional[str] = "enterprise"
    use_live_terraform: bool = False
    use_live_aws: bool = False
    region: Optional[str] = None


class TerraformApplyApiRequest(BaseModel):
    plan_id: str
    approved: bool = False
    confirm_destructive: bool = False
    reviewer: str = "Lead FinOps Engineer"
    use_live_aws: bool = False


class GitOpsWorkflowRequest(BaseModel):
    """
    Configuration accepted by POST /api/gitops/workflow.

    In simulation mode (use_live_gitops=False, default), an in-memory PR is created;
    no real Git or GitHub operations are performed.

    In live mode (use_live_gitops=True), the endpoint:
      1. Creates a real local Git branch (finops/<resource>/<action>).
      2. Stages and commits the Terraform patch files.
      3. Pushes the branch to the configured remote.
      4. Opens a GitHub Pull Request via the PyGitHub API.

    Requirements for live mode:
      - GITHUB_TOKEN env var (GitHub personal access token with repo scope)
      - GIT_REPOSITORY env var (e.g. "owner/repo")

    SAFETY:
    - PR creation NEVER executes terraform apply automatically.
    - Merging is NEVER automated; it requires human sign-off in GitHub.
    - No AWS credentials are injected into commits or PR body.
    """
    scenario: Optional[str] = "enterprise"
    use_live_aws: bool = False
    use_live_gitops: bool = False
    base_branch: str = "main"
    region: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        content = index_path.read_text(encoding="utf-8")
        return HTMLResponse(
            content=content,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return "<h1>FinOps Cloud Waste Hunter & Auto-Remediator</h1><p>Static UI loading...</p>"


@app.get("/api/scenarios")
def get_scenarios():
    return {
        "active_scenario": engine.last_report.scenario if engine.last_report else "enterprise",
        "scenarios": [
            {
                "id": s_id,
                "name": s_data["name"],
                "description": s_data["description"],
                "resource_count": len(s_data["resources"])
            }
            for s_id, s_data in SCENARIOS.items()
        ]
    }


@app.get("/api/aws/status")
def get_aws_status(region: Optional[str] = None):
    """
    Performs real read-only AWS authentication and service access checks.
    Verifies STS caller identity and read access to EC2, CloudWatch, S3, Cost Explorer, and Bedrock.
    """
    from core.aws.connection import AWSConnectionService
    service = AWSConnectionService(region_name=region)
    return service.get_full_status()


@app.get("/api/aws/resources")
def get_aws_resources(region: Optional[str] = None):
    """
    Performs real read-only AWS resource discovery across EC2, EBS, Elastic IP, Lambda, and S3.
    Returns grouped resources, counts, service statuses, and errors.
    """
    from core.aws.discovery import AWSDiscoveryService
    discovery = AWSDiscoveryService(region_name=region)
    return discovery.discover_all()


@app.get("/api/aws/metrics")
def get_aws_metrics(region: Optional[str] = None, window_days: int = 14):
    """
    Retrieves real CloudWatch telemetry for discovered resources over the specified window.
    """
    from core.aws.metrics import AWSMetricsService
    metrics_svc = AWSMetricsService(region_name=region)
    return metrics_svc.get_all_metrics(window_days=window_days)


@app.get("/api/aws/costs")
def get_aws_costs(region: Optional[str] = None, days: int = 30):
    """
    Retrieves actual AWS Cost Explorer spend and service breakdown.
    """
    from core.aws.costs import AWSCostService
    cost_svc = AWSCostService(region_name=region)
    return cost_svc.get_full_cost_report(days=days)


@app.post("/api/aws/advisor")
def run_ai_advisor(req: AdvisorRequest):
    """
    Runs the full real AWS evidence pipeline and returns Google Gemini AI
    recommendations for detected waste.

    LIVE mode pipeline:
      1. STS authentication check
      2. Real resource discovery (EC2, EBS, EIP, Lambda, S3)
      3. Real CloudWatch metrics (window_days)
      4. Real Cost Explorer spend
      5. Waste detection on real evidence
      6. Google Gemini recommendations via GeminiAdvisorService

    The frontend may only supply: region, model_id, window_days.
    It cannot inject arbitrary findings — all evidence is obtained from AWS.

    SAFETY:
    - Gemini is analysis/recommendation ONLY.
    - Gemini never modifies AWS, never executes Terraform.
    - No AWS credentials or secrets are sent to Gemini.
    """
    from core.aws.connection import AWSConnectionService, get_configured_region, STATUS_CONNECTED
    from core.gemini_advisor import GeminiAdvisorService, STATUS_MODEL_NOT_AVAILABLE
    from core.aws.discovery import AWSDiscoveryService
    from core.aws.metrics import AWSMetricsService
    from core.aws.costs import AWSCostService
    from core.module1_monitoring import ResourceMonitoringModule
    from core.module2_waste_detection import WasteDetectionModule
    from core.module3_cost_estimation import CostEstimationModule
    from datetime import datetime, timezone

    region = get_configured_region(req.region)
    timestamp = datetime.now(timezone.utc).isoformat()

    # Step 1: Verify AWS authentication
    conn_svc = AWSConnectionService(region_name=region)
    identity = conn_svc.get_caller_identity()
    if not identity["authenticated"]:
        return {
            "status": identity["status"],
            "account_id": None,
            "arn": None,
            "region": region,
            "model_used": req.model_id or "not_invoked",
            "real_mode": True,
            "timestamp": timestamp,
            "recommendations": [],
            "assumptions": [],
            "errors": [identity["message"]],
            "summary": f"Advisor aborted: {identity['message']}",
        }

    account_id = identity["account_id"]
    arn = identity["arn"]

    # Step 2: Real resource discovery
    monitoring = ResourceMonitoringModule(use_live_aws=True)
    monitoring.region_name = region
    try:
        resources = monitoring.fetch_resources()
    except Exception as exc:
        return {
            "status": "ERROR",
            "account_id": account_id,
            "arn": arn,
            "region": region,
            "model_used": req.model_id or "not_invoked",
            "real_mode": True,
            "timestamp": timestamp,
            "recommendations": [],
            "assumptions": [],
            "errors": [f"Resource discovery failed: {exc}"],
            "summary": "Advisor aborted at resource discovery stage.",
        }

    # Step 3: Real CloudWatch metrics
    metrics_svc = AWSMetricsService(region_name=region)
    metrics_svc.collect_metrics_for_resources(resources=resources)

    # Step 4: Real Cost Explorer spend
    cost_svc = AWSCostService(region_name=region)
    ce_data = cost_svc.get_actual_costs()

    # Step 5: Waste detection on real evidence
    waste_module = WasteDetectionModule()
    cost_module = CostEstimationModule()
    waste_findings = waste_module.detect_waste(resources)
    cost_findings = cost_module.estimate_savings(
        findings=waste_findings,
        resources=resources,
        cost_explorer_data=ce_data,
        is_real_aws=True,
    )

    if not waste_findings:
        return {
            "status": STATUS_CONNECTED,
            "account_id": account_id,
            "arn": arn,
            "region": region,
            "model_used": req.model_id or "not_invoked",
            "real_mode": True,
            "timestamp": timestamp,
            "recommendations": [],
            "assumptions": [],
            "errors": [],
            "summary": f"No waste findings detected in {region}. No Gemini invocation needed.",
        }

    # Step 6: Google Gemini recommendations
    gemini_svc = GeminiAdvisorService(region_name=region, model_id=req.model_id)
    result = gemini_svc.generate_all_recommendations(
        findings=waste_findings,
        costs=cost_findings,
        region_name=region,
        model_id=req.model_id,
    )

    return {
        "status": result.get("status"),
        "account_id": account_id,
        "arn": arn,
        "region": region,
        "model_used": result.get("model_used"),
        "real_mode": True,
        "timestamp": result.get("timestamp", timestamp),
        "recommendations": result.get("recommendations", []),
        "assumptions": result.get("assumptions", []),
        "errors": result.get("errors", []),
        "summary": result.get("summary", ""),
        "waste_findings_count": len(waste_findings),
        "resources_discovered": len(resources),
    }


@app.post("/api/pipeline/run")
def run_pipeline(req: PipelineRunRequest):
    try:
        report = engine.execute_full_pipeline(
            scenario_id=req.scenario,
            use_live_aws=req.use_live_aws,
            region_name=req.region,
            use_live_terraform=req.use_live_aws,
        )
        return {
            "status": "SUCCESS",
            "run_id": report.run_id,
            "timestamp": report.timestamp,
            "scenario": report.scenario,
            "summary": {
                "monitored_resources_count": len(report.monitored_resources),
                "waste_findings_count": len(report.waste_findings),
                "total_monthly_savings": report.total_monthly_savings,
                "total_annualized_savings": report.total_annualized_savings,
                "total_carbon_savings_kg": report.total_carbon_savings_kg,
                "ai_recommendations_count": len(report.ai_recommendations),
                "terraform_patches_count": len(report.terraform_patches),
                "terraform_plan_id": report.terraform_plan_id,
                "terraform_plan_status": report.terraform_plan_status,
                "gitops_pr_id": report.gitops_pr.pr_id if report.gitops_pr else None,
                "gitops_pr_status": report.gitops_pr.status if report.gitops_pr else None,
                "s3_uri": report.s3_uri,
                "dynamodb_id": report.dynamodb_id,
                "is_real_aws": report.is_real_aws,
                "ai_status": report.ai_status,
                "ai_error": report.ai_error,
                "bedrock_status": report.bedrock_status,
                "bedrock_error": report.bedrock_error,
                "errors": report.errors
            },
            "report": report.model_dump()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/modules/{module_num}")
def get_module_data(
    module_num: int,
    scenario: str = "enterprise",
    use_live_aws: Optional[bool] = None,
    region: Optional[str] = None
):
    if module_num < 1 or module_num > 7:
        raise HTTPException(status_code=400, detail="Module number must be between 1 and 7")
    return engine.get_module_data(
        module_num,
        scenario_id=scenario,
        use_live_aws=use_live_aws,
        region_name=region
    )


@app.post("/api/gitops/pr/{pr_id}/approve")
def approve_pull_request(pr_id: str, req: PRActionRequest):
    pr = engine.module7.approve_pr(pr_id, reviewer=req.reviewer)
    if not pr:
        raise HTTPException(status_code=404, detail="PR not found")
    return {"status": "SUCCESS", "pr": pr.model_dump()}


@app.post("/api/gitops/pr/{pr_id}/merge")
def merge_pull_request(pr_id: str, req: PRActionRequest):
    pr = engine.module7.merge_pr(pr_id, reviewer=req.reviewer)
    if not pr:
        raise HTTPException(status_code=404, detail="PR not found")
    return {"status": "SUCCESS", "pr": pr.model_dump()}


@app.post("/api/gitops/pr/{pr_id}/reject")
def reject_pull_request(pr_id: str, req: PRActionRequest):
    reason = req.reason or "Closed by FinOps Reviewer"
    pr = engine.module7.reject_pr(pr_id, reason=reason)
    if not pr:
        raise HTTPException(status_code=404, detail="PR not found")
    return {"status": "SUCCESS", "pr": pr.model_dump()}


@app.post("/api/gitops/workflow")
def run_gitops_workflow(req: GitOpsWorkflowRequest):
    """
    Executes the full GitOps PR workflow for FinOps-detected waste.

    Simulation mode (use_live_gitops=False, default):
      - In-memory PR is generated with full FinOps audit trail in the PR body.
      - No real Git or GitHub operations are executed.
      - Safe to run without any Git or GitHub credentials.

    Live mode (use_live_gitops=True):
      - Creates a real local branch: finops/<resource>/<action>.
      - Commits the generated Terraform patch files.
      - Pushes to the configured 'origin' remote.
      - Opens a GitHub Pull Request using GITHUB_TOKEN + GIT_REPOSITORY env vars.
      - Returns GIT_CREDENTIALS_MISSING or GIT_REPOSITORY_CONFIG_MISSING if
        the environment is not configured; never fakes success.

    SAFETY:
    - PR creation NEVER triggers terraform apply.
    - Merging is NEVER automated; human sign-off in GitHub is required.
    - No AWS credentials or secrets are included in commits or PR body.
    """
    from core.gitops.orchestrator import GitOpsOrchestrator
    from core.module7_gitops import GitOpsReviewModule

    # Build evidence from pipeline
    if req.use_live_aws:
        from core.module1_monitoring import ResourceMonitoringModule
        from core.module2_waste_detection import WasteDetectionModule
        from core.module3_cost_estimation import CostEstimationModule
        from core.aws.metrics import AWSMetricsService
        from core.aws.costs import AWSCostService
        from core.aws.connection import AWSConnectionService

        conn_svc = AWSConnectionService(region_name=req.region)
        identity = conn_svc.get_caller_identity()
        if not identity["authenticated"]:
            return {
                "status": identity["status"],
                "mode": "LIVE" if req.use_live_gitops else "SIMULATION",
                "message": f"GitOps aborted: {identity['message']}",
                "pr_number": None,
                "pr_url": None,
                "branch": None,
                "requires_human_approval": True,
                "automatic_apply_triggered": False,
                "errors": [identity["message"]],
            }

        monitoring = ResourceMonitoringModule(use_live_aws=True)
        if req.region:
            monitoring.region_name = req.region
        try:
            resources = monitoring.fetch_resources()
        except Exception as exc:
            return {
                "status": "ERROR",
                "mode": "LIVE" if req.use_live_gitops else "SIMULATION",
                "message": f"Resource discovery failed: {str(exc)}",
                "pr_number": None,
                "pr_url": None,
                "branch": None,
                "requires_human_approval": True,
                "automatic_apply_triggered": False,
                "errors": [str(exc)],
            }

        metrics_svc = AWSMetricsService(region_name=req.region)
        metrics_svc.collect_metrics_for_resources(resources=resources)

        cost_svc = AWSCostService(region_name=req.region)
        ce_data = cost_svc.get_actual_costs()

        waste_module = WasteDetectionModule()
        cost_module = CostEstimationModule()
        findings = waste_module.detect_waste(resources)
        costs = cost_module.estimate_savings(
            findings=findings,
            resources=resources,
            cost_explorer_data=ce_data,
            is_real_aws=True,
        )
        recommendations = []
        patches = []
        total_savings = sum(c.monthly_savings for c in costs)
    else:
        # Simulation: use or generate last pipeline report
        if not engine.last_report or (req.scenario and engine.last_report.scenario != req.scenario):
            engine.execute_full_pipeline(req.scenario or "enterprise")
        report = engine.last_report
        findings = report.waste_findings if report else []
        costs = report.cost_findings if report else []
        recommendations = report.ai_recommendations if report else []
        patches = report.terraform_patches if report else []
        total_savings = report.total_monthly_savings if report else 0.0

    if not findings:
        return {
            "status": "NO_FINDINGS",
            "mode": "LIVE" if req.use_live_gitops else "SIMULATION",
            "message": "No waste findings detected; no GitOps PR required.",
            "pr_number": None,
            "pr_url": None,
            "branch": None,
            "requires_human_approval": True,
            "automatic_apply_triggered": False,
        }

    # Determine if any action is destructive (EBS delete, EIP release, EC2 terminate)
    destructive_categories = {"UNATTACHED_STORAGE", "IDLE_NETWORKING"}
    is_destructive = any(f.waste_category.value in destructive_categories for f in findings)

    orchestrator = GitOpsOrchestrator(use_live_gitops=req.use_live_gitops)
    result = orchestrator.create_remediation_pr(
        run_id=engine.last_report.run_id if engine.last_report else "manual",
        findings=findings,
        costs=costs,
        recommendations=recommendations,
        patches=patches or None,
        total_monthly_savings=total_savings,
        is_destructive=is_destructive,
        base_branch=req.base_branch,
    )
    return result.model_dump()


@app.get("/api/terraform/diff")
def get_terraform_diff():
    if not engine.last_report:
        engine.execute_full_pipeline("enterprise")
    patches = engine.last_report.terraform_patches
    combined_diff = "\n".join([p.unified_diff for p in patches])
    return {
        "patch_count": len(patches),
        "combined_diff": combined_diff,
        "patches": [p.model_dump() for p in patches]
    }


@app.post("/api/terraform/plan")
def create_terraform_plan(req: TerraformPlanApiRequest):
    """
    Executes the pre-apply Terraform pipeline:
    HCL Generation -> terraform fmt -> terraform validate -> terraform plan.
    Returns structured plan output for explicit human review.
    NEVER automatically applies changes.
    """
    from core.terraform.service import RealTerraformService

    if req.use_live_aws:
        # In live mode, obtain real findings from AWS first
        from core.module1_monitoring import ResourceMonitoringModule
        from core.module2_waste_detection import WasteDetectionModule
        from core.module3_cost_estimation import CostEstimationModule
        from core.aws.metrics import AWSMetricsService
        from core.aws.costs import AWSCostService
        from core.aws.connection import AWSConnectionService

        conn_svc = AWSConnectionService(region_name=req.region)
        identity = conn_svc.get_caller_identity()
        if not identity["authenticated"]:
            from core.terraform.models import TerraformPlanResult
            return TerraformPlanResult(
                plan_id="",
                success=False,
                return_code=1,
                stdout="",
                stderr=f"Terraform plan aborted: {identity['message']}",
                status=identity["status"],
                errors=[identity["message"]],
            ).model_dump()

        monitoring = ResourceMonitoringModule(use_live_aws=True)
        if req.region:
            monitoring.region_name = req.region
        try:
            resources = monitoring.fetch_resources()
        except Exception as exc:
            from core.terraform.models import TerraformPlanResult
            return TerraformPlanResult(
                plan_id="",
                success=False,
                return_code=1,
                stdout="",
                stderr=f"Resource discovery failed: {str(exc)}",
                status="ERROR",
                errors=[str(exc)],
            ).model_dump()

        metrics_svc = AWSMetricsService(region_name=req.region)
        metrics_svc.collect_metrics_for_resources(resources=resources)

        cost_svc = AWSCostService(region_name=req.region)
        ce_data = cost_svc.get_actual_costs()

        waste_module = WasteDetectionModule()
        cost_module = CostEstimationModule()
        findings = waste_module.detect_waste(resources)
        costs = cost_module.estimate_savings(
            findings=findings,
            resources=resources,
            cost_explorer_data=ce_data,
            is_real_aws=True
        )
        if engine.last_report and engine.last_report.is_real_aws and engine.last_report.ai_recommendations:
            recommendations = engine.last_report.ai_recommendations
        else:
            try:
                recommendations = engine.module4.generate_recommendations(findings, costs)
            except Exception:
                recommendations = []
    else:
        # Simulation mode: ensure last_report is present
        if not engine.last_report or (req.scenario and engine.last_report.scenario != req.scenario):
            engine.execute_full_pipeline(req.scenario or "enterprise")
        findings = engine.last_report.waste_findings if engine.last_report else []
        recommendations = engine.last_report.ai_recommendations if engine.last_report else []
        costs = engine.last_report.cost_findings if engine.last_report else []

    # Configure service
    engine.terraform_service.use_live_terraform = req.use_live_terraform or req.use_live_aws
    if req.region:
        engine.terraform_service.region = req.region

    plan_result = engine.terraform_service.create_plan(
        findings=findings,
        recommendations=recommendations,
        cost_findings=costs,
    )
    if engine.last_report:
        engine.last_report.terraform_plan_id = plan_result.plan_id
        engine.last_report.terraform_plan_file = str(plan_result.plan_file) if plan_result.plan_file else None
        engine.last_report.terraform_plan_status = plan_result.status
        engine.last_report.terraform_plan_stdout = plan_result.stdout
        engine.last_report.terraform_plan_stderr = plan_result.stderr
        engine.last_report.terraform_plan_hash = plan_result.config_hash
        engine.last_report.terraform_plan_result = plan_result.model_dump()

    return plan_result.model_dump()


@app.post("/api/terraform/apply")
def apply_terraform_plan(req: TerraformApplyApiRequest):
    """
    Applies an already-reviewed and validated Terraform plan.
    Requires explicit user approval (approved=True) and checks for staleness,
    configuration integrity, and confirmation for destructive actions.
    NEVER allows Gemini, Bedrock, or background automation to bypass human sign-off.
    """
    from core.terraform.models import TerraformApprovalRequest

    approval = TerraformApprovalRequest(
        plan_id=req.plan_id,
        approved=req.approved,
        confirm_destructive=req.confirm_destructive,
        reviewer=req.reviewer,
    )

    apply_result = engine.terraform_service.apply_plan(
        approval=approval,
        use_live_aws=req.use_live_aws,
    )
    return apply_result.model_dump()


@app.get("/api/reports/download/{fmt}")
def download_report(fmt: str):
    if not engine.last_report:
        engine.execute_full_pipeline("enterprise")
    report = engine.last_report

    if fmt == "json":
        data = json.dumps(report.model_dump(), indent=2)
        return Response(
            content=data,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=finops-report-{report.run_id}.json"}
        )
    elif fmt == "markdown" or fmt == "md":
        md = engine.module5._generate_markdown_report(report.model_dump())
        return Response(
            content=md,
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename=finops-report-{report.run_id}.md"}
        )
    elif fmt == "csv":
        import io, csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Resource ID", "Resource Name", "Type", "Waste Category", "Severity", "Monthly Savings ($)", "Annualized Savings ($)"])
        cost_map = {c.finding_id: c for c in report.cost_findings}
        for f in report.waste_findings:
            c = cost_map.get(f.id)
            writer.writerow([
                f.resource_id,
                f.resource_name,
                f.resource_type,
                f.waste_category,
                f.severity,
                c.monthly_savings if c else 0.0,
                c.annualized_savings if c else 0.0
            ])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=finops-waste-{report.run_id}.csv"}
        )
    raise HTTPException(status_code=400, detail="Format must be json, markdown, or csv")


@app.get("/api/meta")
def get_metadata():
    return {
        "project": "FinOps Cloud Waste Hunter & Auto-Remediator",
        "course": "ISWE309L Cloud Computing",
        "slot": "A1 + TA1",
        "institution": "Vellore Institute of Technology (VIT)",
        "team": [
            {"name": "Vivek Pandey", "reg_no": "24MIS0216", "email": "vivek.pandey2024@vitstudent.ac.in"},
            {"name": "S. Hemal", "reg_no": "24MIS0050", "email": "hemal.s2024@vitstudent.ac.in"}
        ],
        "modules": [
            {"num": 1, "name": "Resource Monitoring", "desc": "Collects utilization metrics from simulated/live AWS infrastructure."},
            {"num": 2, "name": "Waste Detection", "desc": "Identifies unattached EBS, idle Lambdas, oversized EC2, and unused EIPs."},
            {"num": 3, "name": "Cost & Savings Estimation", "desc": "Computes current spend, optimized spend, monthly savings, and CO2e."},
            {"num": 4, "name": "AI Recommendation", "desc": "Google Gemini (gemini-3.5-flash-lite) synthesizes rationale, risk, and steps."},
            {"num": 5, "name": "Report Storage", "desc": "Persists structured reports to S3 and registers audit records in DynamoDB."},
            {"num": 6, "name": "Terraform Remediation", "desc": "Translates approved recommendations into HCL code patches and diffs."},
            {"num": 7, "name": "GitOps Review", "desc": "Automates reviewable pull requests and simulated CI/CD approval workflows."}
        ]
    }
