"""
FinOps Cloud Waste Hunter AWS Service Layer
"""

from core.aws.connection import (
    AWSConnectionService,
    get_aws_session,
    has_aws_credentials,
    get_configured_region,
    DEFAULT_AWS_REGION,
    STATUS_CONNECTED,
    STATUS_NO_PERMISSION,
    STATUS_ACCOUNT_VERIFICATION_REQUIRED,
    STATUS_NOT_AVAILABLE,
    STATUS_CREDENTIALS_MISSING,
    STATUS_ERROR,
)

from core.aws.discovery import (
    AWSDiscoveryService,
    AWSDiscoveryError
)

from core.aws.metrics import AWSMetricsService
from core.aws.costs import AWSCostService
def __getattr__(name: str):
    if name in ("GeminiAdvisorService", "AWSBedrockAdvisorService"):
        from core.gemini_advisor import GeminiAdvisorService
        return GeminiAdvisorService
    if name == "STATUS_MODEL_NOT_AVAILABLE":
        from core.gemini_advisor import STATUS_MODEL_NOT_AVAILABLE
        return STATUS_MODEL_NOT_AVAILABLE
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "AWSConnectionService",
    "AWSDiscoveryService",
    "AWSDiscoveryError",
    "AWSMetricsService",
    "AWSCostService",
    "AWSBedrockAdvisorService",
    "get_aws_session",
    "has_aws_credentials",
    "get_configured_region",
    "DEFAULT_AWS_REGION",
    "STATUS_CONNECTED",
    "STATUS_NO_PERMISSION",
    "STATUS_ACCOUNT_VERIFICATION_REQUIRED",
    "STATUS_NOT_AVAILABLE",
    "STATUS_MODEL_NOT_AVAILABLE",
    "STATUS_CREDENTIALS_MISSING",
    "STATUS_ERROR",
]
