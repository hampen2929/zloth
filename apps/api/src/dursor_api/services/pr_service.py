"""Pull Request management service.

This service manages PR creation and updates following the orchestrator
management pattern. PRs are created from branches that have already been
pushed by RunService, so this service only handles GitHub API operations.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlencode, urlparse

from dursor_api.config import settings
from dursor_api.domain.enums import ExecutorType
from dursor_api.domain.models import (
    PR,
    PRCreate,
    PRCreateAuto,
    PRCreated,
    PRCreateLink,
    PRLinkJob,
    PRLinkJobResult,
    PRSyncResult,
    PRUpdate,
    Repo,
    Run,
    Task,
)
from dursor_api.executors.claude_code_executor import ClaudeCodeExecutor, ClaudeCodeOptions
from dursor_api.executors.codex_executor import CodexExecutor, CodexOptions
from dursor_api.executors.gemini_executor import GeminiExecutor, GeminiOptions
from dursor_api.services.commit_message import ensure_english_commit_message
from dursor_api.services.git_service import GitService
from dursor_api.services.model_service import ModelService
from dursor_api.services.repo_service import RepoService
from dursor_api.storage.dao import PRDAO, RunDAO, TaskDAO

if TYPE_CHECKING:
    from dursor_api.services.github_service import GitHubService

logger = logging.getLogger(__name__)


class GitHubPermissionError(Exception):
    """Raised when GitHub App lacks required permissions."""

    pass


@dataclass
class PRLinkJobData:
    """Data for a PR link generation job."""

    job_id: str
    task_id: str
    selected_run_id: str
    status: str = "pending"  # pending, completed, failed
    result: PRCreateLink | None = None
    error: str | None = None


class PRLinkJobQueue:
    """In-memory queue for PR link generation jobs."""

    def __init__(self) -> None:
        self._jobs: dict[str, PRLinkJobData] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def create_job(self, task_id: str, selected_run_id: str) -> PRLinkJobData:
        """Create a new job."""
        job_id = str(uuid.uuid4())
        job = PRLinkJobData(
            job_id=job_id,
            task_id=task_id,
            selected_run_id=selected_run_id,
        )
        self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> PRLinkJobData | None:
        """Get job by ID."""
        return self._jobs.get(job_id)

    def set_task(self, job_id: str, task: asyncio.Task[None]) -> None:
        """Set asyncio task for job."""
        self._tasks[job_id] = task

    def complete_job(self, job_id: str, result: PRCreateLink) -> None:
        """Mark job as completed with result."""
        job = self._jobs.get(job_id)
        if job:
            job.status = "completed"
            job.result = result

    def fail_job(self, job_id: str, error: str) -> None:
        """Mark job as failed with error."""
        job = self._jobs.get(job_id)
        if job:
            job.status = "failed"
            job.error = error

    def cleanup_old_jobs(self, max_jobs: int = 100) -> None:
        """Remove oldest jobs if too many."""
        if len(self._jobs) > max_jobs:
            # Remove oldest completed/failed jobs
            completed = [
                (k, v) for k, v in self._jobs.items() if v.status in ("completed", "failed")
            ]
            for job_id, _ in completed[: len(completed) - max_jobs // 2]:
                del self._jobs[job_id]
                self._tasks.pop(job_id, None)


class PRService:
    """Service for managing Pull Requests.

    Following the orchestrator management pattern, this service:
    - Creates PRs from pre-pushed branches (no commit/push operations)
    - Updates PR descriptions via GitHub API
    - Generates descriptions from diffs using LLM
    """

    def __init__(
        self,
        pr_dao: PRDAO,
        task_dao: TaskDAO,
        run_dao: RunDAO,
        repo_service: RepoService,
        github_service: GitHubService,
        model_service: ModelService,
        git_service: GitService | None = None,
    ):
        self.pr_dao = pr_dao
        self.task_dao = task_dao
        self.run_dao = run_dao
        self.repo_service = repo_service
        self.github_service = github_service
        self.model_service = model_service
        self.git_service = git_service or GitService()
        # Job queue for async PR link generation
        self.link_job_queue = PRLinkJobQueue()
        # Initialize executors for PR description generation
        self.claude_executor = ClaudeCodeExecutor(
            ClaudeCodeOptions(claude_cli_path=settings.claude_cli_path)
        )
        self.codex_executor = CodexExecutor(CodexOptions(codex_cli_path=settings.codex_cli_path))
        self.gemini_executor = GeminiExecutor(
            GeminiOptions(gemini_cli_path=settings.gemini_cli_path)
        )

    def _parse_github_url(self, repo_url: str) -> tuple[str, str]:
        """Parse owner and repo from GitHub URL.

        Args:
            repo_url: GitHub repository URL.

        Returns:
            Tuple of (owner, repo_name).
        """
        # Handle different URL formats
        if repo_url.startswith("git@github.com:"):
            path = repo_url.replace("git@github.com:", "").replace(".git", "")
        else:
            parsed = urlparse(repo_url)
            path = parsed.path.strip("/").replace(".git", "")

        parts = path.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid GitHub URL: {repo_url}")

        return parts[0], parts[1]

    async def _ensure_branch_pushed(
        self, *, owner: str, repo: str, repo_obj: Repo, run: Run
    ) -> None:
        """Ensure the run's working branch exists on the remote.

        For CLI runs, we usually have a worktree and can push from it.
        If the push fails due to permission issues, raise a friendly error.
        """
        if not run.worktree_path or not run.working_branch:
            return
        try:
            auth_url = await self.github_service.get_auth_url(owner, repo)
            await self.git_service.push(
                Path(run.worktree_path),
                branch=run.working_branch,
                auth_url=auth_url,
            )
        except Exception as e:
            if "403" in str(e) or "Write access" in str(e):
                raise GitHubPermissionError(
                    f"GitHub App lacks write access to {owner}/{repo}. "
                    "Please ensure the GitHub App has 'Contents' permission "
                    "set to 'Read and write' and is installed on this repository."
                ) from e
            raise

    def _build_github_compare_url(
        self,
        *,
        owner: str,
        repo: str,
        base: str,
        head: str,
        title: str | None = None,
        body: str | None = None,
    ) -> str:
        """Build a GitHub compare URL that leads to PR creation UI."""
        # Note: GitHub accepts query params like `expand=1` and `quick_pull=1`.
        params: dict[str, str] = {"expand": "1", "quick_pull": "1"}
        if title:
            params["title"] = title
        if body:
            params["body"] = body

        compare_path = f"https://github.com/{owner}/{repo}/compare/{base}...{head}"
        return f"{compare_path}?{urlencode(params)}"

    async def create(self, task_id: str, data: PRCreate) -> PR:
        """Create a Pull Request from an already-pushed branch.

        Following the orchestrator pattern, this method expects the branch
        to already be pushed by RunService. It only creates the PR via
        GitHub API.

        Args:
            task_id: Task ID.
            data: PR creation data.

        Returns:
            Created PR object.
        """
        # Get task and repo
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        repo_obj = await self.repo_service.get(task.repo_id)
        if not repo_obj:
            raise ValueError(f"Repo not found: {task.repo_id}")

        # Get run
        run = await self.run_dao.get(data.selected_run_id)
        if not run:
            raise ValueError(f"Run not found: {data.selected_run_id}")

        # Verify run has a branch and commit
        if not run.working_branch:
            raise ValueError(f"Run has no working branch: {data.selected_run_id}")
        if not run.commit_sha:
            raise ValueError(f"Run has no commits: {data.selected_run_id}")

        # Parse GitHub info
        owner, repo_name = self._parse_github_url(repo_obj.repo_url)

        await self._ensure_branch_pushed(
            owner=owner,
            repo=repo_name,
            repo_obj=repo_obj,
            run=run,
        )

        # Diagnostics: confirm PR branch is based on latest default (origin/<default>)
        await self._log_pr_branch_base_state(repo_obj, run)

        # Use provided body or fallback to run summary
        pr_body = data.body or f"Generated by dursor\n\n{run.summary or ''}"

        pr_data = await self.github_service.create_pull_request(
            owner=owner,
            repo=repo_name,
            title=data.title,
            head=run.working_branch,
            base=repo_obj.default_branch,
            body=pr_body,
        )

        # Save to database
        return await self.pr_dao.create(
            task_id=task_id,
            number=pr_data["number"],
            url=pr_data["html_url"],
            branch=run.working_branch,
            title=data.title,
            body=pr_body,
            latest_commit=run.commit_sha,
        )

    async def create_auto(self, task_id: str, data: PRCreateAuto) -> PR:
        """Create a Pull Request with AI-generated title and description.

        This method automatically generates the PR title and description
        using Agent Tool based on the diff and task context.

        Args:
            task_id: Task ID.
            data: PR auto-creation data (only run_id needed).

        Returns:
            Created PR object.
        """
        # Get task and repo
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        repo_obj = await self.repo_service.get(task.repo_id)
        if not repo_obj:
            raise ValueError(f"Repo not found: {task.repo_id}")

        # Get run
        run = await self.run_dao.get(data.selected_run_id)
        if not run:
            raise ValueError(f"Run not found: {data.selected_run_id}")

        # Verify run has a branch and commit
        if not run.working_branch:
            raise ValueError(f"Run has no working branch: {data.selected_run_id}")
        if not run.commit_sha:
            raise ValueError(f"Run has no commits: {data.selected_run_id}")

        # Parse GitHub info
        owner, repo_name = self._parse_github_url(repo_obj.repo_url)

        await self._ensure_branch_pushed(
            owner=owner,
            repo=repo_name,
            repo_obj=repo_obj,
            run=run,
        )

        # Diagnostics: confirm PR branch is based on latest default (origin/<default>)
        await self._log_pr_branch_base_state(repo_obj, run)

        # Get diff for AI generation
        diff = ""
        if run.worktree_path:
            worktree_path = Path(run.worktree_path)
            if worktree_path.exists():
                diff = await self.git_service.get_diff_from_base(
                    worktree_path,
                    base_ref=run.base_ref or repo_obj.default_branch,
                )
        if not diff and run.patch:
            diff = run.patch

        # Generate title and description with AI in a single call
        template = await self._load_pr_template(repo_obj)
        title, description = await self._generate_title_and_description(
            diff=diff,
            template=template,
            task=task,
            run=run,
        )

        # Create PR via GitHub API
        pr_data = await self.github_service.create_pull_request(
            owner=owner,
            repo=repo_name,
            title=title,
            head=run.working_branch,
            base=repo_obj.default_branch,
            body=description,
        )

        # Save to database
        return await self.pr_dao.create(
            task_id=task_id,
            number=pr_data["number"],
            url=pr_data["html_url"],
            branch=run.working_branch,
            title=title,
            body=description,
            latest_commit=run.commit_sha,
        )

    async def create_link(self, task_id: str, data: PRCreate) -> PRCreateLink:
        """Generate a GitHub compare URL for manual PR creation."""
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        repo_obj = await self.repo_service.get(task.repo_id)
        if not repo_obj:
            raise ValueError(f"Repo not found: {task.repo_id}")

        run = await self.run_dao.get(data.selected_run_id)
        if not run:
            raise ValueError(f"Run not found: {data.selected_run_id}")

        if not run.working_branch:
            raise ValueError(f"Run has no working branch: {data.selected_run_id}")

        owner, repo_name = self._parse_github_url(repo_obj.repo_url)
        await self._ensure_branch_pushed(owner=owner, repo=repo_name, repo_obj=repo_obj, run=run)

        base = repo_obj.default_branch
        url = self._build_github_compare_url(
            owner=owner,
            repo=repo_name,
            base=base,
            head=run.working_branch,
            title=data.title,
            body=(data.body or "").strip() or None,
        )
        return PRCreateLink(url=url, branch=run.working_branch, base=base)

    async def create_link_auto(self, task_id: str, data: PRCreateAuto) -> PRCreateLink:
        """Generate a GitHub compare URL with AI-generated title and description."""
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        repo_obj = await self.repo_service.get(task.repo_id)
        if not repo_obj:
            raise ValueError(f"Repo not found: {task.repo_id}")

        run = await self.run_dao.get(data.selected_run_id)
        if not run:
            raise ValueError(f"Run not found: {data.selected_run_id}")

        if not run.working_branch:
            raise ValueError(f"Run has no working branch: {data.selected_run_id}")

        owner, repo_name = self._parse_github_url(repo_obj.repo_url)
        await self._ensure_branch_pushed(owner=owner, repo=repo_name, repo_obj=repo_obj, run=run)

        # Get diff for AI generation
        diff = ""
        if run.worktree_path:
            worktree_path = Path(run.worktree_path)
            if worktree_path.exists():
                diff = await self.git_service.get_diff_from_base(
                    worktree_path,
                    base_ref=run.base_ref or repo_obj.default_branch,
                )
        if not diff and run.patch:
            diff = run.patch

        # Generate title and description with AI in a single call
        template = await self._load_pr_template(repo_obj)
        title, description = await self._generate_title_and_description(
            diff=diff,
            template=template,
            task=task,
            run=run,
        )

        base = repo_obj.default_branch
        url = self._build_github_compare_url(
            owner=owner,
            repo=repo_name,
            base=base,
            head=run.working_branch,
            title=title,
            body=description,
        )
        return PRCreateLink(url=url, branch=run.working_branch, base=base)

    async def sync_manual_pr(self, task_id: str, selected_run_id: str) -> PRSyncResult:
        """Sync a PR that may have been created manually via GitHub UI."""
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        repo_obj = await self.repo_service.get(task.repo_id)
        if not repo_obj:
            raise ValueError(f"Repo not found: {task.repo_id}")

        run = await self.run_dao.get(selected_run_id)
        if not run:
            raise ValueError(f"Run not found: {selected_run_id}")

        if not run.working_branch:
            raise ValueError(f"Run has no working branch: {selected_run_id}")

        owner, repo_name = self._parse_github_url(repo_obj.repo_url)
        base = repo_obj.default_branch
        head = f"{owner}:{run.working_branch}"

        pr_data = await self.github_service.find_pull_request_by_head(
            owner=owner,
            repo=repo_name,
            head=head,
            base=base,
            state="all",
        )
        if not pr_data:
            return PRSyncResult(found=False, pr=None)

        number = pr_data["number"]
        existing = await self.pr_dao.get_by_task_and_number(task_id, number)
        if existing:
            return PRSyncResult(
                found=True,
                pr=PRCreated(
                    pr_id=existing.id,
                    url=existing.url,
                    branch=existing.branch,
                    number=existing.number,
                ),
            )

        created = await self.pr_dao.create(
            task_id=task_id,
            number=number,
            url=pr_data["html_url"],
            branch=pr_data["head"]["ref"],
            title=pr_data["title"],
            body=pr_data.get("body"),
            latest_commit=pr_data.get("head", {}).get("sha") or run.commit_sha or "",
        )
        return PRSyncResult(
            found=True,
            pr=PRCreated(
                pr_id=created.id,
                url=created.url,
                branch=created.branch,
                number=created.number,
            ),
        )

    def start_link_auto_job(self, task_id: str, data: PRCreateAuto) -> PRLinkJob:
        """Start async PR link generation job.

        This method returns immediately with a job ID that can be polled
        to check the status of the PR link generation.

        Args:
            task_id: Task ID.
            data: PR creation data.

        Returns:
            PRLinkJob with job ID and initial status.
        """
        # Create job
        job = self.link_job_queue.create_job(task_id, data.selected_run_id)

        # Start background task
        async def run_job() -> None:
            try:
                result = await self.create_link_auto(task_id, data)
                self.link_job_queue.complete_job(job.job_id, result)
            except Exception as e:
                logger.exception(f"PR link job {job.job_id} failed")
                self.link_job_queue.fail_job(job.job_id, str(e))

        task = asyncio.create_task(run_job())
        self.link_job_queue.set_task(job.job_id, task)

        # Cleanup old jobs
        self.link_job_queue.cleanup_old_jobs()

        return PRLinkJob(job_id=job.job_id, status=job.status)

    def get_link_auto_job(self, job_id: str) -> PRLinkJobResult | None:
        """Get status of PR link generation job.

        Args:
            job_id: Job ID.

        Returns:
            PRLinkJobResult or None if job not found.
        """
        job = self.link_job_queue.get_job(job_id)
        if not job:
            return None

        return PRLinkJobResult(
            job_id=job.job_id,
            status=job.status,
            result=job.result,
            error=job.error,
        )

    async def _generate_title_and_description(
        self,
        diff: str,
        template: str | None,
        task: Task,
        run: Run,
    ) -> tuple[str, str]:
        """Generate PR title and description in a single Agent Tool call.

        This method combines title and description generation to avoid
        multiple executor calls that can cause timeouts.

        Args:
            diff: Unified diff string.
            template: Optional PR template.
            task: Task object.
            run: Run object.

        Returns:
            Tuple of (title, description).
        """
        # Need worktree_path to run executor
        if not run.worktree_path:
            logger.warning("No worktree_path available, using fallback")
            fallback_title = self._generate_fallback_title(run)
            fallback_desc = self._generate_fallback_description_for_new_pr(
                diff, fallback_title, run, template
            )
            return fallback_title, fallback_desc

        worktree_path = Path(run.worktree_path)
        if not worktree_path.exists():
            logger.warning(f"Worktree path does not exist: {worktree_path}")
            fallback_title = self._generate_fallback_title(run)
            fallback_desc = self._generate_fallback_description_for_new_pr(
                diff, fallback_title, run, template
            )
            return fallback_title, fallback_desc

        # Truncate diff if too long
        truncated_diff = diff[:10000] if len(diff) > 10000 else diff

        # Build combined prompt
        prompt_parts = [
            "Generate a PR Title and PR Description based on the following information.",
            "",
            "## User Instruction",
            task.title or "(None)",
            "",
            "## Run Summary",
            run.summary or "(None)",
            "",
            "## Diff",
            "```diff",
            truncated_diff,
            "```",
        ]

        if template:
            prompt_parts.extend(
                [
                    "",
                    "## Template",
                    "```markdown",
                    template,
                    "```",
                ]
            )

        prompt_parts.extend(
            [
                "",
                "## Output Format",
                "Output MUST be in this exact format:",
                "```",
                "TITLE: <your title here>",
                "---DESCRIPTION---",
                "<your description here>",
                "```",
                "",
                "## Rules for Title",
                "- Keep it under 72 characters",
                "- Use imperative mood (e.g., 'Add feature X' not 'Added feature X')",
                "- Be specific but concise",
                "",
                "## Rules for Description",
            ]
        )

        if template:
            prompt_parts.extend(
                [
                    "- Fill in each section of the template with actual content",
                    "- Replace placeholders and HTML comments with real content",
                    "- Keep the template structure (headings, checkboxes, etc.)",
                    "- Base all content on the user instruction and diff",
                ]
            )
        else:
            prompt_parts.extend(
                [
                    "- Create a concise PR description",
                    "- Base the content on the user instruction and diff",
                ]
            )

        prompt = "\n".join(prompt_parts)

        try:
            result = await self._execute_for_description(
                worktree_path=worktree_path,
                executor_type=run.executor_type,
                prompt=prompt,
            )
            if result:
                # Parse the output
                title, description = self._parse_title_and_description(result)
                if title and description:
                    return title, description
            logger.warning("Failed to parse title/description, using fallback")
        except Exception as e:
            logger.warning(f"Failed to generate title/description: {e}")

        fallback_title = self._generate_fallback_title(run)
        return fallback_title, self._generate_fallback_description_for_new_pr(
            diff, fallback_title, run, template
        )

    def _parse_title_and_description(self, output: str) -> tuple[str | None, str | None]:
        """Parse title and description from executor output.

        Args:
            output: Raw output string from executor.

        Returns:
            Tuple of (title, description), either can be None if parsing fails.
        """
        # Try to find TITLE: line
        title = None
        description = None

        lines = output.strip().split("\n")
        for i, line in enumerate(lines):
            if line.startswith("TITLE:"):
                title = line[6:].strip().strip("\"'")
                # Ensure title is not too long
                if len(title) > 72:
                    title = title[:69] + "..."
                break

        # Try to find ---DESCRIPTION--- separator
        separator_idx = -1
        for i, line in enumerate(lines):
            if "---DESCRIPTION---" in line:
                separator_idx = i
                break

        if separator_idx >= 0:
            description = "\n".join(lines[separator_idx + 1 :]).strip()

        return title, description

    async def _generate_title(self, diff: str, task: Task, run: Run) -> str:
        """Generate PR title using Agent Tool (executor).

        Note: Prefer using _generate_title_and_description() for efficiency.

        Args:
            diff: Unified diff string.
            task: Task object.
            run: Run object.

        Returns:
            Generated title string.
        """
        # Need worktree_path to run executor
        if not run.worktree_path:
            return self._generate_fallback_title(run)

        worktree_path = Path(run.worktree_path)
        if not worktree_path.exists():
            return self._generate_fallback_title(run)

        # Truncate diff if too long
        truncated_diff = diff[:5000] if len(diff) > 5000 else diff

        prompt = f"""Generate a concise Pull Request title based on the following information.

