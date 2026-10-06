"""
tests/test_gitops.py
Comprehensive test suite for Checkpoint 7: Real GitOps CLI Integration.

All subprocess executions and GitHub API calls are safely mocked — Git and
PyGitHub do NOT need to be installed or configured.

Test scenarios:
 1. sanitize_branch_name produces safe branch names
 2. sanitize_git_output masks tokens, AWS keys, and Basic-auth URLs
 3. GitService: git not installed returns GIT_NOT_INSTALLED
 4. GitService: not a git repository returns GIT_REPOSITORY_NOT_FOUND
 5. GitService: branch creation success
 6. GitService: branch already exists — checkout existing
 7. GitService: invalid branch name rejected (INVALID_BRANCH_NAME)
 8. GitService: forbidden file staging rejected (FILE_SECURITY_VIOLATION)
 9. GitService: commit success
10. GitService: commit with nothing to commit
11. GitService: push success
12. GitService: push authentication failure
13. GitService: push branch conflict
14. GitService: push to remote not found
15. GitHubProvider: missing token returns GIT_CREDENTIALS_MISSING
16. GitHubProvider: missing repository returns GIT_REPOSITORY_CONFIG_MISSING
17. GitHubProvider: PR creation success (mocked PyGitHub)
18. GitHubProvider: 401 authentication failure
19. GitHubProvider: 422 PR creation failure
20. GitOpsOrchestrator: simulation mode creates in-memory PR (no real git)
21. GitOpsOrchestrator: simulation mode with zero findings returns early
22. GitOpsOrchestrator: live mode aborts when git not installed
23. GitOpsOrchestrator: live mode aborts when not a git repo
24. GitOpsOrchestrator: live mode aborts when GitHub token missing
25. GitOpsOrchestrator: full live mode pipeline success (fully mocked)
26. GitOpsOrchestrator: automatic_apply_triggered is ALWAYS False
27. Credentials not leaked in PR body (no GITHUB_TOKEN in output)
28. POST /api/gitops/workflow endpoint — simulation mode
29. POST /api/gitops/workflow endpoint — live mode missing credentials

ISWE309L Cloud Computing - Course Project Review-1
Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
"""

import sys
import os
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.models import (
    WasteFinding,
    CostFinding,
    ResourceType,
    WasteCategory,
    Severity,
)
from core.gitops.git_service import (
    GitService,
    sanitize_branch_name,
    sanitize_git_output,
    STATUS_SUCCESS,
    STATUS_GIT_NOT_INSTALLED,
    STATUS_GIT_REPOSITORY_NOT_FOUND,
    STATUS_INVALID_BRANCH_NAME,
    STATUS_FILE_SECURITY_VIOLATION,
    STATUS_AUTHENTICATION_FAILED,
    STATUS_BRANCH_CONFLICT,
    STATUS_REMOTE_NOT_FOUND,
    STATUS_NOTHING_TO_COMMIT,
)
from core.gitops.github_provider import (
    GitHubProvider,
    STATUS_GIT_CREDENTIALS_MISSING,
    STATUS_GIT_REPOSITORY_CONFIG_MISSING,
    STATUS_AUTHENTICATION_FAILED as GH_STATUS_AUTH_FAILED,
    STATUS_PR_CREATION_FAILED,
)
from core.gitops.orchestrator import GitOpsOrchestrator
from core.gitops.models import GitCommandResult, GitBranchResult, GitPushResult, GitCommitResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ec2_finding() -> WasteFinding:
    return WasteFinding(
        id="waste-ec2-test-0001",
        resource_id="i-0123456789abcdef0",
        resource_name="analytics-batch-worker-prod",
        resource_type=ResourceType.EC2,
        waste_category=WasteCategory.OVERSIZED_COMPUTE,
        severity=Severity.HIGH,
        description="Underutilized EC2 instance.",
        current_specs="c5.2xlarge (8 vCPU, 16GB RAM)",
        recommended_specs="t3.medium (2 vCPU, 4GB RAM)",
        confidence_score=0.97,
        metrics_summary={"cpu_utilization_avg": 3.2, "recommended_instance_type": "t3.medium"},
    )


