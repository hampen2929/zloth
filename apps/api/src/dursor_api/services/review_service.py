"""Review service for code review functionality.

This service manages the execution of AI-powered code reviews
following the same patterns as RunService.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Callable, Coroutine
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dursor_api.config import settings
from dursor_api.domain.enums import (
    ExecutorType,
    MessageRole,
    ReviewCategory,
    ReviewSeverity,
    ReviewStatus,
    RunStatus,
)
from dursor_api.domain.models import (
    FixInstructionRequest,
    FixInstructionResponse,
    Message,
    Review,
    ReviewCreate,
    ReviewFeedbackItem,
    ReviewSummary,
)
from dursor_api.executors.claude_code_executor import ClaudeCodeExecutor, ClaudeCodeOptions
from dursor_api.executors.codex_executor import CodexExecutor, CodexOptions
from dursor_api.executors.gemini_executor import GeminiExecutor, GeminiOptions
from dursor_api.storage.dao import MessageDAO, ReviewDAO, RunDAO, TaskDAO, generate_id

if TYPE_CHECKING:
    from dursor_api.services.output_manager import OutputManager

logger = logging.getLogger(__name__)


REVIEW_SYSTEM_PROMPT = """You are an expert code reviewer. \
Analyze the provided code changes and provide detailed feedback.

For each issue found, provide:
1. **Severity**: critical, high, medium, or low
   - critical: Security vulnerabilities, data loss risks, critical bugs
   - high: Significant bugs, performance issues
   - medium: Code quality, maintainability concerns
   - low: Style suggestions, minor improvements

2. **Category**: security, bug, performance, maintainability, best_practice, style, \
documentation, test

3. **Location**: File path and line numbers

4. **Description**: Clear explanation of the issue

5. **Suggestion**: Recommended fix (if applicable)

Output your review in the following JSON format:
```json
{
  "overall_summary": "Brief summary of the review",
  "overall_score": 0.85,
  "feedbacks": [
    {
      "file_path": "src/example.py",
      "line_start": 42,
      "line_end": 45,
      "severity": "high",
      "category": "bug",
      "title": "Potential null pointer exception",
      "description": "The variable 'user' may be None...",
      "suggestion": "Add null check before accessing...",
      "code_snippet": "user.name"
    }
  ]
}
```

Focus on:
- Security vulnerabilities
- Logic errors and bugs
- Performance issues
- Code maintainability
- Best practices adherence
"""

REVIEW_USER_PROMPT_TEMPLATE = """Please review the following code changes:

{patch}

Provide your detailed review with severity levels and actionable feedback.
Output ONLY the JSON response, no additional text.
"""

REVIEW_USER_PROMPT_FILE_TEMPLATE = """Please review the code changes in the file at: {file_path}

Provide your detailed review with severity levels and actionable feedback.
Output ONLY the JSON response, no additional text.
"""

# Maximum patch size to embed directly in the prompt (in characters)
# Larger patches will be written to a file
MAX_INLINE_PATCH_SIZE = 50000


class ReviewQueueAdapter:
    """Simple in-memory queue adapter for reviews."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def enqueue(
        self,
        review_id: str,
        coro: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        """Enqueue a review for execution."""
        task: asyncio.Task[None] = asyncio.create_task(coro())
        self._tasks[review_id] = task