DO NOT edit any files. Only output the title text.

## Task Description
{task.title or "(None)"}

## Run Summary
{run.summary or "(None)"}

## Diff (truncated)
```diff
{truncated_diff}
```

## Rules
- Output ONLY the title, no quotes or extra text
- Keep it under 72 characters
- Use imperative mood (e.g., "Add feature X" not "Added feature X")
- Be specific but concise
"""

        try:
            result = await self._execute_for_description(
                worktree_path=worktree_path,
                executor_type=run.executor_type,
                prompt=prompt,
            )
            if result:
                # Clean up the response - remove quotes and extra whitespace
                title = result.strip().strip("\"'")
                # Take only the first line
                title = title.split("\n")[0].strip()
                # Ensure title is not too long
                if len(title) > 72:
                    title = title[:69] + "..."
                return title
            return self._generate_fallback_title(run)
        except Exception:
            return self._generate_fallback_title(run)

    def _generate_fallback_title(self, run: Run) -> str:
        """Generate a fallback title from run summary."""
        if run.summary:
            summary_title = run.summary.split("\n")[0][:69]
            return summary_title if len(summary_title) <= 72 else summary_title[:69] + "..."
        return "Update code changes"

    async def _generate_description_for_new_pr(
        self,
        diff: str,
        template: str | None,
        task: Task,
        title: str,
        run: Run,
    ) -> str:
        """Generate PR description for new PR using Agent Tool (executor).

        Uses the same executor type as the Run to generate the PR description.

        Args:
            diff: Unified diff string.
            template: Optional PR template.
            task: Task object.
            title: Generated PR title.
            run: Run object.

        Returns:
            Generated description string.
        """
        # Need worktree_path to run executor
        if not run.worktree_path:
            logger.warning("No worktree_path available, using fallback description")
            return self._generate_fallback_description_for_new_pr(diff, title, run, template)

        worktree_path = Path(run.worktree_path)
        if not worktree_path.exists():
            logger.warning(f"Worktree path does not exist: {worktree_path}")
            return self._generate_fallback_description_for_new_pr(diff, title, run, template)

        prompt = self._build_description_prompt_for_new_pr(diff, template, task, title, run)

        try:
            result = await self._execute_for_description(
                worktree_path=worktree_path,
                executor_type=run.executor_type,
                prompt=prompt,
            )
            if result:
                return result
            logger.warning("Executor returned empty result, using fallback")
            return self._generate_fallback_description_for_new_pr(diff, title, run, template)
        except Exception as e:
            logger.warning(f"Failed to generate PR description with executor: {e}")
            return self._generate_fallback_description_for_new_pr(diff, title, run, template)

    async def _execute_for_description(
        self,
        worktree_path: Path,
        executor_type: ExecutorType,
        prompt: str,
    ) -> str | None:
        """Execute Agent Tool to generate PR description.

        Writes the result to a temp file and reads it back.

        Args:
            worktree_path: Path to the worktree.
            executor_type: Type of executor to use.
            prompt: Prompt for description generation.

        Returns:
            Generated description or None if failed.
        """
        # Create a unique temp file path inside the worktree
        # This ensures CLI tools (especially Codex) can write to it
        # Use a hidden file name to avoid git tracking
        temp_file = worktree_path / f".dursor_pr_desc_{uuid.uuid4().hex}.md"

        # Wrap the prompt to write output to the temp file
        wrapped_prompt = f"""{prompt}

