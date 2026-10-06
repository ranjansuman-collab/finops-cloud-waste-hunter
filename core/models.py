"""
FinOps Cloud Waste Hunter & Auto-Remediator
Data Models for Cloud Resources, Telemetry, Waste Detection, Cost, AI, IaC, and GitOps.
ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class ResourceType(str, Enum):
    EC2 = "EC2"
    EBS = "EBS"
    LAMBDA = "LAMBDA"
    RDS = "RDS"
    EIP = "EIP"
    NAT_GATEWAY = "NAT_GATEWAY"
    S3 = "S3"


class WasteCategory(str, Enum):
    UNATTACHED_STORAGE = "UNATTACHED_STORAGE"
    IDLE_SERVERLESS = "IDLE_SERVERLESS"
    OVERSIZED_COMPUTE = "OVERSIZED_COMPUTE"
    IDLE_NETWORKING = "IDLE_NETWORKING"
    ORPHAN_SNAPSHOT = "ORPHAN_SNAPSHOT"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class CloudResource(BaseModel):
    id: str
    name: str
    resource_type: ResourceType
    region: str = "us-east-1"
    state: str  # running, stopped, available, in-use, active
    specs: Dict[str, Any] = Field(default_factory=dict)
    tags: Dict[str, str] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None


class WasteFinding(BaseModel):
    id: str
    resource_id: str
    resource_name: str
    resource_type: ResourceType
    waste_category: WasteCategory
    severity: Severity
    description: str
    current_specs: str
    recommended_specs: str
    confidence_score: float = 0.95
    metrics_summary: Dict[str, Any] = Field(default_factory=dict)


class CostFinding(BaseModel):
    finding_id: str
    resource_id: str
    resource_name: str
    resource_type: ResourceType
    current_monthly_cost: float
    optimized_monthly_cost: float
    monthly_savings: float
    annualized_savings: float
    carbon_savings_kg_co2e: float
    pricing_breakdown: str


class AIRecommendation(BaseModel):
    finding_id: str
    resource_id: str
    resource_name: str
    title: str
    executive_summary: str
    risk_level: str  # Low Risk, Medium Risk, High Risk
    rationale: str
    steps_to_remediate: List[str]
    rollback_plan: str
    confidence_score: float
    model_used: str = "Amazon Bedrock Nova Lite (amazon.nova-lite-v1:0)"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TerraformPatch(BaseModel):
    patch_id: str
    resource_id: str
    resource_name: str
    target_file: str
    action_type: str  # RESIZE, DELETE, DISASSOCIATE, ADD_LIFECYCLE
    original_hcl: str
    patched_hcl: str
    unified_diff: str
    validation_status: str = "VALIDATED"


class GitOpsPR(BaseModel):
    pr_id: str
    pr_number: int
    branch_name: str
    base_branch: str = "main"
    title: str
    description: str
    author: str = "finops-bot[bot]"
    status: str = "OPEN"  # OPEN, APPROVED, MERGED, REJECTED
    files_changed: List[str] = Field(default_factory=list)
    total_monthly_savings: float
    total_annualized_savings: float
    checks: List[Dict[str, str]] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    merged_at: Optional[str] = None
    audit_trail: List[str] = Field(default_factory=list)


class PipelineReport(BaseModel):
    run_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    scenario: str
    monitored_resources: List[CloudResource]
    waste_findings: List[WasteFinding]
    cost_findings: List[CostFinding]
    total_current_monthly_cost: float
    total_optimized_monthly_cost: float
    total_monthly_savings: float
    total_annualized_savings: float
    total_carbon_savings_kg: float
    ai_recommendations: List[AIRecommendation]
    terraform_patches: List[TerraformPatch]
    gitops_pr: Optional[GitOpsPR] = None
    s3_uri: str = ""
    dynamodb_id: str = ""
