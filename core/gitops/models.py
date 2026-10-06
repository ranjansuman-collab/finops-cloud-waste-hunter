"""
core/gitops/models.py
Pydantic data models for the real GitOps service and GitHub integration.

ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class GitCommandResult(BaseModel):
    command: List[str]
    success: bool
    return_code: int
    stdout: str
    stderr: str
    status: str  # SUCCESS, GIT_NOT_INSTALLED, GIT_REPOSITORY_NOT_FOUND, EXECUTION_ERROR, TIMEOUT
    duration_seconds: float = 0.0


class GitBranchResult(BaseModel):
    branch_name: str
    base_branch: str
    created: bool
    checked_out: bool
    status: str  # SUCCESS, BRANCH_EXISTS, BRANCH_CONFLICT, INVALID_BRANCH_NAME, GIT_NOT_INSTALLED, GIT_REPOSITORY_NOT_FOUND, ERROR
    message: str


class GitCommitResult(BaseModel):
    commit_hash: Optional[str] = None
    branch_name: str
    files_committed: List[str] = Field(default_factory=list)
    message: str
    status: str  # SUCCESS, NOTHING_TO_COMMIT, FILE_SECURITY_VIOLATION, ERROR
    details: str = ""


class GitPushResult(BaseModel):
    branch_name: str
    remote: str
    pushed: bool
    status: str  # SUCCESS, REMOTE_NOT_FOUND, AUTHENTICATION_FAILED, BRANCH_CONFLICT, NETWORK_ERROR, ERROR
    message: str


class GitHubPRResult(BaseModel):
    pr_number: Optional[int] = None
    pr_id: Optional[str] = None
    pr_url: Optional[str] = None
    title: str = ""
    state: str = "OPEN"  # OPEN, CLOSED, MERGED
    branch_name: str = ""
    base_branch: str = "main"
    html_url: Optional[str] = None
    status: str  # SUCCESS, GIT_CREDENTIALS_MISSING, GIT_REPOSITORY_CONFIG_MISSING, AUTHENTICATION_FAILED, PR_CREATION_FAILED, ERROR
    message: str = ""


class GitOpsWorkflowResult(BaseModel):
    status: str  # SUCCESS, GIT_NOT_INSTALLED, GIT_REPOSITORY_NOT_FOUND, GIT_CREDENTIALS_MISSING, AUTHENTICATION_FAILED, REMOTE_NOT_FOUND, BRANCH_CONFLICT, PR_CREATION_FAILED, FILE_SECURITY_VIOLATION, ERROR
    mode: str = "LIVE"  # LIVE or SIMULATION
    branch: Optional[str] = None
    commit_hash: Optional[str] = None
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    is_destructive: bool = False
    files_changed: List[str] = Field(default_factory=list)
    requires_human_approval: bool = True
    automatic_apply_triggered: bool = False  # Invariant: ALWAYS False
    message: str = ""
    errors: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
