"""
core/terraform/__init__.py
Real Terraform Integration Service Layer for FinOps Cloud Waste Hunter.
"""

from core.terraform.models import (
    TerraformCommandResult,
    TerraformFmtResult,
    TerraformValidateResult,
    TerraformPlanResult,
    TerraformApplyResult,
    TerraformApprovalRequest,
    AWSVerificationResult,
)
from core.terraform.cli import (
    TerraformCLI,
    STATUS_SUCCESS,
    STATUS_TERRAFORM_NOT_INSTALLED,
    STATUS_EXECUTION_ERROR,
    STATUS_TIMEOUT,
    STATUS_FMT_FAILED,
    STATUS_VALIDATION_FAILED,
)
from core.terraform.generator import (
    TerraformChangeGenerator,
    STATUS_UNSUPPORTED_ACTION,
    STATUS_SECURITY_POLICY_VIOLATION,
    STATUS_RESOURCE_NOT_FOUND_IN_CONFIG,
)
from core.terraform.service import (
    RealTerraformService,
)

__all__ = [
    "RealTerraformService",
    "TerraformCLI",
    "TerraformChangeGenerator",
    "TerraformCommandResult",
    "TerraformFmtResult",
    "TerraformValidateResult",
    "TerraformPlanResult",
    "TerraformApplyResult",
    "TerraformApprovalRequest",
    "AWSVerificationResult",
    "STATUS_SUCCESS",
    "STATUS_TERRAFORM_NOT_INSTALLED",
    "STATUS_EXECUTION_ERROR",
    "STATUS_TIMEOUT",
    "STATUS_FMT_FAILED",
    "STATUS_VALIDATION_FAILED",
    "STATUS_UNSUPPORTED_ACTION",
    "STATUS_SECURITY_POLICY_VIOLATION",
    "STATUS_RESOURCE_NOT_FOUND_IN_CONFIG",
]
