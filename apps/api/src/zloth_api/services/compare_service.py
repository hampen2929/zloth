"""Compare service for comparing multiple executor outputs.

This service manages the execution of AI-powered comparisons
of code changes from different executors.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zloth_api.config import settings
from zloth_api.domain.enums import (
    ComparisonStatus,
    ExecutorType,
)
from zloth_api.domain.models import (
    Comparison,
    ComparisonFileOverlap,
    ComparisonRequest,
    Run,
    RunComparisonMetrics,
)
from zloth_api.executors.claude_code_executor import ClaudeCodeExecutor, ClaudeCodeOptions
from zloth_api.executors.codex_executor import CodexExecutor, CodexOptions
from zloth_api.executors.gemini_executor import GeminiExecutor, GeminiOptions
from zloth_api.storage.dao import ComparisonDAO, RunDAO, TaskDAO, generate_id

if TYPE_CHECKING:
    from zloth_api.services.model_service import ModelService
    from zloth_api.services.output_manager import OutputManager
    from zloth_api.services.repo_service import RepoService

logger = logging.getLogger(__name__)


COMPARISON_SYSTEM_PROMPT = """You are an expert code reviewer and software architect.
Your task is to compare and analyze code changes from multiple AI coding assistants
that were given the same task.

CRITICAL: This is a READ-ONLY comparison task.
- DO NOT modify any files
- DO NOT write any code changes
- DO NOT create new files
- ONLY analyze and compare the provided outputs

For each comparison, analyze and provide:

1. **Approach Comparison**: How each agent approached the problem
   - What design patterns or strategies did each use?
   - How did their architectural decisions differ?

2. **Code Quality Assessment**: Compare the quality of each solution
   - Readability and maintainability
   - Code organization and structure
   - Use of best practices

3. **Completeness**: Did each solution fully address the requirements?
   - Missing features or edge cases
   - Over-engineering concerns

4. **Potential Issues**: Any bugs, security concerns, or edge cases
   - Identify issues specific to each implementation
   - Compare error handling approaches

5. **Recommendation**: Which solution would you recommend and why?
   - Provide a clear winner with justification
   - Suggest potential improvements from combining approaches

