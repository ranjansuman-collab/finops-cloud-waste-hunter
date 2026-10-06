"""
core/terraform/models.py
Pydantic data models for the real Terraform execution layer.

ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class TerraformCommandResult(BaseModel):
    command: List[str]
    success: bool
    return_code: int
    stdout: str
    stderr: str
    status: str  # SUCCESS, TERRAFORM_NOT_INSTALLED, EXECUTION_ERROR, TIMEOUT, FMT_FAILED, VALIDATION_FAILED
    duration_seconds: float = 0.0


class TerraformFmtResult(BaseModel):
    success: bool
    return_code: int
    stdout: str
    stderr: str
    status: str  # SUCCESS, FMT_FAILED, TERRAFORM_NOT_INSTALLED


class TerraformValidateResult(BaseModel):
    valid: bool
    return_code: int
    stdout: str
    stderr: str
    status: str  # SUCCESS, VALIDATION_FAILED, TERRAFORM_NOT_INSTALLED
    error_count: int = 0


class TerraformPlanResult(BaseModel):
    plan_id: str
    success: bool
    return_code: int
    stdout: str
    stderr: str
    status: str  # SUCCESS, PLAN_FAILED, TERRAFORM_NOT_INSTALLED, UNSUPPORTED_ACTION, FMT_FAILED, VALIDATION_FAILED
    config_hash: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    affected_resources: List[str] = Field(default_factory=list)
    proposed_actions: List[str] = Field(default_factory=list)
    estimated_savings: float = 0.0
    is_destructive: bool = False
    requires_approval: bool = True
    unified_diff: str = ""
    plan_file: Optional[str] = None
    errors: List[str] = Field(default_factory=list)


class TerraformApprovalRequest(BaseModel):
    plan_id: str
    approved: bool
    confirm_destructive: bool = False
    reviewer: str = "FinOps Reviewer"


class AWSVerificationResult(BaseModel):
    resource_id: str
    resource_type: str
    verified: bool
    status: str  # VERIFIED, RESOURCE_NOT_FOUND, STATUS_MISMATCH, CREDENTIALS_MISSING, NOT_ATTEMPTED, SIMULATED, ERROR
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class TerraformApplyResult(BaseModel):
    plan_id: str
    success: bool
    return_code: int
    stdout: str
    stderr: str
    status: str  # SUCCESS, APPLY_FAILED, APPROVAL_REQUIRED, PLAN_NOT_FOUND, PLAN_STALE, CONFIG_TAMPERED, DESTRUCTIVE_CONFIRMATION_REQUIRED, TERRAFORM_NOT_INSTALLED
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    affected_resources: List[str] = Field(default_factory=list)
    proposed_actions: List[str] = Field(default_factory=list)
    verification: Optional[AWSVerificationResult] = None
    errors: List[str] = Field(default_factory=list)
