"""Run execution service.

This service manages the execution of AI Agent runs following the
orchestrator management pattern where dursor centrally manages git
operations while AI Agents only edit files.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

from dursor_api.agents.llm_router import LLMConfig, LLMRouter
from dursor_api.agents.patch_agent import PatchAgent
from dursor_api.config import settings
from dursor_api.domain.enums import ExecutorType, RunStatus
from dursor_api.domain.models import (
    SUMMARY_FILE_PATH,
    AgentConstraints,
    AgentRequest,
    FileDiff,
    Run,
    RunCreate,
)
from dursor_api.executors.claude_code_executor import ClaudeCodeExecutor, ClaudeCodeOptions
from dursor_api.executors.codex_executor import CodexExecutor, CodexOptions
from dursor_api.executors.gemini_executor import GeminiExecutor, GeminiOptions
from dursor_api.services.git_service import GitService
from dursor_api.services.model_service import ModelService
from dursor_api.services.repo_service import RepoService
from dursor_api.storage.dao import RunDAO, TaskDAO

if TYPE_CHECKING:
    from dursor_api.services.github_service import GitHubService
    from dursor_api.services.output_manager import OutputManager


class QueueAdapter:
    """Simple in-memory queue adapter for v0.1.

    Can be replaced with Celery/RQ/Redis in v0.2+.
    """

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}

    def enqueue(
        self,
        run_id: str,
        coro: Callable[[], Awaitable[None]],
    ) -> None:
        """Enqueue a run for execution.

        Args:
            run_id: Run ID.
            coro: Coroutine to execute.
        """
        task = asyncio.create_task(coro())
        self._tasks[run_id] = task

    def cancel(self, run_id: str) -> bool:
        """Cancel a queued run.

        Args:
            run_id: Run ID.

        Returns:
            True if cancelled, False if not found or already completed.
        """
        task = self._tasks.get(run_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def is_running(self, run_id: str) -> bool:
        """Check if a run is currently running.

        Args:
            run_id: Run ID.

        Returns:
            True if running.
        """
        task = self._tasks.get(run_id)
        return task is not None and not task.done()


class RunService:
    """Service for managing and executing runs.

    Following the orchestrator management pattern, this service:
    - Creates worktrees for isolated execution
    - Runs AI Agent CLIs (file editing only)
    - Automatically stages, commits, and pushes changes
    - Tracks commit SHAs for PR creation
    """

    def __init__(
        self,
        run_dao: RunDAO,
        task_dao: TaskDAO,
        model_service: ModelService,
        repo_service: RepoService,
        git_service: GitService | None = None,
        github_service: "GitHubService | None" = None,
        output_manager: "OutputManager | None" = None,
    ):
        self.run_dao = run_dao
        self.task_dao = task_dao
        self.model_service = model_service
        self.repo_service = repo_service
        self.git_service = git_service or GitService()
        self.github_service = github_service
        self.output_manager = output_manager
        self.queue = QueueAdapter()
        self.llm_router = LLMRouter()
        self.claude_executor = ClaudeCodeExecutor(
            ClaudeCodeOptions(claude_cli_path=settings.claude_cli_path)
        )
        self.codex_executor = CodexExecutor(
            CodexOptions(codex_cli_path=settings.codex_cli_path)
        )
        self.gemini_executor = GeminiExecutor(
            GeminiOptions(gemini_cli_path=settings.gemini_cli_path)
        )

    async def create_runs(self, task_id: str, data: RunCreate) -> list[Run]:
        """Create runs for multiple models or Claude Code.

        Args:
            task_id: Task ID.
            data: Run creation data with model IDs or executor type.

        Returns:
            List of created Run objects.
        """
        # Verify task exists
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        # Get repo for workspace
        repo = await self.repo_service.get(task.repo_id)
        if not repo:
            raise ValueError(f"Repo not found: {task.repo_id}")

        runs = []

        # Lock executor after the first run in the task.
        # Users expect "resume" style conversations to keep using the initially chosen executor.
        existing_runs = await self.run_dao.list(task_id)
        locked_executor: ExecutorType | None = None
        if existing_runs:
            # DAO returns newest-first; the earliest run is last.
            locked_executor = existing_runs[-1].executor_type
            if data.executor_type != locked_executor:
                data = data.model_copy(update={"executor_type": locked_executor})

        if data.executor_type == ExecutorType.CLAUDE_CODE:
            # Create a single Claude Code run
            run = await self._create_cli_run(
                task_id=task_id,
                repo=repo,
                instruction=data.instruction,
                base_ref=data.base_ref or repo.default_branch,
                executor_type=ExecutorType.CLAUDE_CODE,
            )
            runs.append(run)
        elif data.executor_type == ExecutorType.CODEX_CLI:
            # Create a single Codex CLI run
            run = await self._create_cli_run(
                task_id=task_id,
                repo=repo,
                instruction=data.instruction,
                base_ref=data.base_ref or repo.default_branch,
                executor_type=ExecutorType.CODEX_CLI,
            )
            runs.append(run)
        elif data.executor_type == ExecutorType.GEMINI_CLI:
            # Create a single Gemini CLI run
            run = await self._create_cli_run(
                task_id=task_id,
                repo=repo,
                instruction=data.instruction,
                base_ref=data.base_ref or repo.default_branch,
                executor_type=ExecutorType.GEMINI_CLI,
            )
            runs.append(run)
        else:
            # Create runs for each model (PatchAgent)
            model_ids = data.model_ids
            if not model_ids:
                # If the task is already locked to patch_agent, reuse the most recent
                # model set (grouped by latest patch_agent instruction).
                patch_runs = [r for r in existing_runs if r.executor_type == ExecutorType.PATCH_AGENT]
                if patch_runs:
                    latest_instruction = patch_runs[0].instruction  # newest-first
                    model_ids = []
                    seen: set[str] = set()
                    for r in patch_runs:
                        if r.instruction != latest_instruction:
                            continue
                        if r.model_id and r.model_id not in seen:
                            seen.add(r.model_id)
                            model_ids.append(r.model_id)
                if not model_ids:
                    raise ValueError("model_ids required for patch_agent executor")

            for model_id in model_ids:
                # Verify model exists and get model info
                model = await self.model_service.get(model_id)
                if not model:
                    raise ValueError(f"Model not found: {model_id}")

                # Create run record with denormalized model info
                run = await self.run_dao.create(
                    task_id=task_id,
                    instruction=data.instruction,
                    executor_type=ExecutorType.PATCH_AGENT,
                    model_id=model_id,
                    model_name=model.model_name,
                    provider=model.provider,
                    base_ref=data.base_ref or repo.default_branch,
                )
                runs.append(run)

                # Enqueue for execution
                self.queue.enqueue(
                    run.id,
                    lambda r=run, rp=repo: self._execute_patch_agent_run(r, rp),
                )

        return runs

    async def _create_cli_run(
        self,
        task_id: str,
        repo: Any,
        instruction: str,
        base_ref: str,
        executor_type: ExecutorType,
    ) -> Run:
        """Create and start a CLI-based run (Claude Code, Codex, or Gemini).

        This method reuses an existing worktree/branch for the same task and
        executor type to enable conversation continuation in the same working
        directory. Only creates a new worktree if none exists.

        Args:
            task_id: Task ID.
            repo: Repository object.
            instruction: Natural language instruction.
            base_ref: Base branch to work from.
            executor_type: Type of CLI executor to use.

        Returns:
            Created Run object.
        """
        from dursor_api.services.git_service import WorktreeInfo

        # Get the latest session ID for this task and executor type
        # This enables conversation persistence across multiple runs
        previous_session_id = await self.run_dao.get_latest_session_id(
            task_id=task_id,
            executor_type=executor_type,
        )

        # Check for existing worktree to reuse
        existing_run = await self.run_dao.get_latest_worktree_run(
            task_id=task_id,
            executor_type=executor_type,
        )

        worktree_info = None

        if existing_run and existing_run.worktree_path:
            # Verify worktree is still valid (exists and is a valid git repo)
            worktree_path = Path(existing_run.worktree_path)
            if await self.git_service.is_valid_worktree(worktree_path):
                # Reuse existing worktree
                worktree_info = WorktreeInfo(
                    path=worktree_path,
                    branch_name=existing_run.working_branch,
                    base_branch=existing_run.base_ref or base_ref,
                    created_at=existing_run.created_at,
                )
                logger.info(f"Reusing existing worktree: {worktree_path}")
            else:
                logger.warning(f"Worktree invalid or broken, will create new: {worktree_path}")

        # Create the run record
        run = await self.run_dao.create(
            task_id=task_id,
            instruction=instruction,
            executor_type=executor_type,
            base_ref=base_ref,
        )

        if not worktree_info:
            # Create new worktree for this run
            worktree_info = await self.git_service.create_worktree(
                repo=repo,
                base_branch=base_ref,
                run_id=run.id,
            )

        # Update run with worktree info
        await self.run_dao.update_worktree(
            run.id,
            working_branch=worktree_info.branch_name,
            worktree_path=str(worktree_info.path),
        )

        # Update the run object with new info
        run = await self.run_dao.get(run.id)

        # Enqueue for execution based on executor type
        self.queue.enqueue(
            run.id,
            lambda r=run, wt=worktree_info, et=executor_type, ps=previous_session_id, rp=repo: self._execute_cli_run(
                r, wt, et, ps, rp
            ),
        )

        return run

    async def get(self, run_id: str) -> Run | None:
        """Get a run by ID.

        Args:
            run_id: Run ID.

        Returns:
            Run object or None if not found.
        """
        return await self.run_dao.get(run_id)

    async def list(self, task_id: str) -> list[Run]:
        """List runs for a task.

        Args:
            task_id: Task ID.

        Returns:
            List of Run objects.
        """
        return await self.run_dao.list(task_id)

    async def cancel(self, run_id: str) -> bool:
        """Cancel a run.

        Args:
            run_id: Run ID.

        Returns:
            True if cancelled.
        """
        run = await self.run_dao.get(run_id)
        cancelled = self.queue.cancel(run_id)

        if cancelled:
            await self.run_dao.update_status(run_id, RunStatus.CANCELED)

            # Cleanup worktree if it's a CLI executor run
            cli_executors = {
                ExecutorType.CLAUDE_CODE,
                ExecutorType.CODEX_CLI,
                ExecutorType.GEMINI_CLI,
            }
            if run and run.executor_type in cli_executors and run.worktree_path:
                await self.git_service.cleanup_worktree(
                    Path(run.worktree_path),
                    delete_branch=True,
                )

        return cancelled

    async def cleanup_worktree(self, run_id: str) -> bool:
        """Clean up the worktree for a run.

        Args:
            run_id: Run ID.

        Returns:
            True if cleanup was successful.
        """
        run = await self.run_dao.get(run_id)
        if not run or not run.worktree_path:
            return False

        await self.git_service.cleanup_worktree(
            Path(run.worktree_path),
            delete_branch=False,  # Keep branch for PR
        )
        return True

    async def _execute_patch_agent_run(self, run: Run, repo: Any) -> None:
        """Execute a PatchAgent run.

        Args:
            run: Run object.
            repo: Repository object.
        """
        try:
            # Update status to running
            await self.run_dao.update_status(run.id, RunStatus.RUNNING)

            # Create working copy
            workspace_path = self.repo_service.create_working_copy(repo, run.id)

            try:
                # Get API key
                api_key = await self.model_service.get_decrypted_key(run.model_id)
                if not api_key:
                    raise ValueError("API key not found")

                # Create LLM client
                config = LLMConfig(
                    provider=run.provider,
                    model_name=run.model_name,
                    api_key=api_key,
                )
                llm_client = self.llm_router.get_client(config)

                # Create and run agent
                agent = PatchAgent(llm_client)
                request = AgentRequest(
                    workspace_path=str(workspace_path),
                    base_ref=run.base_ref or "HEAD",
                    instruction=run.instruction,
                    constraints=AgentConstraints(),
                )

                result = await agent.run(request)

                # Update run with results
                await self.run_dao.update_status(
                    run.id,
                    RunStatus.SUCCEEDED,
                    summary=result.summary,
                    patch=result.patch,
                    files_changed=result.files_changed,
                    logs=result.logs,
                    warnings=result.warnings,
                )

            finally:
                # Cleanup working copy
                self.repo_service.cleanup_working_copy(run.id)

        except Exception as e:
            # Update status to failed
            await self.run_dao.update_status(
                run.id,
                RunStatus.FAILED,
                error=str(e),
                logs=[f"Execution failed: {str(e)}"],
            )

    async def _execute_cli_run(
        self,
        run: Run,
        worktree_info: Any,
        executor_type: ExecutorType,
        resume_session_id: str | None = None,
        repo: Any = None,
    ) -> None:
        """Execute a CLI-based run with automatic commit/push.

        Following the orchestrator management pattern:
        1. Execute CLI (file editing only)
        2. Stage all changes
        3. Get patch
        4. Commit (automatic)
        5. Push (automatic)
        6. Save results

        Args:
            run: Run object.
            worktree_info: WorktreeInfo object with path and branch info.
            executor_type: Type of CLI executor to use.
            resume_session_id: Optional session ID to resume a previous conversation.
            repo: Repository object for push operations.
        """
        logs: list[str] = []
        commit_sha: str | None = None

        # Map executor types to their executors and names
        executor_map = {
            ExecutorType.CLAUDE_CODE: (self.claude_executor, "Claude Code"),
            ExecutorType.CODEX_CLI: (self.codex_executor, "Codex"),
            ExecutorType.GEMINI_CLI: (self.gemini_executor, "Gemini"),
        }

        executor, executor_name = executor_map[executor_type]

        try:
            # Update status to running
            await self.run_dao.update_status(run.id, RunStatus.RUNNING)
            logger.info(f"[{run.id[:8]}] Starting {executor_name} run")

            # 1. Record pre-execution status
            pre_status = await self.git_service.get_status(worktree_info.path)
            logs.append(f"Pre-execution status: {pre_status.has_changes} changes")

            logs.append(f"Starting {executor_name} execution in {worktree_info.path}")
            logs.append(f"Working branch: {worktree_info.branch_name}")
            # We proactively attempt to resume conversations via session_id when available.
            # If the CLI rejects the session (e.g., "already in use"), we retry once without it.

            # 2. Build instruction with constraints
            constraints = AgentConstraints()
            instruction_with_constraints = f"{constraints.to_prompt()}\n\n## Task\n{run.instruction}"
            logger.info(f"[{run.id[:8]}] Instruction length: {len(instruction_with_constraints)} chars")

            # 3. Execute the CLI (file editing only)
            logger.info(f"[{run.id[:8]}] Executing CLI...")
            attempt_session_id = resume_session_id
            result = await executor.execute(
                worktree_path=worktree_info.path,
                instruction=instruction_with_constraints,
                on_output=lambda line: self._log_output(run.id, line),
                resume_session_id=attempt_session_id,
            )
            if (
                not result.success
                and attempt_session_id
                and result.error
                and ("session" in result.error.lower())
                and ("already in use" in result.error.lower() or "in use" in result.error.lower())
            ):
                # Retry once without session continuation if the CLI rejects the session.
                logs.append(
                    "Session continuation failed (session already in use). Retrying without session_id."
                )
                result = await executor.execute(
                    worktree_path=worktree_info.path,
                    instruction=instruction_with_constraints,
                    on_output=lambda line: self._log_output(run.id, line),
                    resume_session_id=None,
                )
            logger.info(f"[{run.id[:8]}] CLI execution completed: success={result.success}")

            if not result.success:
                await self.run_dao.update_status(
                    run.id,
                    RunStatus.FAILED,
                    error=result.error,
                    logs=logs + result.logs,
                    session_id=result.session_id or resume_session_id,
                )
                return

            # 4. Read and remove summary file (before staging)
            summary_from_file = await self._read_and_remove_summary_file(
                worktree_info.path, logs
            )

            # 5. Stage all changes
            await self.git_service.stage_all(worktree_info.path)

            # 6. Get patch
            patch = await self.git_service.get_diff(worktree_info.path, staged=True)

            # Skip commit/push if no changes
            if not patch.strip():
                logs.append("No changes detected, skipping commit/push")
                await self.run_dao.update_status(
                    run.id,
                    RunStatus.SUCCEEDED,
                    summary="No changes made",
                    patch="",
                    files_changed=[],
                    logs=logs + result.logs,
                    session_id=result.session_id or resume_session_id,
                )
                return

            # Parse diff to get file changes
            files_changed = self._parse_diff(patch)
            logs.append(f"Detected {len(files_changed)} changed file(s)")

            # Determine final summary (priority: file > CLI output > generated)
            final_summary = (
                summary_from_file
                or result.summary
                or self._generate_summary(files_changed)
            )

            # 7. Commit (automatic)
            commit_message = self._generate_commit_message(run.instruction, final_summary)
            commit_sha = await self.git_service.commit(
                worktree_info.path,
                message=commit_message,
            )
            logs.append(f"Committed: {commit_sha[:8]}")

            # 8. Push (automatic) - only if we have GitHub service configured
            if self.github_service and repo:
                try:
                    owner, repo_name = self._parse_github_url(repo.repo_url)
                    auth_url = await self.github_service.get_auth_url(owner, repo_name)
                    await self.git_service.push(
                        worktree_info.path,
                        branch=worktree_info.branch_name,
                        auth_url=auth_url,
                    )
                    logs.append(f"Pushed to branch: {worktree_info.branch_name}")
                except Exception as push_error:
                    logs.append(f"Push failed (will retry on PR creation): {push_error}")
                    # Continue without failing - push can be retried during PR creation

            # 9. Save results
            await self.run_dao.update_status(
                run.id,
                RunStatus.SUCCEEDED,
                summary=final_summary,
                patch=patch,
                files_changed=files_changed,
                logs=logs + result.logs,
                warnings=result.warnings,
                session_id=result.session_id or resume_session_id,
                commit_sha=commit_sha,
            )

        except Exception as e:
            # Update status to failed
            await self.run_dao.update_status(
                run.id,
                RunStatus.FAILED,
                error=str(e),
                logs=logs + [f"Execution failed: {str(e)}"],
                commit_sha=commit_sha,
            )

        finally:
            # Mark output stream as complete for SSE subscribers
            if self.output_manager:
                await self.output_manager.mark_complete(run.id)

    async def _read_and_remove_summary_file(
        self,
        worktree_path: Path,
        logs: list[str],
    ) -> str | None:
        """Read summary from the agent-generated summary file and remove it.

        The summary file is created by the agent at the end of execution.
        We read it before staging to use as the run summary, then delete it
        so it's not included in the commit.

        Args:
            worktree_path: Path to the worktree.
            logs: Log list to append to.

        Returns:
            Summary text if file exists, None otherwise.
        """
        summary_file = worktree_path / SUMMARY_FILE_PATH
        summary: str | None = None

        try:
            if summary_file.exists():
                summary = summary_file.read_text(encoding="utf-8").strip()
                logs.append(f"Read summary from {SUMMARY_FILE_PATH}")

                # Remove the file so it's not committed
                summary_file.unlink()
                logs.append(f"Removed {SUMMARY_FILE_PATH}")

                # Clean up empty summary
                if not summary:
                    summary = None
        except Exception as e:
            logs.append(f"Warning: Could not read summary file: {e}")

        return summary

    async def _log_output(self, run_id: str, line: str) -> None:
        """Log output from CLI execution.

        This logs output to console for debugging and publishes to
        OutputManager for SSE streaming to connected clients.

        Args:
            run_id: Run ID.
            line: Output line.
        """
        # Log to console for debugging
        logger.info(f"[{run_id[:8]}] {line}")

        # Publish to OutputManager for SSE streaming
        # Use await to ensure immediate delivery to subscribers
        if self.output_manager:
            await self.output_manager.publish_async(run_id, line)
        else:
            logger.warning(f"[{run_id[:8]}] OutputManager not available, cannot publish")

    def _generate_commit_message(self, instruction: str, summary: str | None) -> str:
        """Generate a commit message from instruction and summary.

        Args:
            instruction: Original user instruction.
            summary: Optional summary from executor.

        Returns:
            Commit message string.
        """
        # Use first line of instruction (truncate if too long)
        first_line = instruction.split("\n")[0][:72]
        if summary:
            return f"{first_line}\n\n{summary}"
        return first_line

    def _parse_diff(self, diff: str) -> list[FileDiff]:
        """Parse unified diff to extract file change information.

        Args:
            diff: Unified diff string.

        Returns:
            List of FileDiff objects.
        """
        files: list[FileDiff] = []
        current_file: str | None = None
        current_patch_lines: list[str] = []
        added_lines = 0
        removed_lines = 0

        for line in diff.split("\n"):
            if line.startswith("--- a/"):
                # Save previous file if exists
                if current_file:
                    files.append(FileDiff(
                        path=current_file,
                        added_lines=added_lines,
                        removed_lines=removed_lines,
                        patch="\n".join(current_patch_lines),
                    ))
                # Reset for new file
                current_patch_lines = [line]
                added_lines = 0
                removed_lines = 0
            elif line.startswith("+++ b/"):
                current_file = line[6:]
                current_patch_lines.append(line)
            elif line.startswith("--- /dev/null"):
                # New file
                current_patch_lines = [line]
                added_lines = 0
                removed_lines = 0
            elif line.startswith("+++ b/") and current_file is None:
                # New file path
                current_file = line[6:]
                current_patch_lines.append(line)
            elif current_file:
                current_patch_lines.append(line)
                if line.startswith("+") and not line.startswith("+++"):
                    added_lines += 1
                elif line.startswith("-") and not line.startswith("---"):
                    removed_lines += 1

        # Save last file
        if current_file:
            files.append(FileDiff(
                path=current_file,
                added_lines=added_lines,
                removed_lines=removed_lines,
                patch="\n".join(current_patch_lines),
            ))

        return files

    def _parse_github_url(self, repo_url: str) -> tuple[str, str]:
        """Parse GitHub URL to extract owner and repo name.

        Args:
            repo_url: GitHub repository URL.

        Returns:
            Tuple of (owner, repo_name).

        Raises:
            ValueError: If URL cannot be parsed.
        """
        # Handle various URL formats:
        # - https://github.com/owner/repo.git
        # - https://github.com/owner/repo
        # - git@github.com:owner/repo.git
        patterns = [
            r"github\.com[:/]([^/]+)/([^/.]+)(?:\.git)?$",
        ]
        for pattern in patterns:
            match = re.search(pattern, repo_url)
            if match:
                return match.group(1), match.group(2)
        raise ValueError(f"Could not parse GitHub URL: {repo_url}")

    def _generate_summary(self, files_changed: list[FileDiff]) -> str:
        """Generate a human-readable summary of changes.

        Args:
            files_changed: List of changed files.

        Returns:
            Summary string.
        """
        if not files_changed:
            return "No files were modified."

        total_added = sum(f.added_lines for f in files_changed)
        total_removed = sum(f.removed_lines for f in files_changed)

        summary_parts = [
            f"Modified {len(files_changed)} file(s)",
            f"+{total_added} -{total_removed} lines",
        ]

        # List files
        file_list = ", ".join(f.path for f in files_changed[:5])
        if len(files_changed) > 5:
            file_list += f" and {len(files_changed) - 5} more"

        summary_parts.append(f"Files: {file_list}")

        return ". ".join(summary_parts) + "."
