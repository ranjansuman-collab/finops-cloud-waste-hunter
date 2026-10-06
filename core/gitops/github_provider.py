"""
core/gitops/github_provider.py
GitHub REST API client for Pull Request creation and inspection.

Safety Invariants:
- Uses standard environment variables: GITHUB_TOKEN, GIT_REPOSITORY.
- Never hardcodes credentials, repository paths, or tokens.
- Never leaks GITHUB_TOKEN in logs, API responses, or error strings.
- Rejects automatic PR merging; merging requires human sign-off.
- Returns explicit error statuses: GIT_CREDENTIALS_MISSING, AUTHENTICATION_FAILED, etc.

ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import os
import logging
from typing import Optional, Dict, Any, Tuple
from github import Github, GithubException, Auth

from core.gitops.models import GitHubPRResult
from core.gitops.git_service import sanitize_git_output

logger = logging.getLogger("finops.gitops.github")

STATUS_SUCCESS = "SUCCESS"
STATUS_GIT_CREDENTIALS_MISSING = "GIT_CREDENTIALS_MISSING"
STATUS_GIT_REPOSITORY_CONFIG_MISSING = "GIT_REPOSITORY_CONFIG_MISSING"
STATUS_AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
STATUS_PR_CREATION_FAILED = "PR_CREATION_FAILED"
STATUS_ERROR = "ERROR"


class GitHubProvider:
    """Manages Pull Request lifecycle on GitHub."""

    def __init__(
        self,
        token: Optional[str] = None,
        repository: Optional[str] = None,
    ):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.repository = repository or os.getenv("GIT_REPOSITORY")

    def is_configured(self) -> Tuple[bool, str]:
        """Checks if both GITHUB_TOKEN and GIT_REPOSITORY are configured."""
        if not self.token or not self.token.strip():
            return False, STATUS_GIT_CREDENTIALS_MISSING
        if not self.repository or not self.repository.strip() or "/" not in self.repository:
            return False, STATUS_GIT_REPOSITORY_CONFIG_MISSING
        return True, "Configured"

    def get_client(self) -> Optional[Github]:
        """Instantiates authenticated PyGithub client without logging token."""
        if not self.token:
            return None
        auth = Auth.Token(self.token.strip())
        return Github(auth=auth)

    def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = "main"
    ) -> GitHubPRResult:
        """
        Creates a real Pull Request in the target GitHub repository.
        NEVER automatically merges the PR.
        """
        configured, msg = self.is_configured()
        if not configured:
            return GitHubPRResult(
                pr_number=None,
                pr_id=None,
                pr_url=None,
                title=title,
                state="OPEN",
                branch_name=head_branch,
                base_branch=base_branch,
                status=msg,
                message=f"GitHub provider configuration check failed: {msg}",
            )

        try:
            gh = self.get_client()
            repo = gh.get_repo(self.repository.strip())

            # Create pull request
            pr = repo.create_pull(
                title=title,
                body=body,
                head=head_branch,
                base=base_branch,
            )

            logger.info(f"Successfully created GitHub PR #{pr.number} on {self.repository}")

            return GitHubPRResult(
                pr_number=pr.number,
                pr_id=f"PR-{pr.number}",
                pr_url=pr.html_url,
                title=pr.title,
                state=pr.state.upper(),
                branch_name=head_branch,
                base_branch=base_branch,
                html_url=pr.html_url,
                status=STATUS_SUCCESS,
                message=f"Pull Request #{pr.number} created successfully on {self.repository}.",
            )

        except GithubException as ghe:
            status_code = ghe.status
            err_msg = sanitize_git_output(str(ghe.data.get("message", str(ghe)) if isinstance(ghe.data, dict) else str(ghe)))

            if status_code in (401, 403):
                logger.warning("GitHub authentication failed.")
                return GitHubPRResult(
                    pr_number=None,
                    pr_id=None,
                    pr_url=None,
                    title=title,
                    state="OPEN",
                    branch_name=head_branch,
                    base_branch=base_branch,
                    status=STATUS_AUTHENTICATION_FAILED,
                    message=f"GitHub authentication error (HTTP {status_code}): {err_msg}",
                )

            if status_code == 422:
                # E.g., No commits between base and head, or PR already exists
                logger.warning(f"GitHub PR validation error: {err_msg}")
                return GitHubPRResult(
                    pr_number=None,
                    pr_id=None,
                    pr_url=None,
                    title=title,
                    state="OPEN",
                    branch_name=head_branch,
                    base_branch=base_branch,
                    status=STATUS_PR_CREATION_FAILED,
                    message=f"GitHub rejected PR creation (HTTP 422): {err_msg}",
                )

            return GitHubPRResult(
                pr_number=None,
                pr_id=None,
                pr_url=None,
                title=title,
                state="OPEN",
                branch_name=head_branch,
                base_branch=base_branch,
                status=STATUS_ERROR,
                message=f"GitHub API error (HTTP {status_code}): {err_msg}",
            )

        except Exception as exc:
            clean_err = sanitize_git_output(str(exc))
            logger.error(f"Unexpected error creating GitHub PR: {clean_err}")
            return GitHubPRResult(
                pr_number=None,
                pr_id=None,
                pr_url=None,
                title=title,
                state="OPEN",
                branch_name=head_branch,
                base_branch=base_branch,
                status=STATUS_ERROR,
                message=f"Failed to create PR: {clean_err}",
            )
