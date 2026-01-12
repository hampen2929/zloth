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

from dursor_api.config import settings
from dursor_api.domain.enums import (
    AgenticPhase,
    CodingMode,
    ExecutorType,
    MessageRole,
    ReviewSeverity,
)
from dursor_api.domain.models import (
    AgentConstraints,
    AgenticConfig,
    AgenticState,
    CIJobResult,
    CIResult,
    FixInstructionRequest,
    IterationLimits,
    ReviewCreate,
)

if TYPE_CHECKING:
    from dursor_api.domain.models import PR
    from dursor_api.services.ci_polling_service import CIPollingService
    from dursor_api.services.git_service import GitService
    from dursor_api.services.github_service import GitHubService
    from dursor_api.services.merge_gate_service import MergeGateService
    from dursor_api.services.notification_service import NotificationService
    from dursor_api.services.pr_service import PRService
    from dursor_api.services.review_service import ReviewService
    from dursor_api.services.run_service import RunService
    from dursor_api.storage.dao import PRDAO, AgenticRunDAO, MessageDAO, TaskDAO

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
        pr_service: "PRService",
        task_dao: "TaskDAO",
        pr_dao: "PRDAO",
        agentic_dao: "AgenticRunDAO",
        message_dao: "MessageDAO",
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
            pr_service: Service for PR operations.
            task_dao: Task DAO.
            pr_dao: PR DAO.
            agentic_dao: Agentic run DAO.
            message_dao: Message DAO for recording CI results to task.
        """
        self.run_service = run_service
        self.review_service = review_service
        self.merger = merge_gate_service
        self.git = git_service
        self.github = github_service
        self.notifier = notification_service
        self.ci_poller = ci_polling_service
        self.pr_service = pr_service
        self.task_dao = task_dao
        self.pr_dao = pr_dao
        self.agentic_dao = agentic_dao
        self.message_dao = message_dao

        # In-memory state management
        self._states: dict[str, AgenticState] = {}
        self._locks: dict[str, asyncio.Lock] = {}

        # Default limits from settings
        self._default_limits = IterationLimits(
            max_ci_iterations=settings.agentic_max_ci_iterations,
            max_review_iterations=settings.agentic_max_review_iterations,
            max_total_iterations=settings.agentic_max_total_iterations,
            min_review_score=settings.review_min_score,
            timeout_minutes=settings.agentic_timeout_minutes,
        )

    # =========================================
    # Public API
    # =========================================

    async def start_task(
        self,
        task_id: str,
        instruction: str,
        mode: CodingMode = CodingMode.FULL_AUTO,
        message_id: str | None = None,
        config: AgenticConfig | None = None,
    ) -> AgenticState:
        """Start agentic execution for a task.

        Args:
            task_id: Target task ID.
            instruction: Development instruction.
            mode: CodingMode (SEMI_AUTO or FULL_AUTO).
            message_id: Optional message ID to link runs to (for UI display).
            config: Optional agentic configuration.

        Returns:
            Initial agentic state.

        Raises:
            ValueError: If mode is INTERACTIVE.
        """
        if mode == CodingMode.INTERACTIVE:
            raise ValueError("Interactive mode is not supported by AgenticOrchestrator")

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

        # Start coding phase in background (pass message_id for UI linking)
        asyncio.create_task(
            self._run_coding_phase(task_id, instruction, limits, message_id=message_id)
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

        # Record CI result as a message in the task
        await self._record_ci_result_message(task_id, ci_result, state)

        async with self._locks[task_id]:
            state.last_ci_result = ci_result
            state.last_activity = datetime.utcnow()

            if ci_result.success:
                # CI passed - proceed to review
                state.phase = AgenticPhase.REVIEWING
                await self.agentic_dao.update(state)
                asyncio.create_task(self._run_review_phase(task_id))
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
                asyncio.create_task(self._run_ci_fix_phase(task_id, ci_result))

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
                    asyncio.create_task(self._run_merge_phase(task_id))
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
                asyncio.create_task(self._run_review_fix_phase(task_id, review_id))

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

            # Proceed to merge
            asyncio.create_task(self._run_merge_phase(task_id))

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
                asyncio.create_task(
                    self._run_coding_phase(
                        task_id,
                        feedback,
                        self._default_limits,
                        context={"human_feedback": True},
                    )
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
        message_id: str | None = None,
    ) -> None:
        """Execute Claude Code for coding.

        Args:
            task_id: Task ID.
            instruction: Coding instruction.
            limits: Iteration limits.
            context: Additional context.
            message_id: Optional message ID to link runs to (for UI display).
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
            from dursor_api.domain.models import RunCreate

            run_data = RunCreate(
                instruction=full_instruction,
                executor_type=ExecutorType.CLAUDE_CODE,
                message_id=message_id,  # Link run to message for UI display
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
            logger.info(
                f"Run completed for task {task_id}: "
                f"status={run.status if run else 'None'}, "
                f"working_branch={run.working_branch if run else 'None'}, "
                f"commit_sha={run.commit_sha if run else 'None'}"
            )

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

            # Auto-create PR if not exists (required for CI polling in Semi/Full Auto mode)
            logger.info(f"Checking if PR needs to be created: state.pr_number={state.pr_number}")
            if not state.pr_number:
                pr = await self._auto_create_pr(task_id, run_id)
                if pr:
                    async with self._locks[task_id]:
                        state.pr_number = pr.number
                        await self.agentic_dao.update(state)
                else:
                    async with self._locks[task_id]:
                        state.phase = AgenticPhase.FAILED
                        state.error = "Failed to auto-create PR for CI polling"
                        await self.agentic_dao.update(state)
                        await self._notify_failure(state)
                    return

            async with self._locks[task_id]:
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
            merge_result = await self.merger.merge(
                pr_number=state.pr_number,
                repo_full_name=repo_full_name,
                method=settings.merge_method,
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

    async def _auto_create_pr(self, task_id: str, run_id: str) -> "PR | None":
        """Auto-create PR for agentic execution (Semi Auto / Full Auto mode).

        This method creates a PR automatically when the first commit is made
        in Semi Auto or Full Auto mode. This is required for CI polling to work.

        Args:
            task_id: Task ID.
            run_id: Run ID that created the commit.

        Returns:
            Created PR object or None if failed.
        """
        from dursor_api.domain.models import PRCreateAuto

        try:
            logger.info(f"Auto-creating PR for task {task_id}, run {run_id}")

            # Get run to verify it has necessary data
            run = await self.run_service.get(run_id)
            if not run:
                logger.error(f"Run not found for PR creation: {run_id}")
                raise ValueError(f"Run not found: {run_id}")

            logger.info(
                f"Run details for PR creation: "
                f"working_branch={run.working_branch}, "
                f"commit_sha={run.commit_sha}, "
                f"status={run.status}"
            )

            if not run.working_branch:
                logger.error(f"Run has no working_branch: {run_id}")
                raise ValueError(f"Run has no working branch: {run_id}")

            if not run.commit_sha:
                logger.error(f"Run has no commit_sha: {run_id}")
                raise ValueError(f"Run has no commits: {run_id}")

            # Create PR with auto-generated title and description
            pr_data = PRCreateAuto(selected_run_id=run_id)
            pr = await self.pr_service.create_auto(task_id, pr_data)

            # Record PR creation as a message in the task
            await self._record_pr_created_message(task_id, pr)

            logger.info(f"Auto-created PR #{pr.number} for task {task_id}")
            return pr

        except Exception as e:
            logger.error(f"Failed to auto-create PR for task {task_id}: {e}", exc_info=True)
            # Record failure as a message
            try:
                await self.message_dao.create(
                    task_id=task_id,
                    role=MessageRole.ASSISTANT,
                    content=f"## PR Creation Failed\n\nFailed to automatically create PR: {str(e)}",
                )
            except Exception:
                pass
            return None

    async def _record_pr_created_message(self, task_id: str, pr: "PR") -> None:
        """Record PR creation as a message in the task.

        Args:
            task_id: Task ID.
            pr: Created PR object.
        """
        try:
            message_content = f"""## PR Created

**PR #{pr.number}**: [{pr.title}]({pr.url})

Branch: `{pr.branch}`

The PR has been automatically created. CI will now be monitored for results.
"""
            await self.message_dao.create(
                task_id=task_id,
                role=MessageRole.ASSISTANT,
                content=message_content,
            )
            logger.info(f"Recorded PR creation message for task {task_id}")
        except Exception as e:
            logger.warning(f"Failed to record PR creation message: {e}")

    # =========================================
    # Helper Methods
    # =========================================

    async def _record_ci_result_message(
        self,
        task_id: str,
        ci_result: CIResult,
        state: AgenticState,
    ) -> None:
        """Record CI result as a message in the task.

        Args:
            task_id: Task ID.
            ci_result: CI execution result.
            state: Current agentic state.
        """
        try:
            if ci_result.success:
                # CI passed message
                message_content = self._build_ci_success_message(ci_result, state)
            else:
                # CI failed message
                message_content = self._build_ci_failure_message(ci_result, state)

            await self.message_dao.create(
                task_id=task_id,
                role=MessageRole.ASSISTANT,
                content=message_content,
            )
            logger.info(f"Recorded CI result message for task {task_id}")
        except Exception as e:
            # Don't fail the CI handling if message recording fails
            logger.warning(f"Failed to record CI result message: {e}")

    def _build_ci_success_message(
        self,
        ci_result: CIResult,
        state: AgenticState,
    ) -> str:
        """Build message content for successful CI.

        Args:
            ci_result: CI execution result.
            state: Current agentic state.

        Returns:
            Formatted message string.
        """
        parts = [
            "## CI Result: PASSED",
            "",
            f"**Commit:** `{ci_result.sha[:8]}`",
            f"**Workflow Run ID:** {ci_result.workflow_run_id}",
            f"**Iteration:** {state.iteration} (CI attempts: {state.ci_iterations})",
            "",
            "### Job Results",
        ]

        for job_name, result in ci_result.jobs.items():
            status_icon = "+" if result == "success" else "-"
            parts.append(f"- [{status_icon}] {job_name}: {result}")

        parts.append("")
        parts.append("Proceeding to code review phase.")

        return "\n".join(parts)

    def _build_ci_failure_message(
        self,
        ci_result: CIResult,
        state: AgenticState,
    ) -> str:
        """Build message content for failed CI.

        Args:
            ci_result: CI execution result.
            state: Current agentic state.

        Returns:
            Formatted message string.
        """
        parts = [
            "## CI Result: FAILED",
            "",
            f"**Commit:** `{ci_result.sha[:8]}`",
            f"**Workflow Run ID:** {ci_result.workflow_run_id}",
            f"**Iteration:** {state.iteration} (CI attempts: {state.ci_iterations + 1})",
            "",
            "### Job Results",
        ]

        for job_name, result in ci_result.jobs.items():
            status_icon = "+" if result == "success" else "x"
            parts.append(f"- [{status_icon}] {job_name}: {result}")

        if ci_result.failed_jobs:
            parts.append("")
            parts.append("### Failed Job Details")
            for job in ci_result.failed_jobs:
                parts.append(f"\n#### {job.job_name}")
                if job.error_log:
                    # Truncate error log if too long
                    error_log = job.error_log
                    if len(error_log) > 2000:
                        error_log = error_log[:2000] + "\n... (truncated)"
                    parts.append(f"```\n{error_log}\n```")

        parts.append("")
        if state.ci_iterations + 1 >= self._default_limits.max_ci_iterations:
            parts.append(
                f"Max CI iterations ({self._default_limits.max_ci_iterations}) reached. "
                "Stopping agentic execution."
            )
        else:
            parts.append("Attempting automatic fix...")

        return "\n".join(parts)

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
