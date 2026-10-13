"""
FinOps Cloud Waste Hunter & Auto-Remediator
Real Google Gemini AI Advisor Service
Analyzes real waste findings and CloudWatch telemetry using Google Gemini API (gemini-3.5-flash-lite).
Strictly analytical and advisory: NEVER executes AWS actions or calls Terraform apply.

ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import os
import json
import re
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from pydantic import BaseModel, Field, ValidationError

import httpx
from google import genai
from google.genai import types, errors

from core.models import WasteFinding, CostFinding, AIRecommendation
from core.aws.connection import (
    AWSConnectionService,
    get_aws_session,
    get_configured_region,
    setup_windows_ca_bundle,
    STATUS_CONNECTED,
    STATUS_CREDENTIALS_MISSING,
    STATUS_NO_PERMISSION,
    STATUS_NOT_AVAILABLE,
    STATUS_ERROR,
)

logger = logging.getLogger("finops.gemini")

# Status constants for Gemini service
STATUS_RATE_LIMITED = "RATE_LIMITED"
STATUS_MODEL_NOT_AVAILABLE = "MODEL_NOT_AVAILABLE"
STATUS_NETWORK_ERROR = "NETWORK_ERROR"

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"

FINOPS_SAFETY_INSTRUCTION = (
    "You are an automated FinOps AI recommendation and remediation engine. "
    "You analyze infrastructure waste findings and synthesize actionable optimization recommendations "
    "together with corresponding Terraform HCL remediation configurations. "
    "You must not execute changes. "
    "Do not claim that an action was performed. "
    "Do not invent AWS metrics, resources, accounts, or costs. "
    "Use only the supplied evidence. "
    "For terraform_hcl, generate clean, valid Terraform HCL representing the remediation "
    "for the exact discovered resource (e.g. decommissioned/commented resource block for unattached storage removal). "
    "NEVER include provisioners, local-exec, remote-exec, shell scripts, curl, wget, or credentials. "
    "Return only valid JSON matching the specified schema."
)


class GeminiStructuredOutput(BaseModel):
    title: str = Field(description="Action-oriented summary title")
    executive_summary: str = Field(description="Summary of identified waste and projected benefit")
    risk_level: str = Field(default="Low Risk", description="Risk level (Low Risk, Medium Risk, High Risk)")
    rationale: str = Field(description="Technical rationale grounded in the provided CloudWatch metrics")
    steps_to_remediate: List[str] = Field(description="Prescriptive steps for engineering review")
    rollback_plan: str = Field(description="Safe recovery or rollback procedure")
    confidence_score: float = Field(default=0.95, ge=0.0, le=1.0)
    estimated_savings: Optional[float] = None
    proposed_action: Optional[str] = None
    assumptions: List[str] = Field(default_factory=list)
    action_type: Optional[str] = Field(default="DELETE", description="FinOps action type: DELETE, RESIZE, DISASSOCIATE, or REMOVE")
    terraform_hcl: Optional[str] = Field(default=None, description="Valid Terraform HCL representing the remediation for this exact resource")
    terraform_explanation: Optional[str] = Field(default=None, description="Technical explanation of the generated Terraform remediation HCL")


def classify_gemini_error(exc: Exception) -> Tuple[str, str]:
    """
    Classifies exceptions raised during Gemini API invocation into standard status codes:
    - CREDENTIALS_MISSING
    - NO_PERMISSION (401/403/invalid API key)
    - RATE_LIMITED (429/quota)
    - MODEL_NOT_AVAILABLE (404/model not found)
    - NETWORK_ERROR (connection/timeout)
    - ERROR (general / invalid response / validation)
    """
    if isinstance(exc, errors.APIError):
        code = getattr(exc, "code", None)
        message = getattr(exc, "message", str(exc))
        lower_msg = message.lower()
        if code in (401, 403) or "api key" in lower_msg or "unauthenticated" in lower_msg or "permission" in lower_msg:
            return STATUS_NO_PERMISSION, f"Gemini authentication failed: {message}"
        if code == 429 or "resource has been exhausted" in lower_msg or "quota" in lower_msg or "rate" in lower_msg:
            return STATUS_RATE_LIMITED, f"Gemini rate limit exceeded: {message}"
        if code == 503 or "high demand" in lower_msg or "spikes in demand" in lower_msg:
            return STATUS_RATE_LIMITED, f"Gemini temporarily unavailable due to high demand: {message}"
        if code == 404 or "not found" in lower_msg or "no longer available" in lower_msg:
            return STATUS_MODEL_NOT_AVAILABLE, f"Gemini model unavailable: {message}"
        if code in (500, 502, 504):
            return STATUS_ERROR, f"Gemini service error [{code}]: {message}"
        return STATUS_ERROR, f"Gemini API error [{code}]: {message}"

    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return STATUS_NETWORK_ERROR, f"Gemini network connection error: {exc}"

    if isinstance(exc, (json.JSONDecodeError, ValidationError)):
        return STATUS_ERROR, f"Invalid Gemini response structure: {exc}"

    if isinstance(exc, ValueError) and "api key" in str(exc).lower():
        return STATUS_CREDENTIALS_MISSING, "GEMINI_API_KEY environment variable is not configured."

    return STATUS_ERROR, str(exc)


class GeminiAdvisorService:
    """
    Direct interface to Google Gemini API for generative FinOps optimization analysis.
    Validates model output using Pydantic schemas and reports exact service limitations.
    Enforces strict safety: never hard-codes credentials and never executes infrastructure mutations.
    """

    def __init__(
        self,
        region_name: Optional[str] = None,
        model_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.region = get_configured_region(region_name)
        self.model_id = (
            model_id
            or os.getenv("GEMINI_MODEL")
            or DEFAULT_GEMINI_MODEL
        )
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.conn_service = AWSConnectionService(self.region)

    def is_configured(self) -> bool:
        """Checks if the GEMINI_API_KEY is configured in the environment."""
        key = self.api_key or os.getenv("GEMINI_API_KEY")
        return bool(key and key.strip())

    def get_client(self) -> Tuple[Optional[genai.Client], Dict[str, Any]]:
        """
        Initializes and returns a Google GenAI client using GEMINI_API_KEY.
        Handles Windows CA bundle configuration transparently.
        """
        setup_windows_ca_bundle()
        # Ensure httpx on Windows picks up CA bundle if configured
        ca_bundle = os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("AWS_CA_BUNDLE")
        if ca_bundle and not os.getenv("SSL_CERT_FILE"):
            os.environ["SSL_CERT_FILE"] = ca_bundle

        key = self.api_key or os.getenv("GEMINI_API_KEY")
        if not key or not key.strip():
            return None, {
                "status": STATUS_CREDENTIALS_MISSING,
                "message": "GEMINI_API_KEY environment variable is not configured. Real Gemini advice requires a valid API key.",
            }

        try:
            client = genai.Client(api_key=key.strip())
            return client, {"status": STATUS_CONNECTED, "message": "OK"}
        except Exception as exc:
            status, msg = classify_gemini_error(exc)
            return None, {"status": status, "message": msg}

    def _sanitize_evidence_payload(
        self,
        finding: WasteFinding,
        cost: Optional[CostFinding] = None,
    ) -> Dict[str, Any]:
        """
        Builds the minimal necessary FinOps evidence dictionary.
        Strictly guarantees that no credentials, tokens, or secrets are included.
        """
        payload = {
            "resource_id": finding.resource_id,
            "resource_name": finding.resource_name,
            "resource_type": (
                finding.resource_type.value
                if hasattr(finding.resource_type, "value")
                else str(finding.resource_type)
            ),
            "region": self.region,
            "waste_category": (
                finding.waste_category.value
                if hasattr(finding.waste_category, "value")
                else str(finding.waste_category)
            ),
            "severity": (
                finding.severity.value
                if hasattr(finding.severity, "value")
                else str(finding.severity)
            ),
            "description": finding.description,
            "current_specs": finding.current_specs,
            "recommended_specs": finding.recommended_specs,
            "telemetry_evidence": finding.metrics_summary,
            "cost_details": {
                "monthly_savings": cost.monthly_savings if cost else 0.0,
                "current_monthly_cost": cost.current_monthly_cost if cost else 0.0,
                "optimized_monthly_cost": cost.optimized_monthly_cost if cost else 0.0,
                "pricing_breakdown": cost.pricing_breakdown if cost else "",
            },
        }
        return payload

    def analyze_finding(
        self,
        finding: WasteFinding,
        cost: Optional[CostFinding] = None,
        client: Optional[genai.Client] = None,
    ) -> Tuple[Optional[AIRecommendation], Dict[str, Any]]:
        """
        Invokes Google Gemini for a single waste finding using structured output.
        Returns:
            (AIRecommendation, status_info)
        """
        cli = client
        if cli is None:
            cli, status_info = self.get_client()
            if not cli:
                return None, {
                    "status": status_info["status"],
                    "model_used": self.model_id,
                    "assumptions": [],
                    "proposed_action": None,
                    "message": status_info["message"],
                }

        evidence = self._sanitize_evidence_payload(finding, cost)

        prompt_instructions = (
            f"EVIDENCE PAYLOAD:\n{json.dumps(evidence, indent=2)}\n\n"
            "Produce an actionable optimization recommendation for human engineer review.\n"
            "Synthesize concrete, valid Terraform HCL remediation in `terraform_hcl`.\n"
            "For action_type, specify DELETE, RESIZE, DISASSOCIATE, or REMOVE.\n"
            "For terraform_hcl, generate clean Terraform HCL representing the remediation for this exact discovered resource.\n"
            "For terraform_explanation, provide a concise technical explanation of the HCL patch.\n"
            "Ground all identifiers, regions, availability zones, and specs strictly in the provided evidence. Do NOT invent IDs or regions.\n"
            "Respond ONLY with a JSON object adhering exactly to the specified schema."
        )

        try:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GeminiStructuredOutput,
                system_instruction=FINOPS_SAFETY_INSTRUCTION,
                temperature=0.2,
            )

            # Retry up to 4 times on transient 503 high demand or 429 rate limit spikes
            last_exc = None
            resp = None
            for attempt in range(1, 5):
                try:
                    resp = cli.models.generate_content(
                        model=self.model_id,
                        contents=prompt_instructions,
                        config=config,
                    )
                    break
                except Exception as exc:
                    last_exc = exc
                    status, msg = classify_gemini_error(exc)
                    if status == STATUS_RATE_LIMITED and attempt < 4:
                        import time
                        logger.warning(f"Gemini attempt {attempt} high demand spike; retrying in {attempt * 2}s...")
                        time.sleep(attempt * 2)
                        continue
                    raise exc

            if resp is None and last_exc:
                raise last_exc

            raw_text = resp.text or ""
            cleaned_text = raw_text.strip()
            if "```" in cleaned_text:
                json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned_text)
                if json_match:
                    cleaned_text = json_match.group(1).strip()

            parsed_dict = json.loads(cleaned_text)
            validated = GeminiStructuredOutput.model_validate(parsed_dict)

            rec_savings = (
                validated.estimated_savings
                if validated.estimated_savings is not None
                else (cost.monthly_savings if cost else None)
            )

            rec_action = (
                validated.action_type
                or validated.proposed_action
                or (
                    "DELETE" if getattr(finding, "waste_category", None) == WasteCategory.UNATTACHED_STORAGE
                    else "RESIZE" if getattr(finding, "waste_category", None) == WasteCategory.OVERSIZED_COMPUTE
                    else "DISASSOCIATE" if getattr(finding, "waste_category", None) == WasteCategory.IDLE_NETWORKING
                    else "DELETE"
                )
            )

            recommendation = AIRecommendation(
                finding_id=finding.id,
                resource_id=finding.resource_id,
                resource_name=finding.resource_name,
                title=validated.title,
                executive_summary=validated.executive_summary,
                risk_level=validated.risk_level,
                rationale=validated.rationale,
                steps_to_remediate=validated.steps_to_remediate,
                rollback_plan=validated.rollback_plan,
                confidence_score=validated.confidence_score,
                estimated_monthly_savings=rec_savings,
                proposed_action=validated.proposed_action,
                action_type=rec_action,
                terraform_hcl=validated.terraform_hcl,
                terraform_explanation=validated.terraform_explanation,
                model_used=f"{self.model_id} (Google Gemini)",
            )

            status_info = {
                "status": STATUS_CONNECTED,
                "model_used": self.model_id,
                "assumptions": validated.assumptions,
                "proposed_action": validated.proposed_action,
                "message": "Gemini analysis completed successfully.",
            }
            return recommendation, status_info

        except Exception as exc:
            status, msg = classify_gemini_error(exc)
            logger.warning(f"Gemini invocation failed for {finding.resource_name}: {msg}")
            return None, {
                "status": status,
                "model_used": self.model_id,
                "assumptions": [],
                "proposed_action": None,
                "message": msg,
            }

    def generate_all_recommendations(
        self,
        findings: List[WasteFinding],
        costs: Optional[List[CostFinding]] = None,
        region_name: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Coordinates batch Gemini analysis for all waste findings.
        Returns recommendations if successful, or explicit status errors (no fake output).
        """
        if region_name:
            self.region = get_configured_region(region_name)
            self.conn_service = AWSConnectionService(self.region)
        if model_id:
            self.model_id = model_id

        now_iso = datetime.now(timezone.utc).isoformat()

        # Step 1: Verify AWS authentication context
        session = get_aws_session(self.region)
        caller_identity = self.conn_service.get_caller_identity(session)
        if not caller_identity["authenticated"]:
            err_status = caller_identity["status"]
            err_msg = caller_identity["message"]
            return {
                "account_id": None,
                "arn": None,
                "region": self.region,
                "model_used": self.model_id,
                "timestamp": now_iso,
                "is_real_aws": True,
                "status": err_status,
                "recommendations": [],
                "errors": [err_msg],
                "assumptions": [],
                "summary": f"Gemini advisor aborted: {err_msg}",
            }

        # Step 2: Initialize Gemini client
        client, client_status = self.get_client()
        if not client:
            err_status = client_status["status"]
            err_msg = client_status["message"]
            return {
                "account_id": caller_identity["account_id"],
                "arn": caller_identity["arn"],
                "region": self.region,
                "model_used": self.model_id,
                "timestamp": now_iso,
                "is_real_aws": True,
                "status": err_status,
                "recommendations": [],
                "errors": [err_msg],
                "assumptions": [],
                "summary": f"Gemini advisor aborted: {err_msg}",
            }

        cost_map = {c.finding_id: c for c in (costs or [])}
        recs: List[Dict[str, Any]] = []
        errors_list: List[str] = []
        all_assumptions: List[str] = []
        final_status = STATUS_CONNECTED

        for finding in findings:
            cost = cost_map.get(finding.id)
            rec, status_info = self.analyze_finding(finding, cost, client=client)

            if rec:
                recs.append(rec.model_dump())
                if status_info.get("assumptions"):
                    all_assumptions.extend(status_info["assumptions"])
            else:
                final_status = status_info["status"]
                err = f"[{finding.resource_name}] {status_info['message']}"
                errors_list.append(err)

        if not recs and errors_list:
            summary_msg = f"Gemini analysis failed: {errors_list[0]}"
        else:
            summary_msg = f"Generated {len(recs)} recommendation(s) using {self.model_id} for AWS in {self.region}."

        return {
            "account_id": caller_identity["account_id"],
            "arn": caller_identity["arn"],
            "region": self.region,
            "model_used": self.model_id,
            "timestamp": now_iso,
            "is_real_aws": True,
            "status": final_status if not recs else STATUS_CONNECTED,
            "recommendations": recs,
            "errors": errors_list,
            "assumptions": list(set(all_assumptions)),
            "summary": summary_msg,
        }
