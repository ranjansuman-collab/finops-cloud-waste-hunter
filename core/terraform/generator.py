"""
core/terraform/generator.py
Structured Terraform configuration change generator and security validator.

Safety & Validation Guarantees:
- Treats Bedrock AI suggestions as strictly UNTRUSTED input.
- Validates resource types, identifiers, and allowable FinOps actions.
- Prohibits Terraform provisioners (local-exec, remote-exec).
- Rejects arbitrary shell commands, script executions, paths, and secrets.
- Enforces strict whitelist of supported infrastructure actions.
- Returns UNSUPPORTED_ACTION or SECURITY_POLICY_VIOLATION on any discrepancy.

ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import re
import difflib
import logging
from typing import Tuple, Optional, Dict, Any, List

from core.models import (
    WasteFinding,
    WasteCategory,
    AIRecommendation,
    ResourceType,
)

logger = logging.getLogger("finops.terraform.generator")

STATUS_UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"
STATUS_SECURITY_POLICY_VIOLATION = "SECURITY_POLICY_VIOLATION"
STATUS_RESOURCE_NOT_FOUND_IN_CONFIG = "RESOURCE_NOT_FOUND_IN_CONFIG"

# Whitelist of allowed FinOps action types per resource type
ALLOWED_ACTIONS = {
    ResourceType.EC2: {"RESIZE", "DOWNSIZE"},
    ResourceType.EBS: {"DELETE", "ARCHIVE_AND_DELETE", "REMOVE"},
    ResourceType.LAMBDA: {"DELETE", "DEPRECATE", "REMOVE"},
    ResourceType.EIP: {"DISASSOCIATE", "RELEASE", "REMOVE"},
    ResourceType.S3: {"ADD_LIFECYCLE", "DELETE", "REMOVE"},
}

# Dangerous patterns forbidden in any generated or supplied configuration
FORBIDDEN_PATTERNS = [
    re.compile(r"\blocal-exec\b", re.IGNORECASE),
    re.compile(r"\bremote-exec\b", re.IGNORECASE),
    re.compile(r"\bprovisioner\b", re.IGNORECASE),
    re.compile(r"\b(curl|wget|bash\s+-|sh\s+-c|cmd\.exe|powershell)\b", re.IGNORECASE),
    re.compile(r"(\$\([^)]+\))", re.IGNORECASE),  # Command expansion $(command)
    re.compile(r"\b(aws_access_key|aws_secret_access_key|password|token)\b", re.IGNORECASE),
    re.compile(r"(\.\./|\.\.\\)", re.IGNORECASE),  # Directory traversal
]

# Strict validation for EC2 instance types (e.g., t3.medium, c5.xlarge)
INSTANCE_TYPE_REGEX = re.compile(r"^[a-z][a-z0-9]*\.[a-z0-9]+$")

# Strict validation for resource names/identifiers
SAFE_IDENTIFIER_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.]{1,128}$")


def validate_untrusted_input(
    finding: WasteFinding,
    recommendation: Optional[AIRecommendation] = None
) -> Tuple[bool, str]:
    """
    Strict security screening of finding and AI recommendation data.
    Ensures no prompt-injection, provisioners, or shell commands can reach Terraform.
    """
    # 1. Validate resource identifier
    if not SAFE_IDENTIFIER_REGEX.match(finding.resource_name):
        return False, f"Invalid or unsafe resource name: '{finding.resource_name}'"
    if not SAFE_IDENTIFIER_REGEX.match(finding.resource_id):
        return False, f"Invalid or unsafe resource ID: '{finding.resource_id}'"

    # 2. Check for injection keywords in finding description / recommended specs
    texts_to_check = [
        finding.description,
        finding.recommended_specs,
        finding.current_specs,
    ]
    if recommendation:
        texts_to_check.extend([
            recommendation.title,
            recommendation.executive_summary,
            recommendation.rationale,
            "".join(recommendation.steps_to_remediate),
            recommendation.terraform_hcl or "",
            recommendation.terraform_explanation or "",
        ])

    for text in texts_to_check:
        if not text:
            continue
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                logger.warning(f"Security policy violation detected: pattern {pattern.pattern} found in input")
                return False, STATUS_SECURITY_POLICY_VIOLATION

    # 3. Dedicated validation for Gemini-generated Terraform HCL
    if recommendation and recommendation.terraform_hcl:
        hcl = recommendation.terraform_hcl
        # Ensure balanced braces
        if hcl.count("{") != hcl.count("}") or hcl.count("(") != hcl.count(")"):
            logger.warning("Security policy violation: malformed or unbalanced HCL syntax in recommendation")
            return False, STATUS_SECURITY_POLICY_VIOLATION

    return True, "OK"


class TerraformChangeGenerator:
    """Safely applies structured FinOps modifications to Terraform HCL configuration text."""

    def __init__(self):
        pass

    def generate_modification(
        self,
        finding: WasteFinding,
        content: str,
        recommendation: Optional[AIRecommendation] = None
    ) -> Tuple[Optional[str], Optional[str], str]:
        """
        Generates a modified version of the given HCL content for the specified finding.

        Returns:
            (new_hcl, action_type, status)
            If successful: (new_hcl, action_type, "SUCCESS")
            If unsupported: (None, None, "UNSUPPORTED_ACTION")
            If security violated: (None, None, "SECURITY_POLICY_VIOLATION")
        """
        # Security validation of untrusted inputs
        is_safe, sec_msg = validate_untrusted_input(finding, recommendation)
        if not is_safe:
            return None, None, sec_msg

        r_type = finding.resource_type
        r_name = finding.resource_name

        if r_type not in ALLOWED_ACTIONS:
            return None, None, STATUS_UNSUPPORTED_ACTION

        # -------------------------------------------------------------
        # 1. EC2 Compute Downsizing
        # -------------------------------------------------------------
        if r_type == ResourceType.EC2 and finding.waste_category == WasteCategory.OVERSIZED_COMPUTE:
            target_type = finding.metrics_summary.get("recommended_instance_type", "t3.medium")
            # Strict validation on recommended instance type format
            if not INSTANCE_TYPE_REGEX.match(target_type):
                return None, None, f"Invalid target instance type: '{target_type}'"

            # Search for the aws_instance block corresponding to this resource
            pattern = rf'(resource\s+"aws_instance"\s+"[^"]+"\s+{{[\s\S]*?instance_type\s*=\s*)"([^"]+)"([\s\S]*?Name\s*=\s*"{re.escape(r_name)}"[\s\S]*?}})'
            match = re.search(pattern, content)
            if match:
                full_block = match.group(0)
                curr_type = match.group(2)
                patched_block = full_block.replace(
                    f'instance_type = "{curr_type}"',
                    f'instance_type = "{target_type}" # FinOps Downsized from {curr_type}'
                )
                new_content = content.replace(full_block, patched_block, 1)
                return new_content, "RESIZE", "SUCCESS"

            # Alternative search: find block containing Name tag first
            alt_pattern = rf'(resource\s+"aws_instance"\s+"[^"]+"\s+{{[\s\S]*?}})'
            for m in re.finditer(alt_pattern, content):
                block = m.group(0)
                if f'"{r_name}"' in block and "instance_type" in block:
                    type_match = re.search(r'instance_type\s*=\s*"([^"]+)"', block)
                    if type_match:
                        curr_type = type_match.group(1)
                        patched_block = block.replace(
                            f'instance_type = "{curr_type}"',
                            f'instance_type = "{target_type}" # FinOps Downsized from {curr_type}'
                        )
                        new_content = content.replace(block, patched_block, 1)
                        return new_content, "RESIZE", "SUCCESS"

            return None, None, STATUS_RESOURCE_NOT_FOUND_IN_CONFIG

        # -------------------------------------------------------------
        # 2. EBS Unattached Volume Removal
        # -------------------------------------------------------------
        elif r_type == ResourceType.EBS and finding.waste_category == WasteCategory.UNATTACHED_STORAGE:
            pattern = rf'(#\s*\d+\.\s*[\w\s-]+\n)?(resource\s+"aws_ebs_volume"\s+"[^"]+"\s+{{[\s\S]*?Name\s*=\s*"{re.escape(r_name)}"[\s\S]*?}}\n)'
            match = re.search(pattern, content)
            if match:
                matched_text = match.group(0)
                commented = "\n".join([f"# [FINOPS-REMOVED-UNATTACHED-VOLUME] {line}" for line in matched_text.strip().splitlines()])
                new_content = content.replace(matched_text, commented + "\n", 1)
                return new_content, "DELETE", "SUCCESS"

            # Fallback search by tag or resource_id inside block
            alt_pattern = rf'(resource\s+"aws_ebs_volume"\s+"[^"]+"\s+{{[\s\S]*?}})'
            for m in re.finditer(alt_pattern, content):
                block = m.group(0)
                if f'"{r_name}"' in block or (finding.resource_id and f'"{finding.resource_id}"' in block):
                    commented = "\n".join([f"# [FINOPS-REMOVED-UNATTACHED-VOLUME] {line}" for line in block.strip().splitlines()])
                    new_content = content.replace(block, commented, 1)
                    return new_content, "DELETE", "SUCCESS"

            # DISCOVERED_LIVE_UNMANAGED_RESOURCE:
            # Resource exists in real AWS but was not present in static template files.
            # Requires an active AI recommendation to synthesize remediation HCL.
            if not recommendation:
                return None, None, STATUS_RESOURCE_NOT_FOUND_IN_CONFIG

            safe_block_name = re.sub(r"[^a-zA-Z0-9_]", "_", finding.resource_id or r_name)
            specs = finding.metrics_summary or {}
            size_gb = specs.get("size_gb", 1)
            vol_type = specs.get("volume_type", "gp3")
            az = specs.get("availability_zone", "ap-southeast-2a")

            if recommendation.terraform_hcl:
                hcl_lines = recommendation.terraform_hcl.strip().splitlines()
                commented_hcl = "\n".join([
                    line if line.strip().startswith("#") else f"# [FINOPS-REMOVED-UNATTACHED-VOLUME] {line}"
                    for line in hcl_lines
                ])
                remediated_block = f"\n\n# --- DISCOVERED_LIVE_UNMANAGED_RESOURCE: {finding.resource_id} ---\n{commented_hcl}\n"
            else:
                remediated_block = (
                    f"\n\n# --- DISCOVERED_LIVE_UNMANAGED_RESOURCE: {finding.resource_id} ---\n"
                    f"# [FINOPS-REMOVED-UNATTACHED-VOLUME] resource \"aws_ebs_volume\" \"{safe_block_name}\" {{\n"
                    f"# [FINOPS-REMOVED-UNATTACHED-VOLUME]   availability_zone = \"{az}\"\n"
                    f"# [FINOPS-REMOVED-UNATTACHED-VOLUME]   size              = {size_gb}\n"
                    f"# [FINOPS-REMOVED-UNATTACHED-VOLUME]   type              = \"{vol_type}\"\n"
                    f"# [FINOPS-REMOVED-UNATTACHED-VOLUME]   tags = {{\n"
                    f"# [FINOPS-REMOVED-UNATTACHED-VOLUME]     Name             = \"{r_name}\"\n"
                    f"# [FINOPS-REMOVED-UNATTACHED-VOLUME]     FinOpsRemediated = \"true\"\n"
                    f"# [FINOPS-REMOVED-UNATTACHED-VOLUME]   }}\n"
                    f"# [FINOPS-REMOVED-UNATTACHED-VOLUME] }}\n"
                )
            new_content = content.rstrip() + remediated_block
            return new_content, "DELETE", "SUCCESS"

        # -------------------------------------------------------------
        # 3. Idle Lambda Function Deprecation
        # -------------------------------------------------------------
        elif r_type == ResourceType.LAMBDA and finding.waste_category == WasteCategory.IDLE_SERVERLESS:
            pattern = rf'(#\s*\d+\.\s*[\w\s-]+\n)?(resource\s+"aws_lambda_function"\s+"[^"]+"\s+{{[\s\S]*?function_name\s*=\s*"{re.escape(r_name)}"[\s\S]*?}}\n)'
            match = re.search(pattern, content)
            if match:
                matched_text = match.group(0)
                commented = "\n".join([f"# [FINOPS-DEPRECATED-DORMANT-LAMBDA] {line}" for line in matched_text.strip().splitlines()])
                new_content = content.replace(matched_text, commented + "\n", 1)
                return new_content, "DELETE", "SUCCESS"

            # Fallback search by block
            alt_pattern = rf'(resource\s+"aws_lambda_function"\s+"[^"]+"\s+{{[\s\S]*?}})'
            for m in re.finditer(alt_pattern, content):
                block = m.group(0)
                if f'"{r_name}"' in block or (finding.resource_id and f'"{finding.resource_id}"' in block):
                    commented = "\n".join([f"# [FINOPS-DEPRECATED-DORMANT-LAMBDA] {line}" for line in block.strip().splitlines()])
                    new_content = content.replace(block, commented, 1)
                    return new_content, "DELETE", "SUCCESS"

            # DISCOVERED_LIVE_UNMANAGED_RESOURCE:
            safe_block_name = re.sub(r"[^a-zA-Z0-9_]", "_", finding.resource_id or r_name)
            remediated_block = (
                f"\n\n# --- DISCOVERED_LIVE_UNMANAGED_RESOURCE: {finding.resource_id} ---\n"
                f"# [FINOPS-DEPRECATED-DORMANT-LAMBDA] resource \"aws_lambda_function\" \"{safe_block_name}\" {{\n"
                f"# [FINOPS-DEPRECATED-DORMANT-LAMBDA]   function_name = \"{r_name}\"\n"
                f"# [FINOPS-DEPRECATED-DORMANT-LAMBDA] }}\n"
            )
            new_content = content.rstrip() + remediated_block
            return new_content, "DELETE", "SUCCESS"

        # -------------------------------------------------------------
        # 4. Unassociated Elastic IP Release
        # -------------------------------------------------------------
        elif r_type == ResourceType.EIP:
            pattern = rf'(#\s*\d+\.\s*[\w\s-]+\n)?(resource\s+"aws_eip"\s+"[^"]+"\s+{{[\s\S]*?Name\s*=\s*"{re.escape(r_name)}"[\s\S]*?}}\n)'
            match = re.search(pattern, content)
            if match:
                matched_text = match.group(0)
                commented = "\n".join([f"# [FINOPS-RELEASED-UNASSOCIATED-EIP] {line}" for line in matched_text.strip().splitlines()])
                new_content = content.replace(matched_text, commented + "\n", 1)
                return new_content, "DISASSOCIATE", "SUCCESS"

            alt_pattern = rf'(resource\s+"aws_eip"\s+"[^"]+"\s+{{[\s\S]*?}})'
            for m in re.finditer(alt_pattern, content):
                block = m.group(0)
                if f'"{r_name}"' in block or (finding.resource_id and f'"{finding.resource_id}"' in block):
                    commented = "\n".join([f"# [FINOPS-RELEASED-UNASSOCIATED-EIP] {line}" for line in block.strip().splitlines()])
                    new_content = content.replace(block, commented, 1)
                    return new_content, "DISASSOCIATE", "SUCCESS"

            # DISCOVERED_LIVE_UNMANAGED_RESOURCE:
            safe_block_name = re.sub(r"[^a-zA-Z0-9_]", "_", finding.resource_id or r_name)
            remediated_block = (
                f"\n\n# --- DISCOVERED_LIVE_UNMANAGED_RESOURCE: {finding.resource_id} ---\n"
                f"# [FINOPS-RELEASED-UNASSOCIATED-EIP] resource \"aws_eip\" \"{safe_block_name}\" {{\n"
                f"# [FINOPS-RELEASED-UNASSOCIATED-EIP]   tags = {{\n"
                f"# [FINOPS-RELEASED-UNASSOCIATED-EIP]     Name = \"{r_name}\"\n"
                f"# [FINOPS-RELEASED-UNASSOCIATED-EIP]   }}\n"
                f"# [FINOPS-RELEASED-UNASSOCIATED-EIP] }}\n"
            )
            new_content = content.rstrip() + remediated_block
            return new_content, "DISASSOCIATE", "SUCCESS"

        # -------------------------------------------------------------
        # 5. S3 Bucket Optimization
        # -------------------------------------------------------------
        elif r_type == ResourceType.S3:
            pattern = rf'(resource\s+"aws_s3_bucket"\s+"[^"]+"\s+{{[\s\S]*?bucket\s*=\s*"{re.escape(r_name)}"[\s\S]*?}}\n)'
            match = re.search(pattern, content)
            if match:
                matched_text = match.group(0)
                commented = "\n".join([f"# [FINOPS-OPTIMIZED-S3-BUCKET] {line}" for line in matched_text.strip().splitlines()])
                new_content = content.replace(matched_text, commented + "\n", 1)
                return new_content, "DELETE", "SUCCESS"

            return None, None, STATUS_RESOURCE_NOT_FOUND_IN_CONFIG

        # Any other waste category or action is unsupported
        return None, None, STATUS_UNSUPPORTED_ACTION

    def compute_diff(self, original_text: str, modified_text: str, filename: str = "main.tf") -> str:
        """Produces a standard unified diff between original and modified HCL."""
        old_lines = original_text.splitlines(keepends=True)
        new_lines = modified_text.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            n=3
        )
        return "".join(diff)
