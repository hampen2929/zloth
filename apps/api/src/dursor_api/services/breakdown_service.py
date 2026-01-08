"""Task breakdown service for decomposing hearing content into tasks.

This service uses CLI executors (Claude Code, Codex, Gemini) to analyze
a codebase and break down hearing content into actionable development tasks.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any

from dursor_api.config import settings
from dursor_api.domain.enums import BreakdownStatus, BrokenDownTaskType, EstimatedSize, ExecutorType
from dursor_api.domain.models import (
    BrokenDownTask,
    CodebaseAnalysis,
    Repo,
    TaskBreakdownRequest,
    TaskBreakdownResponse,
)
from dursor_api.executors.claude_code_executor import ClaudeCodeExecutor, ClaudeCodeOptions
from dursor_api.executors.codex_executor import CodexExecutor, CodexOptions
from dursor_api.executors.gemini_executor import GeminiExecutor, GeminiOptions
from dursor_api.services.output_manager import OutputManager
from dursor_api.storage.dao import RepoDAO

logger = logging.getLogger(__name__)

# JSON file name for breakdown result
BREAKDOWN_RESULT_FILE = ".dursor-breakdown.json"

# Prompt template for task breakdown
BREAKDOWN_INSTRUCTION_TEMPLATE = """
You are a software development task decomposition expert.
Break down the following hearing content into specific development tasks.

## Important: Codebase Analysis
1. First, review the codebase in this repository
2. Understand existing implementation patterns, architecture, and naming conventions
3. Show specifically how each task relates to existing code

## Hearing Content
{content}

## Output Format
Output the result as a JSON file at `.dursor-breakdown.json`:

```json
{{
  "codebase_analysis": {{
    "files_analyzed": <number of files analyzed>,
    "relevant_modules": ["relevant module names"],
    "tech_stack": ["detected technologies"]
  }},
  "tasks": [
    {{
      "title": "Brief task title (max 50 chars)",
      "description": "Detailed task description with implementation approach",
      "type": "feature | bug_fix | refactoring | docs | test",
      "estimated_size": "small | medium | large",
      "target_files": ["paths to files that need changes"],
      "implementation_hint": "Specific implementation hints (referencing existing code)",
      "tags": ["related tags"]
    }}
  ]
}}
```

## Rules
1. **Always read code first** before creating tasks
2. target_files must be actual existing file paths
3. implementation_hint should be specific, referencing existing code patterns
4. Each task should be independently executable
5. Separate bug fixes and feature additions
6. Note dependencies in description if any
7. Size estimation guide:
   - small: 1-2 file changes, few hours
   - medium: 3-5 file changes, about 1 day
   - large: Multiple modules, several days
