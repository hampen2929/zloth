"""Review service for code review functionality.

This service manages the execution of AI-powered code reviews
following the same patterns as RunService.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Coroutine
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tazuna_api.config import settings
from tazuna_api.domain.enums import (
    ExecutorType,
    MessageRole,
    ReviewCategory,
    ReviewSeverity,
    ReviewStatus,
    RoleExecutionStatus,
    RunStatus,
)
from tazuna_api.domain.models import (
    AgentConstraints,
    FixInstructionRequest,
    FixInstructionResponse,
    Message,
    Review,
    ReviewCreate,
    ReviewExecutionResult,
    ReviewFeedbackItem,
    ReviewSummary,
)
from tazuna_api.executors.claude_code_executor import ClaudeCodeExecutor, ClaudeCodeOptions
from tazuna_api.executors.codex_executor import CodexExecutor, CodexOptions
from tazuna_api.executors.gemini_executor import GeminiExecutor, GeminiOptions
from tazuna_api.roles.base_service import BaseRoleService
from tazuna_api.roles.registry import RoleRegistry
from tazuna_api.storage.dao import MessageDAO, ReviewDAO, RunDAO, TaskDAO, generate_id

if TYPE_CHECKING:
    from tazuna_api.services.output_manager import OutputManager

logger = logging.getLogger(__name__)


REVIEW_SYSTEM_PROMPT = """You are an expert code reviewer. \
Analyze the provided code changes and provide detailed feedback.

CRITICAL: This is a READ-ONLY review task.
- DO NOT modify any files
- DO NOT write any code changes
- DO NOT create new files
- DO NOT use any file editing tools
- ONLY analyze the code and provide feedback in JSON format

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

IMPORTANT: You MUST output ONLY valid JSON in the following format. Do not include any text \
before or after the JSON. Do not use markdown code blocks. Output raw JSON only.
DO NOT make any file modifications - just analyze and respond with JSON.

{
  "overall_summary": "Brief summary of the code review findings",
  "overall_score": 0.85,
  "feedbacks": [
    {
      "file_path": "src/example.py",
      "line_start": 42,
      "line_end": 45,
      "severity": "high",
      "category": "bug",
      "title": "Potential null pointer exception",
      "description": "The variable 'user' may be None when accessed here.",
      "suggestion": "Add null check before accessing user properties.",
      "code_snippet": "user.name"
    }
  ]
}

Rules:
- overall_score: A number between 0.0 and 1.0 (1.0 = perfect code)
- severity: Must be one of: "critical", "high", "medium", "low"
- category: Must be one of: "security", "bug", "performance", "maintainability", \
"best_practice", "style", "documentation", "test"
- If no issues found, return empty feedbacks array: "feedbacks": []
- Always provide overall_summary and overall_score

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