def _make_ebs_finding() -> WasteFinding:
    return WasteFinding(
        id="waste-ebs-test-0002",
        resource_id="vol-0abc1234def56789",
        resource_name="orphaned-data-volume",
        resource_type=ResourceType.EBS,
        waste_category=WasteCategory.UNATTACHED_STORAGE,
        severity=Severity.HIGH,
        description="Unattached EBS volume.",
        current_specs="500 GB gp3",
        recommended_specs="Snapshot & Delete",
        confidence_score=0.99,
        metrics_summary={"size_gb": 500},
    )


def _make_cost_finding(finding_id: str) -> CostFinding:
    return CostFinding(
        finding_id=finding_id,
        resource_id="i-0123456789abcdef0",
        resource_name="analytics-batch-worker-prod",
        resource_type=ResourceType.EC2,
        current_monthly_cost=350.0,
        optimized_monthly_cost=30.0,
        monthly_savings=320.0,
        annualized_savings=3840.0,
        carbon_savings_kg_co2e=45.0,
        pricing_breakdown="c5.2xlarge downsized to t3.medium",
    )


def _git_success(stdout: str = "", stderr: str = "") -> GitCommandResult:
    return GitCommandResult(
        command=["git"],
        success=True,
        return_code=0,
        stdout=stdout,
        stderr=stderr,
        status=STATUS_SUCCESS,
    )


def _git_fail(status: str = "EXECUTION_ERROR", stderr: str = "error") -> GitCommandResult:
    return GitCommandResult(
        command=["git"],
        success=False,
        return_code=1,
        stdout="",
        stderr=stderr,
        status=status,
    )


# ---------------------------------------------------------------------------
# 1-2. Branch name & output sanitization
# ---------------------------------------------------------------------------

class TestSanitizers(unittest.TestCase):

    def test_sanitize_branch_name_produces_safe_name(self):
        """► 1. sanitize_branch_name produces a finops/<resource>/<action> name."""
        name = sanitize_branch_name("analytics-batch-worker-prod", "downsize")
        self.assertTrue(name.startswith("finops/"))
        self.assertIn("downsize", name)
        # No spaces or special chars
        self.assertNotIn(" ", name)
        self.assertNotIn("@", name)

    def test_sanitize_branch_name_strips_special_characters(self):
        """► 1b. Special characters in resource name are replaced with hyphens."""
        name = sanitize_branch_name("my bucket (us-east-1)", "optimize")
        self.assertNotIn("(", name)
        self.assertNotIn(")", name)
        self.assertNotIn(" ", name)

    def test_sanitize_git_output_masks_github_token(self):
        """► 2. GitHub PAT tokens are redacted from output."""
        text = "remote: https://user:ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZaBcDeFgHiJ@github.com/..."
        result = sanitize_git_output(text)
        self.assertNotIn("ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZaBcDeFgHiJ", result)

    def test_sanitize_git_output_masks_aws_access_key(self):
        """► 2b. AWS Access Key IDs are redacted from output."""
        text = "export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
        result = sanitize_git_output(text)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", result)

    def test_sanitize_git_output_masks_basic_auth_url(self):
        """► 2c. Basic auth tokens in URLs are redacted."""
        text = "Pushing to https://myuser:supersecret@github.com/org/repo.git"
        result = sanitize_git_output(text)
        self.assertNotIn("supersecret", result)
        self.assertIn("github.com", result)  # URL host preserved


# ---------------------------------------------------------------------------
# 3-14. GitService
# ---------------------------------------------------------------------------

