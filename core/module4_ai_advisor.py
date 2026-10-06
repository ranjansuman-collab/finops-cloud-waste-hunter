"""
Module 4: AI Recommendation Engine
Delegates to AWSBedrockAdvisorService in LIVE AWS mode for real Bedrock analysis.
Falls back to built-in intelligent FinOps reasoning only in SIMULATION mode.

ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)

SAFETY:
- Bedrock is analysis/recommendation ONLY.
- Bedrock NEVER modifies AWS resources.
- Bedrock NEVER executes Terraform or terraform apply.
- No AWS credentials or secrets are sent to Bedrock.
"""

import logging
from typing import List, Optional

from core.models import (
    WasteFinding,
    CostFinding,
    AIRecommendation,
    WasteCategory,
)
from core.aws.connection import (
    STATUS_CONNECTED,
    STATUS_CREDENTIALS_MISSING,
    STATUS_NO_PERMISSION,
    STATUS_ACCOUNT_VERIFICATION_REQUIRED,
    STATUS_ERROR,
)
from core.aws.bedrock import STATUS_MODEL_NOT_AVAILABLE

logger = logging.getLogger("finops.module4")


class AIAdvisorModule:
    """
    Implements FR5 & FR6.

    LIVE mode  — delegates to AWSBedrockAdvisorService which calls Amazon Bedrock
                 over the standard Boto3 credential chain.  If Bedrock is
                 unavailable, an explicit error status is surfaced; fake output
                 is NEVER returned in live mode.

    SIMULATION — uses the built-in intelligent FinOps reasoning engine that
                 produces realistic static recommendations without any real AWS
                 calls or Bedrock invocations.
    """

    # Default model exposed for informational purposes; actual value is read at
    # runtime from FINOPS_BEDROCK_MODEL / BEDROCK_MODEL_ID env vars inside
    # AWSBedrockAdvisorService.
    DEFAULT_MODEL_ID = "amazon.nova-lite-v1:0"

    def __init__(self, region_name: str = "ap-southeast-2", use_live_aws: bool = False):
        self.region_name = region_name
        self.use_live_aws = use_live_aws

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_recommendations(
        self,
        findings: List[WasteFinding],
        costs: Optional[List[CostFinding]] = None,
        model_id: Optional[str] = None,
    ) -> List[AIRecommendation]:
        """
        Generates recommendations for every waste finding.

        In LIVE mode the entire batch is delegated to AWSBedrockAdvisorService.
        The service enforces the standard Boto3 credential chain and the FinOps
        safety prompt, and returns explicit status errors when Bedrock cannot be
        reached.

        In SIMULATION mode local intelligent reasoning is used; Bedrock is
        never contacted.
        """
        if not findings:
            return []

        if self.use_live_aws:
            return self._generate_via_bedrock(findings, costs, model_id=model_id)

        # Simulation / demo mode: safe local reasoning
        cost_map = {c.finding_id: c for c in (costs or [])}
        return [
            self._generate_intelligent_recommendation(f, cost_map.get(f.id))
            for f in findings
        ]

    # ------------------------------------------------------------------
    # Live Bedrock path
    # ------------------------------------------------------------------

    def _generate_via_bedrock(
        self,
        findings: List[WasteFinding],
        costs: Optional[List[CostFinding]],
        model_id: Optional[str] = None,
    ) -> List[AIRecommendation]:
        """
        Calls AWSBedrockAdvisorService to get real recommendations.
        If Bedrock cannot be reached, raises RuntimeError with the status code
        so the caller (engine or endpoint) can surface an explicit error rather
        than silently returning fake output.
        """
        from core.aws.bedrock import AWSBedrockAdvisorService

        svc = AWSBedrockAdvisorService(
            region_name=self.region_name,
            model_id=model_id,
        )
        result = svc.generate_all_recommendations(
            findings=findings,
            costs=costs,
            region_name=self.region_name,
            model_id=model_id,
        )

        status = result.get("status", STATUS_ERROR)

        # Any status other than CONNECTED with at least one recommendation is an error.
        if status != STATUS_CONNECTED or not result.get("recommendations"):
            if result.get("recommendations"):
                # Partial success: some findings got recommendations, some failed.
                # Convert successfully returned dicts back to AIRecommendation objects.
                return [AIRecommendation(**r) for r in result["recommendations"]]
            # Total failure — raise so the caller can communicate the real status.
            errors = result.get("errors") or []
            raise RuntimeError(
                f"BEDROCK_ERROR:{status}:{'; '.join(errors) if errors else 'Bedrock unavailable'}"
            )

        return [AIRecommendation(**r) for r in result["recommendations"]]

    # ------------------------------------------------------------------
    # Simulation / demo mode — local intelligent FinOps reasoning
    # ------------------------------------------------------------------

    def _generate_intelligent_recommendation(
        self,
        finding: WasteFinding,
        cost: Optional[CostFinding] = None,
    ) -> AIRecommendation:
        savings_text = f"${cost.monthly_savings:.2f}/mo" if cost else "substantial cost"
        annual_text = f"${cost.annualized_savings:.2f}/yr" if cost else ""

        if finding.waste_category == WasteCategory.OVERSIZED_COMPUTE:
            target_type = finding.metrics_summary.get("recommended_instance_type", "t3.medium")
            return AIRecommendation(
                finding_id=finding.id,
                resource_id=finding.resource_id,
                resource_name=finding.resource_name,
                title=f"Downsize Compute Instance '{finding.resource_name}' to {target_type}",
                executive_summary=(
                    f"Nova Lite identified that '{finding.resource_name}' is operating at only "
                    f"{finding.metrics_summary.get('cpu_utilization_avg', 0)}% average CPU. Downsizing will "
                    f"recover {savings_text} ({annual_text}) with zero application latency penalty."
                ),
                risk_level="Low Risk",
                rationale=(
                    f"The 30-day CloudWatch evaluation confirms peak load did not exceed "
                    f"{finding.metrics_summary.get('cpu_utilization_max', 0)}% CPU. Current instance capacity "
                    f"is over-provisioned by 400%. The {target_type} family offers bursting compute credits and "
                    f"sufficient baseline memory."
                ),
                steps_to_remediate=[
                    f"Update Terraform configuration: set `instance_type = \"{target_type}\"`.",
                    "Verify target AMI compatibility with nitro/t3 generation hypervisor.",
                    "Submit GitOps Pull Request for automated approval and peer review.",
                    "Apply change during standard maintenance window with minimal rolling reboot."
                ],
                rollback_plan=(
                    f"If CPU exceeds 80% post-downsize, trigger GitOps rollback PR to restore original "
                    f"instance type via `terraform apply` within 3 minutes."
                ),
                confidence_score=0.98,
                model_used=self.DEFAULT_MODEL_ID
            )

        elif finding.waste_category == WasteCategory.UNATTACHED_STORAGE:
            size_gb = finding.metrics_summary.get("size_gb", 100)
            days = finding.metrics_summary.get("days_unattached", 14)
            return AIRecommendation(
                finding_id=finding.id,
                resource_id=finding.resource_id,
                resource_name=finding.resource_name,
                title=f"Archive & Purge Abandoned EBS Volume '{finding.resource_name}'",
                executive_summary=(
                    f"Nova Lite verified that this {size_gb}GB EBS volume has been detached for {days} days. "
                    f"Terminating it saves {savings_text} recurring spend immediately."
                ),
                risk_level="Low Risk",
                rationale=(
                    f"Orphaned EBS volumes continue to bill for provisioned GB and IOPS even when unattached. "
                    f"Zero I/O operations have been observed over the last {days} days. A safety snapshot "
                    f"guarantees 100% data recovery capability while cutting costs."
                ),
                steps_to_remediate=[
                    "Create automated pre-deletion AWS EBS Snapshot for disaster recovery.",
                    "Tag snapshot with retention policy `DeleteAfter=90Days`.",
                    "Remove `aws_ebs_volume` declaration from Terraform infrastructure code.",
                    "Submit GitOps pull request for automated peer approval."
                ],
                rollback_plan=(
                    "In the unlikely event data is requested, restore the created snapshot into a new EBS volume "
                    "via `aws ec2 create-volume --snapshot-id <snap_id>`."
                ),
                confidence_score=0.99,
                model_used=self.DEFAULT_MODEL_ID
            )

        elif finding.waste_category == WasteCategory.IDLE_SERVERLESS:
            prov = finding.metrics_summary.get("provisioned_concurrency", 0)
            return AIRecommendation(
                finding_id=finding.id,
                resource_id=finding.resource_id,
                resource_name=finding.resource_name,
                title=f"Deprecate Dormant Lambda Function '{finding.resource_name}'",
                executive_summary=(
                    f"Function has received 0 invocations in 30+ days. "
                    f"Eliminating idle provisioned concurrency and archiving yields {savings_text} in savings."
                ),
                risk_level="Low Risk",
                rationale=(
                    f"Serverless components should scale to zero. Maintaining provisioned concurrency ({prov} units) "
                    f"on a dormant function directly violates serverless cost efficiency."
                ),
                steps_to_remediate=[
                    "Remove `aws_lambda_provisioned_concurrency_config` from Terraform.",
                    "Export function deployment package to S3 cold archive.",
                    "Delete function resource through controlled GitOps pull request."
                ],
                rollback_plan="Redeploy function from S3 zipped archive using existing CI/CD deployment pipeline.",
                confidence_score=0.97,
                model_used=self.DEFAULT_MODEL_ID
            )

        elif finding.waste_category == WasteCategory.IDLE_NETWORKING:
            return AIRecommendation(
                finding_id=finding.id,
                resource_id=finding.resource_id,
                resource_name=finding.resource_name,
                title=f"Release Unused Networking Asset '{finding.resource_name}'",
                executive_summary=(
                    f"Nova Lite identified idle networking component incurring reservation fees without active traffic. "
                    f"Releasing reclaims {savings_text}."
                ),
                risk_level="Low Risk",
                rationale=(
                    "AWS penalizes unassociated IPv4 allocations to encourage public address recycling. "
                    "Releasing the asset produces immediate ongoing financial reduction."
                ),
                steps_to_remediate=[
                    "Check DNS records (Route 53) to verify no domain points to the allocated IP.",
                    "Remove resource block from Terraform code.",
                    "Submit PR to execute clean release."
                ],
                rollback_plan="Allocate new Elastic IP if required and update DNS records via automation.",
                confidence_score=0.99,
                model_used=self.DEFAULT_MODEL_ID
            )

        return AIRecommendation(
            finding_id=finding.id,
            resource_id=finding.resource_id,
            resource_name=finding.resource_name,
            title=f"Optimize Resource '{finding.resource_name}'",
            executive_summary=finding.description,
            risk_level="Medium Risk",
            rationale="Cloud cost optimization through automated remediation.",
            steps_to_remediate=["Review resource in console", "Apply Terraform adjustment"],
            rollback_plan="Revert Terraform commit.",
            confidence_score=0.90,
            model_used=self.DEFAULT_MODEL_ID
        )
