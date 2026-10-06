"""
core/gitops/git_service.py
Secure Python subprocess wrapper for real Git CLI operations.

Safety Invariants:
- NEVER uses shell=True.
- Enforces strict execution timeouts.
- Masks GitHub tokens, bearer tokens, and credentials from all outputs and logs.
- Rejects dangerous branch names and staging of secrets or Terraform state files.
- Returns explicit error statuses: GIT_NOT_INSTALLED, GIT_REPOSITORY_NOT_FOUND, etc.

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

from core.gitops.models import (
    GitCommandResult,
    GitBranchResult,
    GitCommitResult,
    GitPushResult,
)

logger = logging.getLogger("finops.gitops.git")

STATUS_SUCCESS = "SUCCESS"
STATUS_GIT_NOT_INSTALLED = "GIT_NOT_INSTALLED"
STATUS_GIT_REPOSITORY_NOT_FOUND = "GIT_REPOSITORY_NOT_FOUND"
STATUS_BRANCH_CONFLICT = "BRANCH_CONFLICT"
STATUS_INVALID_BRANCH_NAME = "INVALID_BRANCH_NAME"
STATUS_FILE_SECURITY_VIOLATION = "FILE_SECURITY_VIOLATION"
STATUS_REMOTE_NOT_FOUND = "REMOTE_NOT_FOUND"
STATUS_AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
STATUS_NOTHING_TO_COMMIT = "NOTHING_TO_COMMIT"
STATUS_EXECUTION_ERROR = "EXECUTION_ERROR"
STATUS_TIMEOUT = "TIMEOUT"

DEFAULT_TIMEOUT_SECONDS = 30

# Forbidden file patterns that must never be staged or committed
FORBIDDEN_FILE_PATTERNS = [
    re.compile(r"^\.env(\..+)?$", re.IGNORECASE),
    re.compile(r".*\.(pem|key|p12|pfx|pkcs12)$", re.IGNORECASE),
    re.compile(r".*(id_rsa|id_ed25519|id_ecdsa).*", re.IGNORECASE),
    re.compile(r".*(credentials|secrets).*", re.IGNORECASE),
    re.compile(r".*\.tfstate(\..+)?$", re.IGNORECASE),
    re.compile(r".*\.terraform.*", re.IGNORECASE),
    re.compile(r".*crash.*\.log$", re.IGNORECASE),
]

# Valid branch name pattern
SAFE_BRANCH_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.\/]{1,100}$")


def sanitize_git_output(text: str) -> str:
    """Masks GitHub tokens, passwords, and AWS credentials from text."""
    if not text:
        return ""
    # Mask GitHub personal access tokens
    text = re.sub(r"ghp_[a-zA-Z0-9]{36}", "ghp_************************************", text)
    text = re.sub(r"github_pat_[a-zA-Z0-9_]{82}", "github_pat_**********************************************************************************", text)
    # Mask Basic auth in URLs: https://user:token@github.com/...
    text = re.sub(r"(https?://)([^:@\s]+):([^@\s]+)@", r"\1\2:********@", text)
    # Mask Bearer tokens
    text = re.sub(r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}", "Bearer ********", text)
    # Mask AWS Access Keys
    text = re.sub(r"AKIA[0-9A-Z]{16}", "AKIA****************", text)
    return text


def sanitize_branch_name(resource_id: str, action: str) -> str:
    """Generates a clean, predictable branch name in format: finops/<resource>/<action>."""
    clean_res = re.sub(r"[^a-zA-Z0-9_\-]", "-", resource_id).strip("-")[:40]
    clean_act = re.sub(r"[^a-zA-Z0-9_\-]", "-", action.lower()).strip("-")[:20]
    return f"finops/{clean_res}/{clean_act}"


class GitService:
    """Provides safe local Git repository management."""

    def __init__(self, repo_dir: Optional[Path] = None, binary_name: str = "git", timeout: int = DEFAULT_TIMEOUT_SECONDS):
        self.repo_dir = Path(repo_dir or Path(__file__).parent.parent.parent).resolve()
        self.binary_name = binary_name
        self.timeout = timeout

    def resolve_binary(self) -> Optional[str]:
        return shutil.which(self.binary_name)

    def is_git_available(self) -> Tuple[bool, str]:
        """Checks if Git executable is found and callable."""
        binary_path = self.resolve_binary()
        if not binary_path:
            return False, STATUS_GIT_NOT_INSTALLED

        try:
            res = subprocess.run(
                [binary_path, "--version"],
                cwd=str(self.repo_dir),
                shell=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0:
                first_line = res.stdout.strip().splitlines()[0] if res.stdout else "git"
                return True, sanitize_git_output(first_line)
            return False, f"Git returned exit code {res.returncode}: {res.stderr.strip()}"
        except FileNotFoundError:
            return False, STATUS_GIT_NOT_INSTALLED
        except subprocess.TimeoutExpired:
            return False, "Git version check timed out."
        except Exception as exc:
            return False, f"Git check failed: {str(exc)}"

    def is_repo(self) -> Tuple[bool, str]:
        """Checks if repo_dir is inside a valid Git work tree."""
        available, msg = self.is_git_available()
        if not available:
            return False, msg

        res = self.run_command(["rev-parse", "--is-inside-work-tree"])
        if res.success and res.stdout.strip().lower() == "true":
            return True, "Valid Git repository."
        return False, STATUS_GIT_REPOSITORY_NOT_FOUND

    def run_command(
        self,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None
    ) -> GitCommandResult:
        """Executes a git command safely using subprocess without shell=True."""
        binary_path = self.resolve_binary()
        if not binary_path:
            return GitCommandResult(
                command=[self.binary_name] + args,
                success=False,
                return_code=127,
                stdout="",
                stderr="Git executable is not installed or not in PATH.",
                status=STATUS_GIT_NOT_INSTALLED,
                duration_seconds=0.0,
            )

        cmd = [binary_path] + args
        start_time = time.time()
        timeout_val = timeout or self.timeout

        exec_env = os.environ.copy()
        if env:
            exec_env.update(env)

        try:
            logger.debug(f"Running git command: {' '.join(cmd)} in {self.repo_dir}")
            proc = subprocess.run(
                cmd,
                cwd=str(self.repo_dir),
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout_val,
                env=exec_env,
            )
            duration = round(time.time() - start_time, 3)
            stdout = sanitize_git_output(proc.stdout)
            stderr = sanitize_git_output(proc.stderr)
            success = (proc.returncode == 0)

            return GitCommandResult(
                command=cmd,
                success=success,
                return_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                status=STATUS_SUCCESS if success else STATUS_EXECUTION_ERROR,
                duration_seconds=duration,
            )

        except FileNotFoundError:
            return GitCommandResult(
                command=cmd,
                success=False,
                return_code=127,
                stdout="",
                stderr="Git executable not found.",
                status=STATUS_GIT_NOT_INSTALLED,
                duration_seconds=round(time.time() - start_time, 3),
            )
        except subprocess.TimeoutExpired as te:
            return GitCommandResult(
                command=cmd,
                success=False,
                return_code=-1,
                stdout=sanitize_git_output(te.stdout or ""),
                stderr=f"Git command timed out after {timeout_val} seconds.",
                status=STATUS_TIMEOUT,
                duration_seconds=round(time.time() - start_time, 3),
            )
        except Exception as exc:
            return GitCommandResult(
                command=cmd,
                success=False,
                return_code=-1,
                stdout="",
                stderr=f"Unexpected error running Git: {str(exc)}",
                status=STATUS_EXECUTION_ERROR,
                duration_seconds=round(time.time() - start_time, 3),
            )

    def get_current_branch(self) -> str:
        """Returns the name of the currently checked out branch."""
        res = self.run_command(["branch", "--show-current"])
        if res.success and res.stdout.strip():
            return res.stdout.strip()
        # Fallback for detached HEAD
        res_fallback = self.run_command(["rev-parse", "--abbrev-ref", "HEAD"])
        if res_fallback.success:
            return res_fallback.stdout.strip()
        return "main"

    def get_status(self) -> Dict[str, Any]:
        """Returns porcelain status and parsed file lists."""
        res = self.run_command(["status", "--porcelain"])
        if not res.success:
            return {"success": False, "status": res.status, "files": [], "error": res.stderr}

        changed_files = []
        for line in res.stdout.splitlines():
            line_str = line.strip()
            if len(line_str) >= 3:
                changed_files.append(line_str[2:].strip())

        return {
            "success": True,
            "status": STATUS_SUCCESS,
            "raw": res.stdout,
            "files": changed_files,
            "is_clean": len(changed_files) == 0,
        }

    def create_and_checkout_branch(
        self,
        branch_name: str,
        base_branch: Optional[str] = None
    ) -> GitBranchResult:
        """Creates and checks out a new branch safely."""
        # 1. Check repo
        is_r, msg = self.is_repo()
        if not is_r:
            return GitBranchResult(
                branch_name=branch_name,
                base_branch=base_branch or "main",
                created=False,
                checked_out=False,
                status=msg,
                message=f"Git repository check failed: {msg}",
            )

        # 2. Validate branch name syntax
        if not SAFE_BRANCH_REGEX.match(branch_name) or ".." in branch_name:
            return GitBranchResult(
                branch_name=branch_name,
                base_branch=base_branch or "main",
                created=False,
                checked_out=False,
                status=STATUS_INVALID_BRANCH_NAME,
                message=f"Branch name '{branch_name}' violates naming policies (no spaces, special chars, or traversal allowed).",
            )

        current = self.get_current_branch()
        base = base_branch or current

        # 3. Check if branch already exists
        check_res = self.run_command(["rev-parse", "--verify", branch_name])
        if check_res.success:
            # Branch already exists -> checkout existing
            co_res = self.run_command(["checkout", branch_name])
            if co_res.success:
                return GitBranchResult(
                    branch_name=branch_name,
                    base_branch=base,
                    created=False,
                    checked_out=True,
                    status="BRANCH_EXISTS",
                    message=f"Switched to existing branch '{branch_name}'.",
                )
            return GitBranchResult(
                branch_name=branch_name,
                base_branch=base,
                created=False,
                checked_out=False,
                status=STATUS_BRANCH_CONFLICT,
                message=f"Branch '{branch_name}' exists but checkout failed: {co_res.stderr}",
            )

        # 4. Create and checkout new branch
        create_res = self.run_command(["checkout", "-b", branch_name])
        if create_res.success:
            return GitBranchResult(
                branch_name=branch_name,
                base_branch=base,
                created=True,
                checked_out=True,
                status=STATUS_SUCCESS,
                message=f"Created and checked out branch '{branch_name}' from '{base}'.",
            )

        return GitBranchResult(
            branch_name=branch_name,
            base_branch=base,
            created=False,
            checked_out=False,
            status=STATUS_EXECUTION_ERROR,
            message=f"Failed to create branch '{branch_name}': {create_res.stderr}",
        )

    def stage_files(self, files: List[str]) -> GitCommandResult:
        """
        Stages specified files for commit after verifying no secrets or unexpected files are included.
        """
        for f in files:
            # File security inspection
            filename = os.path.basename(f)
            for pattern in FORBIDDEN_FILE_PATTERNS:
                if pattern.match(filename) or pattern.match(f):
                    logger.warning(f"File security violation: attempted to stage forbidden file '{f}'")
                    return GitCommandResult(
                        command=["git", "add", f],
                        success=False,
                        return_code=1,
                        stdout="",
                        stderr=f"Security violation: file '{f}' is prohibited from Git staging.",
                        status=STATUS_FILE_SECURITY_VIOLATION,
                    )

        # Add files safely
        add_res = self.run_command(["add"] + files)
        return add_res

    def commit(
        self,
        message: str,
        author: Optional[str] = None
    ) -> GitCommitResult:
        """Commits currently staged changes with the provided message."""
        current_branch = self.get_current_branch()

        # Sanitize commit message (no shell metacharacters)
        clean_msg = message.replace('"', '\\"').strip()
        if not clean_msg:
            clean_msg = "FinOps: Infrastructure optimization"

        cmd = ["commit", "-m", clean_msg]
        if author:
            cmd.extend(["--author", author])

        res = self.run_command(cmd)

        if not res.success:
            if "nothing to commit" in res.stdout.lower() or "nothing to commit" in res.stderr.lower():
                return GitCommitResult(
                    commit_hash=None,
                    branch_name=current_branch,
                    files_committed=[],
                    message=clean_msg,
                    status=STATUS_NOTHING_TO_COMMIT,
                    details=res.stdout,
                )
            return GitCommitResult(
                commit_hash=None,
                branch_name=current_branch,
                files_committed=[],
                message=clean_msg,
                status=STATUS_EXECUTION_ERROR,
                details=res.stderr,
            )

        # Retrieve commit hash
        hash_res = self.run_command(["rev-parse", "HEAD"])
        commit_hash = hash_res.stdout.strip() if hash_res.success else None

        return GitCommitResult(
            commit_hash=commit_hash,
            branch_name=current_branch,
            files_committed=[],
            message=clean_msg,
            status=STATUS_SUCCESS,
            details=res.stdout,
        )

    def push(
        self,
        branch_name: str,
        remote: str = "origin",
        set_upstream: bool = True
    ) -> GitPushResult:
        """Pushes the branch to the specified remote."""
        # 1. Verify remote exists
        remote_res = self.run_command(["remote", "get-url", remote])
        if not remote_res.success:
            return GitPushResult(
                branch_name=branch_name,
                remote=remote,
                pushed=False,
                status=STATUS_REMOTE_NOT_FOUND,
                message=f"Git remote '{remote}' is not configured in this repository.",
            )

        cmd = ["push"]
        if set_upstream:
            cmd.extend(["-u", remote, branch_name])
        else:
            cmd.extend([remote, branch_name])

        res = self.run_command(cmd)

        if res.success:
            return GitPushResult(
                branch_name=branch_name,
                remote=remote,
                pushed=True,
                status=STATUS_SUCCESS,
                message=f"Successfully pushed branch '{branch_name}' to remote '{remote}'.",
            )

        stderr_lower = res.stderr.lower()
        if "authentication failed" in stderr_lower or "permission denied" in stderr_lower or "invalid credentials" in stderr_lower:
            return GitPushResult(
                branch_name=branch_name,
                remote=remote,
                pushed=False,
                status=STATUS_AUTHENTICATION_FAILED,
                message=f"Authentication failed when pushing to remote '{remote}'.",
            )

        if "conflict" in stderr_lower or "rejected" in stderr_lower or "fetch first" in stderr_lower:
            return GitPushResult(
                branch_name=branch_name,
                remote=remote,
                pushed=False,
                status=STATUS_BRANCH_CONFLICT,
                message=f"Push rejected due to branch conflict on remote '{remote}'.",
            )

        return GitPushResult(
            branch_name=branch_name,
            remote=remote,
            pushed=False,
            status=STATUS_EXECUTION_ERROR,
            message=f"Failed to push branch: {res.stderr}",
        )