8. IMPORTANT: Create the `.dursor-breakdown.json` file with your analysis
"""


class BreakdownService:
    """Service for breaking down hearing content into development tasks.

    This service:
    1. Prepares a temporary worktree for code analysis
    2. Runs an executor to analyze codebase and decompose tasks
    3. Parses the result and returns structured tasks
    """

    def __init__(
        self,
        repo_dao: RepoDAO,
        output_manager: OutputManager,
    ):
        """Initialize BreakdownService.

        Args:
            repo_dao: Repository data access object.
            output_manager: Manager for streaming output.
        """
        self.repo_dao = repo_dao
        self.output_manager = output_manager

        # Store breakdown results (in-memory for now)
        self._results: dict[str, TaskBreakdownResponse] = {}
        # Track running tasks
        self._running_tasks: dict[str, asyncio.Task[None]] = {}

        # Initialize executors
        self._claude_executor = ClaudeCodeExecutor(
            ClaudeCodeOptions(
                timeout_seconds=1800,  # 30 min for breakdown
                claude_cli_path=settings.claude_cli_path,
            )
        )
        self._codex_executor = CodexExecutor(
            CodexOptions(
                timeout_seconds=1800,
                codex_cli_path=settings.codex_cli_path,
            )
        )
        self._gemini_executor = GeminiExecutor(
            GeminiOptions(
                timeout_seconds=1800,
                gemini_cli_path=settings.gemini_cli_path,
            )
        )

        # Executor map
        self._executors: dict[
            ExecutorType, ClaudeCodeExecutor | CodexExecutor | GeminiExecutor
        ] = {
            ExecutorType.CLAUDE_CODE: self._claude_executor,
            ExecutorType.CODEX_CLI: self._codex_executor,
            ExecutorType.GEMINI_CLI: self._gemini_executor,
        }

    def _get_executor(
        self, executor_type: ExecutorType
    ) -> ClaudeCodeExecutor | CodexExecutor | GeminiExecutor:
        """Get executor for the given type.

        Args:
            executor_type: Type of executor.

        Returns:
            Executor instance.

        Raises:
            ValueError: If executor type is not supported for breakdown.
        """
        if executor_type == ExecutorType.PATCH_AGENT:
            raise ValueError("patch_agent is not supported for task breakdown. Use CLI executors.")

        executor = self._executors.get(executor_type)
        if not executor:
            raise ValueError(f"Unknown executor type: {executor_type}")

        return executor

    async def breakdown(
        self,
        request: TaskBreakdownRequest,
    ) -> TaskBreakdownResponse:
        """Start breaking down hearing content into development tasks.

        This method returns immediately with a 'running' status and processes
        the breakdown in the background. Use get_result() to poll for completion.

        Args:
            request: Breakdown request with content, executor type, and repo ID.

        Returns:
            TaskBreakdownResponse with 'running' status and breakdown_id.
        """
        breakdown_id = str(uuid.uuid4())
        logger.info(f"Starting breakdown {breakdown_id} for repo {request.repo_id}")

        # Validate repository exists first
        repo = await self.repo_dao.get(request.repo_id)
        if not repo:
            return TaskBreakdownResponse(
                breakdown_id=breakdown_id,
                status=BreakdownStatus.FAILED,
                tasks=[],
                summary=None,
                original_content=request.content,
                error=f"Repository not found: {request.repo_id}",
            )

        # Create initial response with 'running' status
        initial_response = TaskBreakdownResponse(
            breakdown_id=breakdown_id,
            status=BreakdownStatus.RUNNING,
            tasks=[],
            summary=None,
            original_content=request.content,
        )

        # Store initial result
        self._results[breakdown_id] = initial_response

        # Start background task
        task = asyncio.create_task(
            self._run_breakdown_in_background(breakdown_id, repo, request)
        )
        self._running_tasks[breakdown_id] = task

        return initial_response

    async def _run_breakdown_in_background(
        self,
        breakdown_id: str,
        repo: Repo,
        request: TaskBreakdownRequest,
    ) -> None:
        """Run breakdown in background and update result when done."""
        try:
            result = await self._execute_breakdown(
                breakdown_id=breakdown_id,
                repo=repo,
                request=request,
            )
            self._results[breakdown_id] = result
        except Exception as e:
            logger.exception(f"Breakdown {breakdown_id} failed: {e}")
            await self.output_manager.mark_complete(breakdown_id)
            self._results[breakdown_id] = TaskBreakdownResponse(
                breakdown_id=breakdown_id,
                status=BreakdownStatus.FAILED,
                tasks=[],
                summary=None,
                original_content=request.content,
                error=str(e),
            )
        finally:
            # Clean up running task reference
            self._running_tasks.pop(breakdown_id, None)

    async def get_result(self, breakdown_id: str) -> TaskBreakdownResponse | None:
        """Get the result of a breakdown.

        Args:
            breakdown_id: The breakdown ID to get result for.

        Returns:
            TaskBreakdownResponse if found, None otherwise.
        """
        return self._results.get(breakdown_id)

    async def _execute_breakdown(
        self,
        breakdown_id: str,
        repo: Repo,
        request: TaskBreakdownRequest,
    ) -> TaskBreakdownResponse:
        """Execute the breakdown using the selected executor.

        Args:
            breakdown_id: Unique breakdown session ID.
            repo: Repository to analyze.
            request: Breakdown request.

        Returns:
            TaskBreakdownResponse with results.
        """
        executor = self._get_executor(request.executor_type)
        workspace_path = Path(repo.workspace_path)

        # Build instruction
        instruction = BREAKDOWN_INSTRUCTION_TEMPLATE.format(content=request.content)

        # Add context if provided
        if request.context:
            context_str = "\n".join(f"- {k}: {v}" for k, v in request.context.items())
            instruction += f"\n\n## Additional Context\n{context_str}"

        # Stream output callback
        async def on_output(line: str) -> None:
            await self.output_manager.publish_async(breakdown_id, line)

        await on_output("Starting task breakdown analysis...")
        await on_output(f"Using executor: {request.executor_type.value}")
        await on_output(f"Repository: {repo.repo_url}")

        # Execute
        result = await executor.execute(
            worktree_path=workspace_path,
            instruction=instruction,
            on_output=on_output,
        )

        if not result.success:
            await self.output_manager.mark_complete(breakdown_id)
            return TaskBreakdownResponse(
                breakdown_id=breakdown_id,
                status=BreakdownStatus.FAILED,
                tasks=[],
                summary=None,
                original_content=request.content,
                error=result.error or "Breakdown execution failed",
            )

        # Parse result from file
        result_file = workspace_path / BREAKDOWN_RESULT_FILE
        parsed = await self._parse_breakdown_result(result_file, result.logs)

        # Clean up result file
        if result_file.exists():
            try:
                result_file.unlink()
            except OSError:
                pass

        await self.output_manager.mark_complete(breakdown_id)

        if parsed is None:
            return TaskBreakdownResponse(
                breakdown_id=breakdown_id,
                status=BreakdownStatus.FAILED,
                tasks=[],
                summary=None,
                original_content=request.content,
                error="Failed to parse breakdown result. "
                "The agent may not have created the result file.",
            )

        tasks, codebase_analysis = parsed
        task_count = len(tasks)
        await on_output(f"Breakdown complete: {task_count} task(s) identified")

        return TaskBreakdownResponse(
            breakdown_id=breakdown_id,
            status=BreakdownStatus.SUCCEEDED,
            tasks=tasks,
            summary=f"Analyzed codebase and identified {task_count} task(s)",
            original_content=request.content,
            codebase_analysis=codebase_analysis,
        )

    async def _parse_breakdown_result(
        self,
        result_file: Path,
        logs: list[str],
    ) -> tuple[list[BrokenDownTask], CodebaseAnalysis | None] | None:
        """Parse breakdown result from file or logs.

        Args:
            result_file: Path to the result JSON file.
            logs: Execution logs (fallback for finding JSON).

        Returns:
            Tuple of (tasks, codebase_analysis) or None if parsing failed.
        """
        json_data: dict[str, Any] | None = None

        # Try to read from file first
        if result_file.exists():
            try:
                content = result_file.read_text(encoding="utf-8")
                json_data = json.loads(content)
                logger.info(f"Parsed breakdown result from file: {result_file}")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to parse result file: {e}")

        # Fallback: try to extract JSON from logs
        if json_data is None:
            json_data = self._extract_json_from_logs(logs)

        if json_data is None:
            logger.error("Could not find breakdown result in file or logs")
            return None

        return self._parse_json_data(json_data)

    def _extract_json_from_logs(self, logs: list[str]) -> dict[str, Any] | None:
        """Extract JSON from execution logs.

        Args:
            logs: List of log lines.

        Returns:
            Parsed JSON data or None.
        """
        # Join logs and look for JSON block
        combined = "\n".join(logs)

        # Try to find JSON block in markdown code fence
        json_pattern = r"```(?:json)?\s*(\{[\s\S]*?\})\s*```"
        matches = re.findall(json_pattern, combined)

        for match in matches:
            try:
                data = json.loads(match)
                if "tasks" in data:
                    return data
            except json.JSONDecodeError:
                continue

        # Try to find raw JSON object
        # Look for pattern starting with { and containing "tasks"
        raw_json_pattern = r'(\{\s*"(?:codebase_analysis|tasks)"[\s\S]*\})'
        matches = re.findall(raw_json_pattern, combined)

        for match in matches:
            try:
                data = json.loads(match)
                if "tasks" in data:
                    return data
            except json.JSONDecodeError:
                continue

        return None

    def _parse_json_data(
        self, data: dict[str, Any]
    ) -> tuple[list[BrokenDownTask], CodebaseAnalysis | None]:
        """Parse JSON data into structured models.

        Args:
            data: Raw JSON data.

        Returns:
            Tuple of (tasks, codebase_analysis).
        """
        tasks: list[BrokenDownTask] = []
        codebase_analysis: CodebaseAnalysis | None = None

        # Parse codebase analysis
        if "codebase_analysis" in data:
            ca = data["codebase_analysis"]
            codebase_analysis = CodebaseAnalysis(
                files_analyzed=ca.get("files_analyzed", 0),
                relevant_modules=ca.get("relevant_modules", []),
                tech_stack=ca.get("tech_stack", []),
            )

        # Parse tasks
        for task_data in data.get("tasks", []):
            # Parse type with fallback
            task_type_str = task_data.get("type", "feature")
            try:
                task_type = BrokenDownTaskType(task_type_str)
            except ValueError:
                task_type = BrokenDownTaskType.FEATURE

            # Parse size with fallback
            size_str = task_data.get("estimated_size", "medium")
            try:
                estimated_size = EstimatedSize(size_str)
            except ValueError:
                estimated_size = EstimatedSize.MEDIUM

            task = BrokenDownTask(
                title=task_data.get("title", "Untitled Task")[:50],
                description=task_data.get("description", ""),
                type=task_type,
                estimated_size=estimated_size,
                target_files=task_data.get("target_files", []),
                implementation_hint=task_data.get("implementation_hint"),
                tags=task_data.get("tags", []),
            )
            tasks.append(task)

        return tasks, codebase_analysis

    async def get_logs(
        self,
        breakdown_id: str,
        from_line: int = 0,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Get breakdown logs.

        Args:
            breakdown_id: Breakdown session ID.
            from_line: Line number to start from.

        Returns:
            Tuple of (logs, is_complete).
        """
        history = await self.output_manager.get_history(breakdown_id, from_line)
        is_complete = await self.output_manager.is_complete(breakdown_id)

        logs = [
            {
                "line_number": line.line_number,
                "content": line.content,
                "timestamp": line.timestamp,
            }
            for line in history
        ]

        return logs, is_complete