class ReviewService:
    """Service for managing code reviews."""

    def __init__(
        self,
        review_dao: ReviewDAO,
        run_dao: RunDAO,
        task_dao: TaskDAO,
        message_dao: MessageDAO,
        output_manager: OutputManager | None = None,
    ) -> None:
        self.review_dao = review_dao
        self.run_dao = run_dao
        self.task_dao = task_dao
        self.message_dao = message_dao
        self.output_manager = output_manager
        self.queue = ReviewQueueAdapter()
        self.claude_executor = ClaudeCodeExecutor(
            ClaudeCodeOptions(claude_cli_path=settings.claude_cli_path)
        )
        self.codex_executor = CodexExecutor(CodexOptions(codex_cli_path=settings.codex_cli_path))
        self.gemini_executor = GeminiExecutor(
            GeminiOptions(gemini_cli_path=settings.gemini_cli_path)
        )

    async def create_review(
        self,
        task_id: str,
        data: ReviewCreate,
    ) -> Review:
        """Create and start a review."""
        # 1. Verify task exists
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        # 2. Get and validate target runs
        runs = []
        for run_id in data.target_run_ids:
            run = await self.run_dao.get(run_id)
            if not run:
                raise ValueError(f"Run not found: {run_id}")
            if run.status != RunStatus.SUCCEEDED:
                raise ValueError(f"Run {run_id} is not succeeded")
            runs.append(run)

        # 3. Create review record
        review = Review(
            id=generate_id(),
            task_id=task_id,
            target_run_ids=data.target_run_ids,
            executor_type=data.executor_type,
            model_id=data.model_id,
            model_name=None,
            status=ReviewStatus.QUEUED,
            feedbacks=[],
            logs=[],
            created_at=datetime.utcnow(),
        )
        await self.review_dao.create(review)

        # 4. Enqueue for execution
        def make_coro(r: Review, rns: list[Any]) -> Callable[[], Coroutine[Any, Any, None]]:
            return lambda: self._execute_review(r, rns)

        self.queue.enqueue(review.id, make_coro(review, runs))

        return review

    async def get_review(self, review_id: str) -> Review | None:
        """Get a review by ID."""
        return await self.review_dao.get(review_id)

    async def list_reviews(self, task_id: str) -> list[ReviewSummary]:
        """List reviews for a task."""
        return await self.review_dao.list_by_task(task_id)

    async def get_logs(self, review_id: str, from_line: int = 0) -> dict[str, object]:
        """Get review execution logs."""
        review = await self.review_dao.get(review_id)
        if not review:
            raise ValueError(f"Review not found: {review_id}")

        logs = review.logs[from_line:] if review.logs else []
        is_complete = review.status in (ReviewStatus.SUCCEEDED, ReviewStatus.FAILED)

        return {
            "logs": logs,
            "is_complete": is_complete,
            "total_lines": len(review.logs) if review.logs else 0,
        }

    async def generate_fix_instruction(
        self,
        data: FixInstructionRequest,
    ) -> FixInstructionResponse:
        """Generate fix instruction from review feedbacks."""
        if not data.review_id:
            raise ValueError("review_id is required")

        review = await self.review_dao.get(data.review_id)
        if not review:
            raise ValueError(f"Review not found: {data.review_id}")

        # Filter feedbacks
        feedbacks = review.feedbacks

        if data.feedback_ids:
            feedbacks = [f for f in feedbacks if f.id in data.feedback_ids]

        if data.severity_filter:
            feedbacks = [f for f in feedbacks if f.severity in data.severity_filter]

        if not feedbacks:
            raise ValueError("No feedbacks match the filter criteria")

        # Build fix instruction
        instruction = self._build_fix_instruction(feedbacks, data.additional_instruction)

        return FixInstructionResponse(
            instruction=instruction,
            target_feedbacks=feedbacks,
            estimated_changes=len(set(f.file_path for f in feedbacks)),
        )

    async def add_review_to_conversation(
        self,
        review_id: str,
    ) -> Message:
        """Add completed review as a message in the conversation."""
        review = await self.review_dao.get(review_id)
        if not review:
            raise ValueError(f"Review not found: {review_id}")

        if review.status != ReviewStatus.SUCCEEDED:
            raise ValueError(f"Review not completed: {review.status}")

        # Format review result as markdown
        content = self._format_review_as_message(review)

        # Save as message
        message = await self.message_dao.create(
            task_id=review.task_id,
            role=MessageRole.ASSISTANT,
            content=content,
        )

        return message

    async def _execute_review(
        self,
        review: Review,
        runs: list[Any],
    ) -> None:
        """Execute review using selected executor."""
        logs: list[str] = []
        try:
            # Update status to running
            await self.review_dao.update_status(
                review.id,
                ReviewStatus.RUNNING,
            )
            logs.append("Starting review execution...")

            # Combine patches from runs
            combined_patch = self._combine_patches(runs)
            logs.append(f"Combined {len(runs)} run(s) for review")

            # Get worktree path from the first run with a valid path
            worktree_path: Path | None = None
            for run in runs:
                if run.worktree_path:
                    worktree_path = Path(run.worktree_path)
                    if worktree_path.exists():
                        break
                    worktree_path = None

            # Execute review based on executor type
            if review.executor_type in (
                ExecutorType.CLAUDE_CODE,
                ExecutorType.CODEX_CLI,
                ExecutorType.GEMINI_CLI,
            ):
                result = await self._execute_cli_review(review, combined_patch, logs, worktree_path)
            else:
                # For patch_agent, use a simpler approach
                result = self._create_default_review_result(combined_patch)
                logs.append("Used default review analysis")

            # Save results
            await self.review_dao.update_status(
                review.id,
                ReviewStatus.SUCCEEDED,
                summary=result.get("overall_summary"),
                score=result.get("overall_score"),
                feedbacks=result.get("feedbacks", []),
                logs=logs,
            )

        except Exception as e:
            logger.exception(f"Review execution failed: {e}")
            logs.append(f"Review failed: {str(e)}")
            await self.review_dao.update_status(
                review.id,
                ReviewStatus.FAILED,
                error=str(e),
                logs=logs,
            )

    async def _execute_cli_review(
        self,
        review: Review,
        patch: str,
        logs: list[str],
        worktree_path: Path | None,
    ) -> dict[str, Any]:
        """Execute review using CLI executor."""
        import tempfile as tmpfile

        # Select executor
        executor_map: dict[
            ExecutorType, tuple[ClaudeCodeExecutor | CodexExecutor | GeminiExecutor, str]
        ] = {
            ExecutorType.CLAUDE_CODE: (self.claude_executor, "Claude Code"),
            ExecutorType.CODEX_CLI: (self.codex_executor, "Codex"),
            ExecutorType.GEMINI_CLI: (self.gemini_executor, "Gemini"),
        }

        executor, executor_name = executor_map[review.executor_type]
        logs.append(f"Using {executor_name} for review")
        logs.append(f"Patch size: {len(patch)} characters")

        # Determine working directory
        if worktree_path and worktree_path.exists():
            work_dir = worktree_path
            logs.append(f"Using worktree: {work_dir}")
        else:
            # Create a temporary directory for review if no worktree
            work_dir = Path(tmpfile.mkdtemp(prefix="review_"))
            logs.append(f"Using temporary directory: {work_dir}")

        try:
            # For large patches, write to a file and reference it
            if len(patch) > MAX_INLINE_PATCH_SIZE:
                patch_file = work_dir / "review_patch.diff"
                patch_file.write_text(patch, encoding="utf-8")
                logs.append(f"Patch too large for inline, written to: {patch_file}")

                review_prompt = f"""{REVIEW_SYSTEM_PROMPT}

{REVIEW_USER_PROMPT_FILE_TEMPLATE.format(file_path=str(patch_file))}"""
            else:
                review_prompt = f"""{REVIEW_SYSTEM_PROMPT}

{REVIEW_USER_PROMPT_TEMPLATE.format(patch=patch)}"""

            logs.append(f"Prompt size: {len(review_prompt)} characters")

            result = await executor.execute(
                worktree_path=work_dir,
                instruction=review_prompt,
                on_output=lambda line: self._log_output(review.id, line, logs),
            )

            if not result.success:
                raise RuntimeError(f"CLI execution failed: {result.error}")

            # Parse response to extract JSON
            response_text = "\n".join(result.logs)
            return self._parse_review_response(response_text, logs)

        finally:
            # Cleanup temporary directory if we created one
            if not worktree_path or not worktree_path.exists():
                import shutil

                if work_dir.exists():
                    shutil.rmtree(work_dir, ignore_errors=True)

    def _parse_review_response(self, response_text: str, logs: list[str]) -> dict[str, Any]:
        """Parse the review response from CLI output."""
        # Try to extract JSON from the response
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if json_match:
            try:
                data = json.loads(json_match.group())
                feedbacks = []
                for fb_data in data.get("feedbacks", []):
                    try:
                        feedback = ReviewFeedbackItem(
                            id=generate_id(),
                            file_path=fb_data.get("file_path", "unknown"),
                            line_start=fb_data.get("line_start"),
                            line_end=fb_data.get("line_end"),
                            severity=ReviewSeverity(fb_data.get("severity", "medium").lower()),
                            category=ReviewCategory(
                                fb_data.get("category", "maintainability").lower()
                            ),
                            title=fb_data.get("title", "Review finding"),
                            description=fb_data.get("description", ""),
                            suggestion=fb_data.get("suggestion"),
                            code_snippet=fb_data.get("code_snippet"),
                        )
                        feedbacks.append(feedback)
                    except Exception as e:
                        logs.append(f"Warning: Could not parse feedback: {e}")

                logs.append(f"Parsed {len(feedbacks)} feedback items")
                return {
                    "overall_summary": data.get("overall_summary", "Review completed"),
                    "overall_score": data.get("overall_score"),
                    "feedbacks": feedbacks,
                }
            except json.JSONDecodeError as e:
                logs.append(f"Warning: Could not parse JSON response: {e}")

        # Fallback: create a summary-only result
        logs.append("Using fallback review parsing")
        return self._create_default_review_result(response_text)

    def _create_default_review_result(self, content: str) -> dict[str, Any]:
        """Create a default review result when parsing fails."""
        return {
            "overall_summary": "Review completed. Please check the logs for details.",
            "overall_score": None,
            "feedbacks": [],
        }

    def _combine_patches(self, runs: list[Any]) -> str:
        """Combine patches from multiple runs."""
        patches = []
        for run in runs:
            if run.patch:
                patches.append(f"# Changes from Run {run.id[:8]}\n{run.patch}")
        return "\n\n".join(patches)

    def _build_fix_instruction(
        self,
        feedbacks: list[ReviewFeedbackItem],
        additional: str | None,
    ) -> str:
        """Build fix instruction from feedbacks."""
        parts = ["Please fix the following issues identified in the code review:\n"]

        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_feedbacks = sorted(feedbacks, key=lambda f: severity_order.get(f.severity.value, 4))

        for i, fb in enumerate(sorted_feedbacks, 1):
            parts.append(f"\n## Issue {i}: [{fb.severity.value.upper()}] {fb.title}")
            parts.append(f"**File**: `{fb.file_path}`")
            if fb.line_start:
                line_info = f"Line {fb.line_start}"
                if fb.line_end and fb.line_end != fb.line_start:
                    line_info += f"-{fb.line_end}"
                parts.append(f"**Location**: {line_info}")
            parts.append(f"**Category**: {fb.category.value}")
            parts.append(f"\n{fb.description}")
            if fb.suggestion:
                parts.append(f"\n**Suggested fix**: {fb.suggestion}")

        if additional:
            parts.append(f"\n---\n**Additional instructions**: {additional}")

        parts.append(
            "\n---\nPlease address all the issues above and ensure the code is correct and secure."
        )

        return "\n".join(parts)

    def _format_review_as_message(self, review: Review) -> str:
        """Format review result as conversation message."""
        parts = ["## Code Review Results\n"]

        if review.overall_summary:
            parts.append(f"{review.overall_summary}\n")

        if review.overall_score is not None:
            score_pct = int(review.overall_score * 100)
            parts.append(f"**Overall Score**: {score_pct}%\n")

        # Summary statistics
        severity_counts = {
            "critical": len([f for f in review.feedbacks if f.severity.value == "critical"]),
            "high": len([f for f in review.feedbacks if f.severity.value == "high"]),
            "medium": len([f for f in review.feedbacks if f.severity.value == "medium"]),
            "low": len([f for f in review.feedbacks if f.severity.value == "low"]),
        }
        parts.append(f"**Issues Found**: {len(review.feedbacks)} total")
        parts.append(f"  - Critical: {severity_counts['critical']}")
        parts.append(f"  - High: {severity_counts['high']}")
        parts.append(f"  - Medium: {severity_counts['medium']}")
        parts.append(f"  - Low: {severity_counts['low']}\n")

        # Each feedback
        if review.feedbacks:
            parts.append("### Issues\n")
            for fb in review.feedbacks:
                parts.append(f"- **[{fb.severity.value.upper()}]** {fb.title}")
                parts.append(f"  - File: `{fb.file_path}`")
                if fb.line_start:
                    parts.append(f"  - Line: {fb.line_start}")

        return "\n".join(parts)

    async def _log_output(self, review_id: str, line: str, logs: list[str]) -> None:
        """Log output from CLI execution."""
        logger.info(f"[review-{review_id[:8]}] {line}")
        logs.append(line)

        if self.output_manager:
            await self.output_manager.publish_async(f"review-{review_id}", line)
