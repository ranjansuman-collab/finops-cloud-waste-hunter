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
import shlex
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

    def __init__(
        self,
        workspace_dir: Path,
        binary_name: str = "terraform",
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        use_wsl: Optional[bool] = None,
    ):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.binary_name = binary_name
        self.timeout = timeout

        # Resolve Linux binary for WSL bypass (avoids Windows local network proxy/antivirus TLS interception)
        base_dir = Path(__file__).resolve().parent.parent.parent
        self.linux_binary = base_dir / "storage" / "tf_linux" / "terraform"
        self.wsl_binary = shutil.which("wsl")

        if use_wsl is not None:
            self.use_wsl = use_wsl
        else:
            is_testing = bool(os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("UNITTEST"))
            self.use_wsl = (
                not is_testing
                and os.name == "nt"
                and self.wsl_binary is not None
                and self.linux_binary.exists()
            )

    def _to_wsl_path(self, path: Path) -> str:
        """Converts Windows Path C:\\foo\\bar to WSL path /mnt/c/foo/bar."""
        resolved = path.resolve()
        drive = resolved.drive.replace(":", "").lower()
        parts = list(resolved.parts[1:])
        return f"/mnt/{drive}/" + "/".join(parts)

    def resolve_binary(self) -> Optional[str]:
        """Resolves the terraform executable path."""
        if self.use_wsl and self.linux_binary.exists() and self.wsl_binary:
            return str(self.linux_binary)
        return shutil.which(self.binary_name)

    def is_installed(self) -> Tuple[bool, str]:
        """Checks if Terraform CLI is available and functional."""
        if self.use_wsl:
            if not self.linux_binary.exists() or not self.wsl_binary:
                return False, STATUS_TERRAFORM_NOT_INSTALLED
            res = self.run_command(["version"], timeout=10)
            if res.success:
                first_line = res.stdout.strip().splitlines()[0] if res.stdout else "Terraform"
                return True, sanitize_output(first_line)
            return False, f"Terraform returned exit code {res.return_code}: {res.stderr.strip()}"

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
        start_time = time.time()
        timeout_val = timeout or self.timeout

        # Ensure workspace directory exists
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        exec_env = os.environ.copy()
        if env:
            exec_env.update(env)

        if self.use_wsl:
            if not self.wsl_binary or not self.linux_binary.exists():
                return TerraformCommandResult(
                    command=[self.binary_name] + args,
                    success=False,
                    return_code=127,
                    stdout="",
                    stderr="Terraform CLI executable is not installed or WSL is unavailable.",
                    status=STATUS_TERRAFORM_NOT_INSTALLED,
                    duration_seconds=0.0,
                )
            wsl_workspace = self._to_wsl_path(self.workspace_dir)
            wsl_tf = self._to_wsl_path(self.linux_binary)
            quoted_args = " ".join(shlex.quote(a) for a in args)

            env_exports = ""
            for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_DEFAULT_REGION", "AWS_REGION"):
                if k in exec_env and exec_env[k]:
                    env_exports += f"export {k}={shlex.quote(str(exec_env[k]))}; "
            if env:
                for k, v in env.items():
                    if k not in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_DEFAULT_REGION", "AWS_REGION"):
                        env_exports += f"export {k}={shlex.quote(str(v))}; "

            bash_cmd = f"cd {shlex.quote(wsl_workspace)} && {env_exports}{shlex.quote(wsl_tf)} {quoted_args}"
            cmd = [self.wsl_binary, "bash", "-c", bash_cmd]
        else:
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

    def init(self, upgrade: bool = False) -> TerraformCommandResult:
        """Runs terraform init -no-color [-upgrade]."""
        args = ["init", "-no-color", "-input=false"]
        if upgrade:
            args.append("-upgrade")
        return self.run_command(args)

    def state_list(self) -> List[str]:
        """Runs terraform state list -no-color and returns resource addresses in state."""
        res = self.run_command(["state", "list"])
        if not res.success or not res.stdout:
            return []
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]

    def import_resource(
        self,
        address: str,
        resource_id: str,
        vars: Optional[Dict[str, str]] = None
    ) -> TerraformCommandResult:
        """Runs terraform import -no-color [-var=k=v] <address> <resource_id>."""
        args = ["import", "-no-color", "-input=false"]
        if vars:
            for k, v in vars.items():
                args.append(f"-var={k}={v}")
        args.extend([address, resource_id])
        return self.run_command(args)

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

    def plan(
        self,
        plan_out: Optional[str] = None,
        vars: Optional[Dict[str, str]] = None
    ) -> TerraformCommandResult:
        """Runs terraform plan -no-color -input=false [-var=k=v] [-out=...]."""
        args = ["plan", "-no-color", "-input=false"]
        if vars:
            for k, v in vars.items():
                args.append(f"-var={k}={v}")
        if plan_out:
            args.append(f"-out={plan_out}")
        return self.run_command(args)

    def show(self, plan_file: Optional[str] = None) -> TerraformCommandResult:
        """Runs terraform show -no-color [plan_file]."""
        args = ["show", "-no-color"]
        if plan_file:
            args.append(plan_file)
        return self.run_command(args)

    def apply(self, plan_file: Optional[str] = None) -> TerraformCommandResult:
        """Runs terraform apply -no-color [-input=false] [plan_file]."""
        args = ["apply", "-no-color", "-input=false"]
        if plan_file:
            args.append(plan_file)
        else:
            args.append("-auto-approve")
        return self.run_command(args)
