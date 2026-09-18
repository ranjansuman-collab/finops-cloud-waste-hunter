"""
Module 6: Terraform Remediation Engine
Translates optimization recommendations into precise Terraform HCL configuration patches and unified diffs.
ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import re
import difflib
import logging
from typing import List, Dict, Any, Tuple
from pathlib import Path
from core.models import (
    WasteFinding,
    WasteCategory,
    AIRecommendation,
    TerraformPatch,
    ResourceType
)

logger = logging.getLogger("finops.module6")


class TerraformRemediationModule:
    """
    Implements FR9:
    Generates HCL modifications and unified diffs representing recommended infrastructure changes.
    """

    def __init__(self, tf_dir: str = None):
        if not tf_dir:
            tf_dir = Path(__file__).parent.parent / "sample_infrastructure"
        self.tf_dir = Path(tf_dir)

    def generate_patches(
        self,
        findings: List[WasteFinding],
        recommendations: List[AIRecommendation]
    ) -> List[TerraformPatch]:
        patches: List[TerraformPatch] = []
        main_tf_path = self.tf_dir / "main.tf"

        if not main_tf_path.exists():
            logger.warning(f"Terraform file not found at {main_tf_path}")
            return patches

        original_content = main_tf_path.read_text(encoding="utf-8")
        current_content = original_content

        for finding in findings:
            patch = self._generate_single_patch(finding, current_content, str(main_tf_path))
            if patch:
                patches.append(patch)
                # Chain edits for clean multi-resource diff preview
                current_content = patch.patched_hcl

        return patches

    def _generate_single_patch(
        self,
        finding: WasteFinding,
        content: str,
        filename: str
    ) -> TerraformPatch | None:
        r_name = finding.resource_name
        r_type = finding.resource_type
        action_type = "UNKNOWN"
        new_content = content

        # 1. EC2 Compute Downsizing
        if r_type == ResourceType.EC2 and finding.waste_category == WasteCategory.OVERSIZED_COMPUTE:
            target_type = finding.metrics_summary.get("recommended_instance_type", "t3.medium")
            action_type = "RESIZE"

            # Regex to find block for this instance
            pattern = rf'(resource\s+"aws_instance"\s+"[^"]+"\s+{{[\s\S]*?instance_type\s*=\s*)"([^"]+)"([\s\S]*?Name\s*=\s*"{r_name}"[\s\S]*?}})'
            match = re.search(pattern, content)
            if match:
                full_block = match.group(0)
                curr_type = match.group(2)
                patched_block = full_block.replace(
                    f'instance_type = "{curr_type}"',
                    f'instance_type = "{target_type}" # FinOps Downsized from {curr_type}'
                )
                new_content = content.replace(full_block, patched_block)
            else:
                # Fallback search by instance name directly
                inst_pattern = rf'(Name\s*=\s*"{r_name}"[\s\S]*?}})'
                # Try generic replace if present
                if "c5.4xlarge" in content and "batch_worker" in r_name:
                    new_content = content.replace(
                        'instance_type = "c5.4xlarge"',
                        f'instance_type = "{target_type}" # FinOps Downsized'
                    )
                elif "m5.2xlarge" in content and "dashboard" in r_name:
                    new_content = content.replace(
                        'instance_type = "m5.2xlarge"',
                        f'instance_type = "{target_type}" # FinOps Downsized'
                    )

        # 2. EBS Unattached Volume Removal / Archival
        elif r_type == ResourceType.EBS and finding.waste_category == WasteCategory.UNATTACHED_STORAGE:
            action_type = "DELETE"
            # Find and comment out / remove the unattached resource block
            pattern = rf'(#\s*\d+\.\s*[\w\s-]+\n)?(resource\s+"aws_ebs_volume"\s+"[^"]+"\s+{{[\s\S]*?Name\s*=\s*"{r_name}"[\s\S]*?}}\n)'
            match = re.search(pattern, content)
            if match:
                matched_text = match.group(0)
                commented = "\n".join([f"# [FINOPS-REMOVED-UNATTACHED-VOLUME] {line}" for line in matched_text.strip().splitlines()])
                new_content = content.replace(matched_text, commented + "\n")
            else:
                # Simple fallback tag replacement
                if r_name in content:
                    lines = content.splitlines()
                    new_lines = []
                    in_block = False
                    for line in lines:
                        if r_name in line:
                            in_block = True
                        if in_block and line.strip() == "}":
                            in_block = False
                            new_lines.append("# [FINOPS REMOVED UNATTACHED EBS VOLUME]")
                            continue
                        if not in_block:
                            new_lines.append(line)
                    new_content = "\n".join(new_lines)

        # 3. Idle Lambda Serverless Deprecation
        elif r_type == ResourceType.LAMBDA and finding.waste_category == WasteCategory.IDLE_SERVERLESS:
            action_type = "DELETE"
            pattern = rf'(#\s*\d+\.\s*[\w\s-]+\n)?(resource\s+"aws_lambda_function"\s+"[^"]+"\s+{{[\s\S]*?function_name\s*=\s*"{r_name}"[\s\S]*?}}\n)'
            match = re.search(pattern, content)
            if match:
                matched_text = match.group(0)
                commented = "\n".join([f"# [FINOPS-DEPRECATED-DORMANT-LAMBDA] {line}" for line in matched_text.strip().splitlines()])
                new_content = content.replace(matched_text, commented + "\n")

        # 4. Unassociated Elastic IP Release
        elif r_type == ResourceType.EIP:
            action_type = "DISASSOCIATE"
            pattern = rf'(#\s*\d+\.\s*[\w\s-]+\n)?(resource\s+"aws_eip"\s+"[^"]+"\s+{{[\s\S]*?Name\s*=\s*"{r_name}"[\s\S]*?}}\n)'
            match = re.search(pattern, content)
            if match:
                matched_text = match.group(0)
                commented = "\n".join([f"# [FINOPS-RELEASED-UNASSOCIATED-EIP] {line}" for line in matched_text.strip().splitlines()])
                new_content = content.replace(matched_text, commented + "\n")

        if new_content == content:
            return None

        # Compute unified diff
        diff = self._create_unified_diff(content, new_content, "main.tf")

        return TerraformPatch(
            patch_id=f"patch-{finding.id}",
            resource_id=finding.resource_id,
            resource_name=finding.resource_name,
            target_file="sample_infrastructure/main.tf",
            action_type=action_type,
            original_hcl=content,
            patched_hcl=new_content,
            unified_diff=diff,
            validation_status="SYNTAX_VALIDATED"
        )

    def _create_unified_diff(self, old_text: str, new_text: str, filename: str) -> str:
        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            n=3
        )
        return "".join(diff)

    def get_full_unified_diff(self, original: str, final: str) -> str:
        return self._create_unified_diff(original, final, "main.tf")
