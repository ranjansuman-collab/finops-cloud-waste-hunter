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
    description="Automated cloud waste detection, Bedrock Nova Lite AI recommendation, and GitOps Terraform remediation.",
    version="1.0.0"
)

# Initialize engine
engine = FinOpsEngine(use_live_aws=False)

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class PipelineRunRequest(BaseModel):
    scenario: str = "enterprise"
    use_live_aws: bool = False


class PRActionRequest(BaseModel):
    reviewer: str = "Vivek Pandey (Lead FinOps Engineer)"
    reason: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
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


@app.post("/api/pipeline/run")
def run_pipeline(req: PipelineRunRequest):
    try:
        report = engine.execute_full_pipeline(scenario_id=req.scenario)
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
                "gitops_pr_id": report.gitops_pr.pr_id if report.gitops_pr else None,
                "gitops_pr_status": report.gitops_pr.status if report.gitops_pr else None,
                "s3_uri": report.s3_uri,
                "dynamodb_id": report.dynamodb_id
            },
            "report": report.model_dump()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/modules/{module_num}")
def get_module_data(module_num: int, scenario: str = "enterprise"):
    if module_num < 1 or module_num > 7:
        raise HTTPException(status_code=400, detail="Module number must be between 1 and 7")
    return engine.get_module_data(module_num, scenario_id=scenario)


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
            {"num": 4, "name": "AI Recommendation", "desc": "Amazon Bedrock Nova Lite synthesizes rationale, risk, and steps."},
            {"num": 5, "name": "Report Storage", "desc": "Persists structured reports to S3 and registers audit records in DynamoDB."},
            {"num": 6, "name": "Terraform Remediation", "desc": "Translates approved recommendations into HCL code patches and diffs."},
            {"num": 7, "name": "GitOps Review", "desc": "Automates reviewable pull requests and simulated CI/CD approval workflows."}
        ]
    }
