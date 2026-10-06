"""
core/terraform/cli.py
Secure Python subprocess wrapper for real Terraform CLI execution.

Safety Guarantees:
- NEVER uses shell=True.
- Enforces strict execution timeouts.
- Captures stdout, stderr, and return codes cleanly.
- Masks potential secrets and credentials from outputs.
- Returns clear status if Terraform is not installed (TERRAFORM_NOT_INSTALLED).

ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import os
import re
import time
import shutil
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from core.terraform.models import (
    TerraformCommandResult,
    TerraformFmtResult,
    TerraformValidateResult,
)

logger = logging.getLogger("finops.terraform.cli")

STATUS_SUCCESS = "SUCCESS"
STATUS_TERRAFORM_NOT_INSTALLED = "TERRAFORM_NOT_INSTALLED"
STATUS_EXECUTION_ERROR = "EXECUTION_ERROR"
STATUS_TIMEOUT = "TIMEOUT"
STATUS_FMT_FAILED = "FMT_FAILED"
STATUS_VALIDATION_FAILED = "VALIDATION_FAILED"

DEFAULT_TIMEOUT_SECONDS = 60


def sanitize_output(text: str) -> str:
    """Removes sensitive credential fragments, tokens, and secret patterns from outputs."""
    if not text:
        return ""
    # Mask AWS Access Key ID patterns (AKIA...)
    text = re.sub(r"AKIA[0-9A-Z]{16}", "AKIA****************", text)
    # Mask Secret Access Key patterns (40 chars)
    text = re.sub(r"(?i)(secret[_\-\s]*key\s*[:=]\s*)['\"][a-zA-Z0-9/+=]{30,}['\"]", r"\1'********'", text)
    # Mask Bearer tokens
    text = re.sub(r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}", "Bearer ********", text)
    return text


class TerraformCLI:
    """Executes Terraform CLI commands safely using subprocess without shell=True."""

    def __init__(self, workspace_dir: Path, binary_name: str = "terraform", timeout: int = DEFAULT_TIMEOUT_SECONDS):
        self.workspace_dir = Path(workspace_dir)
        self.binary_name = binary_name
        self.timeout = timeout

    def resolve_binary(self) -> Optional[str]:
        """Resolves the terraform executable path on the system PATH."""
        return shutil.which(self.binary_name)

    def is_installed(self) -> Tuple[bool, str]:
        """Checks if Terraform CLI is available and functional."""
        binary_path = self.resolve_binary()
        if not binary_path:
            return False, STATUS_TERRAFORM_NOT_INSTALLED

        try:
            res = subprocess.run(
                [binary_path, "version"],
                cwd=str(self.workspace_dir),
                shell=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0:
                first_line = res.stdout.strip().splitlines()[0] if res.stdout else "Terraform"
                return True, sanitize_output(first_line)
            return False, f"Terraform returned exit code {res.returncode}: {res.stderr.strip()}"
        except FileNotFoundError:
            return False, STATUS_TERRAFORM_NOT_INSTALLED
        except subprocess.TimeoutExpired:
            return False, "Terraform version check timed out."
        except Exception as exc:
            return False, f"Terraform check failed: {str(exc)}"

    def run_command(
        self,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None
    ) -> TerraformCommandResult:
        """
        Executes a terraform subcommand with safe arguments and environment.
        NEVER uses shell=True.
        """
        binary_path = self.resolve_binary()
        if not binary_path:
            logger.warning("Terraform CLI not found on system PATH.")
            return TerraformCommandResult(
                command=[self.binary_name] + args,
                success=False,
                return_code=127,
                stdout="",
                stderr="Terraform CLI executable is not installed or not in PATH.",
                status=STATUS_TERRAFORM_NOT_INSTALLED,
                duration_seconds=0.0,
            )

        cmd = [binary_path] + args
        start_time = time.time()
        timeout_val = timeout or self.timeout

        # Ensure workspace directory exists
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        exec_env = os.environ.copy()
        if env:
            exec_env.update(env)

        try:
            logger.info(f"Running Terraform command: {' '.join(cmd)} in {self.workspace_dir}")
            proc = subprocess.run(
                cmd,
                cwd=str(self.workspace_dir),
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout_val,
                env=exec_env,
            )
            duration = round(time.time() - start_time, 3)
            stdout = sanitize_output(proc.stdout)
            stderr = sanitize_output(proc.stderr)
            success = (proc.returncode == 0)

            return TerraformCommandResult(
                command=cmd,
                success=success,
                return_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                status=STATUS_SUCCESS if success else STATUS_EXECUTION_ERROR,
                duration_seconds=duration,
            )

        except FileNotFoundError:
            return TerraformCommandResult(
                command=cmd,
                success=False,
                return_code=127,
                stdout="",
                stderr="Terraform executable not found.",
                status=STATUS_TERRAFORM_NOT_INSTALLED,
                duration_seconds=round(time.time() - start_time, 3),
            )
        except subprocess.TimeoutExpired as te:
            return TerraformCommandResult(
                command=cmd,
                success=False,
                return_code=-1,
                stdout=sanitize_output(te.stdout or ""),
                stderr=f"Terraform command timed out after {timeout_val} seconds.",
                status=STATUS_TIMEOUT,
                duration_seconds=round(time.time() - start_time, 3),
            )
        except Exception as exc:
            return TerraformCommandResult(
                command=cmd,
                success=False,
                return_code=-1,
                stdout="",
                stderr=f"Unexpected error running Terraform: {str(exc)}",
                status=STATUS_EXECUTION_ERROR,
                duration_seconds=round(time.time() - start_time, 3),
            )

    def fmt(self, check: bool = False) -> TerraformFmtResult:
        """Runs terraform fmt or terraform fmt -check."""
        args = ["fmt", "-no-color"]
        if check:
            args.append("-check")

        res = self.run_command(args)
        if res.status == STATUS_TERRAFORM_NOT_INSTALLED:
            return TerraformFmtResult(
                success=False,
                return_code=127,
                stdout=res.stdout,
                stderr=res.stderr,
                status=STATUS_TERRAFORM_NOT_INSTALLED,
            )

        success = res.success
        status = STATUS_SUCCESS if success else STATUS_FMT_FAILED
        return TerraformFmtResult(
            success=success,
            return_code=res.return_code,
            stdout=res.stdout,
            stderr=res.stderr,
            status=status,
        )

    def validate(self) -> TerraformValidateResult:
        """Runs terraform validate -no-color."""
        res = self.run_command(["validate", "-no-color"])
        if res.status == STATUS_TERRAFORM_NOT_INSTALLED:
            return TerraformValidateResult(
                valid=False,
                return_code=127,
                stdout=res.stdout,
                stderr=res.stderr,
                status=STATUS_TERRAFORM_NOT_INSTALLED,
                error_count=1,
            )

        valid = res.success
        status = STATUS_SUCCESS if valid else STATUS_VALIDATION_FAILED
        error_count = 0 if valid else 1
        return TerraformValidateResult(
            valid=valid,
            return_code=res.return_code,
            stdout=res.stdout,
            stderr=res.stderr,
            status=status,
            error_count=error_count,
        )

    def plan(self, plan_out: Optional[str] = None) -> TerraformCommandResult:
        """Runs terraform plan -no-color [-out=...]."""
        args = ["plan", "-no-color", "-input=false"]
        if plan_out:
            args.append(f"-out={plan_out}")
        return self.run_command(args)

    def apply(self, plan_file: Optional[str] = None) -> TerraformCommandResult:
        """Runs terraform apply -no-color [-input=false] [plan_file]."""
        args = ["apply", "-no-color", "-input=false"]
        if plan_file:
            args.append(plan_file)
        else:
            args.append("-auto-approve")
        return self.run_command(args)
