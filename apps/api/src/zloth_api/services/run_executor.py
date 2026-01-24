"""Run execution helper (extracted from RunService).

This module encapsulates the CLI-based run execution flow to reduce the
responsibilities of RunService (God Class mitigation). It handles:
- Remote sync checks and conflict handling
- CLI execution with session retry logic
- Staging, diff parsing, commit and push
- Status updates and streaming logs
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zloth_api.agents.llm_router import LLMRouter
from zloth_api.domain.enums import ExecutorType, RunStatus
from zloth_api.domain.models import SUMMARY_FILE_PATH, FileDiff, Run
from zloth_api.executors.claude_code_executor import ClaudeCodeExecutor
from zloth_api.executors.codex_executor import CodexExecutor
from zloth_api.executors.gemini_executor import GeminiExecutor
from zloth_api.services.commit_message import ensure_english_commit_message
from zloth_api.services.diff_parser import parse_unified_diff
from zloth_api.services.git_service import GitService
from zloth_api.services.workspace_adapters import ExecutionWorkspaceInfo, WorkspaceAdapter
from zloth_api.storage.dao import RunDAO
from zloth_api.utils.github_url import parse_github_owner_repo

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    # Imported for type checking only to avoid runtime cycles
    from zloth_api.services.github_service import GitHubService
    from zloth_api.services.output_manager import OutputManager


@dataclass
class ExecutorEntry:
    executor: ClaudeCodeExecutor | CodexExecutor | GeminiExecutor
    name: str


class RunExecutor:
    """Encapsulates CLI run execution steps.

    Dependencies are passed in to keep this class reusable and easy to test.
    """

    def __init__(
        self,
        *,
        run_dao: RunDAO,
        git_service: GitService,
        workspace_adapter: WorkspaceAdapter,
        executors: dict[ExecutorType, ExecutorEntry],
        llm_router: LLMRouter | None = None,
        output_manager: OutputManager | None = None,
        github_service: GitHubService | None = None,
    ) -> None:
        self._run_dao = run_dao
        self._git = git_service
        self._ws = workspace_adapter
        self._executors = executors
        self._llm_router = llm_router or LLMRouter()
        self._out = output_manager
        self._gh = github_service

    async def execute_cli_run(
        self,
        *,
        run: Run,
        worktree: ExecutionWorkspaceInfo,
        executor_type: ExecutorType,
        repo: Any | None,
        resume_session_id: str | None,
    ) -> None:
        """Execute the CLI run and persist results to the database."""
        logs: list[str] = []
        commit_sha: str | None = None

        entry = self._executors[executor_type]
        executor = entry.executor
        executor_name = entry.name

        conflict_instruction: str | None = None

        try:
            await self._run_dao.update_status(run.id, RunStatus.RUNNING)
            logger.info("[%s] Starting %s run", run.id[:8], executor_name)
            await self._log_output(run.id, f"Starting {executor_name} execution...")

            # 0. Sync with remote if behind
            if self._gh and repo:
                try:
                    await self._log_output(run.id, "Checking for remote updates...")
                    owner, repo_name = parse_github_owner_repo(repo.repo_url)
                    auth_url = await self._gh.get_auth_url(owner, repo_name)

                    is_behind = await self._ws.is_behind_remote(
                        worktree.path,
                        branch=worktree.branch_name,
                        auth_url=auth_url,
                    )
                    if is_behind:
                        logs.append("Detected remote updates, pulling latest changes...")
                        sync_result = await self._ws.sync_with_remote(
                            worktree.path,
                            branch=worktree.branch_name,
                            auth_url=auth_url,
                        )
                        if sync_result.success:
                            logs.append("Successfully pulled latest changes from remote")
                        elif sync_result.has_conflicts:
                            files_str = ", ".join(sync_result.conflict_files)
                            logs.append(f"Merge conflicts detected in: {files_str}.")
                            logs.append("AI will be asked to resolve them.")
                            conflict_instruction = self._build_conflict_instruction(
                                sync_result.conflict_files
                            )
                        else:
                            logs.append(f"Pull failed: {sync_result.error}")
                except Exception as sync_error:
                    logs.append(f"Remote sync warning: {sync_error}")

            # 1. Record pre-status
            pre_status = await self._git.get_status(worktree.path)
            logs.append(f"Pre-execution status: {pre_status.has_changes} changes")
            logs.append(f"Working branch: {worktree.branch_name}")

            # 2. Build instruction
            from zloth_api.domain.models import AgentConstraints  # local import to avoid cycle

            constraints = AgentConstraints()
            if conflict_instruction:
                instruction = (
                    f"{constraints.to_prompt()}\n\n"
                    f"{conflict_instruction}\n\n"
                    f"## Task\n{run.instruction}"
                )
            else:
                instruction = (
                    f"{constraints.to_prompt()}\n\n"
                    f"## Task\n{run.instruction}"
                )

            # 3. Execute CLI
            await self._log_output(run.id, f"Launching {executor_name} CLI...")
            attempt_session_id = resume_session_id
            result = await executor.execute(
                worktree_path=worktree.path,
                instruction=instruction,
                on_output=lambda line: self._log_output(run.id, line),
                resume_session_id=attempt_session_id,
            )

            # Retry once without session_id on session-specific errors
            session_error_patterns = [
                "already in use",
                "in use",
                "no conversation found",
                "not found",
                "invalid session",
                "session expired",
            ]
            if (
                not result.success
                and attempt_session_id
                and result.error
                and ("session" in result.error.lower())
                and any(p in result.error.lower() for p in session_error_patterns)
            ):
                logs.append(
                    f"Session continuation failed ({result.error}). Retrying without session_id."
                )
                result = await executor.execute(
                    worktree_path=worktree.path,
                    instruction=instruction,
                    on_output=lambda line: self._log_output(run.id, line),
                    resume_session_id=None,
                )

            if not result.success:
                await self._run_dao.update_status(
                    run.id,
                    RunStatus.FAILED,
                    error=result.error,
                    logs=logs + result.logs,
                    session_id=result.session_id or resume_session_id,
                )
                return

            # 4. Read and remove summary file
            summary_from_file = await self._read_and_remove_summary_file(worktree.path, logs)

            # 5. Stage all changes
            await self._ws.stage_all(worktree.path)

            # 6. Get patch
            patch = await self._ws.get_diff(worktree.path, staged=True)
            if not patch.strip():
                logs.append("No changes detected, skipping commit/push")
                await self._run_dao.update_status(
                    run.id,
                    RunStatus.SUCCEEDED,
                    summary="No changes made",
                    patch="",
                    files_changed=[],
                    logs=logs + result.logs,
                    session_id=result.session_id or resume_session_id,
                )
                return

            # Parse diff
            files_changed = parse_unified_diff(patch)
            logs.append(f"Detected {len(files_changed)} changed file(s)")

            # 7. Commit
            final_summary = summary_from_file or result.summary or self._summarize_files(
                files_changed
            )
            message = self._generate_commit_message(run.instruction, final_summary)
            message = await ensure_english_commit_message(
                message, llm_router=self._llm_router, hint=final_summary or ""
            )
            commit_sha = await self._ws.commit(worktree.path, message=message)
            logs.append(f"Committed: {commit_sha[:8]}")

            # 8. Push
            if self._gh and repo:
                owner, repo_name = parse_github_owner_repo(repo.repo_url)
                auth_url = await self._gh.get_auth_url(owner, repo_name)
                push_result = await self._ws.push(
                    worktree.path,
                    branch=worktree.branch_name,
                    auth_url=auth_url,
                )
                if push_result.success:
                    if push_result.required_pull:
                        logs.append(
                            f"Pulled remote changes and pushed to branch: {worktree.branch_name}"
                        )
                    else:
                        logs.append(f"Pushed to branch: {worktree.branch_name}")
                else:
                    logs.append(f"Push failed (will retry on PR creation): {push_result.error}")

            # 9. Persist results
            await self._run_dao.update_status(
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

        except asyncio.CancelledError:
            logger.warning("[%s] CLI run was cancelled", run.id[:8])
            await self._run_dao.update_status(
                run.id,
                RunStatus.FAILED,
                error="Task was cancelled (timeout or user cancellation)",
                logs=logs + ["Execution cancelled"],
                commit_sha=commit_sha,
            )
            raise
        except Exception as e:
            await self._run_dao.update_status(
                run.id,
                RunStatus.FAILED,
                error=str(e),
                logs=logs + [f"Execution failed: {str(e)}"],
                commit_sha=commit_sha,
            )
        finally:
            if self._out:
                await self._out.mark_complete(run.id)

    async def _read_and_remove_summary_file(
        self, worktree_path: Path, logs: list[str]
    ) -> str | None:
        """Read summary from agent summary file, then delete it."""
        summary_file = worktree_path / SUMMARY_FILE_PATH
        summary: str | None = None
        try:
            if summary_file.exists():
                summary = summary_file.read_text(encoding="utf-8").strip()
                logs.append(f"Read summary from {SUMMARY_FILE_PATH}")
                summary_file.unlink()
                logs.append(f"Removed {SUMMARY_FILE_PATH}")
                if not summary:
                    summary = None
        except Exception as e:
            logs.append(f"Warning: Could not read summary file: {e}")
        return summary

    async def _log_output(self, run_id: str, line: str) -> None:
        logger.info("[%s] %s", run_id[:8], line)
        if self._out:
            await self._out.publish_async(run_id, line)

    def _generate_commit_message(self, instruction: str, summary: str | None) -> str:
        first_line = instruction.split("\n")[0][:72]
        if summary:
            return f"{first_line}\n\n{summary}"
        return first_line

    def _summarize_files(self, files_changed: list[FileDiff]) -> str:
        if not files_changed:
            return "No files were modified."
        total_added = sum(f.added_lines for f in files_changed)
        total_removed = sum(f.removed_lines for f in files_changed)
        parts = [
            f"Modified {len(files_changed)} file(s)",
            f"+{total_added} -{total_removed} lines",
        ]
        file_list = ", ".join(f.path for f in files_changed[:5])
        if len(files_changed) > 5:
            file_list += f" and {len(files_changed) - 5} more"
        parts.append(f"Files: {file_list}")
        return ". ".join(parts) + "."

    def _build_conflict_instruction(self, conflict_files: list[str]) -> str:
        files_list = "\n".join(f"- {f}" for f in conflict_files)
        return f"""## IMPORTANT: Merge Conflict Resolution Required

The following files have merge conflicts that MUST be resolved before proceeding with the task:

{files_list}

### Instructions for Conflict Resolution:
1. Open each conflicted file listed above
2. Look for conflict markers: `<<<<<<<`, `=======`, and `>>>>>>>`
3. Understand both versions of the conflicting code
4. Resolve each conflict by keeping the correct code (you may combine both versions if appropriate)
5. Remove ALL conflict markers completely
6. Ensure the resolved code is syntactically correct and functional

### Conflict Marker Format:
```
<<<<<<< HEAD
(your local changes)
=======
(incoming changes from remote)
>>>>>>> branch-name
```

After resolving ALL conflicts, proceed with the original task below.
"""
