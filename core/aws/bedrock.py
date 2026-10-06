"""
FinOps Cloud Waste Hunter & Auto-Remediator
Real Amazon Bedrock AI Advisor Service
Analyzes real waste findings and CloudWatch telemetry using Bedrock models.
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

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from core.models import WasteFinding, CostFinding, AIRecommendation
from core.aws.connection import (
    AWSConnectionService,
    get_aws_session,
    get_configured_region,
    classify_aws_error,
    STATUS_CONNECTED,
    STATUS_CREDENTIALS_MISSING,
    STATUS_NO_PERMISSION,
    STATUS_ACCOUNT_VERIFICATION_REQUIRED,
    STATUS_NOT_AVAILABLE,
    STATUS_ERROR
)

logger = logging.getLogger("finops.aws.bedrock")

# Bedrock-specific status — returned when the configured model is unavailable in this region/account.
# Distinct from STATUS_NOT_AVAILABLE which covers general service/region unavailability.
STATUS_MODEL_NOT_AVAILABLE = "MODEL_NOT_AVAILABLE"

DEFAULT_BEDROCK_MODEL_ID = "amazon.nova-lite-v1:0"

FINOPS_SAFETY_INSTRUCTION = (
    "You are a FinOps recommendation engine. "
    "You may recommend infrastructure changes. "
    "You must not execute changes. "
    "Do not claim that an action was performed. "
    "Do not invent AWS metrics or costs. "
    "Use only the supplied evidence. "
    "If evidence is insufficient, say so. "
    "Return only valid JSON matching the specified schema."
)


class BedrockStructuredOutput(BaseModel):
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


class AWSBedrockAdvisorService:
    """
    Direct interface to Amazon Bedrock for generative FinOps optimization analysis.
    Validates model output using Pydantic schemas and reports exact service limitations.
    """

    def __init__(self, region_name: Optional[str] = None, model_id: Optional[str] = None):
        self.region = get_configured_region(region_name)
        self.model_id = model_id or os.getenv("FINOPS_BEDROCK_MODEL") or os.getenv("BEDROCK_MODEL_ID") or DEFAULT_BEDROCK_MODEL_ID
        self.conn_service = AWSConnectionService(self.region)

    def _sanitize_evidence_payload(
        self,
        finding: WasteFinding,
        cost: Optional[CostFinding] = None
    ) -> Dict[str, Any]:
        """
        Builds the minimal necessary FinOps evidence dictionary.
        Strictly guarantees that no credentials, tokens, or secrets are included.
        """
        payload = {
            "resource_id": finding.resource_id,
            "resource_name": finding.resource_name,
            "resource_type": finding.resource_type.value if hasattr(finding.resource_type, "value") else str(finding.resource_type),
            "region": self.region,
            "waste_category": finding.waste_category.value if hasattr(finding.waste_category, "value") else str(finding.waste_category),
            "severity": finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity),
            "description": finding.description,
            "current_specs": finding.current_specs,
            "recommended_specs": finding.recommended_specs,
            "telemetry_evidence": finding.metrics_summary,
            "cost_details": {
                "monthly_savings": cost.monthly_savings if cost else 0.0,
                "current_monthly_cost": cost.current_monthly_cost if cost else 0.0,
                "optimized_monthly_cost": cost.optimized_monthly_cost if cost else 0.0,
                "pricing_breakdown": cost.pricing_breakdown if cost else ""
            }
        }
        return payload

    def analyze_finding(
        self,
        finding: WasteFinding,
        cost: Optional[CostFinding] = None,
        session: Optional[boto3.Session] = None
    ) -> Tuple[Optional[AIRecommendation], Dict[str, Any]]:
        """
        Invokes Amazon Bedrock for a single waste finding.
        Returns:
            (AIRecommendation, status_info)
        """
        sess = session or get_aws_session(self.region)
        evidence = self._sanitize_evidence_payload(finding, cost)

        prompt_instructions = (
            f"{FINOPS_SAFETY_INSTRUCTION}\n\n"
            f"EVIDENCE PAYLOAD:\n{json.dumps(evidence, indent=2)}\n\n"
            "Produce an actionable optimization recommendation for human engineer review.\n"
            "Respond ONLY with a JSON object adhering exactly to this structure:\n"
            "{\n"
            '  "title": "<Concise Action Title>",\n'
            '  "executive_summary": "<Executive Summary>",\n'
            '  "risk_level": "Low Risk" | "Medium Risk" | "High Risk",\n'
            '  "rationale": "<Grounded Technical Rationale>",\n'
            '  "steps_to_remediate": ["<Step 1>", "<Step 2>"],\n'
            '  "rollback_plan": "<Rollback Procedure>",\n'
            '  "confidence_score": 0.95,\n'
            '  "estimated_savings": 0.0,\n'
            '  "proposed_action": "<RESIZE|DELETE|ARCHIVE|RELEASE>",\n'
            '  "assumptions": ["<Assumption 1>"]\n'
            "}"
        )

        try:
            bedrock_runtime = sess.client("bedrock-runtime", region_name=self.region)

            # Use converse API (standard across all modern foundation models in Bedrock)
            try:
                resp = bedrock_runtime.converse(
                    modelId=self.model_id,
                    system=[{"text": FINOPS_SAFETY_INSTRUCTION}],
                    messages=[{"role": "user", "content": [{"text": prompt_instructions}]}],
                    inferenceConfig={"maxTokens": 1000, "temperature": 0.2}
                )
                raw_text = resp.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "")
            except (AttributeError, ClientError) as conv_err:
                # If converse is not supported by legacy client, fallback to invoke_model
                if isinstance(conv_err, ClientError):
                    code = conv_err.response.get("Error", {}).get("Code", "")
                    if code not in ("UnknownServiceError", "ValidationException"):
                        raise conv_err

                body = json.dumps({
                    "system": [{"text": FINOPS_SAFETY_INSTRUCTION}],
                    "messages": [{"role": "user", "content": [{"text": prompt_instructions}]}],
                    "inferenceConfig": {"max_new_tokens": 1000, "temperature": 0.2}
                })
                resp = bedrock_runtime.invoke_model(
                    modelId=self.model_id,
                    body=body,
                    contentType="application/json",
                    accept="application/json"
                )
                response_body = json.loads(resp.get("body").read().decode("utf-8"))
                # Extract text based on Nova or Claude format
                if "output" in response_body:
                    raw_text = response_body["output"].get("message", {}).get("content", [{}])[0].get("text", "")
                elif "results" in response_body:
                    raw_text = response_body["results"][0].get("outputText", "")
                elif "content" in response_body:
                    raw_text = response_body["content"][0].get("text", "")
                else:
                    raw_text = str(response_body)

            # Strip markdown fences if present
            cleaned_text = raw_text.strip()
            if "```" in cleaned_text:
                json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned_text)
                if json_match:
                    cleaned_text = json_match.group(1).strip()

            parsed_dict = json.loads(cleaned_text)
            validated = BedrockStructuredOutput.model_validate(parsed_dict)

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
                model_used=f"{self.model_id} (Real Amazon Bedrock)"
            )

            status_info = {
                "status": STATUS_CONNECTED,
                "model_used": self.model_id,
                "assumptions": validated.assumptions,
                "proposed_action": validated.proposed_action,
                "message": "Bedrock analysis completed successfully."
            }
            return recommendation, status_info

        except Exception as exc:
            # Intercept Bedrock model-specific errors before generic classification,
            # so callers receive the explicit MODEL_NOT_AVAILABLE status.
            if isinstance(exc, ClientError):
                code = exc.response.get("Error", {}).get("Code", "")
                if code in (
                    "ModelNotFoundException",
                    "ModelNotReadyException",
                    "ModelTimeoutException",
                    "ModelErrorException",
                    "ModelStreamErrorException",
                    "ModelNotSubscribedException",
                ):
                    msg = exc.response.get("Error", {}).get("Message", str(exc))
                    logger.warning(f"Bedrock model unavailable for {finding.resource_name}: [{code}] {msg}")
                    return None, {
                        "status": STATUS_MODEL_NOT_AVAILABLE,
                        "model_used": self.model_id,
                        "assumptions": [],
                        "proposed_action": None,
                        "message": f"[{code}] {msg}",
                    }
            # JSON parse / Pydantic validation failures are ERROR, not a model error
            if isinstance(exc, (json.JSONDecodeError, ValidationError)):
                msg = f"Invalid Bedrock model output: {exc}"
                logger.warning(f"Bedrock output validation failed for {finding.resource_name}: {msg}")
                return None, {
                    "status": STATUS_ERROR,
                    "model_used": self.model_id,
                    "assumptions": [],
                    "proposed_action": None,
                    "message": msg,
                }
            st, msg = classify_aws_error(exc)
            logger.warning(f"Bedrock invocation failed for {finding.resource_name}: {msg}")
            status_info = {
                "status": st,
                "model_used": self.model_id,
                "assumptions": [],
                "proposed_action": None,
                "message": msg
            }
            return None, status_info

    def generate_all_recommendations(
        self,
        findings: List[WasteFinding],
        costs: Optional[List[CostFinding]] = None,
        region_name: Optional[str] = None,
        model_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Coordinates batch Bedrock analysis for all findings.
        Returns recommendations if successful, or explicit AWS status errors (no fake output).
        """
        if region_name:
            self.region = get_configured_region(region_name)
            self.conn_service = AWSConnectionService(self.region)
        if model_id:
            self.model_id = model_id

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
                "model_used": self.model_id,
                "timestamp": now_iso,
                "is_real_aws": True,
                "status": err_status,
                "recommendations": [],
                "errors": [err_msg],
                "assumptions": [],
                "summary": f"Bedrock advisor aborted: {err_msg}"
            }

        cost_map = {c.finding_id: c for c in (costs or [])}
        recs: List[Dict[str, Any]] = []
        errors: List[str] = []
        all_assumptions: List[str] = []
        final_status = STATUS_CONNECTED

        for finding in findings:
            cost = cost_map.get(finding.id)
            rec, status_info = self.analyze_finding(finding, cost, session=session)

            if rec:
                recs.append(rec.model_dump())
                if status_info.get("assumptions"):
                    all_assumptions.extend(status_info["assumptions"])
            else:
                final_status = status_info["status"]
                err = f"[{finding.resource_name}] {status_info['message']}"
                errors.append(err)

        if not recs and errors:
            summary_msg = f"Bedrock analysis failed: {errors[0]}"
        else:
            summary_msg = f"Generated {len(recs)} recommendation(s) using {self.model_id} in {self.region}."

        return {
            "account_id": caller_identity["account_id"],
            "arn": caller_identity["arn"],
            "region": self.region,
            "model_used": self.model_id,
            "timestamp": now_iso,
            "is_real_aws": True,
            "status": final_status if not recs else STATUS_CONNECTED,
            "recommendations": recs,
            "errors": errors,
            "assumptions": list(set(all_assumptions)),
            "summary": summary_msg
        }