class TestGitService(unittest.TestCase):

    def setUp(self):
        self.service = GitService(repo_dir=PROJECT_ROOT)

    # ► 3. git not installed
    @patch("shutil.which", return_value=None)
    def test_git_not_installed(self, mock_which):
        available, msg = self.service.is_git_available()
        self.assertFalse(available)
        self.assertEqual(msg, STATUS_GIT_NOT_INSTALLED)

    # ► 4. not a git repository
    @patch("shutil.which", return_value="/usr/bin/git")
    @patch("subprocess.run")
    def test_not_a_git_repository(self, mock_run, mock_which):
        # First call: git --version succeeds
        # Second call: rev-parse --is-inside-work-tree fails
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="git version 2.45.0", stderr=""),
            MagicMock(returncode=128, stdout="", stderr="not a git repository"),
        ]
        is_r, msg = self.service.is_repo()
        self.assertFalse(is_r)
        self.assertEqual(msg, STATUS_GIT_REPOSITORY_NOT_FOUND)

    # ► 5. branch creation success
    @patch.object(GitService, "is_repo", return_value=(True, "ok"))
    @patch.object(GitService, "run_command")
    @patch.object(GitService, "get_current_branch", return_value="main")
    def test_branch_creation_success(self, mock_branch, mock_run, mock_is_repo):
        # rev-parse --verify fails (branch doesn't exist), then checkout -b succeeds
        mock_run.side_effect = [
            _git_fail(),           # branch doesn't exist
            _git_success(),        # checkout -b succeeds
        ]
        result = self.service.create_and_checkout_branch("finops/test/downsize")
        self.assertTrue(result.created)
        self.assertTrue(result.checked_out)
        self.assertEqual(result.status, STATUS_SUCCESS)

    # ► 6. branch already exists — checkout existing
    @patch.object(GitService, "is_repo", return_value=(True, "ok"))
    @patch.object(GitService, "run_command")
    @patch.object(GitService, "get_current_branch", return_value="main")
    def test_branch_already_exists(self, mock_branch, mock_run, mock_is_repo):
        # rev-parse --verify succeeds (branch exists), checkout succeeds
        mock_run.side_effect = [
            _git_success(),        # branch exists
            _git_success(),        # checkout
        ]
        result = self.service.create_and_checkout_branch("finops/test/downsize")
        self.assertFalse(result.created)
        self.assertTrue(result.checked_out)
        self.assertEqual(result.status, "BRANCH_EXISTS")

    # ► 7. invalid branch name rejected
    @patch.object(GitService, "is_repo", return_value=(True, "ok"))
    def test_invalid_branch_name_rejected(self, mock_is_repo):
        result = self.service.create_and_checkout_branch("finops/../../../etc/passwd")
        self.assertFalse(result.created)
        self.assertEqual(result.status, STATUS_INVALID_BRANCH_NAME)

    # ► 8. forbidden file staging rejected
    def test_forbidden_file_staging_rejected(self):
        result = self.service.stage_files(["credentials.pem"])
        self.assertFalse(result.success)
        self.assertEqual(result.status, STATUS_FILE_SECURITY_VIOLATION)

    def test_forbidden_tfstate_staging_rejected(self):
        result = self.service.stage_files(["main.tfstate"])
        self.assertFalse(result.success)
        self.assertEqual(result.status, STATUS_FILE_SECURITY_VIOLATION)

    def test_forbidden_env_staging_rejected(self):
        result = self.service.stage_files([".env"])
        self.assertFalse(result.success)
        self.assertEqual(result.status, STATUS_FILE_SECURITY_VIOLATION)

    # ► 9. commit success
    @patch.object(GitService, "get_current_branch", return_value="finops/test/downsize")
    @patch.object(GitService, "run_command")
    def test_commit_success(self, mock_run, mock_branch):
        mock_run.side_effect = [
            _git_success(stdout="1 file changed"),  # commit
            _git_success(stdout="abc123def456"),    # rev-parse HEAD
        ]
        result = self.service.commit("FinOps: optimize 2 resources")
        self.assertEqual(result.status, STATUS_SUCCESS)
        self.assertEqual(result.commit_hash, "abc123def456")

    # ► 10. commit with nothing to commit
    @patch.object(GitService, "get_current_branch", return_value="finops/test/downsize")
    @patch.object(GitService, "run_command")
    def test_commit_nothing_to_commit(self, mock_run, mock_branch):
        mock_run.return_value = _git_fail(
            status="EXECUTION_ERROR",
            stderr="nothing to commit, working tree clean",
        )
        # patch stdout too
        mock_run.return_value = MagicMock(
            success=False,
            return_code=1,
            stdout="nothing to commit, working tree clean",
            stderr="",
        )
        result = self.service.commit("FinOps: optimize resources")
        self.assertEqual(result.status, STATUS_NOTHING_TO_COMMIT)

    # ► 11. push success
    @patch.object(GitService, "run_command")
    def test_push_success(self, mock_run):
        mock_run.side_effect = [
            _git_success(stdout="https://github.com/org/repo.git"),  # remote get-url
            _git_success(),  # push
        ]
        result = self.service.push("finops/test/downsize", remote="origin")
        self.assertTrue(result.pushed)
        self.assertEqual(result.status, STATUS_SUCCESS)

    # ► 12. push authentication failure
    @patch.object(GitService, "run_command")
    def test_push_auth_failure(self, mock_run):
        mock_run.side_effect = [
            _git_success(stdout="https://github.com/org/repo.git"),
            _git_fail(stderr="remote: Permission denied (authentication failed)."),
        ]
        result = self.service.push("finops/test/downsize")
        self.assertFalse(result.pushed)
        self.assertEqual(result.status, STATUS_AUTHENTICATION_FAILED)

    # ► 13. push branch conflict
    @patch.object(GitService, "run_command")
    def test_push_branch_conflict(self, mock_run):
        mock_run.side_effect = [
            _git_success(stdout="https://github.com/org/repo.git"),
            _git_fail(stderr="! [rejected] branch 'finops/x/y' is rejected — fetch first"),
        ]
        result = self.service.push("finops/test/downsize")
        self.assertFalse(result.pushed)
        self.assertEqual(result.status, STATUS_BRANCH_CONFLICT)

    # ► 14. push to remote not found
    @patch.object(GitService, "run_command")
    def test_push_remote_not_found(self, mock_run):
        mock_run.return_value = _git_fail(
            status="EXECUTION_ERROR",
            stderr="error: No such remote 'origin'",
        )
        result = self.service.push("finops/test/downsize", remote="origin")
        self.assertFalse(result.pushed)
        self.assertEqual(result.status, STATUS_REMOTE_NOT_FOUND)


