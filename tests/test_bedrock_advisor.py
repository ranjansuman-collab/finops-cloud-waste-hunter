"""
tests/test_bedrock_advisor.py
Unit tests for AWSBedrockAdvisorService (Checkpoint 5).

All boto3 / botocore calls are fully mocked — no real AWS credentials required.

Covers:
 1. Successful Bedrock response (mocked converse API)
 2. Malformed / invalid JSON from Bedrock model
 3. Missing AWS credentials → CREDENTIALS_MISSING
 4. AccessDenied / NO_PERMISSION
 5. AWS account verification required → ACCOUNT_VERIFICATION_REQUIRED
 6. Unavailable model → MODEL_NOT_AVAILABLE
 7. Simulation mode — local reasoning, Bedrock is NOT contacted
 8. Credential / secret leakage prevention (payload inspection)

ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import json
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

from botocore.exceptions import ClientError, NoCredentialsError

from core.models import WasteFinding, CostFinding, ResourceType, WasteCategory, Severity
from core.aws.bedrock import (
    AWSBedrockAdvisorService,
    STATUS_MODEL_NOT_AVAILABLE,
    FINOPS_SAFETY_INSTRUCTION,
)
from core.aws.connection import (
    STATUS_CONNECTED,
    STATUS_CREDENTIALS_MISSING,
    STATUS_NO_PERMISSION,
    STATUS_ACCOUNT_VERIFICATION_REQUIRED,
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
            "cpu_utilization_avg": 3.2,
            "cpu_utilization_max": 11.5,
            "recommended_instance_type": "t3.medium",
        },
    )


def _make_cost(finding_id: str = "finding-1") -> CostFinding:
    return CostFinding(
        finding_id=finding_id,
        resource_id="i-00000000000000001",
        resource_name="web-server-01",
        resource_type=ResourceType.EC2,
        current_monthly_cost=280.00,
        optimized_monthly_cost=35.00,
        monthly_savings=245.00,
        annualized_savings=2940.00,
        carbon_savings_kg_co2e=14.7,
        pricing_breakdown="m5.2xlarge on-demand @ $0.384/hr",
    )


def _bedrock_converse_response(json_payload: dict) -> dict:
    """Builds a mock converse() response dict containing the given JSON payload."""
    return {
        "output": {
            "message": {
                "content": [{"text": json.dumps(json_payload)}]
            }
        }
    }


def _valid_bedrock_payload() -> dict:
    return {
        "title": "Downsize web-server-01 to t3.medium",
        "executive_summary": "Instance running at 3.2% avg CPU — heavily over-provisioned.",
        "risk_level": "Low Risk",
        "rationale": "CloudWatch confirms <12% peak CPU over 30 days.",
        "steps_to_remediate": ["Update instance_type in Terraform", "Submit GitOps PR"],
        "rollback_plan": "Restore to m5.2xlarge if CPU spikes above 80%.",
        "confidence_score": 0.97,
        "estimated_savings": 245.0,
        "proposed_action": "RESIZE",
        "assumptions": ["Workload is CPU-bound"],
    }


def _make_client_error(code: str, message: str = "Test error") -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": message}},
        "InvokeModel",
    )


# ---------------------------------------------------------------------------
# AWSBedrockAdvisorService unit tests
# ---------------------------------------------------------------------------

class TestBedrockAdvisorService(unittest.TestCase):

    # ── 1. Successful Bedrock response ──────────────────────────────────

    @patch("core.aws.bedrock.get_aws_session")
    def test_successful_bedrock_invocation(self, mock_get_session):
        """
        A well-formed converse() response is parsed and returns a valid
        AIRecommendation with real_mode metadata.
        """
        mock_client = MagicMock()
        mock_client.converse.return_value = _bedrock_converse_response(_valid_bedrock_payload())
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_get_session.return_value = mock_session

        svc = AWSBedrockAdvisorService(region_name="ap-southeast-2")
        finding = _make_finding()
        cost = _make_cost()
        rec, status_info = svc.analyze_finding(finding, cost, session=mock_session)

        self.assertIsNotNone(rec, "Expected a recommendation, got None")
        self.assertEqual(status_info["status"], STATUS_CONNECTED)
        self.assertEqual(rec.resource_id, finding.resource_id)
        self.assertEqual(rec.resource_name, finding.resource_name)
        self.assertIn("Real Amazon Bedrock", rec.model_used)
        self.assertIsInstance(status_info["assumptions"], list)

    # ── 2. Malformed / invalid Bedrock JSON output ──────────────────────

    @patch("core.aws.bedrock.get_aws_session")
    def test_invalid_json_from_bedrock_returns_error(self, mock_get_session):
        """
        If the model returns non-parsable text, analyze_finding returns
        (None, {status: ERROR}) — never a fake recommendation.
        """
        mock_client = MagicMock()
        mock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "I'm sorry, I cannot produce JSON right now. Here is some prose instead."}]
                }
            }
        }
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_get_session.return_value = mock_session

        svc = AWSBedrockAdvisorService(region_name="ap-southeast-2")
        rec, status_info = svc.analyze_finding(_make_finding(), session=mock_session)

        self.assertIsNone(rec, "No recommendation should be returned for malformed output")
        self.assertEqual(status_info["status"], STATUS_ERROR)
        self.assertIn("Invalid Bedrock model output", status_info["message"])

    # ── 3. Missing credentials → CREDENTIALS_MISSING ───────────────────

    @patch("core.aws.bedrock.get_aws_session")
    def test_missing_credentials_returns_credentials_missing(self, mock_get_session):
        """
        NoCredentialsError from Boto3 must surface as CREDENTIALS_MISSING,
        never as a fake recommendation.
        """
        mock_session = MagicMock()
        mock_session.client.side_effect = NoCredentialsError()
        mock_get_session.return_value = mock_session

        svc = AWSBedrockAdvisorService(region_name="ap-southeast-2")
        rec, status_info = svc.analyze_finding(_make_finding(), session=mock_session)

        self.assertIsNone(rec)
        self.assertEqual(status_info["status"], STATUS_CREDENTIALS_MISSING)

    # ── 4. AccessDenied → NO_PERMISSION ────────────────────────────────

    @patch("core.aws.bedrock.get_aws_session")
    def test_access_denied_returns_no_permission(self, mock_get_session):
        """
        A Bedrock AccessDeniedException must map to NO_PERMISSION.
        """
        mock_client = MagicMock()
        mock_client.converse.side_effect = _make_client_error(
            "AccessDeniedException",
            "User: arn:aws:iam::123:user/test is not authorized to perform bedrock:InvokeModel",
        )
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_get_session.return_value = mock_session

        svc = AWSBedrockAdvisorService(region_name="ap-southeast-2")
        rec, status_info = svc.analyze_finding(_make_finding(), session=mock_session)

        self.assertIsNone(rec)
        self.assertEqual(status_info["status"], STATUS_NO_PERMISSION)

    # ── 5. Account verification required ────────────────────────────────

    @patch("core.aws.bedrock.get_aws_session")
    def test_account_verification_required(self, mock_get_session):
        """
        An OptInRequired / account verification error must surface as
        ACCOUNT_VERIFICATION_REQUIRED.
        """
        mock_client = MagicMock()
        mock_client.converse.side_effect = _make_client_error(
            "OptInRequired",
            "Your AWS account requires phone verification before using Bedrock.",
        )
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_get_session.return_value = mock_session

        svc = AWSBedrockAdvisorService(region_name="ap-southeast-2")
        rec, status_info = svc.analyze_finding(_make_finding(), session=mock_session)

        self.assertIsNone(rec)
        self.assertEqual(status_info["status"], STATUS_ACCOUNT_VERIFICATION_REQUIRED)

    # ── 6. Model not available → MODEL_NOT_AVAILABLE ────────────────────

    @patch("core.aws.bedrock.get_aws_session")
    def test_model_not_available_returns_explicit_status(self, mock_get_session):
        """
        ModelNotFoundException must return MODEL_NOT_AVAILABLE, NOT 'NOT_AVAILABLE'.
        """
        mock_client = MagicMock()
        mock_client.converse.side_effect = _make_client_error(
            "ModelNotFoundException",
            "The provided model identifier is invalid.",
        )
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_get_session.return_value = mock_session

        svc = AWSBedrockAdvisorService(region_name="ap-southeast-2")
        rec, status_info = svc.analyze_finding(_make_finding(), session=mock_session)

        self.assertIsNone(rec)
        self.assertEqual(
            status_info["status"],
            STATUS_MODEL_NOT_AVAILABLE,
            f"Expected MODEL_NOT_AVAILABLE but got {status_info['status']}",
        )
        self.assertNotEqual(status_info["status"], "NOT_AVAILABLE",
                            "Must not return generic NOT_AVAILABLE for model errors")

    @patch("core.aws.bedrock.get_aws_session")
    def test_model_not_ready_returns_model_not_available(self, mock_get_session):
        """ModelNotReadyException also maps to MODEL_NOT_AVAILABLE."""
        mock_client = MagicMock()
        mock_client.converse.side_effect = _make_client_error(
            "ModelNotReadyException", "Model is not ready."
        )
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_get_session.return_value = mock_session

        svc = AWSBedrockAdvisorService(region_name="ap-southeast-2")
        rec, status_info = svc.analyze_finding(_make_finding(), session=mock_session)

        self.assertIsNone(rec)
        self.assertEqual(status_info["status"], STATUS_MODEL_NOT_AVAILABLE)

    # ── 7. Simulation mode — Bedrock is NEVER contacted ─────────────────

    @patch("core.aws.bedrock.AWSBedrockAdvisorService")
    def test_simulation_mode_does_not_invoke_bedrock(self, mock_bedrock_class):
        """
        AIAdvisorModule in simulation mode (use_live_aws=False) must produce
        local recommendations without touching AWSBedrockAdvisorService.
        """
        advisor = AIAdvisorModule(use_live_aws=False)
        findings = [_make_finding(1), _make_finding(2)]
        costs = [_make_cost("finding-1")]

        recs = advisor.generate_recommendations(findings, costs)

        mock_bedrock_class.assert_not_called()
        self.assertEqual(len(recs), 2)
        for r in recs:
            self.assertIsNotNone(r.title)
            self.assertIsNotNone(r.rationale)
            self.assertIsNotNone(r.rollback_plan)

    def test_simulation_mode_empty_findings_returns_empty(self):
        advisor = AIAdvisorModule(use_live_aws=False)
        self.assertEqual(advisor.generate_recommendations([]), [])

    # ── 8. Credential / secret leakage prevention ───────────────────────

    @patch("core.aws.bedrock.get_aws_session")
    def test_bedrock_payload_contains_no_credentials(self, mock_get_session):
        """
        The text sent to Bedrock must NOT contain any AWS credential values,
        secret keys, session tokens, or other secrets.
        """
        captured_calls = []

        mock_client = MagicMock()

        def capture_converse(**kwargs):
            captured_calls.append(kwargs)
            return _bedrock_converse_response(_valid_bedrock_payload())

        mock_client.converse.side_effect = capture_converse
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_get_session.return_value = mock_session

        # Inject fake env-var credentials to make sure they don't leak
        import os
        os.environ["AWS_ACCESS_KEY_ID"] = "AKIAIOSFODNN7EXAMPLE"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        os.environ["AWS_SESSION_TOKEN"] = "FakeSessionToken123"

        try:
            svc = AWSBedrockAdvisorService(region_name="ap-southeast-2")
            svc.analyze_finding(_make_finding(), session=mock_session)
        finally:
            os.environ.pop("AWS_ACCESS_KEY_ID", None)
            os.environ.pop("AWS_SECRET_ACCESS_KEY", None)
            os.environ.pop("AWS_SESSION_TOKEN", None)

        self.assertTrue(len(captured_calls) > 0, "converse() should have been called")

        # Flatten the entire call args to a string and check for credential leakage
        call_text = json.dumps(captured_calls, default=str)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", call_text,
                         "AWS_ACCESS_KEY_ID must not appear in Bedrock payload")
        self.assertNotIn("wJalrXUtnFEMI", call_text,
                         "AWS_SECRET_ACCESS_KEY must not appear in Bedrock payload")
        self.assertNotIn("FakeSessionToken123", call_text,
                         "AWS_SESSION_TOKEN must not appear in Bedrock payload")

    # ── 9. Model configurability ─────────────────────────────────────────

    def test_model_id_uses_env_var(self):
        """BEDROCK_MODEL_ID env var is honoured; no hardcoded model name."""
        import os
        os.environ["BEDROCK_MODEL_ID"] = "anthropic.claude-3-sonnet-20240229-v1:0"
        try:
            svc = AWSBedrockAdvisorService(region_name="ap-southeast-2")
            self.assertEqual(svc.model_id, "anthropic.claude-3-sonnet-20240229-v1:0")
        finally:
            os.environ.pop("BEDROCK_MODEL_ID", None)

    def test_model_id_uses_finops_env_var(self):
        """FINOPS_BEDROCK_MODEL env var takes precedence over BEDROCK_MODEL_ID."""
        import os
        os.environ["FINOPS_BEDROCK_MODEL"] = "amazon.nova-pro-v1:0"
        os.environ["BEDROCK_MODEL_ID"] = "amazon.nova-lite-v1:0"
        try:
            svc = AWSBedrockAdvisorService(region_name="ap-southeast-2")
            self.assertEqual(svc.model_id, "amazon.nova-pro-v1:0")
        finally:
            os.environ.pop("FINOPS_BEDROCK_MODEL", None)
            os.environ.pop("BEDROCK_MODEL_ID", None)

    def test_model_id_explicit_parameter_overrides_env(self):
        """Explicit model_id constructor parameter takes highest precedence."""
        import os
        os.environ["BEDROCK_MODEL_ID"] = "amazon.nova-lite-v1:0"
        try:
            svc = AWSBedrockAdvisorService(
                region_name="ap-southeast-2",
                model_id="my-custom-model-v1"
            )
            self.assertEqual(svc.model_id, "my-custom-model-v1")
        finally:
            os.environ.pop("BEDROCK_MODEL_ID", None)

    # ── 10. generate_all_recommendations auth gate ───────────────────────

    @patch("core.aws.bedrock.get_aws_session")
    @patch("core.aws.bedrock.AWSConnectionService")
    def test_generate_all_recommendations_fails_without_auth(
        self, mock_conn_class, mock_get_session
    ):
        """
        generate_all_recommendations must abort with CREDENTIALS_MISSING
        if STS auth fails — never fabricating recommendations.
        """
        mock_conn = MagicMock()
        mock_conn.get_caller_identity.return_value = {
            "authenticated": False,
            "status": STATUS_CREDENTIALS_MISSING,
            "account_id": None,
            "arn": None,
            "message": "No AWS credentials found.",
        }
        mock_conn_class.return_value = mock_conn
        mock_get_session.return_value = MagicMock()

        svc = AWSBedrockAdvisorService(region_name="ap-southeast-2")
        result = svc.generate_all_recommendations(findings=[_make_finding()])

        self.assertEqual(result["status"], STATUS_CREDENTIALS_MISSING)
        self.assertEqual(result["recommendations"], [])
        self.assertTrue(len(result["errors"]) > 0)
        self.assertFalse(result["is_real_aws"] is False,
                         "is_real_aws must be True even on auth failure")

    # ── 11. API endpoint: returns CREDENTIALS_MISSING in no-credential env

    def test_advisor_api_endpoint_returns_credentials_missing(self):
        """
        POST /api/aws/advisor with no AWS credentials must return
        CREDENTIALS_MISSING, not fake recommendations.
        """
        from fastapi.testclient import TestClient
        from app.server import app

        client = TestClient(app)
        resp = client.post("/api/aws/advisor", json={"region": "ap-southeast-2"})

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # In this environment there are no AWS credentials
        self.assertIn(data["status"], (
            STATUS_CREDENTIALS_MISSING,
            STATUS_NO_PERMISSION,
            STATUS_ACCOUNT_VERIFICATION_REQUIRED,
            "CONNECTED",   # if local AWS config exists
        ))
        # Regardless of status, real_mode must be True
        self.assertTrue(data["real_mode"])


class TestBedrockSafetyPrompt(unittest.TestCase):
    """Verify the safety prompt enforces the no-mutation contract."""

    def test_safety_instruction_contains_no_execute(self):
        self.assertIn("must not execute", FINOPS_SAFETY_INSTRUCTION.lower())

    def test_safety_instruction_contains_no_invent(self):
        self.assertIn("do not invent", FINOPS_SAFETY_INSTRUCTION.lower())

    def test_safety_instruction_requests_json_only(self):
        self.assertIn("valid JSON", FINOPS_SAFETY_INSTRUCTION)


if __name__ == "__main__":
    unittest.main()
