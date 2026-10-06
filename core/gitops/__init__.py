"""
core/gitops/__init__.py
GitOps Service Layer for FinOps Cloud Waste Hunter & Auto-Remediator.
"""

from core.gitops.models import (
    GitCommandResult,
    GitBranchResult,
    GitCommitResult,
    GitPushResult,
    GitHubPRResult,
    GitOpsWorkflowResult,
)
from core.gitops.git_service import (
    GitService,
    sanitize_git_output,
    sanitize_branch_name,
    STATUS_SUCCESS,
    STATUS_GIT_NOT_INSTALLED,
    STATUS_GIT_REPOSITORY_NOT_FOUND,
    STATUS_BRANCH_CONFLICT,
    STATUS_INVALID_BRANCH_NAME,
    STATUS_FILE_SECURITY_VIOLATION,
    STATUS_REMOTE_NOT_FOUND,
    STATUS_AUTHENTICATION_FAILED,
)
from core.gitops.github_provider import (
    GitHubProvider,
    STATUS_GIT_CREDENTIALS_MISSING,
    STATUS_GIT_REPOSITORY_CONFIG_MISSING,
    STATUS_PR_CREATION_FAILED,
)
from core.gitops.orchestrator import (
    GitOpsOrchestrator,
    build_pr_body,
)

__all__ = [
    "GitService",
    "GitHubProvider",
    "GitOpsOrchestrator",
    "GitCommandResult",
    "GitBranchResult",
    "GitCommitResult",
    "GitPushResult",
    "GitHubPRResult",
    "GitOpsWorkflowResult",
    "build_pr_body",
    "sanitize_git_output",
    "sanitize_branch_name",
    "STATUS_SUCCESS",
    "STATUS_GIT_NOT_INSTALLED",
    "STATUS_GIT_REPOSITORY_NOT_FOUND",
    "STATUS_BRANCH_CONFLICT",
    "STATUS_INVALID_BRANCH_NAME",
    "STATUS_FILE_SECURITY_VIOLATION",
    "STATUS_REMOTE_NOT_FOUND",
    "STATUS_AUTHENTICATION_FAILED",
    "STATUS_GIT_CREDENTIALS_MISSING",
    "STATUS_GIT_REPOSITORY_CONFIG_MISSING",
    "STATUS_PR_CREATION_FAILED",
]