IMPORTANT INSTRUCTIONS:
1. Write the PR description to this file: {temp_file}
2. Do NOT modify any other files in the repository
3. The file should contain ONLY the PR description content"""

        try:
            if executor_type == ExecutorType.CLAUDE_CODE:
                result = await self.claude_executor.execute(worktree_path, wrapped_prompt)
            elif executor_type == ExecutorType.CODEX_CLI:
                result = await self.codex_executor.execute(worktree_path, wrapped_prompt)
            elif executor_type == ExecutorType.GEMINI_CLI:
                result = await self.gemini_executor.execute(worktree_path, wrapped_prompt)
            else:
                logger.warning(f"Unsupported executor type for description: {executor_type}")
                return None

            if not result.success:
                logger.warning(f"Executor failed: {result.error}")
                return None

            # Read the generated description from temp file
            if temp_file.exists():
                description = temp_file.read_text().strip()
                return description if description else None
            else:
                logger.warning(f"Temp file not created: {temp_file}")
                return None
        finally:
            # Clean up temp file
            if temp_file.exists():
                temp_file.unlink()

    def _build_description_prompt_for_new_pr(
        self,
        diff: str,
        template: str | None,
        task: Task,
        title: str,
        run: Run,
    ) -> str:
        """Build prompt for description generation for new PR.

        Args:
            diff: Unified diff string.
            template: Optional PR template.
            task: Task object.
            title: Generated PR title.
            run: Run object.

        Returns:
            Prompt string.
        """
        # Truncate diff if too long
        truncated_diff = diff[:10000] if len(diff) > 10000 else diff

        prompt_parts = [
            "Create a PR Description based on the template, user instruction, and diff below.",
            "Fill in ALL sections of the template with appropriate content.",
            "",
            "## User Instruction",
            task.title or "(None)",
            "",
            "## Diff",
            "```diff",
            truncated_diff,
            "```",
        ]

        if template:
            prompt_parts.extend(
                [
                    "",
                    "## Template",
                    "```markdown",
                    template,
                    "```",
                    "",
                    "## Rules",
                    "- Fill in each section of the template with actual content",
                    "- Replace placeholders and HTML comments with real content",
                    "- Keep the template structure (headings, checkboxes, etc.)",
                    "- Base all content on the user instruction and diff",
                ]
            )
        else:
            prompt_parts.extend(
                [
                    "",
                    "## Rules",
                    "- Create a concise PR description",
                    "- Base the content on the user instruction and diff",
                ]
            )

        return "\n".join(prompt_parts)

    def _generate_fallback_description_for_new_pr(
        self, diff: str, title: str, run: Run, template: str | None = None
    ) -> str:
        """Generate a simple fallback description for new PR.

        Args:
            diff: Unified diff string.
            title: PR title.
            run: Run object.
            template: Optional PR template string (unused, kept for signature).

        Returns:
            Simple description string.
        """
        # Count changes
        added_lines = len(re.findall(r"^\+[^+]", diff, re.MULTILINE))
        removed_lines = len(re.findall(r"^-[^-]", diff, re.MULTILINE))
        files = set(re.findall(r"^\+\+\+ b/(.+)$", diff, re.MULTILINE))

        summary = run.summary or title

        # Generate changes as simple bullet points
        files_list = [f"- {f}" for f in sorted(files)[:10]]
        if len(files) > 10:
            files_list.append("- ...")
        changes_text = "\n".join(files_list)
        changes_text += f"\n- Total: +{added_lines} -{removed_lines} lines"

        return f"""## Summary
{summary}

