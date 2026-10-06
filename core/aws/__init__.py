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
from core.aws.bedrock import AWSBedrockAdvisorService, STATUS_MODEL_NOT_AVAILABLE

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
