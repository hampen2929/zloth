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
from dursor_api.domain.enums import (
    BreakdownStatus,
    BrokenDownTaskType,
    EstimatedSize,
    ExecutorType,
)
from dursor_api.domain.models import (
    BacklogItem,
    BrokenDownSubTask,
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
from dursor_api.storage.dao import BacklogDAO, RepoDAO

logger = logging.getLogger(__name__)

# JSON file name for breakdown result
BREAKDOWN_RESULT_FILE = ".dursor-breakdown.json"

# Prompt template for task breakdown (v1 - deprecated)
BREAKDOWN_INSTRUCTION_TEMPLATE = """
You are a software development task decomposition expert.
Break down the following requirements into specific development tasks.

## Important: Codebase Analysis
1. First, review the codebase in this repository
2. Understand existing implementation patterns, architecture, and naming conventions
3. Show specifically how each task relates to existing code

## Requirements
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

# Prompt template for task breakdown v2 (feature-level granularity)
BREAKDOWN_INSTRUCTION_TEMPLATE_V2 = """
You are a software development requirements analysis expert.
Organize the following requirements into **feature-level** development tasks.

## Important Guidelines

### About Granularity
- **1 feature request = 1 task** is the principle
- Examples: "Dark mode support", "Add search feature", "Implement authentication"
- Detailed implementation steps should be listed as `subtasks`
- Guideline: 1 task = 1 Pull Request that can be completed independently

### Granularity Examples
❌ Bad example (too granular):
- Task 1: Create ThemeContext
- Task 2: Implement useTheme hook
- Task 3: Define dark mode CSS variables
- Task 4: Create ToggleButton component

✅ Good example (appropriate granularity):
- Task: Dark mode support
  - subtask: Create theme context
  - subtask: Define color variables
  - subtask: Implement toggle component

### Breakdown Rules
1. Classify user requirements at the feature level
2. Technical implementation steps go in subtasks
3. Group related elements into a single task
4. Think in terms of units that can be explained in a PR

## Requirements
{content}

## Output Format
Output the result as a JSON file at `.dursor-breakdown.json`:

```json
{{
  "codebase_analysis": {{
    "files_analyzed": <number>,
    "relevant_modules": ["relevant modules"],
    "tech_stack": ["technology stack"]
  }},
  "tasks": [
    {{
      "title": "Feature-level title (max 30 chars)",
      "description": "What this feature achieves and why it's needed",
      "type": "feature | bug_fix | refactoring | docs | test",
      "estimated_size": "small | medium | large",
      "target_files": ["file paths to change"],
      "implementation_hint": "Overall implementation approach (referencing existing code)",
      "tags": ["tags"],
      "subtasks": [
        {{ "title": "Implementation step 1" }},
        {{ "title": "Implementation step 2" }}
      ]
    }}
  ]
}}
```

## Size Guidelines (per task)
- small: Completes in 1-2 days, simple changes
- medium: 3-5 days, affects multiple modules
- large: 1+ week, major feature addition or refactoring

## Important
1. **Read existing code first** before creating tasks
2. target_files must be actual existing file paths
3. implementation_hint should reference existing code patterns
4. IMPORTANT: Create the `.dursor-breakdown.json` file with your analysis
"""


class BreakdownService:
    """Service for breaking down hearing content into development tasks.

    This service:
    1. Starts breakdown in background (non-blocking)
    2. Runs an executor to analyze codebase and decompose tasks
    3. Stores results as BacklogItems for later retrieval
    """

    def __init__(
        self,
        repo_dao: RepoDAO,
        output_manager: OutputManager,
        backlog_dao: BacklogDAO | None = None,
    ):
        """Initialize BreakdownService.

        Args:
            repo_dao: Repository data access object.
            output_manager: Manager for streaming output.
            backlog_dao: Backlog data access object (optional, for v2).
        """
        self.repo_dao = repo_dao
        self.output_manager = output_manager
        self.backlog_dao = backlog_dao

        # In-memory storage for breakdown results
        self._results: dict[str, TaskBreakdownResponse] = {}

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
        self._executors: dict[ExecutorType, ClaudeCodeExecutor | CodexExecutor | GeminiExecutor] = {
            ExecutorType.CLAUDE_CODE: self._claude_executor,
            ExecutorType.CODEX_CLI: self._codex_executor,
            ExecutorType.GEMINI_CLI: self._gemini_executor,
        }

    def _get_executor(
        self, executor_type: ExecutorType
    ) -> ClaudeCodeExecutor | CodexExecutor | GeminiExecutor:
        """Get executor for the given type."""
        if executor_type == ExecutorType.PATCH_AGENT:
            raise ValueError("patch_agent is not supported for task breakdown. Use CLI executors.")

        executor = self._executors.get(executor_type)
        if not executor:
            raise ValueError(f"Unknown executor type: {executor_type}")

        return executor

    async def start_breakdown(
        self,
        request: TaskBreakdownRequest,
    ) -> TaskBreakdownResponse:
        """Start breakdown in background and return immediately.

        Args:
            request: Breakdown request with content, executor type, and repo ID.

        Returns:
            TaskBreakdownResponse with RUNNING status and breakdown_id.
        """
        breakdown_id = str(uuid.uuid4())
        logger.info(f"Starting breakdown {breakdown_id} for repo {request.repo_id}")

        # Get repository first to validate
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

        # Create initial response with RUNNING status
        initial_response = TaskBreakdownResponse(
            breakdown_id=breakdown_id,
            status=BreakdownStatus.RUNNING,
            tasks=[],
            summary=None,
            original_content=request.content,
        )
        self._results[breakdown_id] = initial_response

        # Start background task
        asyncio.create_task(self._run_breakdown(breakdown_id, repo, request))

        return initial_response

    async def _run_breakdown(
        self,
        breakdown_id: str,
        repo: Repo,
        request: TaskBreakdownRequest,
    ) -> None:
        """Run breakdown in background."""
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

    async def get_result(self, breakdown_id: str) -> TaskBreakdownResponse | None:
        """Get breakdown result by ID.

        Args:
            breakdown_id: Breakdown session ID.

        Returns:
            TaskBreakdownResponse or None if not found.
        """
        return self._results.get(breakdown_id)

    async def _execute_breakdown(
        self,
        breakdown_id: str,
        repo: Repo,
        request: TaskBreakdownRequest,
    ) -> TaskBreakdownResponse:
        """Execute the breakdown using the selected executor."""
        executor = self._get_executor(request.executor_type)
        workspace_path = Path(repo.workspace_path)

        # Build instruction using v2 template
        instruction = BREAKDOWN_INSTRUCTION_TEMPLATE_V2.format(content=request.content)

        # Add context if provided
        if request.context:
            context_str = "\n".join(f"- {k}: {v}" for k, v in request.context.items())
            instruction += f"\n\n## Additional Context\n{context_str}"

        # Stream output callback
        async def on_output(line: str) -> None:
            await self.output_manager.publish_async(breakdown_id, line)

        await on_output("Starting task breakdown analysis (v2)...")
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

        # Save tasks as backlog items if backlog_dao is available
        backlog_items: list[BacklogItem] = []
        if self.backlog_dao:
            for task in tasks:
                subtasks = [{"title": st.title} for st in task.subtasks]
                item = await self.backlog_dao.create(
                    repo_id=repo.id,
                    title=task.title,
                    description=task.description,
                    type=task.type,
                    estimated_size=task.estimated_size,
                    target_files=task.target_files,
                    implementation_hint=task.implementation_hint,
                    tags=task.tags,
                    subtasks=subtasks,
                )
                backlog_items.append(item)
            await on_output(f"Created {len(backlog_items)} backlog item(s)")

        return TaskBreakdownResponse(
            breakdown_id=breakdown_id,
            status=BreakdownStatus.SUCCEEDED,
            tasks=tasks,
            backlog_items=backlog_items,
            summary=f"Analyzed codebase and identified {task_count} task(s)",
            original_content=request.content,
            codebase_analysis=codebase_analysis,
        )

    async def _parse_breakdown_result(
        self,
        result_file: Path,
        logs: list[str],
    ) -> tuple[list[BrokenDownTask], CodebaseAnalysis | None] | None:
        """Parse breakdown result from file or logs."""
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
        """Extract JSON from execution logs."""
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
        """Parse JSON data into structured models."""
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
            task_type_str = task_data.get("type", "feature")
            try:
                task_type = BrokenDownTaskType(task_type_str)
            except ValueError:
                task_type = BrokenDownTaskType.FEATURE

            size_str = task_data.get("estimated_size", "medium")
            try:
                estimated_size = EstimatedSize(size_str)
            except ValueError:
                estimated_size = EstimatedSize.MEDIUM

            # Parse subtasks
            subtasks = []
            for st_data in task_data.get("subtasks", []):
                if isinstance(st_data, dict) and "title" in st_data:
                    subtasks.append(BrokenDownSubTask(title=st_data["title"]))
                elif isinstance(st_data, str):
                    subtasks.append(BrokenDownSubTask(title=st_data))

            task = BrokenDownTask(
                title=task_data.get("title", "Untitled Task")[:50],
                description=task_data.get("description", ""),
                type=task_type,
                estimated_size=estimated_size,
                target_files=task_data.get("target_files", []),
                implementation_hint=task_data.get("implementation_hint"),
                tags=task_data.get("tags", []),
                subtasks=subtasks,
            )
            tasks.append(task)

        return tasks, codebase_analysis

    async def get_logs(
        self,
        breakdown_id: str,
        from_line: int = 0,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Get breakdown logs."""
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