# ---------------------------------------------------------------------------
# 15-19. GitHubProvider
# ---------------------------------------------------------------------------

class TestGitHubProvider(unittest.TestCase):

    # ► 15. missing token
    def test_missing_token_returns_credentials_missing(self):
        provider = GitHubProvider(token=None, repository="org/repo")
        ok, msg = provider.is_configured()
        self.assertFalse(ok)
        self.assertEqual(msg, STATUS_GIT_CREDENTIALS_MISSING)

    # ► 16. missing repository
    def test_missing_repository_returns_config_missing(self):
        provider = GitHubProvider(token="ghp_abc123", repository=None)
        ok, msg = provider.is_configured()
        self.assertFalse(ok)
        self.assertEqual(msg, STATUS_GIT_REPOSITORY_CONFIG_MISSING)

    # ► 16b. repository without slash is invalid
    def test_invalid_repository_format(self):
        provider = GitHubProvider(token="ghp_abc123", repository="badreponame")
        ok, msg = provider.is_configured()
        self.assertFalse(ok)
        self.assertEqual(msg, STATUS_GIT_REPOSITORY_CONFIG_MISSING)

    # ► 17. PR creation success (mocked PyGitHub)
    @patch("core.gitops.github_provider.Github")
    def test_pr_creation_success(self, mock_github_class):
        mock_pr = MagicMock()
        mock_pr.number = 99
        mock_pr.html_url = "https://github.com/org/repo/pull/99"
        mock_pr.title = "FinOps: Optimize worker [Save $320.00/mo]"
        mock_pr.state = "open"

        mock_repo = MagicMock()
        mock_repo.create_pull.return_value = mock_pr

        mock_gh = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        mock_github_class.return_value = mock_gh

        provider = GitHubProvider(token="ghp_faketoken123", repository="org/repo")
        result = provider.create_pull_request(
            title="FinOps: Optimize worker",
            body="## PR Body",
            head_branch="finops/worker/downsize",
        )

        self.assertEqual(result.status, STATUS_SUCCESS)
        self.assertEqual(result.pr_number, 99)
        self.assertIn("pull/99", result.pr_url)

    # ► 18. 401 authentication failure
    @patch("core.gitops.github_provider.Github")
    def test_authentication_failure(self, mock_github_class):
        from github import GithubException
        mock_gh = MagicMock()
        mock_gh.get_repo.side_effect = GithubException(
            status=401,
            data={"message": "Bad credentials"},
            headers={},
        )
        mock_github_class.return_value = mock_gh

        provider = GitHubProvider(token="ghp_badtoken", repository="org/repo")
        result = provider.create_pull_request("title", "body", "head-branch")
        self.assertEqual(result.status, GH_STATUS_AUTH_FAILED)

    # ► 19. 422 PR creation failure
    @patch("core.gitops.github_provider.Github")
    def test_pr_creation_422_failure(self, mock_github_class):
        from github import GithubException
        mock_gh = MagicMock()
        mock_gh.get_repo.return_value.create_pull.side_effect = GithubException(
            status=422,
            data={"message": "No commits between base and head"},
            headers={},
        )
        mock_github_class.return_value = mock_gh

        provider = GitHubProvider(token="ghp_validtoken", repository="org/repo")
        result = provider.create_pull_request("title", "body", "head-branch")
        self.assertEqual(result.status, STATUS_PR_CREATION_FAILED)