## Changes
{changes_text}

## Test Plan
- [ ] Manual testing
- [ ] Unit tests
"""

    async def update(self, task_id: str, pr_id: str, data: PRUpdate) -> PR:
        """Update an existing Pull Request with a new run.

        This method applies the patch from the selected run to the PR branch.
        Note: This method still applies patches for backward compatibility,
        but new runs with CLI executors should already have committed/pushed.

        Args:
            task_id: Task ID.
            pr_id: PR ID.
            data: PR update data.

        Returns:
            Updated PR object.
        """
        # Get PR
        pr = await self.pr_dao.get(pr_id)
        if not pr or pr.task_id != task_id:
            raise ValueError(f"PR not found: {pr_id}")

        # Get task and repo
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        repo_obj = await self.repo_service.get(task.repo_id)
        if not repo_obj:
            raise ValueError(f"Repo not found: {task.repo_id}")

        # Get run
        run = await self.run_dao.get(data.selected_run_id)
        if not run:
            raise ValueError(f"Run not found: {data.selected_run_id}")

        # For CLI executor runs, the commit should already be on the branch
        # The branch should be the same as the PR branch
        if run.commit_sha and run.working_branch == pr.branch:
            # Commit is already on the PR branch, just update the database
            await self.pr_dao.update(pr_id, run.commit_sha)
            updated_pr = await self.pr_dao.get(pr_id)
            if not updated_pr:
                raise ValueError(f"PR not found after update: {pr_id}")
            return updated_pr

        # For PatchAgent runs or different branches, we need to apply the patch
        # This is backward compatibility code
        if not run.patch:
            raise ValueError("Run has no patch to apply")

        # Parse GitHub info
        owner, repo_name = self._parse_github_url(repo_obj.repo_url)

        # Apply patch to PR branch using GitService
        workspace_path = Path(repo_obj.workspace_path)

        # Checkout PR branch, apply patch, commit, and push
        await self.git_service.checkout(workspace_path, pr.branch)

        # Apply patch manually
        import subprocess

        patch_file = workspace_path / ".dursor_patch.diff"
        try:
            patch_file.write_text(run.patch)
            result = subprocess.run(
                ["git", "apply", "--whitespace=fix", str(patch_file)],
                cwd=workspace_path,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                await self.git_service.checkout(workspace_path, repo_obj.default_branch)
                error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                raise ValueError(f"Failed to apply patch: {error_msg}")
        finally:
            patch_file.unlink(missing_ok=True)

        # Stage and commit
        await self.git_service.stage_all(workspace_path)
        commit_message = data.message or f"Update: {run.summary or ''}"
        commit_message = await ensure_english_commit_message(
            commit_message,
            hint=run.summary or "",
        )
        commit_sha = await self.git_service.commit(workspace_path, commit_message)

        # Push
        auth_url = await self.github_service.get_auth_url(owner, repo_name)
        try:
            await self.git_service.push(workspace_path, pr.branch, auth_url)
        except Exception as e:
            if "403" in str(e) or "Write access" in str(e):
                raise GitHubPermissionError(
                    f"GitHub App lacks write access to {owner}/{repo_name}. "
                    "Please ensure the GitHub App has 'Contents' permission "
                    "set to 'Read and write' and is installed on this repository."
                ) from e
            raise

        # Switch back to default branch
        await self.git_service.checkout(workspace_path, repo_obj.default_branch)

        # Update database
        await self.pr_dao.update(pr_id, commit_sha)

        updated_pr = await self.pr_dao.get(pr_id)
        if not updated_pr:
            raise ValueError(f"PR not found after update: {pr_id}")
        return updated_pr

    async def regenerate_description(self, task_id: str, pr_id: str) -> PR:
        """Regenerate PR description from current diff.

        This method:
        1. Gets cumulative diff from base branch
        2. Loads pull_request_template if available
        3. Generates description using LLM
        4. Updates PR via GitHub API

        Args:
            task_id: Task ID.
            pr_id: PR ID.

        Returns:
            Updated PR object.
        """
        # Get PR
        pr = await self.pr_dao.get(pr_id)
        if not pr or pr.task_id != task_id:
            raise ValueError(f"PR not found: {pr_id}")

        # Get task and repo
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        repo_obj = await self.repo_service.get(task.repo_id)
        if not repo_obj:
            raise ValueError(f"Repo not found: {task.repo_id}")

        # Parse GitHub info
        owner, repo_name = self._parse_github_url(repo_obj.repo_url)

        # Get cumulative diff from the worktree or repo
        # Find the latest run associated with this PR
        runs = await self.run_dao.list(task_id)
        latest_run = next(
            (r for r in runs if r.working_branch == pr.branch and r.worktree_path),
            None,
        )

        cumulative_diff = ""
        if latest_run and latest_run.worktree_path:
            worktree_path = Path(latest_run.worktree_path)
            if worktree_path.exists():
                cumulative_diff = await self.git_service.get_diff_from_base(
                    worktree_path,
                    base_ref=latest_run.base_ref or repo_obj.default_branch,
                )

        # Fallback to using patch from latest run
        if not cumulative_diff and latest_run and latest_run.patch:
            cumulative_diff = latest_run.patch

        if not cumulative_diff:
            raise ValueError("Could not get diff for PR description generation")

        # Load pull_request_template
        template = await self._load_pr_template(repo_obj)

        # Generate description with LLM
        new_description = await self._generate_description(
            diff=cumulative_diff,
            template=template,
            task=task,
            pr=pr,
            run=latest_run,
        )

        # Update PR via GitHub API
        await self.github_service.update_pull_request(
            owner=owner,
            repo=repo_name,
            pr_number=pr.number,
            body=new_description,
        )

        # Update database
        await self.pr_dao.update_body(pr_id, new_description)

        updated_pr = await self.pr_dao.get(pr_id)
        if not updated_pr:
            raise ValueError(f"PR not found after update: {pr_id}")
        return updated_pr

    async def _load_pr_template(self, repo: Repo) -> str | None:
        """Load repository's pull_request_template.

        Args:
            repo: Repository object.

        Returns:
            Template content or None if not found.
        """
        workspace_path = Path(repo.workspace_path)

        # Template candidate paths (in priority order)
        template_paths = [
            workspace_path / ".github" / "pull_request_template.md",
            workspace_path / ".github" / "PULL_REQUEST_TEMPLATE.md",
            workspace_path / "pull_request_template.md",
            workspace_path / "PULL_REQUEST_TEMPLATE.md",
            workspace_path / ".github" / "PULL_REQUEST_TEMPLATE" / "default.md",
        ]

        for path in template_paths:
            if path.exists():
                return path.read_text()

        return None

    async def _log_pr_branch_base_state(self, repo_obj: Repo, run: Run) -> None:
        """Log merge-base diagnostics for PR branches.

        This helps confirm whether the PR branch includes the latest default branch.
        The check uses remote refs: origin/<default> and origin/<working_branch>.
        """
        try:
            if not repo_obj.default_branch or not run.working_branch:
                return

            repo_path = Path(repo_obj.workspace_path)
            base_ref = f"origin/{repo_obj.default_branch}"
            head_ref = f"origin/{run.working_branch}"

            base_sha = await self.git_service.get_ref_sha(repo_path, base_ref)
            head_sha = await self.git_service.get_ref_sha(repo_path, head_ref)
            merge_base = await self.git_service.get_merge_base(repo_path, base_ref, head_ref)
            base_is_ancestor = await self.git_service.is_ancestor(
                repo_path=repo_path,
                ancestor=base_ref,
                descendant=head_ref,
            )

            logger.info(
                "PR base diagnostics: "
                f"base_ref={base_ref} base_sha={base_sha} "
                f"head_ref={head_ref} head_sha={head_sha} "
                f"merge_base={merge_base} base_is_ancestor={base_is_ancestor}"
            )
        except Exception as e:
            logger.warning(f"PR base diagnostics failed: {e}")

    async def _generate_description(
        self,
        diff: str,
        template: str | None,
        task: Task,
        pr: PR,
        run: Run | None = None,
    ) -> str:
        """Generate PR description using Agent Tool (executor).

        Args:
            diff: Unified diff string.
            template: Optional PR template.
            task: Task object.
            pr: PR object.
            run: Optional Run object for executor settings.

        Returns:
            Generated description string.
        """
        # Need run with worktree_path to use executor
        if not run or not run.worktree_path:
            logger.warning("No run/worktree_path available, using fallback description")
            return self._generate_fallback_description(diff, pr, template)

        worktree_path = Path(run.worktree_path)
        if not worktree_path.exists():
            logger.warning(f"Worktree path does not exist: {worktree_path}")
            return self._generate_fallback_description(diff, pr, template)

        prompt = self._build_description_prompt(diff, template, task, pr)

        try:
            result = await self._execute_for_description(
                worktree_path=worktree_path,
                executor_type=run.executor_type,
                prompt=prompt,
            )
            if result:
                return result
            logger.warning("Executor returned empty result, using fallback")
            return self._generate_fallback_description(diff, pr, template)
        except Exception as e:
            logger.warning(f"Failed to generate PR description with executor: {e}")
            return self._generate_fallback_description(diff, pr, template)

    def _build_description_prompt(
        self,
        diff: str,
        template: str | None,
        task: Task,
        pr: PR,
    ) -> str:
        """Build prompt for description generation.

        Args:
            diff: Unified diff string.
            template: Optional PR template.
            task: Task object.
            pr: PR object.

        Returns:
            Prompt string.
        """
        # Truncate diff if too long
        truncated_diff = diff[:10000] if len(diff) > 10000 else diff

        prompt_parts = [
            "Create a PR Description based on the template, user instruction, and diff below.",
            "Fill in ALL sections of the template with appropriate content.",
            "",
            "## User Instruction",
            task.title or "(None)",
            "",
            "## Diff",
            "```diff",
            truncated_diff,
            "```",
        ]

        if template:
            prompt_parts.extend(
                [
                    "",
                    "## Template",
                    "```markdown",
                    template,
                    "```",
                    "",
                    "## Rules",
                    "- Fill in each section of the template with actual content",
                    "- Replace placeholders and HTML comments with real content",
                    "- Keep the template structure (headings, checkboxes, etc.)",
                    "- Base all content on the user instruction and diff",
                ]
            )
        else:
            prompt_parts.extend(
                [
                    "",
                    "## Rules",
                    "- Create a concise PR description",
                    "- Base the content on the user instruction and diff",
                ]
            )

        return "\n".join(prompt_parts)

    def _generate_fallback_description(self, diff: str, pr: PR, template: str | None = None) -> str:
        """Generate a simple fallback description.

        Args:
            diff: Unified diff string.
            pr: PR object.
            template: Optional PR template string (unused, kept for signature).

        Returns:
            Simple description string.
        """
        # Count changes
        added_lines = len(re.findall(r"^\+[^+]", diff, re.MULTILINE))
        removed_lines = len(re.findall(r"^-[^-]", diff, re.MULTILINE))
        files = set(re.findall(r"^\+\+\+ b/(.+)$", diff, re.MULTILINE))

        # Generate changes as simple bullet points
        files_list = [f"- {f}" for f in sorted(files)[:10]]
        if len(files) > 10:
            files_list.append("- ...")
        changes_text = "\n".join(files_list)
        changes_text += f"\n- Total: +{added_lines} -{removed_lines} lines"

        return f"""## Summary
{pr.title}

## Changes
{changes_text}

## Test Plan
- [ ] Manual testing
- [ ] Unit tests
"""

    async def get(self, task_id: str, pr_id: str) -> PR | None:
        """Get a PR by ID.

        Args:
            task_id: Task ID.
            pr_id: PR ID.

        Returns:
            PR object or None if not found.
        """
        pr = await self.pr_dao.get(pr_id)
        if pr and pr.task_id == task_id:
            return pr
        return None

    async def list(self, task_id: str) -> list[PR]:
        """List PRs for a task.

        Args:
            task_id: Task ID.

        Returns:
            List of PR objects.
        """
        return await self.pr_dao.list(task_id)
