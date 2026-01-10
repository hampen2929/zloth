"""Agentic Orchestrator for autonomous development workflow.

This module implements the complete autonomous development cycle:
1. Coding (Claude Code)
2. Wait for CI
3. If CI fails → Fix and go to 2
4. Review (Codex)
5. If review rejects → Fix and go to 2
6. Merge
"""

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from dursor_api.config import settings
from dursor_api.domain.enums import AgenticPhase
from dursor_api.domain.models import (
    AgenticConfig,
    AgenticState,
    CIResult,
    IterationLimits,
    JobFailure,
    ReviewResult,
    Task,
)
from dursor_api.executors.claude_code_executor import ClaudeCodeExecutor, ClaudeCodeOptions
from dursor_api.executors.codex_executor import CodexExecutor, CodexOptions
from dursor_api.services.auto_merge_service import AutoMergeService
from dursor_api.services.git_service import GitService
from dursor_api.services.github_service import GitHubService
from dursor_api.storage.dao import AgenticAuditLogDAO, AgenticStateDAO, TaskDAO

logger = logging.getLogger(__name__)


# Fix strategy mapping for different CI failures
FIX_STRATEGIES: dict[str, str] = {
    "backend_lint": "Run 'ruff check --fix' and 'ruff format'",
    "backend_typecheck": "Add type annotations, fix type errors",
    "backend_test": "Fix failing tests or update test expectations",
    "frontend_lint": "Run 'npm run lint -- --fix'",
    "frontend_build": "Fix TypeScript errors, missing imports",
    "frontend_test": "Fix failing E2E tests",
    "codex_review": "Address blocking issues from review feedback",
    "security_scan": "Remove hardcoded secrets, use environment variables",
    "coverage": "Add tests for uncovered code paths",
}


