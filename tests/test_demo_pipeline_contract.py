"""
Regression and Data-Contract Tests for FinOps Demo Pipelines.
Verifies that Enterprise, Startup, and Clean demo scenarios return valid, non-null
numeric metrics and adhere to the frontend data contract without triggering
undefined '.toFixed' errors.
"""

import re
import pytest
from fastapi.testclient import TestClient

from app.server import app
from core.engine import FinOpsEngine
from core.models import ResourceType, WasteCategory


@pytest.fixture
def engine():
    return FinOpsEngine()


@pytest.fixture
def client():
    return TestClient(app)


class TestDemoPipelineContracts:
    """Tests guaranteeing backend-frontend contract consistency across demo scenarios."""

    def test_enterprise_scenario_contract(self, engine):
        report = engine.execute_full_pipeline(scenario_id="enterprise", use_live_aws=False)

        # Top-level executive metrics must be valid floats
        assert isinstance(report.total_monthly_savings, float)
        assert report.total_monthly_savings > 0.0
        assert isinstance(report.total_annualized_savings, float)
        assert report.total_annualized_savings > 0.0
        assert isinstance(report.total_carbon_savings_kg, float)
        assert report.total_carbon_savings_kg > 0.0
        assert isinstance(report.total_current_monthly_cost, float)
        assert report.total_current_monthly_cost > 0.0
        assert isinstance(report.total_optimized_monthly_cost, float)
        assert report.total_optimized_monthly_cost >= 0.0

        # Monitored resources
        assert len(report.monitored_resources) > 0
        for r in report.monitored_resources:
            assert r.id
            assert r.resource_type in list(ResourceType)
            assert isinstance(r.metrics, dict)

        # Waste findings contract
        assert len(report.waste_findings) > 0
        cost_map = {c.finding_id: c for c in report.cost_findings}

        for f in report.waste_findings:
            assert f.id
            assert f.resource_id
            assert f.resource_type in list(ResourceType)
            assert f.waste_category in list(WasteCategory)
            assert f.description
            assert f.current_specs
            assert f.recommended_specs
            assert isinstance(f.confidence_score, float)
            assert 0.0 <= f.confidence_score <= 1.0

            # Verified savings field availability
            assert f.id in cost_map
            cost_item = cost_map[f.id]
            assert isinstance(cost_item.monthly_savings, float)
            assert cost_item.monthly_savings > 0.0

            # Direct model-level enriched savings
            assert isinstance(f.estimated_monthly_savings, float)
            assert f.estimated_monthly_savings == cost_item.monthly_savings
            assert isinstance(f.estimated_monthly_waste, float)
            assert f.estimated_monthly_waste == cost_item.monthly_savings

        # Cost findings contract
        assert len(report.cost_findings) == len(report.waste_findings)
        for c in report.cost_findings:
            assert isinstance(c.current_monthly_cost, float)
            assert isinstance(c.optimized_monthly_cost, float)
            assert isinstance(c.monthly_savings, float)
            assert isinstance(c.annualized_savings, float)
            assert isinstance(c.carbon_savings_kg_co2e, float)
            assert c.pricing_breakdown
            assert c.resource_type in list(ResourceType)

        # AI Recommendations contract
        assert len(report.ai_recommendations) == len(report.waste_findings)
        for rec in report.ai_recommendations:
            assert rec.finding_id
            assert rec.title
            assert rec.executive_summary
            assert rec.risk_level
            assert rec.rationale
            assert isinstance(rec.steps_to_remediate, list)
            assert len(rec.steps_to_remediate) > 0
            assert rec.rollback_plan
            assert isinstance(rec.confidence_score, float)
            # Enriched savings
            assert isinstance(rec.estimated_monthly_savings, float)
            assert rec.estimated_monthly_savings > 0.0

    def test_startup_scenario_contract(self, engine):
        report = engine.execute_full_pipeline(scenario_id="startup", use_live_aws=False)

        assert report.total_monthly_savings > 0.0
        assert len(report.waste_findings) > 0
        for f in report.waste_findings:
            assert isinstance(f.estimated_monthly_savings, float)
            assert f.estimated_monthly_savings > 0.0

        for rec in report.ai_recommendations:
            assert isinstance(rec.estimated_monthly_savings, float)
            assert rec.estimated_monthly_savings > 0.0

    def test_clean_scenario_contract(self, engine):
        report = engine.execute_full_pipeline(scenario_id="clean", use_live_aws=False)

        assert report.total_monthly_savings == 0.0
        assert report.total_annualized_savings == 0.0
        assert report.total_carbon_savings_kg == 0.0
        assert len(report.waste_findings) == 0
        assert len(report.cost_findings) == 0
        assert len(report.ai_recommendations) == 0
        assert report.gitops_pr is None

    def test_api_pipeline_run_endpoint(self, client):
        resp = client.post("/api/pipeline/run", json={"scenario": "enterprise", "use_live_aws": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"
        assert "report" in data

        rep = data["report"]
        assert isinstance(rep["total_monthly_savings"], (int, float))
        assert isinstance(rep["waste_findings"], list)
        assert len(rep["waste_findings"]) > 0

        # Verify findings in the serialized JSON
        first_w = rep["waste_findings"][0]
        assert "estimated_monthly_savings" in first_w
        assert isinstance(first_w["estimated_monthly_savings"], (int, float))
        assert "estimated_monthly_waste" in first_w
        assert isinstance(first_w["estimated_monthly_waste"], (int, float))

        # Verify AI recommendation in serialized JSON
        first_r = rep["ai_recommendations"][0]
        assert "estimated_monthly_savings" in first_r
        assert isinstance(first_r["estimated_monthly_savings"], (int, float))
        assert "rationale" in first_r
        assert "executive_summary" in first_r
        assert "rollback_plan" in first_r

    def test_app_js_tofixed_safety_audit(self):
        """Audits app/static/app.js to ensure every .toFixed() invocation is guarded against undefined."""
        with open("app/static/app.js", "r", encoding="utf-8") as f:
            lines = f.readlines()

        tofixed_patterns = [
            (idx + 1, line.strip())
            for idx, line in enumerate(lines)
            if ".toFixed(" in line
        ]

        assert len(tofixed_patterns) > 0

        # Validate that no line calls .toFixed on an unguarded property
        # Dangerous anti-patterns: f.estimated_monthly_waste.toFixed, rec.estimated_monthly_savings.toFixed
        for line_no, text in tofixed_patterns:
            assert "f.estimated_monthly_waste.toFixed" not in text, f"Line {line_no} calls toFixed on raw f.estimated_monthly_waste: {text}"
            assert "rec.estimated_monthly_savings.toFixed" not in text, f"Line {line_no} calls toFixed on raw rec.estimated_monthly_savings: {text}"
            assert "f.estimated_monthly_savings.toFixed" not in text, f"Line {line_no} calls toFixed on raw f.estimated_monthly_savings: {text}"
