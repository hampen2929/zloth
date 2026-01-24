"""Agentic orchestrator for autonomous development cycles.

This service orchestrates the full agentic development cycle:
1. Coding (Claude Code)
2. Wait for CI
3. If CI fails → Fix and go to 2
4. Review (Codex)
5. If review rejects → Fix and go to 2
6. Merge (Full Auto) or wait for human (Semi Auto)
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from zloth_api.config import settings
from zloth_api.domain.enums import (
    AgenticPhase,
    CodingMode,
    ExecutorType,
    ReviewSeverity,
)
from zloth_api.domain.models import (
    AgentConstraints,
    AgenticConfig,
    AgenticState,
    CIJobResult,
    CIResult,
    FixInstructionRequest,
    IterationLimits,
    ReviewCreate,
)
from zloth_api.services.settings_service import SettingsService

if TYPE_CHECKING:
    from zloth_api.services.ci_polling_service import CIPollingService
    from zloth_api.services.git_service import GitService
    from zloth_api.services.github_service import GitHubService
    from zloth_api.services.merge_gate_service import MergeGateService
    from zloth_api.services.notification_service import NotificationService
    from zloth_api.services.review_service import ReviewService
    from zloth_api.services.run_service import RunService
    from zloth_api.storage.dao import PRDAO, AgenticRunDAO, TaskDAO

logger = logging.getLogger(__name__)


class AgenticOrchestrator:
    """Orchestrates the full agentic development cycle.

    Supports two modes:
    - SEMI_AUTO: Automatic execution, human merge approval
    - FULL_AUTO: Fully autonomous execution including merge
    """

    def __init__(
        self,
        run_service: "RunService",
        review_service: "ReviewService",
        merge_gate_service: "MergeGateService",
        git_service: "GitService",
        github_service: "GitHubService",
        notification_service: "NotificationService",
        ci_polling_service: "CIPollingService",
        task_dao: "TaskDAO",
        pr_dao: "PRDAO",
        agentic_dao: "AgenticRunDAO",
        settings_service: SettingsService | None = None,
    ):
        """Initialize agentic orchestrator.

        Args:
            run_service: Service for code generation runs.
            review_service: Service for code reviews.
            merge_gate_service: Service for merge gate checks.
            git_service: Service for git operations.
            github_service: Service for GitHub API operations.
            notification_service: Service for notifications.
            ci_polling_service: Service for CI status polling.
            task_dao: Task DAO.
            pr_dao: PR DAO.
            agentic_dao: Agentic run DAO.
        """
        self.run_service = run_service
        self.review_service = review_service
        self.merger = merge_gate_service
        self.git = git_service
        self.github = github_service
        self.notifier = notification_service
        self.ci_poller = ci_polling_service
        self.task_dao = task_dao
        self.pr_dao = pr_dao
        self.agentic_dao = agentic_dao
        self.settings_service = settings_service or SettingsService()

        # In-memory state management
        self._states: dict[str, AgenticState] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        # Background task tracking to prevent orphaned tasks
        self._background_tasks: dict[str, asyncio.Task[None]] = {}

        # Default limits from settings
        self._default_limits = IterationLimits(
            max_ci_iterations=settings.agentic_max_ci_iterations,
            max_review_iterations=settings.agentic_max_review_iterations,
            max_total_iterations=settings.agentic_max_total_iterations,
            min_review_score=settings.review_min_score,
            timeout_minutes=settings.agentic_timeout_minutes,
        )

    # =========================================
    # Background Task Management
    # =========================================

    def _start_background_task(
        self,
        task_id: str,
        coro: Any,
        phase_name: str,
        timeout_seconds: int | None = None,
    ) -> asyncio.Task[None]:
        """Start a background task with timeout and proper tracking.

        Args:
            task_id: Task ID for tracking.
            coro: Coroutine to execute.
            phase_name: Name of the phase for logging.
            timeout_seconds: Optional timeout override.

        Returns:
            The created asyncio Task.
        """
        # Cancel any existing background task for this task_id
        self._cancel_background_task(task_id)

        # Default timeout: use agentic_timeout_minutes converted to seconds
        task_timeout = timeout_seconds or (settings.agentic_timeout_minutes * 60)

        async def wrapped_task() -> None:
            """Execute with timeout and error handling."""
            try:
                await asyncio.wait_for(coro, timeout=task_timeout)
            except TimeoutError:
                logger.error(f"[{task_id}] {phase_name} timed out after {task_timeout}s")
                # Update state to failed
                state = self._states.get(task_id)
                if state:
                    async with self._locks.get(task_id, asyncio.Lock()):
                        state.phase = AgenticPhase.FAILED
                        state.error = f"{phase_name} timed out after {task_timeout}s"
                        await self.agentic_dao.update(state)
                        await self._notify_failure(state)
            except asyncio.CancelledError:
                logger.info(f"[{task_id}] {phase_name} was cancelled")
                raise
            except Exception as e:
                logger.error(f"[{task_id}] {phase_name} failed: {e}")
                # Error handling is done within each phase method
                raise
            finally:
                # Cleanup the tracked task
                self._cleanup_background_task(task_id)

        task: asyncio.Task[None] = asyncio.create_task(wrapped_task())
        self._background_tasks[task_id] = task
        logger.debug(f"[{task_id}] Started background task for {phase_name}")
        return task

    def _cancel_background_task(self, task_id: str) -> bool:
        """Cancel an existing background task.

        Args:
            task_id: Task ID to cancel.

        Returns:
            True if a task was cancelled.
        """
        existing_task = self._background_tasks.get(task_id)
        if existing_task and not existing_task.done():
            existing_task.cancel()
            logger.debug(f"[{task_id}] Cancelled existing background task")
            return True
        return False

    def _cleanup_background_task(self, task_id: str) -> None:
        """Remove completed task from tracking.

        Args:
            task_id: Task ID to cleanup.
        """
        if task_id in self._background_tasks:
            del self._background_tasks[task_id]
            logger.debug(f"[{task_id}] Cleaned up background task from tracking")

    def get_active_task_count(self) -> int:
        """Get count of active background tasks.

        Returns:
            Number of active (non-completed) background tasks.
        """
        return sum(1 for t in self._background_tasks.values() if not t.done())

    # =========================================
    # Public API
    # =========================================

    async def start_task(
        self,
        task_id: str,
        instruction: str,
        mode: CodingMode = CodingMode.FULL_AUTO,
        config: AgenticConfig | None = None,
    ) -> AgenticState:
        """Start agentic execution for a task.

        Args:
            task_id: Target task ID.
            instruction: Development instruction.
            mode: CodingMode (SEMI_AUTO or FULL_AUTO).
            config: Optional agentic configuration.

        Returns:
            Initial agentic state.

        Raises:
            ValueError: If mode is INTERACTIVE.
        """
        if mode == CodingMode.INTERACTIVE:
            raise ValueError("Interactive mode is not supported by AgenticOrchestrator")

        await self._refresh_default_limits()

        # Verify task exists
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        # Create agentic run ID
        agentic_run_id = str(uuid.uuid4())[:8]

        # Merge config with defaults
        limits = config.limits if config else self._default_limits

        now = datetime.utcnow()
        state = AgenticState(
            id=agentic_run_id,
            task_id=task_id,
            mode=mode,
            phase=AgenticPhase.CODING,
            iteration=0,
            ci_iterations=0,
            review_iterations=0,
            started_at=now,
            last_activity=now,
        )

        self._states[task_id] = state
        self._locks[task_id] = asyncio.Lock()

        # Persist state
        await self.agentic_dao.create(state)

        # Start coding phase in background with proper tracking and timeout
        self._start_background_task(
            task_id,
            self._run_coding_phase(task_id, instruction, limits),
            "Coding phase",
        )

        return state

    async def get_status(self, task_id: str) -> AgenticState | None:
        """Get current agentic execution status.

        Args:
            task_id: Task ID.

        Returns:
            Current state or None if not found.
        """
        state = self._states.get(task_id)
        if state:
            return state

        # Try to load from database
        return await self.agentic_dao.get_by_task_id(task_id)

    async def cancel(self, task_id: str) -> bool:
        """Cancel agentic execution.

        Args:
            task_id: Task ID.

        Returns:
            True if cancelled, False if not found.
        """
        state = self._states.get(task_id)
        if not state:
            return False

        # Stop CI polling if active
        await self._stop_ci_polling(task_id)

        # Cancel any running background task
        self._cancel_background_task(task_id)

        async with self._locks[task_id]:
            state.phase = AgenticPhase.FAILED
            state.error = "Cancelled by user"
            state.last_activity = datetime.utcnow()
            await self.agentic_dao.update(state)

        return True

    async def handle_ci_result(
        self,
        task_id: str,
        ci_result: CIResult,
    ) -> AgenticState | None:
        """Handle CI completion webhook.

        Args:
            task_id: Task ID.
            ci_result: CI execution result.

        Returns:
            Updated state or None if not found.
        """
        state = self._states.get(task_id)
        if not state:
            logger.warning(f"No active agentic state for task {task_id}")
            return None

        async with self._locks[task_id]:
            state.last_ci_result = ci_result
            state.last_activity = datetime.utcnow()

            if ci_result.success:
                # CI passed - proceed to review
                state.phase = AgenticPhase.REVIEWING
                await self.agentic_dao.update(state)
                self._start_background_task(
                    task_id,
                    self._run_review_phase(task_id),
                    "Review phase",
                )
            else:
                # CI failed - trigger fix
                state.ci_iterations += 1

                if state.ci_iterations > self._default_limits.max_ci_iterations:
                    state.phase = AgenticPhase.FAILED
                    state.error = "Exceeded max CI fix iterations"
                    await self.agentic_dao.update(state)
                    await self._notify_failure(state)
                    return state

                state.phase = AgenticPhase.FIXING_CI
                await self.agentic_dao.update(state)
                self._start_background_task(
                    task_id,
                    self._run_ci_fix_phase(task_id, ci_result),
                    "CI fix phase",
                )

            return state

    async def handle_review_result(
        self,
        task_id: str,
        review_score: float,
        approved: bool,
        review_id: str | None = None,
    ) -> AgenticState | None:
        """Handle review completion.

        Args:
            task_id: Task ID.
            review_score: Review score (0.0-1.0).
            approved: Whether review is approved.
            review_id: Review ID for generating fix instructions.

        Returns:
            Updated state or None if not found.
        """
        state = self._states.get(task_id)
        if not state:
            logger.warning(f"No active agentic state for task {task_id}")
            return None

        async with self._locks[task_id]:
            state.last_review_score = review_score
            state.last_activity = datetime.utcnow()

            if approved and review_score >= self._default_limits.min_review_score:
                # Review passed - proceed based on mode
                if state.mode == CodingMode.SEMI_AUTO:
                    # Semi Auto: Wait for human approval
                    state.phase = AgenticPhase.AWAITING_HUMAN
                    await self.agentic_dao.update(state)
                    await self._notify_ready_for_merge(state)
                else:
                    # Full Auto: Proceed to merge check
                    state.phase = AgenticPhase.MERGE_CHECK
                    await self.agentic_dao.update(state)
                    self._start_background_task(
                        task_id,
                        self._run_merge_phase(task_id),
                        "Merge phase",
                    )
            else:
                # Review rejected - trigger fix
                state.review_iterations += 1

                if state.review_iterations > self._default_limits.max_review_iterations:
                    state.phase = AgenticPhase.FAILED
                    state.error = "Exceeded max review fix iterations"
                    await self.agentic_dao.update(state)
                    await self._notify_failure(state)
                    return state

                state.phase = AgenticPhase.FIXING_REVIEW
                await self.agentic_dao.update(state)
                self._start_background_task(
                    task_id,
                    self._run_review_fix_phase(task_id, review_id),
                    "Review fix phase",
                )

            return state

    async def approve_merge(self, task_id: str) -> AgenticState:
        """Human approves merge (Semi Auto mode only).

        Args:
            task_id: Task ID.

        Returns:
            Updated state.

        Raises:
            ValueError: If not in correct mode/phase.
        """
        state = self._states.get(task_id)
        if not state:
            raise ValueError(f"No active agentic state for task {task_id}")

        if state.mode != CodingMode.SEMI_AUTO:
            raise ValueError("approve_merge is only for Semi Auto mode")

        if state.phase != AgenticPhase.AWAITING_HUMAN:
            raise ValueError(f"Cannot approve merge in phase {state.phase}")

        async with self._locks[task_id]:
            state.human_approved = True
            state.last_activity = datetime.utcnow()
            state.phase = AgenticPhase.MERGE_CHECK
            await self.agentic_dao.update(state)

            # Proceed to merge with proper tracking
            self._start_background_task(
                task_id,
                self._run_merge_phase(task_id),
                "Merge phase (approved)",
            )

            return state

    async def reject_merge(
        self,
        task_id: str,
        feedback: str | None = None,
    ) -> AgenticState:
        """Human rejects merge (Semi Auto mode only).

        Args:
            task_id: Task ID.
            feedback: Optional feedback for AI to address.

        Returns:
            Updated state.

        Raises:
            ValueError: If not in correct mode/phase.
        """
        state = self._states.get(task_id)
        if not state:
            raise ValueError(f"No active agentic state for task {task_id}")

        if state.mode != CodingMode.SEMI_AUTO:
            raise ValueError("reject_merge is only for Semi Auto mode")

        if state.phase != AgenticPhase.AWAITING_HUMAN:
            raise ValueError(f"Cannot reject in phase {state.phase}")

        async with self._locks[task_id]:
            state.last_activity = datetime.utcnow()

            if feedback:
                # Human provided feedback - trigger fix
                state.phase = AgenticPhase.CODING
                await self.agentic_dao.update(state)
                self._start_background_task(
                    task_id,
                    self._run_coding_phase(
                        task_id,
                        feedback,
                        self._default_limits,
                        context={"human_feedback": True},
                    ),
                    "Coding phase (human feedback)",
                )
            else:
                # No feedback - mark as failed
                state.phase = AgenticPhase.FAILED
                state.error = "Human rejected without feedback"
                await self.agentic_dao.update(state)

            return state

    async def find_task_by_pr(self, pr_number: int) -> str | None:
        """Find task ID by PR number.

        Args:
            pr_number: PR number.

        Returns:
            Task ID or None if not found.
        """
        pr = await self.pr_dao.get_by_number(pr_number)
        if pr:
            return pr.task_id
        return None

    # =========================================
    # Phase Implementations
    # =========================================

    async def _run_coding_phase(
        self,
        task_id: str,
        instruction: str,
        limits: IterationLimits,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Execute Claude Code for coding.

        Args:
            task_id: Task ID.
            instruction: Coding instruction.
            limits: Iteration limits.
            context: Additional context.
        """
        state = self._states.get(task_id)
        if not state:
            return

        async with self._locks[task_id]:
            state.phase = AgenticPhase.CODING
            state.iteration += 1
            state.last_activity = datetime.utcnow()

            if state.iteration > limits.max_total_iterations:
                state.phase = AgenticPhase.FAILED
                state.error = "Exceeded max total iterations"
                await self.agentic_dao.update(state)
                await self._notify_failure(state)
                return

            # Check for warning threshold
            if state.iteration >= settings.warn_iteration_threshold:
                await self._notify_warning(
                    state,
                    f"High iteration count: {state.iteration}",
                )

        try:
            # Enhance instruction with context
            full_instruction = self._enhance_instruction(instruction, context, state)

            # Create run via RunService
            from zloth_api.domain.models import RunCreate

            run_data = RunCreate(
                instruction=full_instruction,
                executor_type=ExecutorType.CLAUDE_CODE,
            )

            runs = await self.run_service.create_runs(task_id, run_data)

            if not runs:
                async with self._locks[task_id]:
                    state.phase = AgenticPhase.FAILED
                    state.error = "Failed to create coding run"
                    await self.agentic_dao.update(state)
                    await self._notify_failure(state)
                return

            # Wait for run completion
            run_id = runs[0].id
            await self._wait_for_run(run_id)

            # Get run result
            run = await self.run_service.get(run_id)
            if not run or run.status != "succeeded":
                async with self._locks[task_id]:
                    state.phase = AgenticPhase.FAILED
                    state.error = f"Coding run failed: {run.error if run else 'Unknown'}"
                    await self.agentic_dao.update(state)
                    await self._notify_failure(state)
                return

            # Update state with commit SHA
            async with self._locks[task_id]:
                state.current_sha = run.commit_sha
                state.phase = AgenticPhase.WAITING_CI
                await self.agentic_dao.update(state)

            # Start CI polling
            await self._start_ci_polling(task_id)

        except Exception as e:
            logger.error(f"Coding phase failed: {e}")
            async with self._locks[task_id]:
                state.phase = AgenticPhase.FAILED
                state.error = f"Coding phase error: {str(e)}"
                await self.agentic_dao.update(state)
                await self._notify_failure(state)

    async def _run_ci_fix_phase(
        self,
        task_id: str,
        ci_result: CIResult,
    ) -> None:
        """Fix CI failures using Claude Code.

        Args:
            task_id: Task ID.
            ci_result: CI result with failures.
        """
        # Build fix instruction from CI errors
        instruction = self._build_ci_fix_instruction(ci_result.failed_jobs)

        await self._run_coding_phase(
            task_id,
            instruction,
            self._default_limits,
            context={
                "fix_mode": True,
                "ci_result": ci_result.model_dump(),
            },
        )

    async def _run_review_phase(self, task_id: str) -> None:
        """Execute code review.

        Args:
            task_id: Task ID.
        """
        state = self._states.get(task_id)
        if not state:
            return

        async with self._locks[task_id]:
            state.phase = AgenticPhase.REVIEWING
            state.last_activity = datetime.utcnow()
            await self.agentic_dao.update(state)

        try:
            # Get the latest run for this task
            runs = await self.run_service.list(task_id)
            if not runs:
                raise ValueError("No runs found for task")

            # Get the most recent successful run
            latest_run = None
            for run in runs:
                if run.status == "succeeded":
                    latest_run = run
                    break

            if not latest_run:
                raise ValueError("No successful run found for review")

            # Create review
            review_data = ReviewCreate(
                target_run_ids=[latest_run.id],
                executor_type=ExecutorType.CODEX_CLI,
            )

            review_result = await self.review_service.create_review(task_id, review_data)

            # Wait for review completion
            await self._wait_for_review(review_result.id)

            # Get review result
            review = await self.review_service.get(review_result.id)
            if not review:
                raise ValueError("Review not found")

            # Process review result
            approved = review.status == "succeeded"
            score = review.overall_score or 0.0

            await self.handle_review_result(
                task_id,
                review_score=score,
                approved=approved,
                review_id=review.id,
            )

        except Exception as e:
            logger.error(f"Review phase failed: {e}")
            async with self._locks[task_id]:
                state.phase = AgenticPhase.FAILED
                state.error = f"Review phase error: {str(e)}"
                await self.agentic_dao.update(state)
                await self._notify_failure(state)

    async def _run_review_fix_phase(
        self,
        task_id: str,
        review_id: str | None,
    ) -> None:
        """Fix issues from code review.

        Args:
            task_id: Task ID.
            review_id: Review ID for generating fix instructions.
        """
        instruction = "Address the review feedback and fix the issues."

        if review_id:
            try:
                # Generate fix instruction from review
                fix_request = FixInstructionRequest(
                    review_id=review_id,
                    severity_filter=[ReviewSeverity.CRITICAL, ReviewSeverity.HIGH],
                )
                fix_response = await self.review_service.generate_fix_instruction(fix_request)
                instruction = fix_response.instruction
            except Exception as e:
                logger.warning(f"Failed to generate fix instruction: {e}")

        await self._run_coding_phase(
            task_id,
            instruction,
            self._default_limits,
            context={
                "fix_mode": True,
                "review_fix": True,
            },
        )

    async def _run_merge_phase(self, task_id: str) -> None:
        """Execute auto-merge.

        Args:
            task_id: Task ID.
        """
        state = self._states.get(task_id)
        if not state:
            return

        async with self._locks[task_id]:
            state.phase = AgenticPhase.MERGING
            state.last_activity = datetime.utcnow()
            await self.agentic_dao.update(state)

        try:
            if not state.pr_number:
                raise ValueError("No PR number in state")

            # Get task for repo info
            task = await self.task_dao.get(task_id)
            if not task:
                raise ValueError("Task not found")

            # Get repo full name
            repo = await self.run_service.repo_service.dao.get(task.repo_id)
            if not repo:
                raise ValueError("Repository not found")

            repo_full_name = self._extract_repo_full_name(repo.repo_url)

            # Check conditions and merge
            runtime_settings = await self.settings_service.get_user_runtime_settings()
            merge_result = await self.merger.merge(
                pr_number=state.pr_number,
                repo_full_name=repo_full_name,
                method=runtime_settings.merge_method,
                delete_branch=settings.merge_delete_branch,
            )

            async with self._locks[task_id]:
                if merge_result.success:
                    state.phase = AgenticPhase.COMPLETED
                    await self.agentic_dao.update(state)
                    await self._notify_completion(state)
                else:
                    state.phase = AgenticPhase.FAILED
                    state.error = f"Merge failed: {merge_result.error}"
                    await self.agentic_dao.update(state)
                    await self._notify_failure(state)

        except Exception as e:
            logger.error(f"Merge phase failed: {e}")
            async with self._locks[task_id]:
                state.phase = AgenticPhase.FAILED
                state.error = f"Merge phase error: {str(e)}"
                await self.agentic_dao.update(state)
                await self._notify_failure(state)

    async def _refresh_default_limits(self) -> None:
        """Refresh default iteration limits from user settings."""
        runtime_settings = await self.settings_service.get_user_runtime_settings()
        self._default_limits = IterationLimits(
            max_ci_iterations=settings.agentic_max_ci_iterations,
            max_review_iterations=settings.agentic_max_review_iterations,
            max_total_iterations=settings.agentic_max_total_iterations,
            min_review_score=runtime_settings.review_min_score,
            timeout_minutes=settings.agentic_timeout_minutes,
        )

    # =========================================
    # CI Polling Methods
    # =========================================

    async def _start_ci_polling(self, task_id: str) -> None:
        """Start CI status polling for a task.

        Args:
            task_id: Task ID.
        """
        state = self._states.get(task_id)
        if not state or not state.pr_number:
            logger.warning(f"Cannot start CI polling for task {task_id}: no PR number")
            return

        # Get repo info
        task = await self.task_dao.get(task_id)
        if not task:
            logger.warning(f"Cannot start CI polling: task not found {task_id}")
            return

        repo = await self.run_service.repo_service.dao.get(task.repo_id)
        if not repo:
            logger.warning(f"Cannot start CI polling: repo not found {task.repo_id}")
            return

        repo_full_name = self._extract_repo_full_name(repo.repo_url)

        # Define callbacks
        async def on_ci_complete(ci_result: CIResult) -> None:
            await self.handle_ci_result(task_id, ci_result)

        async def on_ci_timeout() -> None:
            async with self._locks[task_id]:
                state = self._states.get(task_id)
                if state:
                    state.phase = AgenticPhase.FAILED
                    state.error = "CI polling timed out"
                    await self.agentic_dao.update(state)
                    await self._notify_failure(state)

        # Start polling
        await self.ci_poller.start_polling(
            task_id=task_id,
            pr_number=state.pr_number,
            repo_full_name=repo_full_name,
            on_complete=on_ci_complete,
            on_timeout=on_ci_timeout,
        )

        logger.info(f"Started CI polling for task {task_id}, PR #{state.pr_number}")

    async def _stop_ci_polling(self, task_id: str) -> None:
        """Stop CI polling for a task.

        Args:
            task_id: Task ID.
        """
        await self.ci_poller.stop_polling(task_id)

    # =========================================
    # Helper Methods
    # =========================================

    def _build_ci_fix_instruction(self, failed_jobs: list[CIJobResult]) -> str:
        """Build instruction for fixing CI failures.

        Args:
            failed_jobs: List of failed CI jobs.

        Returns:
            Fix instruction string.
        """
        parts = ["Fix the following CI failures:\n"]

        for job in failed_jobs:
            parts.append(f"\n## {job.job_name} (FAILED)\n")
            if job.error_log:
                parts.append(f"```\n{job.error_log}\n```\n")

            # Add fix strategy hint
            strategy = self.merger.get_fix_strategy(job.job_name)
            parts.append(f"Hint: {strategy}\n")

        parts.append("""
Please:
1. Analyze each error carefully
2. Fix the root cause (not just the symptoms)
3. Ensure your fixes don't break other tests
4. Run the relevant checks locally before committing
""")

        return "".join(parts)

    def _enhance_instruction(
        self,
        instruction: str,
        context: dict[str, Any] | None,
        state: AgenticState,
    ) -> str:
        """Enhance instruction with iteration context.

        Args:
            instruction: Base instruction.
            context: Additional context.
            state: Current state.

        Returns:
            Enhanced instruction string.
        """
        parts = [instruction]

        # Add constraints
        constraints = AgentConstraints()
        parts.append(f"\n\n{constraints.to_prompt()}")

        if state.iteration > 1:
            parts.append(f"\n\n---\nThis is iteration {state.iteration}.")
            parts.append(f"CI fix attempts: {state.ci_iterations}")
            parts.append(f"Review fix attempts: {state.review_iterations}")

        if context and context.get("human_feedback"):
            parts.append("\nNote: This instruction came from human feedback.")

        if state.last_review_score is not None:
            parts.append(f"\nPrevious review score: {state.last_review_score:.2f}")

        return "\n".join(parts)

    async def _wait_for_run(self, run_id: str, timeout: int = 1800) -> None:
        """Wait for a run to complete.

        Args:
            run_id: Run ID.
            timeout: Timeout in seconds.
        """
        start = datetime.utcnow()
        while True:
            run = await self.run_service.get(run_id)
            if run and run.status in ["succeeded", "failed", "canceled"]:
                return

            elapsed = (datetime.utcnow() - start).total_seconds()
            if elapsed > timeout:
                raise TimeoutError(f"Run {run_id} timed out after {timeout}s")

            await asyncio.sleep(5)

    async def _wait_for_review(self, review_id: str, timeout: int = 600) -> None:
        """Wait for a review to complete.

        Args:
            review_id: Review ID.
            timeout: Timeout in seconds.
        """
        start = datetime.utcnow()
        while True:
            review = await self.review_service.get(review_id)
            if review and review.status in ["succeeded", "failed", "canceled"]:
                return

            elapsed = (datetime.utcnow() - start).total_seconds()
            if elapsed > timeout:
                raise TimeoutError(f"Review {review_id} timed out after {timeout}s")

            await asyncio.sleep(2)

    def _extract_repo_full_name(self, repo_url: str) -> str:
        """Extract owner/repo from repository URL.

        Args:
            repo_url: Repository URL.

        Returns:
            Full repository name (owner/repo).
        """
        # Handle both HTTPS and SSH URLs
        if repo_url.endswith(".git"):
            repo_url = repo_url[:-4]

        if "github.com" in repo_url:
            parts = repo_url.split("github.com")[-1]
            parts = parts.lstrip("/").lstrip(":")
            return parts

        return repo_url

    # =========================================
    # Notification Methods
    # =========================================

    async def _notify_ready_for_merge(self, state: AgenticState) -> None:
        """Notify human that PR is ready for merge review (Semi Auto only)."""
        if not state.pr_number:
            return

        task = await self.task_dao.get(state.task_id)
        task_title = task.title if task else None

        await self.notifier.notify_ready_for_merge(
            task_id=state.task_id,
            task_title=task_title,
            pr_number=state.pr_number,
            pr_url=f"https://github.com/TODO/pull/{state.pr_number}",  # TODO: Get actual URL
            mode=state.mode.value,
            iterations=state.iteration,
            review_score=state.last_review_score,
        )

    async def _notify_failure(self, state: AgenticState) -> None:
        """Notify about task failure."""
        task = await self.task_dao.get(state.task_id)
        task_title = task.title if task else None

        await self.notifier.notify_failed(
            task_id=state.task_id,
            task_title=task_title,
            error=state.error or "Unknown error",
            mode=state.mode.value,
            iterations=state.iteration,
            pr_number=state.pr_number,
        )

    async def _notify_completion(self, state: AgenticState) -> None:
        """Notify about successful completion."""
        if not state.pr_number:
            return

        task = await self.task_dao.get(state.task_id)
        task_title = task.title if task else None

        await self.notifier.notify_completed(
            task_id=state.task_id,
            task_title=task_title,
            pr_number=state.pr_number,
            pr_url=f"https://github.com/TODO/pull/{state.pr_number}",  # TODO: Get actual URL
            mode=state.mode.value,
            iterations=state.iteration,
        )

    async def _notify_warning(self, state: AgenticState, message: str) -> None:
        """Notify about warning."""
        task = await self.task_dao.get(state.task_id)
        task_title = task.title if task else None

        await self.notifier.notify_warning(
            task_id=state.task_id,
            task_title=task_title,
            message=message,
            mode=state.mode.value,
            iterations=state.iteration,
            pr_number=state.pr_number,
        )