# ---------------------------------------------------------------------------
# 20-27. GitOpsOrchestrator
# ---------------------------------------------------------------------------

class TestGitOpsOrchestrator(unittest.TestCase):

    def _get_findings(self):
        return [_make_ec2_finding(), _make_ebs_finding()]

    def _get_costs(self):
        ec2_f = _make_ec2_finding()
        return [_make_cost_finding(ec2_f.id)]

    # ► 20. simulation mode creates in-memory PR (no real git)
    @patch("subprocess.run")   # ensure subprocess is never called in sim mode
    def test_simulation_mode_creates_in_memory_pr(self, mock_subprocess):
        orch = GitOpsOrchestrator(use_live_gitops=False)
        findings = self._get_findings()
        costs = self._get_costs()

        result = orch.create_remediation_pr(
            run_id="test-run-001",
            findings=findings,
            costs=costs,
            total_monthly_savings=320.0,
        )
        # subprocess must NOT be called in simulation mode
        mock_subprocess.assert_not_called()

        self.assertEqual(result.status, STATUS_SUCCESS)
        self.assertEqual(result.mode, "SIMULATION")
        self.assertIsNotNone(result.pr_number)
        self.assertFalse(result.automatic_apply_triggered)
        self.assertTrue(result.requires_human_approval)

    # ► 21. simulation mode with zero findings returns early
    def test_simulation_mode_no_findings_returns_early(self):
        orch = GitOpsOrchestrator(use_live_gitops=False)
        result = orch.create_remediation_pr(
            run_id="test-run-002",
            findings=[],
        )
        self.assertEqual(result.status, STATUS_SUCCESS)
        self.assertIn("No waste findings", result.message)

    # ► 22. live mode aborts when git not installed
    @patch("core.gitops.git_service.shutil.which", return_value=None)
    def test_live_mode_aborts_git_not_installed(self, mock_which):
        orch = GitOpsOrchestrator(use_live_gitops=True)
        result = orch.create_remediation_pr(
            run_id="test-run-003",
            findings=[_make_ec2_finding()],
        )
        self.assertEqual(result.status, STATUS_GIT_NOT_INSTALLED)
        self.assertEqual(result.mode, "LIVE")

    # ► 23. live mode aborts when not a git repo
    @patch("core.gitops.git_service.shutil.which", return_value="/usr/bin/git")
    @patch("subprocess.run")
    def test_live_mode_aborts_not_a_git_repo(self, mock_run, mock_which):
        # git --version ok, rev-parse fails
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="git version 2.45.0", stderr=""),
            MagicMock(returncode=128, stdout="", stderr="not a git repository"),
        ]
        orch = GitOpsOrchestrator(use_live_gitops=True)
        result = orch.create_remediation_pr(
            run_id="test-run-004",
            findings=[_make_ec2_finding()],
        )
        self.assertEqual(result.status, STATUS_GIT_REPOSITORY_NOT_FOUND)

    # ► 24. live mode aborts when GitHub token missing
    @patch.object(GitService, "is_git_available", return_value=(True, "git version 2.45.0"))
    @patch.object(GitService, "is_repo", return_value=(True, "Valid Git repository."))
    def test_live_mode_aborts_no_github_token(self, mock_repo, mock_git):
        # Clear env vars so GitHubProvider has no token
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GITHUB_TOKEN", None)
            os.environ.pop("GIT_REPOSITORY", None)
            orch = GitOpsOrchestrator(use_live_gitops=True)
            result = orch.create_remediation_pr(
                run_id="test-run-005",
                findings=[_make_ec2_finding()],
            )
        self.assertIn(result.status, (STATUS_GIT_CREDENTIALS_MISSING, STATUS_GIT_REPOSITORY_CONFIG_MISSING))

    # ► 25. full live mode pipeline success (fully mocked)
    @patch("core.gitops.github_provider.Github")
    @patch.object(GitService, "push")
    @patch.object(GitService, "commit")
    @patch.object(GitService, "stage_files")
    @patch.object(GitService, "create_and_checkout_branch")
    @patch.object(GitService, "is_repo", return_value=(True, "Valid Git repository."))
    @patch.object(GitService, "is_git_available", return_value=(True, "git version 2.45.0"))
    def test_live_mode_full_pipeline_success(
        self,
        mock_git_avail,
        mock_is_repo,
        mock_branch,
        mock_stage,
        mock_commit,
        mock_push,
        mock_github_class,
    ):
        # Configure mocks
        mock_branch.return_value = GitBranchResult(
            branch_name="finops/analytics-batch-worker-prod/downsize",
            base_branch="main",
            created=True,
            checked_out=True,
            status=STATUS_SUCCESS,
            message="Created branch.",
        )
        mock_stage.return_value = _git_success()
        mock_commit.return_value = GitCommitResult(
            commit_hash="deadbeef1234",
            branch_name="finops/analytics-batch-worker-prod/downsize",
            message="FinOps: optimize",
            status=STATUS_SUCCESS,
        )
        mock_push.return_value = GitPushResult(
            branch_name="finops/analytics-batch-worker-prod/downsize",
            remote="origin",
            pushed=True,
            status=STATUS_SUCCESS,
            message="Pushed.",
        )

        mock_pr = MagicMock()
        mock_pr.number = 42
        mock_pr.html_url = "https://github.com/org/repo/pull/42"
        mock_pr.title = "FinOps: Optimize"
        mock_pr.state = "open"
        mock_repo_obj = MagicMock()
        mock_repo_obj.create_pull.return_value = mock_pr
        mock_gh = MagicMock()
        mock_gh.get_repo.return_value = mock_repo_obj
        mock_github_class.return_value = mock_gh

        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test", "GIT_REPOSITORY": "org/repo"}):
            orch = GitOpsOrchestrator(use_live_gitops=True)
            result = orch.create_remediation_pr(
                run_id="test-run-006",
                findings=[_make_ec2_finding()],
                costs=[_make_cost_finding(_make_ec2_finding().id)],
                total_monthly_savings=320.0,
            )

        self.assertEqual(result.status, STATUS_SUCCESS)
        self.assertEqual(result.mode, "LIVE")
        self.assertEqual(result.pr_number, 42)
        self.assertIn("pull/42", result.pr_url)
        self.assertFalse(result.automatic_apply_triggered)

    # ► 26. automatic_apply_triggered is ALWAYS False
    def test_automatic_apply_never_triggered(self):
        """Invariant: GitOpsWorkflowResult.automatic_apply_triggered is always False."""
        orch = GitOpsOrchestrator(use_live_gitops=False)
        result = orch.create_remediation_pr(
            run_id="invariant-test",
            findings=[_make_ec2_finding()],
            total_monthly_savings=100.0,
        )
        self.assertFalse(result.automatic_apply_triggered,
                         "automatic_apply_triggered must ALWAYS be False; Bedrock/automation cannot trigger apply.")

    # ► 27. credentials not leaked in PR body
    def test_credentials_not_in_pr_body(self):
        """No GITHUB_TOKEN, AWS keys, or secrets appear in the PR body."""
        from core.gitops.orchestrator import build_pr_body

        body = build_pr_body(
            findings=[_make_ec2_finding()],
            costs=[_make_cost_finding(_make_ec2_finding().id)],
            recommendations=[],
            total_savings=320.0,
            is_destructive=False,
        )
        # Common token / credential patterns must not appear
        self.assertNotRegex(body, r"ghp_[a-zA-Z0-9]{10,}")
        self.assertNotRegex(body, r"AKIA[0-9A-Z]{16}")
        self.assertNotRegex(body, r"AWS_SECRET_ACCESS_KEY\s*=")
        self.assertNotRegex(body, r"GITHUB_TOKEN\s*=")
        # But savings figure should be present
        self.assertIn("320.00", body)


