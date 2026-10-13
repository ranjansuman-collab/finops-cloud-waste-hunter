"""
FinOps Cloud Waste Hunter & Auto-Remediator
AWS Connection & Authentication Service
Provides standard Boto3 credential chain resolution, STS verification,
and read-only service health checks for EC2, CloudWatch, S3, Cost Explorer, and Bedrock.

ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import os
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
import boto3
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    PartialCredentialsError,
    EndpointConnectionError,
    BotoCoreError
)

logger = logging.getLogger("finops.aws.connection")

DEFAULT_AWS_REGION = "ap-southeast-2"

# Status Enums
STATUS_CONNECTED = "CONNECTED"
STATUS_NO_PERMISSION = "NO_PERMISSION"
STATUS_ACCOUNT_VERIFICATION_REQUIRED = "ACCOUNT_VERIFICATION_REQUIRED"
STATUS_NOT_AVAILABLE = "NOT_AVAILABLE"
STATUS_CREDENTIALS_MISSING = "CREDENTIALS_MISSING"
STATUS_ERROR = "ERROR"


def get_configured_region(override_region: Optional[str] = None) -> str:
    """
    Resolves the AWS region with precedence:
    1. Explicit override passed as parameter
    2. FINOPS_AWS_REGION environment variable
    3. AWS_REGION environment variable
    4. AWS_DEFAULT_REGION environment variable
    5. Default region: ap-southeast-2
    """
    if override_region and override_region.strip():
        return override_region.strip()

    return (
        os.getenv("FINOPS_AWS_REGION")
        or os.getenv("AWS_REGION")
        or os.getenv("AWS_DEFAULT_REGION")
        or DEFAULT_AWS_REGION
    ).strip()


def setup_windows_ca_bundle() -> None:
    """
    On Windows systems where TLS certificates are managed in the Windows Certificate Store
    (e.g., enterprise proxies or system cert stores), botocore/requests may raise
    SSLCertVerificationError because they bundle Mozilla certs only.
    This helper safely combines certifi with Windows ROOT and CA stores and sets
    AWS_CA_BUNDLE and REQUESTS_CA_BUNDLE so all Boto3 and requests operations succeed.
    """
    if os.name != "nt":
        return
    if os.getenv("AWS_CA_BUNDLE") or os.getenv("SSL_CERT_FILE"):
        return
    try:
        import ssl
        import certifi
        import tempfile
        root_certs = ssl.enum_certificates("ROOT")
        ca_certs = ssl.enum_certificates("CA")
        if not root_certs and not ca_certs:
            return
        pems = []
        for c in (root_certs + ca_certs):
            try:
                pems.append(ssl.DER_cert_to_PEM_cert(c[0]))
            except Exception:
                pass
        if not pems:
            return

        bundle_path = os.path.join(tempfile.gettempdir(), "finops_windows_ca_bundle.pem")
        base_certifi = ""
        try:
            with open(certifi.where(), "r", encoding="utf-8") as f:
                base_certifi = f.read()
        except Exception:
            pass
        with open(bundle_path, "w", encoding="utf-8") as f:
            f.write(base_certifi + "\n" + "\n".join(pems))

        os.environ["AWS_CA_BUNDLE"] = bundle_path
        os.environ["REQUESTS_CA_BUNDLE"] = bundle_path
    except Exception as e:
        logger.debug(f"Unable to auto-configure Windows CA bundle: {e}")


def get_aws_session(
    region_name: Optional[str] = None,
    profile_name: Optional[str] = None
) -> boto3.Session:
    """
    Creates and returns a boto3.Session utilizing the standard AWS credential chain:
    - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN)
    - Shared credential file (~/.aws/credentials)
    - Config file (~/.aws/config)
    - AWS SSO / IAM Identity Center
    - Instance profile / ECS container credentials
    """
    setup_windows_ca_bundle()
    target_region = get_configured_region(region_name)
    target_profile = profile_name or os.getenv("AWS_PROFILE")

    if target_profile:
        return boto3.Session(profile_name=target_profile, region_name=target_region)
    return boto3.Session(region_name=target_region)


def has_aws_credentials(session: Optional[boto3.Session] = None) -> bool:
    """
    Checks if valid AWS credentials can be discovered via the standard credential chain.
    Does not make an API call, only checks local provider chain discovery.
    """
    try:
        sess = session or get_aws_session()
        creds = sess.get_credentials()
        return creds is not None and creds.access_key is not None
    except Exception as e:
        logger.debug(f"Failed resolving AWS credentials: {e}")
        return False


def classify_aws_error(exc: Exception) -> Tuple[str, str]:
    """
    Inspects Boto3/Botocore exceptions and maps them to standard status categories:
    - CREDENTIALS_MISSING
    - NO_PERMISSION
    - ACCOUNT_VERIFICATION_REQUIRED
    - NOT_AVAILABLE
    - ERROR
    """
    if isinstance(exc, (NoCredentialsError, PartialCredentialsError)):
        return STATUS_CREDENTIALS_MISSING, "No AWS credentials found in the environment, profile, or standard chain."

    if isinstance(exc, EndpointConnectionError):
        return STATUS_NOT_AVAILABLE, f"Service endpoint unreachable: {exc}"

    if isinstance(exc, ClientError):
        error_info = exc.response.get("Error", {})
        code = error_info.get("Code", "ClientError")
        message = error_info.get("Message", str(exc))
        lower_msg = message.lower()
        lower_code = code.lower()

        # Check for Account Verification / Subscription / Opt-in issues
        if (
            "accountverification" in lower_code
            or "accountunverified" in lower_code
            or "optinrequired" in lower_code
            or "account verification" in lower_msg
            or "verification required" in lower_msg
            or "phone verification" in lower_msg
            or "subscription required" in lower_msg
            or "opt-in required" in lower_msg
            or "not subscribed" in lower_msg
            or "operation not allowed" in lower_msg
        ):
            return STATUS_ACCOUNT_VERIFICATION_REQUIRED, f"[{code}] {message}"

        # Check for Authorization / Permission / IAM issues
        if code in (
            "AccessDenied",
            "AccessDeniedException",
            "UnauthorizedOperation",
            "AuthFailure",
            "ForbiddenException",
            "NotAuthorizedException"
        ) or "access denied" in lower_msg or "unauthorized" in lower_msg:
            return STATUS_NO_PERMISSION, f"[{code}] {message}"

        # Check for Invalid / Unrecognized Client Credentials
        if code in ("UnrecognizedClientException", "InvalidClientTokenId", "SignatureDoesNotMatch", "ExpiredToken"):
            return STATUS_NO_PERMISSION, f"[{code}] Invalid or expired credentials: {message}"

        # Check for Service Unavailability in Region
        if (
            code in ("UnknownServiceError", "ServiceUnavailable", "ResourceNotFoundException")
            or "not supported in this region" in lower_msg
            or "invalid region" in lower_msg
            or "service is not available in" in lower_msg
        ):
            return STATUS_NOT_AVAILABLE, f"[{code}] {message}"

        # Cost Explorer specific disabled state
        if code == "DataUnavailableException" or "cost explorer is not enabled" in lower_msg:
            return STATUS_NOT_AVAILABLE, f"[{code}] {message}"

        return STATUS_ERROR, f"[{code}] {message}"

    if isinstance(exc, BotoCoreError):
        return STATUS_ERROR, str(exc)

    return STATUS_ERROR, str(exc)


class AWSConnectionService:
    """
    Manages AWS connection validation, STS identity inspection,
    and granular read-only permission probing across required services.
    """

    def __init__(self, region_name: Optional[str] = None):
        self.region = get_configured_region(region_name)

    def get_caller_identity(self, session: Optional[boto3.Session] = None) -> Dict[str, Any]:
        """
        Executes sts:GetCallerIdentity to verify live authentication.
        Returns:
            dict with {
                'authenticated': bool,
                'status': str,
                'account_id': Optional[str],
                'arn': Optional[str],
                'user_id': Optional[str],
                'region': str,
                'message': str
            }
        """
        sess = session or get_aws_session(self.region)
        try:
            sts = sess.client("sts", region_name=self.region)
            identity = sts.get_caller_identity()
            return {
                "authenticated": True,
                "status": STATUS_CONNECTED,
                "account_id": identity.get("Account"),
                "arn": identity.get("Arn"),
                "user_id": identity.get("UserId"),
                "region": self.region,
                "message": "AWS authentication verified via STS."
            }
        except Exception as exc:
            status, msg = classify_aws_error(exc)
            return {
                "authenticated": False,
                "status": status,
                "account_id": None,
                "arn": None,
                "user_id": None,
                "region": self.region,
                "message": msg
            }

    def check_ec2_access(self, session: boto3.Session) -> Dict[str, str]:
        """Performs a harmless read-only check: describe_regions for current region."""
        try:
            ec2 = session.client("ec2", region_name=self.region)
            ec2.describe_regions(RegionNames=[self.region])
            return {"status": STATUS_CONNECTED, "message": f"Read access verified via describe_regions ({self.region})."}
        except Exception as exc:
            status, msg = classify_aws_error(exc)
            return {"status": status, "message": msg}

    def check_cloudwatch_access(self, session: boto3.Session) -> Dict[str, str]:
        """Performs a harmless read-only check: list_metrics with MaxRecords=1."""
        try:
            cw = session.client("cloudwatch", region_name=self.region)
            cw.list_metrics()
            return {"status": STATUS_CONNECTED, "message": f"Read access verified via list_metrics ({self.region})."}
        except Exception as exc:
            status, msg = classify_aws_error(exc)
            return {"status": status, "message": msg}

    def check_s3_access(self, session: boto3.Session) -> Dict[str, str]:
        """Performs a harmless read-only check: list_buckets."""
        try:
            s3 = session.client("s3", region_name=self.region)
            s3.list_buckets()
            return {"status": STATUS_CONNECTED, "message": "Read access verified via list_buckets."}
        except Exception as exc:
            status, msg = classify_aws_error(exc)
            return {"status": status, "message": msg}

    def check_cost_explorer_access(self, session: boto3.Session) -> Dict[str, str]:
        """
        Performs a harmless read-only check: get_dimension_values for SERVICE dimension.
        Note: AWS Cost Explorer endpoint is global (us-east-1).
        """
        try:
            ce = session.client("ce", region_name="us-east-1")
            today = datetime.now(timezone.utc).date()
            start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")
            if start_date >= end_date:
                start_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")

            ce.get_dimension_values(
                TimePeriod={"Start": start_date, "End": end_date},
                Dimension="SERVICE",
                Context="COST_AND_USAGE"
            )
            return {"status": STATUS_CONNECTED, "message": "Read access verified via Cost Explorer API."}
        except Exception as exc:
            status, msg = classify_aws_error(exc)
            return {"status": status, "message": msg}

    def check_bedrock_access(self, session: boto3.Session) -> Dict[str, str]:
        """
        Performs a harmless read-only check: list_foundation_models.
        Reports exact account verification or permission error without fake fallback.
        """
        try:
            bedrock = session.client("bedrock", region_name=self.region)
            bedrock.list_foundation_models()
            return {"status": STATUS_CONNECTED, "message": f"Read access verified via list_foundation_models ({self.region})."}
        except Exception as exc:
            status, msg = classify_aws_error(exc)
            return {"status": status, "message": msg}

    def get_full_status(self, region_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Evaluates full AWS authentication state and probes read access to all 5 services.
        """
        if region_name:
            self.region = get_configured_region(region_name)

        session = get_aws_session(self.region)
        sts_result = self.get_caller_identity(session)

        # If STS failed to authenticate, service checks cannot succeed
        if not sts_result["authenticated"]:
            overall_status = sts_result["status"]
            return {
                "status": overall_status,
                "account_id": None,
                "arn": None,
                "user_id": None,
                "region": self.region,
                "services": {
                    "ec2": {"status": overall_status, "message": sts_result["message"]},
                    "cloudwatch": {"status": overall_status, "message": sts_result["message"]},
                    "s3": {"status": overall_status, "message": sts_result["message"]},
                    "cost_explorer": {"status": overall_status, "message": sts_result["message"]},
                    "bedrock": {"status": overall_status, "message": sts_result["message"]},
                },
                "summary": sts_result["message"]
            }

        # Probe individual services
        ec2_status = self.check_ec2_access(session)
        cw_status = self.check_cloudwatch_access(session)
        s3_status = self.check_s3_access(session)
        ce_status = self.check_cost_explorer_access(session)
        bedrock_status = self.check_bedrock_access(session)

        services = {
            "ec2": ec2_status,
            "cloudwatch": cw_status,
            "s3": s3_status,
            "cost_explorer": ce_status,
            "bedrock": bedrock_status
        }

        connected_count = sum(1 for s in services.values() if s["status"] == STATUS_CONNECTED)

        return {
            "status": STATUS_CONNECTED,
            "account_id": sts_result["account_id"],
            "arn": sts_result["arn"],
            "user_id": sts_result["user_id"],
            "region": self.region,
            "services": services,
            "summary": f"AWS authenticated as {sts_result['arn']} ({connected_count}/5 services verified accessible in {self.region})."
        }