@RoleRegistry.register("review")
class ReviewService(BaseRoleService[Review, ReviewCreate, ReviewExecutionResult]):
    """Service for managing code reviews (Review Role).

    This service inherits from BaseRoleService for common role patterns
    while maintaining its specialized review logic.
    """

    def __init__(
        self,
        review_dao: ReviewDAO,
        run_dao: RunDAO,
        task_dao: TaskDAO,
        message_dao: MessageDAO,
        output_manager: OutputManager | None = None,
    ) -> None:
        # Initialize base class with output manager
        super().__init__(output_manager=output_manager)

        self.review_dao = review_dao
        self.run_dao = run_dao
        self.task_dao = task_dao
        self.message_dao = message_dao
        # Note: self.output_manager is set by base class
        self.queue = ReviewQueueAdapter()
        # Note: Executors are also available via self._executors from base class
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

        patch_file: Path | None = None
        try:
            # Build constraints to ensure review doesn't modify files
            constraints = AgentConstraints()
            constraints_prompt = constraints.to_prompt()

            # For large patches, write to a file and reference it
            if len(patch) > MAX_INLINE_PATCH_SIZE:
                patch_file = work_dir / "review_patch.diff"
                patch_file.write_text(patch, encoding="utf-8")
                logs.append(f"Patch too large for inline, written to: {patch_file}")

                review_prompt = f"""{constraints_prompt}

{REVIEW_SYSTEM_PROMPT}

{REVIEW_USER_PROMPT_FILE_TEMPLATE.format(file_path=str(patch_file))}"""
            else:
                review_prompt = f"""{constraints_prompt}

{REVIEW_SYSTEM_PROMPT}

{REVIEW_USER_PROMPT_TEMPLATE.format(patch=patch)}"""

            logs.append(f"Prompt size: {len(review_prompt)} characters")

            # Execute in read-only mode to prevent file modifications during review
            result = await executor.execute(
                worktree_path=work_dir,
                instruction=review_prompt,
                on_output=lambda line: self._log_output(review.id, line, logs),
                read_only=True,  # Review should never modify files
            )

            if not result.success:
                raise RuntimeError(f"CLI execution failed: {result.error}")

            # Parse response to extract JSON
            response_text = "\n".join(result.logs)
            return self._parse_review_response(response_text, logs)

        finally:
            # Clean up the patch file if we created one
            if patch_file and patch_file.exists():
                try:
                    patch_file.unlink()
                    logs.append("Cleaned up review_patch.diff")
                except Exception as e:
                    logs.append(f"Warning: Failed to clean up patch file: {e}")

            # Reset any uncommitted changes in the worktree to prevent pollution
            # This is critical to ensure review doesn't affect subsequent runs
            if worktree_path and worktree_path.exists():
                try:
                    import subprocess

                    # Discard any uncommitted changes made by the review executor
                    result_reset = subprocess.run(
                        ["git", "checkout", "--", "."],
                        cwd=work_dir,
                        capture_output=True,
                        text=True,
                    )
                    if result_reset.returncode == 0:
                        logs.append("Reset worktree to clean state after review")
                    # Also remove any untracked files created by review
                    result_clean = subprocess.run(
                        ["git", "clean", "-fd"],
                        cwd=work_dir,
                        capture_output=True,
                        text=True,
                    )
                    if result_clean.returncode == 0:
                        logs.append("Removed untracked files from worktree")
                except Exception as e:
                    logs.append(f"Warning: Failed to reset worktree: {e}")
            else:
                # Cleanup temporary directory if we created one
                import shutil

                if work_dir.exists():
                    shutil.rmtree(work_dir, ignore_errors=True)

    def _parse_review_response(self, response_text: str, logs: list[str]) -> dict[str, Any]:
        """Parse the review response from CLI output."""
        # Try to extract JSON from the response using multiple strategies

        # Strategy 1: Find balanced JSON objects and try each one
        # Process in REVERSE order since the actual response comes after the prompt
        # (the prompt contains an example JSON that we need to skip)
        json_candidates = self._extract_json_objects(response_text)
        logs.append(f"Strategy 1: Found {len(json_candidates)} potential JSON objects")

        review_format_count = 0
        template_count = 0
        parse_error_count = 0

        for i, candidate in enumerate(reversed(json_candidates)):
            original_index = len(json_candidates) - i
            try:
                data = json.loads(candidate)
                # Check if this looks like our expected review format
                if isinstance(data, dict) and ("feedbacks" in data or "overall_summary" in data):
                    review_format_count += 1
                    # Skip if this looks like the template example from the system prompt
                    if self._is_template_example(data):
                        template_count += 1
                        logs.append(f"Strategy 1: Skipping template at position #{original_index}")
                        continue
                    logs.append(
                        f"Strategy 1: Found valid review JSON at position #{original_index}"
                    )
                    return self._process_review_data(data, logs)
            except json.JSONDecodeError as e:
                parse_error_count += 1
                # Log first few parse errors for debugging
                if parse_error_count <= 3:
                    logs.append(
                        f"Strategy 1: JSON parse error at #{original_index}: {str(e)[:100]}"
                    )
                continue

        logs.append(
            f"Strategy 1 summary: {review_format_count} review-format JSONs, "
            f"{template_count} templates skipped, {parse_error_count} parse errors"
        )

        # Strategy 2: Try to find valid JSON by searching from the END of the text
        # This is important because the actual review result comes after the prompt
        # which contains template examples
        logs.append("Strategy 1 failed, trying Strategy 2 (search from end)")

        # Find all { positions and try from the last one first
        brace_positions = [i for i, c in enumerate(response_text) if c == "{"]
        for start_pos in reversed(brace_positions):
            # Try to find a valid JSON starting from this position
            for end_pos in range(len(response_text), start_pos, -1):
                if response_text[end_pos - 1] == "}":
                    candidate = response_text[start_pos:end_pos]
                    try:
                        data = json.loads(candidate)
                        if isinstance(data, dict) and (
                            "feedbacks" in data or "overall_summary" in data
                        ):
                            # Skip template examples
                            if self._is_template_example(data):
                                logs.append(
                                    f"Strategy 2: Skipping template example at position {start_pos}"
                                )
                                break  # Try next start position
                            logs.append(
                                f"Strategy 2: Successfully parsed JSON at position {start_pos}"
                            )
                            return self._process_review_data(data, logs)
                    except json.JSONDecodeError:
                        continue

        # Fallback: create a summary-only result
        logs.append("All strategies failed - no valid review JSON found")
        return self._create_default_review_result(response_text)

    def _extract_json_objects(self, text: str) -> list[str]:
        """Extract balanced JSON objects from text."""
        objects = []
        i = 0
        while i < len(text):
            if text[i] == "{":
                # Find matching closing brace
                depth = 0
                start = i
                in_string = False
                escape_next = False

                while i < len(text):
                    char = text[i]

                    if escape_next:
                        escape_next = False
                        i += 1
                        continue

                    if char == "\\":
                        escape_next = True
                        i += 1
                        continue

                    if char == '"' and not escape_next:
                        in_string = not in_string

                    if not in_string:
                        if char == "{":
                            depth += 1
                        elif char == "}":
                            depth -= 1
                            if depth == 0:
                                objects.append(text[start : i + 1])
                                break
                    i += 1
            else:
                i += 1

        return objects

    def _is_template_example(self, data: dict[str, Any]) -> bool:
        """Check if the parsed JSON looks like the template example from the system prompt.

        The system prompt contains an example JSON with file_path="src/example.py" that
        should not be treated as actual review results.
        """
        feedbacks = data.get("feedbacks", [])
        if not isinstance(feedbacks, list) or not feedbacks:
            return False

        # Check if all feedbacks reference the template example file
        for fb in feedbacks:
            if not isinstance(fb, dict):
                continue
            file_path = fb.get("file_path", "")
            # The template uses "src/example.py" as the example file path
            if file_path != "src/example.py":
                return False

        # Additional check: the template example has specific content
        if len(feedbacks) == 1:
            fb = feedbacks[0]
            if (
                fb.get("title") == "Potential null pointer exception"
                and fb.get("line_start") == 42
                and fb.get("line_end") == 45
            ):
                return True

        # If all feedbacks reference src/example.py, it's likely the template
        return all(
            isinstance(fb, dict) and fb.get("file_path") == "src/example.py" for fb in feedbacks
        )

    def _process_review_data(self, data: dict[str, Any], logs: list[str]) -> dict[str, Any]:
        """Process parsed review data into the expected format."""
        feedbacks = []
        for fb_data in data.get("feedbacks", []):
            try:
                feedback = ReviewFeedbackItem(
                    id=generate_id(),
                    file_path=fb_data.get("file_path", "unknown"),
                    line_start=fb_data.get("line_start"),
                    line_end=fb_data.get("line_end"),
                    severity=ReviewSeverity(fb_data.get("severity", "medium").lower()),
                    category=ReviewCategory(fb_data.get("category", "maintainability").lower()),
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

    # ==========================================
    # BaseRoleService Abstract Method Implementations
    # ==========================================

    async def create(self, task_id: str, data: ReviewCreate) -> Review:
        """Create a review (BaseRoleService interface).

        Args:
            task_id: Task ID.
            data: Review creation data.

        Returns:
            Created Review object.
        """
        return await self.create_review(task_id, data)

    async def get(self, review_id: str) -> Review | None:
        """Get a review by ID (BaseRoleService interface).

        Args:
            review_id: Review ID.

        Returns:
            Review object or None if not found.
        """
        return await self.get_review(review_id)

    async def list_by_task(self, task_id: str) -> list[Review]:
        """List reviews for a task (BaseRoleService interface).

        Note: Returns full Review objects, not ReviewSummary.

        Args:
            task_id: Task ID.

        Returns:
            List of Review objects.
        """
        # Get summaries and convert to full reviews
        summaries = await self.list_reviews(task_id)
        reviews = []
        for summary in summaries:
            review = await self.review_dao.get(summary.id)
            if review:
                reviews.append(review)
        return reviews

    async def _execute(self, record: Review) -> ReviewExecutionResult:
        """Execute review-specific logic (BaseRoleService interface).

        Note: ReviewService uses its own execution flow via _execute_review,
        so this method is not directly used.

        Args:
            record: Review record.

        Returns:
            ReviewExecutionResult.
        """
        # ReviewService manages execution via create_review which enqueues
        # _execute_review directly. This is provided for interface compliance.
        return ReviewExecutionResult(
            success=False,
            error="Direct execution not supported. Use create_review() instead.",
        )

    async def _update_status(
        self,
        record_id: str,
        status: RoleExecutionStatus,
        result: ReviewExecutionResult | None = None,
    ) -> None:
        """Update review status (BaseRoleService interface).

        Args:
            record_id: Review ID.
            status: New status.
            result: Optional result to save.
        """
        if result:
            await self.review_dao.update_status(
                record_id,
                status,
                summary=result.summary,
                score=result.overall_score,
                feedbacks=result.feedbacks,
                logs=result.logs,
                error=result.error,
            )
        else:
            await self.review_dao.update_status(record_id, status)

    def _get_record_id(self, record: Review) -> str:
        """Extract ID from review (BaseRoleService interface).

        Args:
            record: Review record.

        Returns:
            Review ID.
        """
        return record.id

    def _create_error_result(self, error: str) -> ReviewExecutionResult:
        """Create error result (BaseRoleService interface).

        Args:
            error: Error message.

        Returns:
            ReviewExecutionResult with error.
        """
        return ReviewExecutionResult(
            success=False,
            error=error,
            logs=[f"Error: {error}"],
        )