Output your analysis in a clear, structured markdown format.
Be specific and provide concrete examples when comparing approaches.
"""


def _get_executor_display_name(executor_type: ExecutorType) -> str:
    """Get display name for executor type."""
    names = {
        ExecutorType.CLAUDE_CODE: "Claude Code",
        ExecutorType.CODEX_CLI: "Codex",
        ExecutorType.GEMINI_CLI: "Gemini CLI",
        ExecutorType.PATCH_AGENT: "Patch Agent",
    }
    return names.get(executor_type, executor_type.value)


class CompareService:
    """Service for comparing multiple executor outputs."""

    def __init__(
        self,
        comparison_dao: ComparisonDAO,
        run_dao: RunDAO,
        task_dao: TaskDAO,
        repo_service: RepoService,
        model_service: ModelService,
        output_manager: OutputManager,
    ) -> None:
        """Initialize compare service."""
        self.comparison_dao = comparison_dao
        self.run_dao = run_dao
        self.task_dao = task_dao
        self.repo_service = repo_service
        self.model_service = model_service
        self.output_manager = output_manager

        # Executors for comparison (initialized lazily)
        self._claude_executor: ClaudeCodeExecutor | None = None
        self._codex_executor: CodexExecutor | None = None
        self._gemini_executor: GeminiExecutor | None = None

        # Background task tracking
        self._background_tasks: dict[str, asyncio.Task[None]] = {}
        self._semaphore = asyncio.Semaphore(settings.queue_max_concurrent_tasks)

    async def create_comparison(
        self,
        task_id: str,
        request: ComparisonRequest,
    ) -> Comparison:
        """Create and start a comparison.

        Args:
            task_id: The task ID.
            request: Comparison request with run IDs and analysis model/executor.

        Returns:
            The created comparison.
        """
        # Validate task exists
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        # Validate runs exist and belong to the task
        runs: list[Run] = []
        for run_id in request.run_ids:
            run = await self.run_dao.get(run_id)
            if not run:
                raise ValueError(f"Run not found: {run_id}")
            if run.task_id != task_id:
                raise ValueError(f"Run {run_id} does not belong to task {task_id}")
            runs.append(run)

        # Need at least 2 runs to compare
        if len(runs) < 2:
            raise ValueError("At least 2 runs are required for comparison")

        # Calculate metrics and file overlaps from runs
        run_metrics = self._calculate_run_metrics(runs)
        file_overlaps = self._calculate_file_overlaps(runs)

        # Create comparison record
        comparison = Comparison(
            id=generate_id(),
            task_id=task_id,
            run_ids=request.run_ids,
            model_id=request.model_id,
            executor_type=request.executor_type,
            status=ComparisonStatus.PENDING,
            run_metrics=run_metrics,
            file_overlaps=file_overlaps,
            created_at=datetime.now(),
        )

        await self.comparison_dao.create(comparison)

        # Enqueue background execution
        def make_coro(c: Comparison, r: list[Run]) -> Callable[[], Coroutine[Any, Any, None]]:
            return lambda: self._execute_comparison(c, r)

        task_coro = make_coro(comparison, runs)
        bg_task = asyncio.create_task(self._run_with_semaphore(comparison.id, task_coro))
        self._background_tasks[comparison.id] = bg_task

        return comparison

    def _calculate_run_metrics(self, runs: list[Run]) -> list[RunComparisonMetrics]:
        """Calculate metrics for each run."""
        metrics: list[RunComparisonMetrics] = []

        for run in runs:
            # Calculate total lines added/removed
            lines_added = sum(f.added_lines for f in run.files_changed)
            lines_removed = sum(f.removed_lines for f in run.files_changed)

            # Calculate execution time
            execution_time: float | None = None
            if run.started_at and run.completed_at:
                execution_time = (run.completed_at - run.started_at).total_seconds()

            metrics.append(
                RunComparisonMetrics(
                    run_id=run.id,
                    executor_type=run.executor_type,
                    model_name=run.model_name,
                    files_changed=len(run.files_changed),
                    lines_added=lines_added,
                    lines_removed=lines_removed,
                    execution_time_seconds=execution_time,
                    status=run.status,
                )
            )

        return metrics

    def _calculate_file_overlaps(self, runs: list[Run]) -> list[ComparisonFileOverlap]:
        """Calculate file overlap information across runs."""
        # Map: file_path -> list of run_ids that modified it
        file_to_runs: dict[str, list[str]] = defaultdict(list)

        for run in runs:
            for file_diff in run.files_changed:
                file_to_runs[file_diff.path].append(run.id)

        # Create overlap records
        overlaps: list[ComparisonFileOverlap] = []
        for file_path, run_ids in sorted(file_to_runs.items()):
            overlaps.append(
                ComparisonFileOverlap(
                    file_path=file_path,
                    appears_in_runs=run_ids,
                    appears_in_count=len(run_ids),
                )
            )

        return overlaps

    async def _run_with_semaphore(
        self,
        comparison_id: str,
        task_coro: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        """Run a comparison task with semaphore control."""
        async with self._semaphore:
            try:
                await task_coro()
            except Exception as e:
                logger.exception(f"Comparison {comparison_id} failed with error")
                await self.comparison_dao.update_status(
                    comparison_id,
                    ComparisonStatus.FAILED,
                    error=str(e),
                )
            finally:
                self._background_tasks.pop(comparison_id, None)

    async def _execute_comparison(self, comparison: Comparison, runs: list[Run]) -> None:
        """Execute the comparison analysis."""
        logger.info(f"Starting comparison {comparison.id} with {len(runs)} runs")

        # Update status to running
        await self.comparison_dao.update_status(
            comparison.id,
            ComparisonStatus.RUNNING,
        )

        try:
            # Build comparison prompt
            prompt = self._build_comparison_prompt(runs)

            # Get the task for workspace path
            task = await self.task_dao.get(comparison.task_id)
            if not task:
                raise ValueError(f"Task not found: {comparison.task_id}")

            repo = await self.repo_service.get(task.repo_id)
            if not repo:
                raise ValueError(f"Repository not found: {task.repo_id}")

            # Execute analysis with the selected executor or model
            analysis = await self._run_analysis(
                comparison=comparison,
                prompt=prompt,
                workspace_path=repo.workspace_path,
            )

            # Update comparison with results
            await self.comparison_dao.update_status(
                comparison.id,
                ComparisonStatus.SUCCEEDED,
                analysis=analysis,
                run_metrics=comparison.run_metrics,
                file_overlaps=comparison.file_overlaps,
            )

            logger.info(f"Comparison {comparison.id} completed successfully")

        except Exception as e:
            logger.exception(f"Comparison {comparison.id} failed")
            await self.comparison_dao.update_status(
                comparison.id,
                ComparisonStatus.FAILED,
                error=str(e),
            )
            raise

        finally:
            await self.output_manager.mark_complete(comparison.id)

    def _build_comparison_prompt(self, runs: list[Run]) -> str:
        """Build the comparison prompt from runs."""
        prompt_parts = [
            "Compare the following code changes from different AI coding assistants.\n",
            f"All agents were given the same task: {runs[0].instruction}\n\n",
        ]

        for i, run in enumerate(runs, 1):
            executor_name = _get_executor_display_name(run.executor_type)
            if run.model_name:
                executor_name += f" ({run.model_name})"

            prompt_parts.append(f"## Agent {i}: {executor_name}\n\n")

            # Add summary
            if run.summary:
                prompt_parts.append(f"### Summary\n{run.summary}\n\n")

            # Add files changed
            if run.files_changed:
                prompt_parts.append(f"### Files Changed ({len(run.files_changed)} files)\n")
                for f in run.files_changed:
                    prompt_parts.append(f"- {f.path} (+{f.added_lines}, -{f.removed_lines})\n")
                prompt_parts.append("\n")

            # Add patch (truncated if too long)
            if run.patch:
                patch = run.patch
                max_patch_length = 8000
                if len(patch) > max_patch_length:
                    patch = patch[:max_patch_length] + "\n... (truncated)"

                prompt_parts.append(f"### Patch\n```diff\n{patch}\n```\n\n")

            # Add warnings if any
            if run.warnings:
                prompt_parts.append("### Warnings\n")
                for warning in run.warnings:
                    prompt_parts.append(f"- {warning}\n")
                prompt_parts.append("\n")

            prompt_parts.append("---\n\n")

        prompt_parts.append(
            "\nPlease analyze and compare these implementations. "
            "Provide a detailed comparison covering approach, code quality, completeness, "
            "potential issues, and your recommendation."
        )

        return "".join(prompt_parts)

    async def _log_output(self, comparison_id: str, line: str) -> None:
        """Log output line and publish to output manager."""
        logger.info(f"[comparison-{comparison_id[:8]}] {line}")
        await self.output_manager.publish_async(comparison_id, line)

    async def _run_analysis(
        self,
        comparison: Comparison,
        prompt: str,
        workspace_path: str,
    ) -> str:
        """Run the analysis using the specified executor or model."""
        # Full prompt with system instructions
        full_prompt = f"{COMPARISON_SYSTEM_PROMPT}\n\n{prompt}"

        # Use executor if specified
        if comparison.executor_type:
            return await self._run_executor_analysis(
                comparison=comparison,
                executor_type=comparison.executor_type,
                prompt=full_prompt,
                workspace_path=workspace_path,
            )

        # Otherwise use model (default to Claude Code)
        if comparison.model_id:
            # For now, use Claude Code as default executor for model-based analysis
            return await self._run_executor_analysis(
                comparison=comparison,
                executor_type=ExecutorType.CLAUDE_CODE,
                prompt=full_prompt,
                workspace_path=workspace_path,
            )

        raise ValueError("Either executor_type or model_id must be specified")

    async def _run_executor_analysis(
        self,
        comparison: Comparison,
        executor_type: ExecutorType,
        prompt: str,
        workspace_path: str,
    ) -> str:
        """Run analysis using a CLI executor."""
        worktree_path = Path(workspace_path)

        async def on_output(line: str) -> None:
            await self._log_output(comparison.id, line)

        # Execute based on executor type
        if executor_type == ExecutorType.CLAUDE_CODE:
            if not self._claude_executor:
                self._claude_executor = ClaudeCodeExecutor(
                    ClaudeCodeOptions(claude_cli_path=settings.claude_cli_path)
                )
            result = await self._claude_executor.execute(
                worktree_path=worktree_path,
                instruction=prompt,
                on_output=on_output,
                read_only=True,
            )
            return result.summary

        elif executor_type == ExecutorType.CODEX_CLI:
            if not self._codex_executor:
                self._codex_executor = CodexExecutor(
                    CodexOptions(codex_cli_path=settings.codex_cli_path)
                )
            result = await self._codex_executor.execute(
                worktree_path=worktree_path,
                instruction=prompt,
                on_output=on_output,
            )
            return result.summary

        elif executor_type == ExecutorType.GEMINI_CLI:
            if not self._gemini_executor:
                self._gemini_executor = GeminiExecutor(
                    GeminiOptions(gemini_cli_path=settings.gemini_cli_path)
                )
            result = await self._gemini_executor.execute(
                worktree_path=worktree_path,
                instruction=prompt,
                on_output=on_output,
            )
            return result.summary

        else:
            raise ValueError(f"Unsupported executor type for comparison: {executor_type}")

    async def get_comparison(self, comparison_id: str) -> Comparison | None:
        """Get a comparison by ID."""
        return await self.comparison_dao.get(comparison_id)

    async def list_comparisons(self, task_id: str) -> list[Comparison]:
        """List all comparisons for a task."""
        return await self.comparison_dao.list_by_task(task_id)