# ---------------------------------------------------------------------------
# 28-29. API endpoint integration tests
# ---------------------------------------------------------------------------

class TestGitOpsApiEndpoints(unittest.TestCase):

    def setUp(self):
        from fastapi.testclient import TestClient
        from app.server import app
        self.client = TestClient(app)

    # ► 28. simulation workflow endpoint
    def test_gitops_workflow_simulation_endpoint(self):
        """POST /api/gitops/workflow in simulation mode returns a valid PR."""
        resp = self.client.post("/api/gitops/workflow", json={
            "scenario": "enterprise",
            "use_live_aws": False,
            "use_live_gitops": False,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["status"], STATUS_SUCCESS)
        self.assertEqual(data["mode"], "SIMULATION")
        self.assertFalse(data["automatic_apply_triggered"])
        self.assertTrue(data["requires_human_approval"])

    # ► 29. live mode endpoint returns missing credentials gracefully
    @patch("core.gitops.git_service.shutil.which", return_value=None)
    def test_gitops_workflow_live_mode_git_not_installed(self, mock_which):
        """POST /api/gitops/workflow in live mode with no git returns GIT_NOT_INSTALLED."""
        resp = self.client.post("/api/gitops/workflow", json={
            "scenario": "enterprise",
            "use_live_aws": False,
            "use_live_gitops": True,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], STATUS_GIT_NOT_INSTALLED)
        self.assertEqual(data["mode"], "LIVE")
        # automatic_apply must still be False even on failure
        self.assertFalse(data["automatic_apply_triggered"])

    # ► clean scenario returns NO_FINDINGS
    def test_gitops_workflow_clean_scenario_no_findings(self):
        """Clean scenario with no waste returns NO_FINDINGS, not an error."""
        resp = self.client.post("/api/gitops/workflow", json={
            "scenario": "clean",
            "use_live_aws": False,
            "use_live_gitops": False,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "NO_FINDINGS")
        self.assertFalse(data["automatic_apply_triggered"])


if __name__ == "__main__":
    unittest.main()
