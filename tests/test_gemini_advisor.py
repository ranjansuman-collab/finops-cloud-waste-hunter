"""
tests/test_gemini_advisor.py
Unit tests for GeminiAdvisorService.

All Google GenAI SDK calls are mocked — no network access or real GEMINI_API_KEY required.

Covers:
 1. Successful Gemini response (mocked generate_content with structured output)
 2. Malformed / invalid JSON from Gemini
 3. Missing GEMINI_API_KEY -> CREDENTIALS_MISSING
 4. 401/403 or invalid API key -> NO_PERMISSION
 5. 429 quota / rate limit -> RATE_LIMITED
 6. 404 model not found -> MODEL_NOT_AVAILABLE
 7. Simulation mode — local reasoning, Gemini is NOT contacted
 8. Credential / secret leakage prevention (payload inspection)
 9. Environment variable GEMINI_MODEL configuration
 10. FinOps safety prompt verification

ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from google.genai import errors

from core.models import WasteFinding, CostFinding, ResourceType, WasteCategory, Severity
from core.gemini_advisor import (
    GeminiAdvisorService,
    FINOPS_SAFETY_INSTRUCTION,
    DEFAULT_GEMINI_MODEL,
    STATUS_RATE_LIMITED,
    STATUS_MODEL_NOT_AVAILABLE,
    STATUS_NETWORK_ERROR,
)
from core.aws.connection import (
    STATUS_CONNECTED,
    STATUS_CREDENTIALS_MISSING,
    STATUS_NO_PERMISSION,
    STATUS_ERROR,
)
from core.module4_ai_advisor import AIAdvisorModule


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_finding(idx: int = 1) -> WasteFinding:
    return WasteFinding(
        id=f"finding-{idx}",
        resource_id=f"i-{idx:017x}",
        resource_name=f"web-server-{idx:02d}",
        resource_type=ResourceType.EC2,
        waste_category=WasteCategory.OVERSIZED_COMPUTE,
        severity=Severity.HIGH,
        description="Instance running at <5% CPU over 30 days.",
        current_specs="m5.2xlarge",
        recommended_specs="t3.medium",
        confidence_score=0.97,
        metrics_summary={
            "cpu_utilization_avg": 3.8,
            "cpu_utilization_max": 11.2,
            "network_in_avg_bytes": 1024,
            "recommended_instance_type": "t3.medium",
        },
    )


def _make_cost(finding_id: str = "finding-1") -> CostFinding:
    return CostFinding(
        finding_id=finding_id,
        resource_id="i-00000000000000001",
        resource_name="web-server-01",
        resource_type=ResourceType.EC2,
        current_monthly_cost=280.32,
        optimized_monthly_cost=30.37,
        monthly_savings=249.95,
        annualized_savings=2999.40,
        carbon_savings_kg_co2e=14.2,
        pricing_breakdown="m5.2xlarge: $0.384/hr; t3.medium: $0.0416/hr",
    )


def _valid_gemini_payload() -> dict:
    return {
        "title": "Downsize web-server-01 to t3.medium",
        "executive_summary": "Downsizing web-server-01 to t3.medium will save $249.95/month with no impact on performance.",
        "risk_level": "Low Risk",
        "rationale": "Average CPU is 3.8% and peak is 11.2% over 30 days. t3.medium provides sufficient capacity.",
        "steps_to_remediate": [
            "Stop instance during maintenance window.",
            "Modify instance type to t3.medium.",
            "Start instance and verify application health metrics.",
        ],
        "rollback_plan": "Revert instance type to m5.2xlarge if latency exceeds threshold.",
        "confidence_score": 0.96,
        "estimated_savings": 249.95,
        "proposed_action": "RESIZE",
        "assumptions": ["Workload profile does not change drastically."],
    }


def _mock_gemini_response(payload_dict: dict) -> MagicMock:
    resp = MagicMock()
    resp.text = json.dumps(payload_dict)
    return resp


class TestGeminiAdvisorService(unittest.TestCase):

    # 1. Successful Gemini response
    @patch("core.gemini_advisor.genai.Client")
    def test_successful_gemini_invocation(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _mock_gemini_response(_valid_gemini_payload())
        mock_client_cls.return_value = mock_client

        svc = GeminiAdvisorService(api_key="test-key", model_id="gemini-3.5-flash-lite")
        finding = _make_finding(1)
        cost = _make_cost("finding-1")

        rec, status_info = svc.analyze_finding(finding, cost, client=mock_client)

        self.assertIsNotNone(rec)
        self.assertEqual(status_info["status"], STATUS_CONNECTED)
        self.assertIn("Downsize", rec.title)
        self.assertIn("t3.medium", rec.title)
        self.assertEqual(rec.risk_level, "Low Risk")
        self.assertEqual(len(rec.steps_to_remediate), 3)
        self.assertEqual(rec.finding_id, "finding-1")
        self.assertEqual(rec.resource_id, "i-00000000000000001")
        self.assertIn("gemini-3.5-flash-lite", rec.model_used)

    # 2. Malformed / invalid JSON output
    def test_invalid_json_from_gemini_returns_error(self):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "This is plain text without valid JSON."
        mock_client.models.generate_content.return_value = mock_resp

        svc = GeminiAdvisorService(api_key="test-key")
        finding = _make_finding(1)

        rec, status_info = svc.analyze_finding(finding, client=mock_client)

        self.assertIsNone(rec)
        self.assertEqual(status_info["status"], STATUS_ERROR)
        self.assertIn("Invalid Gemini response structure", status_info["message"])

    # 3. Missing GEMINI_API_KEY
    def test_missing_credentials_returns_credentials_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GEMINI_API_KEY", None)
            svc = GeminiAdvisorService(api_key="")
            client, info = svc.get_client()

            self.assertIsNone(client)
            self.assertEqual(info["status"], STATUS_CREDENTIALS_MISSING)
            self.assertIn("GEMINI_API_KEY", info["message"])

    # 4. AccessDenied / Invalid API Key -> NO_PERMISSION
    def test_permission_denied_maps_to_no_permission(self):
        mock_client = MagicMock()
        mock_err = errors.ClientError(403, {"error": {"message": "API_KEY_INVALID: The provided API key is invalid."}})
        mock_client.models.generate_content.side_effect = mock_err

        svc = GeminiAdvisorService(api_key="test-key")
        finding = _make_finding(1)

        rec, status_info = svc.analyze_finding(finding, client=mock_client)

        self.assertIsNone(rec)
        self.assertEqual(status_info["status"], STATUS_NO_PERMISSION)
        self.assertIn("authentication failed", status_info["message"])

    # 5. Rate limited / Quota exceeded -> RATE_LIMITED
    def test_rate_limit_maps_to_rate_limited(self):
        mock_client = MagicMock()
        mock_err = errors.ClientError(429, {"error": {"message": "Resource has been exhausted: quota exceeded"}})
        mock_client.models.generate_content.side_effect = mock_err

        svc = GeminiAdvisorService(api_key="test-key")
        finding = _make_finding(1)

        rec, status_info = svc.analyze_finding(finding, client=mock_client)

        self.assertIsNone(rec)
        self.assertEqual(status_info["status"], STATUS_RATE_LIMITED)
        self.assertIn("rate limit", status_info["message"])

    # 6. Model not found -> MODEL_NOT_AVAILABLE
    def test_model_not_found_maps_to_model_not_available(self):
        mock_client = MagicMock()
        mock_err = errors.ClientError(404, {"error": {"message": "models/gemini-invalid was not found"}})
        mock_client.models.generate_content.side_effect = mock_err

        svc = GeminiAdvisorService(api_key="test-key")
        finding = _make_finding(1)

        rec, status_info = svc.analyze_finding(finding, client=mock_client)

        self.assertIsNone(rec)
        self.assertEqual(status_info["status"], STATUS_MODEL_NOT_AVAILABLE)
        self.assertIn("model unavailable", status_info["message"])

    # 7. Simulation mode — Gemini is NEVER contacted
    @patch("core.gemini_advisor.GeminiAdvisorService.get_client")
    def test_simulation_mode_does_not_invoke_gemini(self, mock_get_client):
        mod4 = AIAdvisorModule(use_live_aws=False)
        finding = _make_finding(1)
        cost = _make_cost("finding-1")

        recs = mod4.generate_recommendations([finding], [cost])

        self.assertEqual(len(recs), 1)
        mock_get_client.assert_not_called()

    # 8. Credential / secret leakage prevention
    def test_gemini_payload_contains_no_credentials(self):
        fake_secrets = {
            "AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE",
            "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "AWS_SESSION_TOKEN": "AQoDYXdzEJr111111111111111111111111111111111",
            "GEMINI_API_KEY": "AIzaSySecretApiKeyForGeminiTest12345",
        }

        svc = GeminiAdvisorService(api_key="test-key")
        finding = _make_finding(1)
        cost = _make_cost("finding-1")

        payload = svc._sanitize_evidence_payload(finding, cost)
        payload_str = json.dumps(payload)

        for secret_name, secret_val in fake_secrets.items():
            self.assertNotIn(
                secret_val,
                payload_str,
                f"{secret_name} must not appear in Gemini evidence payload",
            )

    # 9. Model configuration via environment variable
    def test_gemini_model_env_var_honoured(self):
        with patch.dict(os.environ, {"GEMINI_MODEL": "gemini-2.5-pro"}):
            svc = GeminiAdvisorService()
            self.assertEqual(svc.model_id, "gemini-2.5-pro")

    def test_gemini_default_model(self):
        self.assertEqual(DEFAULT_GEMINI_MODEL, "gemini-3.5-flash-lite")
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GEMINI_MODEL", None)
            svc = GeminiAdvisorService()
            self.assertEqual(svc.model_id, "gemini-3.5-flash-lite")
            self.assertEqual(svc.model_id, DEFAULT_GEMINI_MODEL)

    # 10. Safety instruction enforcement
    @patch("core.gemini_advisor.genai.Client")
    def test_safety_instruction_passed_to_gemini(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _mock_gemini_response(_valid_gemini_payload())
        mock_client_cls.return_value = mock_client

        svc = GeminiAdvisorService(api_key="test-key")
        finding = _make_finding(1)

        svc.analyze_finding(finding, client=mock_client)

        self.assertTrue(mock_client.models.generate_content.called)
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        config = call_kwargs.get("config")
        self.assertIsNotNone(config)
        self.assertEqual(config.system_instruction, FINOPS_SAFETY_INSTRUCTION)
        self.assertEqual(config.response_mime_type, "application/json")


if __name__ == "__main__":
    unittest.main()