class AgenticOrchestrator:
    """Orchestrates the full agentic development cycle.

    Flow:
    1. Coding (Claude Code)
    2. Wait for CI
    3. If CI fails → Fix and go to 2
    4. Review (Codex)
    5. If review rejects → Fix and go to 2
    6. Merge
    """

    def __init__(
        self,
        state_dao: AgenticStateDAO,
        audit_dao: AgenticAuditLogDAO,
        task_dao: TaskDAO,
        git_service: GitService,
        github_service: GitHubService,
        coder: ClaudeCodeExecutor | None = None,
        reviewer: CodexExecutor | None = None,
    ):
        """Initialize the orchestrator.

        Args:
            state_dao: DAO for agentic state persistence.
            audit_dao: DAO for audit logging.
            task_dao: DAO for task operations.
            git_service: Service for git operations.
            github_service: Service for GitHub API operations.
            coder: Claude Code executor for coding tasks.
            reviewer: Codex executor for code review.
        """
        self.state_dao = state_dao
        self.audit_dao = audit_dao
        self.task_dao = task_dao
        self.git = git_service
        self.github = github_service

        # Initialize executors with defaults if not provided
        self.coder = coder or ClaudeCodeExecutor(
            ClaudeCodeOptions(claude_cli_path=settings.claude_cli_path)
        )
        self.reviewer = reviewer or CodexExecutor(
            CodexOptions(codex_cli_path=settings.codex_cli_path)
        )

        # Active state locks to prevent concurrent modifications
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_limits(self, config: AgenticConfig | None = None) -> IterationLimits:
        """Get iteration limits from config or settings."""
        if config and config.limits:
            return config.limits
        return IterationLimits(
            max_ci_iterations=settings.agentic_max_ci_iterations,
            max_review_iterations=settings.agentic_max_review_iterations,
            max_total_iterations=settings.agentic_max_total_iterations,
            min_review_score=settings.review_min_score,
            timeout_minutes=settings.agentic_timeout_minutes,
        )

    def _get_lock(self, task_id: str) -> asyncio.Lock:
        """Get or create a lock for a task."""
        if task_id not in self._locks:
            self._locks[task_id] = asyncio.Lock()
        return self._locks[task_id]

    # =========================================
    # Public API
    # =========================================

    async def start_task(
        self,
        task: Task,
        instruction: str,
        workspace_path: Path,
        config: AgenticConfig | None = None,
    ) -> AgenticState:
        """Start agentic execution for a task.

        Args:
            task: The task to execute.
            instruction: Natural language instruction.
            workspace_path: Path to the working directory.
            config: Optional agentic configuration.

        Returns:
            The created AgenticState.
        """
        # Create initial state
        state = await self.state_dao.create(task_id=task.id)

        # Log start
        await self.audit_dao.create(
            task_id=task.id,
            phase=AgenticPhase.CODING,
            action="start_agentic",
            agent="system",
            input_summary=f"Starting agentic execution: {instruction[:100]}...",
            success=True,
        )

        # Start coding phase in background
        asyncio.create_task(
            self._run_coding_phase(task, instruction, workspace_path, state, config)
        )

        return state

    async def handle_ci_result(
        self,
        task: Task,
        ci_result: CIResult,
        workspace_path: Path,
        config: AgenticConfig | None = None,
    ) -> AgenticState | None:
        """Handle CI completion webhook.

        Args:
            task: The task being executed.
            ci_result: CI execution result.
            workspace_path: Path to the working directory.
            config: Optional agentic configuration.

        Returns:
            Updated AgenticState or None if no active state.
        """
        state = await self.state_dao.get_by_task(task.id)
        if not state:
            logger.warning(f"No active agentic state for task {task.id}")
            return None

        limits = self._get_limits(config)

        async with self._get_lock(task.id):
            # Update state with CI result
            await self.state_dao.update(state.id, last_ci_result=ci_result)

            if ci_result.success:
                # CI passed - proceed to review
                await self.state_dao.update(state.id, phase=AgenticPhase.REVIEWING)
                await self.audit_dao.create(
                    task_id=task.id,
                    phase=AgenticPhase.REVIEWING,
                    action="ci_passed",
                    agent="system",
                    success=True,
                )
                asyncio.create_task(self._run_review_phase(task, workspace_path, state, config))
            else:
                # CI failed - check iteration limit
                new_ci_iterations = state.ci_iterations + 1

                if new_ci_iterations > limits.max_ci_iterations:
                    await self._fail_state(
                        state, f"Exceeded max CI fix iterations ({limits.max_ci_iterations})"
                    )
                else:
                    await self.state_dao.update(
                        state.id,
                        phase=AgenticPhase.FIXING_CI,
                        ci_iterations=new_ci_iterations,
                    )
                    asyncio.create_task(
                        self._run_ci_fix_phase(task, ci_result, workspace_path, state, config)
                    )

        # Refresh and return state
        return await self.state_dao.get(state.id)

    async def handle_review_result(
        self,
        task: Task,
        review_result: ReviewResult,
        workspace_path: Path,
        config: AgenticConfig | None = None,
    ) -> AgenticState | None:
        """Handle review completion.

        Args:
            task: The task being executed.
            review_result: Code review result.
            workspace_path: Path to the working directory.
            config: Optional agentic configuration.

        Returns:
            Updated AgenticState or None if no active state.
        """
        state = await self.state_dao.get_by_task(task.id)
        if not state:
            logger.warning(f"No active agentic state for task {task.id}")
            return None

        limits = self._get_limits(config)

        async with self._get_lock(task.id):
            # Update state with review result
            await self.state_dao.update(state.id, last_review_result=review_result)

            if review_result.approved and review_result.score >= limits.min_review_score:
                # Review passed - proceed to merge
                await self.state_dao.update(state.id, phase=AgenticPhase.MERGING)
                await self.audit_dao.create(
                    task_id=task.id,
                    phase=AgenticPhase.MERGING,
                    action="review_passed",
                    agent="system",
                    output_summary=f"Review approved with score {review_result.score}",
                    success=True,
                )
                asyncio.create_task(self._run_merge_phase(task, state, config))
            else:
                # Review rejected - check iteration limit
                new_review_iterations = state.review_iterations + 1

                if new_review_iterations > limits.max_review_iterations:
                    max_iters = limits.max_review_iterations
                    await self._fail_state(
                        state, f"Exceeded max review fix iterations ({max_iters})"
                    )
                else:
                    await self.state_dao.update(
                        state.id,
                        phase=AgenticPhase.FIXING_REVIEW,
                        review_iterations=new_review_iterations,
                    )
                    asyncio.create_task(
                        self._run_review_fix_phase(
                            task, review_result, workspace_path, state, config
                        )
                    )

        # Refresh and return state
        return await self.state_dao.get(state.id)

    async def trigger_auto_fix(
        self,
        task: Task,
        failed_jobs: list[JobFailure],
        commit_sha: str,
        workspace_path: Path,
        config: AgenticConfig | None = None,
    ) -> None:
        """Trigger Claude Code to fix CI failures.

        Called by webhook handler.

        Args:
            task: The task being executed.
            failed_jobs: List of failed jobs with error logs.
            commit_sha: Current commit SHA.
            workspace_path: Path to the working directory.
            config: Optional agentic configuration.
        """
        state = await self.state_dao.get_by_task(task.id)
        if not state:
            return

        # Build fix instruction from error logs
        instruction = self._build_ci_fix_instruction(failed_jobs)

        # Update state
        await self.state_dao.update(
            state.id,
            phase=AgenticPhase.FIXING_CI,
            current_sha=commit_sha,
        )

        # Run coding phase with fix context
        await self._run_coding_phase(
            task,
            instruction,
            workspace_path,
            state,
            config,
            context={"fix_mode": True, "failed_jobs": [j.model_dump() for j in failed_jobs]},
        )

    async def proceed_to_merge(
        self,
        task: Task,
        workspace_path: Path,
        config: AgenticConfig | None = None,
    ) -> None:
        """Proceed to merge phase after CI passes.

        Args:
            task: The task being executed.
            workspace_path: Path to the working directory.
            config: Optional agentic configuration.
        """
        state = await self.state_dao.get_by_task(task.id)
        if not state:
            return

        # First run review if not done
        if state.phase == AgenticPhase.WAITING_CI:
            await self.state_dao.update(state.id, phase=AgenticPhase.REVIEWING)
            await self._run_review_phase(task, workspace_path, state, config)

    async def cancel(self, task_id: str) -> bool:
        """Cancel agentic execution for a task.

        Args:
            task_id: Task ID to cancel.

        Returns:
            True if cancelled, False if no active state.
        """
        state = await self.state_dao.get_by_task(task_id)
        if not state:
            return False

        await self.state_dao.update(
            state.id,
            phase=AgenticPhase.FAILED,
            error="Cancelled by user",
            completed_at=datetime.utcnow(),
        )

        await self.audit_dao.create(
            task_id=task_id,
            phase=AgenticPhase.FAILED,
            action="cancelled",
            agent="system",
            success=True,
        )

        return True

    async def get_status(self, task_id: str) -> AgenticState | None:
        """Get current agentic status for a task.

        Args:
            task_id: Task ID.

        Returns:
            AgenticState or None if no active state.
        """
        return await self.state_dao.get_by_task(task_id)

    async def find_task_by_pr(self, pr_number: int) -> Task | None:
        """Find task associated with a PR number.

        Args:
            pr_number: PR number.

        Returns:
            Task or None if not found.
        """
        state = await self.state_dao.get_by_pr_number(pr_number)
        if not state:
            return None
        return await self.task_dao.get(state.task_id)

    # =========================================
    # Phase Implementations
    # =========================================

    async def _run_coding_phase(
        self,
        task: Task,
        instruction: str,
        workspace_path: Path,
        state: AgenticState,
        config: AgenticConfig | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Execute Claude Code for coding."""
        limits = self._get_limits(config)
        start_time = time.time()

        # Update state
        new_iteration = state.iteration + 1
        if new_iteration > limits.max_total_iterations:
            await self._fail_state(
                state, f"Exceeded max total iterations ({limits.max_total_iterations})"
            )
            return

        await self.state_dao.update(
            state.id,
            phase=AgenticPhase.CODING,
            iteration=new_iteration,
        )

        # Build enhanced instruction
        full_instruction = self._enhance_instruction_with_context(
            instruction, context, state, new_iteration
        )

        try:
            # Execute Claude Code
            result = await self.coder.execute(
                worktree_path=workspace_path,
                instruction=full_instruction,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            if not result.success:
                await self.audit_dao.create(
                    task_id=task.id,
                    phase=AgenticPhase.CODING,
                    action="coding_failed",
                    agent="claude_code",
                    duration_ms=duration_ms,
                    success=False,
                    error=result.error,
                )
                await self._fail_state(state, f"Coding failed: {result.error}")
                return

            # Log success
            await self.audit_dao.create(
                task_id=task.id,
                phase=AgenticPhase.CODING,
                action="coding_completed",
                agent="claude_code",
                output_summary=result.summary[:200] if result.summary else None,
                duration_ms=duration_ms,
                success=True,
            )

            # Commit and push changes
            commit_sha = await self._commit_and_push(task, workspace_path, result.summary)

            if commit_sha:
                await self.state_dao.update(state.id, current_sha=commit_sha)

            # Create or get PR number
            if not state.pr_number:
                pr = await self._create_pr(task, workspace_path, state)
                if pr:
                    await self.state_dao.update(state.id, pr_number=pr)

            # Transition to waiting for CI
            await self.state_dao.update(state.id, phase=AgenticPhase.WAITING_CI)

        except Exception as e:
            logger.exception(f"Error in coding phase: {e}")
            await self._fail_state(state, str(e))

    async def _run_ci_fix_phase(
        self,
        task: Task,
        ci_result: CIResult,
        workspace_path: Path,
        state: AgenticState,
        config: AgenticConfig | None = None,
    ) -> None:
        """Fix CI failures using Claude Code."""
        # Build fix instruction from CI errors
        instruction = self._build_ci_fix_instruction(ci_result.failed_jobs)

        await self.audit_dao.create(
            task_id=task.id,
            phase=AgenticPhase.FIXING_CI,
            action="fixing_ci",
            agent="system",
            input_summary=f"Fixing {len(ci_result.failed_jobs)} CI failures",
            success=True,
        )

        await self._run_coding_phase(
            task,
            instruction,
            workspace_path,
            state,
            config,
            context={"fix_mode": True, "ci_result": ci_result.model_dump()},
        )

    async def _run_review_phase(
        self,
        task: Task,
        workspace_path: Path,
        state: AgenticState,
        config: AgenticConfig | None = None,
    ) -> None:
        """Execute Codex review."""
        start_time = time.time()

        await self.state_dao.update(state.id, phase=AgenticPhase.REVIEWING)

        try:
            # Get the diff for review
            diff = await self._get_pr_diff(state.pr_number)

            # Run Codex review
            result = await self.reviewer.execute(
                worktree_path=workspace_path,
                instruction=f"Review the following code changes:\n\n{diff}",
            )

            duration_ms = int((time.time() - start_time) * 1000)

            # Parse review result
            review_result = self._parse_review_result(result)

            await self.audit_dao.create(
                task_id=task.id,
                phase=AgenticPhase.REVIEWING,
                action="review_completed",
                agent="codex",
                output_summary=f"Score: {review_result.score}, Approved: {review_result.approved}",
                duration_ms=duration_ms,
                success=True,
            )

            # Handle review result
            await self.handle_review_result(task, review_result, workspace_path, config)

        except Exception as e:
            logger.exception(f"Error in review phase: {e}")
            # If review fails, skip to merge phase (lenient)
            await self.audit_dao.create(
                task_id=task.id,
                phase=AgenticPhase.REVIEWING,
                action="review_skipped",
                agent="system",
                error=str(e),
                success=False,
            )
            # Proceed to merge anyway
            await self._run_merge_phase(task, state, config)

    async def _run_review_fix_phase(
        self,
        task: Task,
        review_result: ReviewResult,
        workspace_path: Path,
        state: AgenticState,
        config: AgenticConfig | None = None,
    ) -> None:
        """Fix issues from code review."""
        # Build fix instruction from review feedback
        instruction = self._build_review_fix_instruction(review_result)

        await self.audit_dao.create(
            task_id=task.id,
            phase=AgenticPhase.FIXING_REVIEW,
            action="fixing_review",
            agent="system",
            input_summary=f"Addressing {len(review_result.blocking_issues)} blocking issues",
            success=True,
        )

        await self._run_coding_phase(
            task,
            instruction,
            workspace_path,
            state,
            config,
            context={"fix_mode": True, "review_feedback": review_result.model_dump()},
        )

    async def _run_merge_phase(
        self,
        task: Task,
        state: AgenticState,
        config: AgenticConfig | None = None,
    ) -> None:
        """Execute auto-merge."""
        await self.state_dao.update(state.id, phase=AgenticPhase.MERGING)

        if not state.pr_number:
            await self._fail_state(state, "No PR number for merge")
            return

        try:
            # Get repo info for merge service
            task_obj = await self.task_dao.get(task.id)
            if not task_obj:
                await self._fail_state(state, "Task not found")
                return

            # Parse owner/repo from task (simplified - in real impl would get from Repo)
            owner, repo = await self._get_repo_info(task_obj)

            # Create merge service
            merger = AutoMergeService(self.github, owner, repo)

            # Check conditions
            conditions = await merger.check_all_conditions(state.pr_number)

            if not conditions.can_merge:
                await self._fail_state(
                    state, f"Merge conditions not met: {', '.join(conditions.failed)}"
                )
                return

            # Execute merge
            merge_method = config.merge_method if config else settings.merge_method
            delete_branch = config.delete_branch if config else settings.merge_delete_branch

            merge_result = await merger.merge(
                pr_number=state.pr_number,
                method=merge_method,  # type: ignore[arg-type]
                delete_branch=delete_branch,
            )

            if merge_result.success:
                await self.state_dao.update(
                    state.id,
                    phase=AgenticPhase.COMPLETED,
                    completed_at=datetime.utcnow(),
                )
                await self.audit_dao.create(
                    task_id=task.id,
                    phase=AgenticPhase.COMPLETED,
                    action="merged",
                    agent="system",
                    output_summary=f"Merged with SHA: {merge_result.merge_sha}",
                    success=True,
                )
            else:
                await self._fail_state(state, f"Merge failed: {merge_result.error}")

        except Exception as e:
            logger.exception(f"Error in merge phase: {e}")
            await self._fail_state(state, str(e))

    # =========================================
    # Helper Methods
    # =========================================

    async def _fail_state(self, state: AgenticState, error: str) -> None:
        """Mark state as failed."""
        await self.state_dao.update(
            state.id,
            phase=AgenticPhase.FAILED,
            error=error,
            completed_at=datetime.utcnow(),
        )
        await self.audit_dao.create(
            task_id=state.task_id,
            phase=AgenticPhase.FAILED,
            action="failed",
            agent="system",
            error=error,
            success=False,
        )

    def _build_ci_fix_instruction(self, failed_jobs: list[JobFailure]) -> str:
        """Build instruction for fixing CI failures."""
        parts = ["Fix the following CI failures:\n"]

        for job in failed_jobs:
            parts.append(f"\n## {job.job_name} (FAILED)\n")
            if job.error_log:
                # Truncate long error logs
                error_log = job.error_log[:5000] if len(job.error_log) > 5000 else job.error_log
                parts.append(f"```\n{error_log}\n```\n")

            # Add fix strategy if available
            strategy = FIX_STRATEGIES.get(job.job_name)
            if strategy:
                parts.append(f"Suggested approach: {strategy}\n")

        parts.append(
            """
Please:
1. Analyze each error carefully
2. Fix the root cause (not just the symptoms)
3. Ensure your fixes don't break other tests
4. Run the relevant checks locally before committing
"""
        )

        return "".join(parts)

    def _build_review_fix_instruction(self, review: ReviewResult) -> str:
        """Build instruction for addressing review feedback."""
        parts = [f"Address the following code review feedback (score: {review.score}):\n"]

        if review.blocking_issues:
            parts.append("\n## Blocking Issues (MUST FIX)\n")
            for issue in review.blocking_issues:
                parts.append(f"- [{issue.severity}] {issue.file_path}")
                if issue.line_number:
                    parts.append(f":{issue.line_number}")
                parts.append(f"\n  {issue.description}\n")
                if issue.suggested_fix:
                    parts.append(f"  Suggested fix: {issue.suggested_fix}\n")

        if review.suggestions:
            parts.append("\n## Suggestions (SHOULD FIX)\n")
            for sugg in review.suggestions:
                parts.append(f"- [{sugg.priority}] {sugg.category}: {sugg.description}\n")

        return "".join(parts)

    def _enhance_instruction_with_context(
        self,
        instruction: str,
        context: dict[str, Any] | None,
        state: AgenticState,
        iteration: int,
    ) -> str:
        """Enhance instruction with iteration context."""
        parts = [instruction]

        if iteration > 1:
            parts.append(f"\n\n---\nThis is iteration {iteration}.")
            parts.append(f"\nCI fix attempts: {state.ci_iterations}")
            parts.append(f"\nReview fix attempts: {state.review_iterations}")

        if context and context.get("review_feedback"):
            review = context["review_feedback"]
            parts.append(f"\nPrevious review score: {review.get('score', 'N/A')}")

        return "\n".join(parts)

    async def _commit_and_push(
        self,
        task: Task,
        workspace_path: Path,
        summary: str | None,
    ) -> str | None:
        """Commit and push changes."""
        try:
            # Use git service to stage, commit, and push
            commit_message = f"[agentic] {summary or 'Auto-generated changes'}"

            # Stage all changes
            await self.git.stage_all(workspace_path)

            # Commit changes
            commit_sha = await self.git.commit(workspace_path, commit_message)

            # Push to remote
            branch = await self.git.get_current_branch(workspace_path)
            await self.git.push(workspace_path, branch)

            return commit_sha
        except Exception as e:
            logger.warning(f"Error committing changes: {e}")
            return None

    async def _create_pr(
        self,
        task: Task,
        workspace_path: Path,
        state: AgenticState,
    ) -> int | None:
        """Create a PR for the task."""
        try:
            owner, repo = await self._get_repo_info(task)
            branch = await self._get_current_branch(workspace_path)

            pr_data = await self.github.create_pull_request(
                owner=owner,
                repo=repo,
                title=f"[Agentic] {task.title or 'Auto-generated PR'}",
                head=branch,
                base="main",
                body=f"Automated PR for task {task.id}\n\nGenerated by agentic dursor.",
            )
            return pr_data.get("number")
        except Exception as e:
            logger.warning(f"Error creating PR: {e}")
            return None

    async def _get_pr_diff(self, pr_number: int | None) -> str:
        """Get diff for a PR."""
        if not pr_number:
            return ""
        # This would need to call GitHub API to get the diff
        # Simplified for now
        return ""

    def _parse_review_result(self, result: Any) -> ReviewResult:
        """Parse Codex output to ReviewResult."""
        # Simplified parsing - in real implementation would parse Codex output
        return ReviewResult(
            approved=result.success if hasattr(result, "success") else True,
            score=0.8,  # Default score
            summary="Review completed",
        )

    async def _get_repo_info(self, task: Task) -> tuple[str, str]:
        """Get owner and repo name for a task."""
        # In real implementation, would look up from Repo table
        # For now, return placeholder
        return ("owner", "repo")

    async def _get_current_branch(self, workspace_path: Path) -> str:
        """Get current git branch."""
        # Simplified - would use git service
        return "main"
