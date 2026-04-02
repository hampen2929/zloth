"""AI Task Creator service for autonomous task creation.

This service uses CLI executors to analyze a codebase and create tasks
directly from high-level instructions. Unlike BreakdownService which
creates BacklogItems for human curation, this service creates Tasks
directly and can optionally auto-start agentic execution.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any

from zloth_api.config import settings
from zloth_api.domain.enums import (
    BreakdownStatus,
    ExecutorType,
    MessageRole,
)
from zloth_api.domain.models import (
    AICreatedTask,
    AITaskCreateRequest,
    AITaskCreateResponse,
    CodebaseAnalysis,
    Repo,
)
from zloth_api.executors.claude_code_executor import ClaudeCodeExecutor, ClaudeCodeOptions
from zloth_api.executors.codex_executor import CodexExecutor, CodexOptions
from zloth_api.executors.gemini_executor import GeminiExecutor, GeminiOptions
from zloth_api.services.output_manager import OutputManager
from zloth_api.storage.dao import MessageDAO, RepoDAO, TaskDAO

logger = logging.getLogger(__name__)

# Output file name for AI task creation result
AI_TASKS_RESULT_FILE = ".zloth-ai-tasks.json"

# Maximum number of tasks AI can create in one session
MAX_TASKS_PER_SESSION = 10

AI_TASK_CREATE_INSTRUCTION_TEMPLATE = """
You are a software development task planning expert.
Analyze the following instruction and the codebase, then break it down
into independently executable development tasks.

## Instruction
{instruction}

## Important: Codebase Analysis
1. First, review the codebase in this repository
2. Understand existing implementation patterns, architecture, and naming conventions
3. Each task should be specific enough for an AI coding agent to execute

## Output Format
Create the file `.zloth-ai-tasks.json` with the following format:

```json
{{
  "codebase_analysis": {{
    "files_analyzed": <number of files analyzed>,
    "relevant_modules": ["relevant module names"],
    "tech_stack": ["detected technologies"]
  }},
  "tasks": [
    {{
      "title": "Task title (max 50 chars)",
      "instruction": "Detailed instruction for the AI coding agent."
    }}
  ]
}}
```

## Rules
1. **Read the code first** before creating tasks
2. Each task should be completable in a single Pull Request
3. The `instruction` field must be specific enough for an AI agent
4. Include file paths, function names, and patterns to follow in each instruction
5. If tasks have dependencies, mention them in the instruction
6. Keep the number of tasks reasonable (1-{max_tasks})
7. IMPORTANT: Create the `.zloth-ai-tasks.json` file with your analysis
"""


class AITaskCreatorService:
    """Service for AI-driven task creation.

    Uses CLI executors to analyze a codebase and create tasks directly
    from high-level instructions.
    """

    def __init__(
        self,
        repo_dao: RepoDAO,
        task_dao: TaskDAO,
        message_dao: MessageDAO,
        output_manager: OutputManager,
    ) -> None:
        """Initialize AITaskCreatorService.

        Args:
            repo_dao: Repository data access object.
            task_dao: Task data access object.
            message_dao: Message data access object.
            output_manager: Manager for streaming output.
        """
        self.repo_dao = repo_dao
        self.task_dao = task_dao
        self.message_dao = message_dao
        self.output_manager = output_manager

        # In-memory storage for session results
        self._results: dict[str, AITaskCreateResponse] = {}

        # Initialize executors
        self._executors: dict[ExecutorType, ClaudeCodeExecutor | CodexExecutor | GeminiExecutor] = {
            ExecutorType.CLAUDE_CODE: ClaudeCodeExecutor(
                ClaudeCodeOptions(
                    timeout_seconds=1800,
                    claude_cli_path=settings.claude_cli_path,
                )
            ),
            ExecutorType.CODEX_CLI: CodexExecutor(
                CodexOptions(
                    timeout_seconds=1800,
                    codex_cli_path=settings.codex_cli_path,
                )
            ),
            ExecutorType.GEMINI_CLI: GeminiExecutor(
                GeminiOptions(
                    timeout_seconds=1800,
                    gemini_cli_path=settings.gemini_cli_path,
                )
            ),
        }

    def _get_executor(
        self, executor_type: ExecutorType
    ) -> ClaudeCodeExecutor | CodexExecutor | GeminiExecutor:
        """Get executor for the given type.

        Args:
            executor_type: Type of executor to use.

        Returns:
            Executor instance.

        Raises:
            ValueError: If executor type is not supported.
        """
        if executor_type == ExecutorType.PATCH_AGENT:
            raise ValueError(
                "patch_agent is not supported for AI task creation. Use CLI executors."
            )
        executor = self._executors.get(executor_type)
        if not executor:
            raise ValueError(f"Unknown executor type: {executor_type}")
        return executor

    async def start(
        self,
        request: AITaskCreateRequest,
    ) -> AITaskCreateResponse:
        """Start AI task creation in background and return immediately.

        Args:
            request: AI task creation request.

        Returns:
            AITaskCreateResponse with RUNNING status and session_id.
        """
        session_id = str(uuid.uuid4())
        logger.info(f"Starting AI task creation {session_id} for repo {request.repo_id}")

        # Validate repository
        repo = await self.repo_dao.get(request.repo_id)
        if not repo:
            return AITaskCreateResponse(
                session_id=session_id,
                status=BreakdownStatus.FAILED,
                error=f"Repository not found: {request.repo_id}",
            )

        # Create initial response
        initial_response = AITaskCreateResponse(
            session_id=session_id,
            status=BreakdownStatus.RUNNING,
        )
        self._results[session_id] = initial_response

        # Start background task
        asyncio.create_task(self._run(session_id, repo, request))

        return initial_response

    async def get_result(self, session_id: str) -> AITaskCreateResponse | None:
        """Get session result by ID.

        Args:
            session_id: Session ID.

        Returns:
            AITaskCreateResponse or None if not found.
        """
        return self._results.get(session_id)

    async def get_logs(
        self,
        session_id: str,
        from_line: int = 0,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Get session logs.

        Args:
            session_id: Session ID.
            from_line: Line number to start from.

        Returns:
            Tuple of (logs, is_complete).
        """
        history = await self.output_manager.get_history(session_id, from_line)
        is_complete = await self.output_manager.is_complete(session_id)

        logs = [
            {
                "line_number": line.line_number,
                "content": line.content,
                "timestamp": line.timestamp,
            }
            for line in history
        ]

        return logs, is_complete

    async def _run(
        self,
        session_id: str,
        repo: Repo,
        request: AITaskCreateRequest,
    ) -> None:
        """Run AI task creation in background."""
        try:
            result = await self._execute(session_id, repo, request)
            self._results[session_id] = result
        except Exception as e:
            logger.exception(f"AI task creation {session_id} failed: {e}")
            await self.output_manager.mark_complete(session_id)
            self._results[session_id] = AITaskCreateResponse(
                session_id=session_id,
                status=BreakdownStatus.FAILED,
                error=str(e),
            )

    async def _execute(
        self,
        session_id: str,
        repo: Repo,
        request: AITaskCreateRequest,
    ) -> AITaskCreateResponse:
        """Execute AI task creation using the selected executor."""
        executor = self._get_executor(request.executor_type)
        workspace_path = Path(repo.workspace_path)

        # Build instruction
        instruction = AI_TASK_CREATE_INSTRUCTION_TEMPLATE.format(
            instruction=request.instruction,
            max_tasks=MAX_TASKS_PER_SESSION,
        )

        # Add context if provided
        if request.context:
            context_str = "\n".join(f"- {k}: {v}" for k, v in request.context.items())
            instruction += f"\n\n## Additional Context\n{context_str}"

        # Stream output callback
        async def on_output(line: str) -> None:
            await self.output_manager.publish_async(session_id, line)

        await on_output("Starting AI task creation analysis...")
        await on_output(f"Using executor: {request.executor_type.value}")
        await on_output(f"Repository: {repo.repo_url}")

        # Execute
        result = await executor.execute(
            worktree_path=workspace_path,
            instruction=instruction,
            on_output=on_output,
        )

        if not result.success:
            await self.output_manager.mark_complete(session_id)
            return AITaskCreateResponse(
                session_id=session_id,
                status=BreakdownStatus.FAILED,
                error=result.error or "AI task creation execution failed",
            )

        # Parse result from file
        result_file = workspace_path / AI_TASKS_RESULT_FILE
        parsed = self._parse_result(result_file, result.logs)

        # Clean up result file
        if result_file.exists():
            try:
                result_file.unlink()
            except OSError:
                pass

        if parsed is None:
            await self.output_manager.mark_complete(session_id)
            return AITaskCreateResponse(
                session_id=session_id,
                status=BreakdownStatus.FAILED,
                error="Failed to parse AI task creation result. "
                "The agent may not have created the result file.",
            )

        tasks_data, codebase_analysis = parsed

        # Limit number of tasks
        if len(tasks_data) > MAX_TASKS_PER_SESSION:
            tasks_data = tasks_data[:MAX_TASKS_PER_SESSION]
            await on_output(f"Warning: Truncated to {MAX_TASKS_PER_SESSION} tasks (maximum)")

        # Create actual Task objects
        created_tasks: list[AICreatedTask] = []
        for task_data in tasks_data:
            title = task_data.get("title", "Untitled Task")[:50]
            task_instruction = task_data.get("instruction", "")

            # Create task in DB
            task = await self.task_dao.create(
                repo_id=repo.id,
                title=title,
                coding_mode=request.coding_mode,
            )

            # Add instruction as the first user message
            await self.message_dao.create(
                task_id=task.id,
                role=MessageRole.USER,
                content=task_instruction,
            )

            auto_started = False
            if request.auto_start:
                # Auto-start will be handled by the caller (route) using
                # the agentic orchestrator, since we don't want circular deps
                auto_started = True

            created_tasks.append(
                AICreatedTask(
                    id=task.id,
                    title=title,
                    instruction=task_instruction,
                    coding_mode=request.coding_mode,
                    auto_started=auto_started,
                )
            )
            await on_output(f"Created task: {title}")

        task_count = len(created_tasks)
        await on_output(f"AI task creation complete: {task_count} task(s) created")
        await self.output_manager.mark_complete(session_id)

        return AITaskCreateResponse(
            session_id=session_id,
            status=BreakdownStatus.SUCCEEDED,
            created_tasks=created_tasks,
            summary=f"Analyzed codebase and created {task_count} task(s)",
            codebase_analysis=codebase_analysis,
        )

    def _parse_result(
        self,
        result_file: Path,
        logs: list[str],
    ) -> tuple[list[dict[str, Any]], CodebaseAnalysis | None] | None:
        """Parse AI task creation result from file or logs."""
        json_data: dict[str, Any] | None = None

        # Try to read from file first
        if result_file.exists():
            try:
                content = result_file.read_text(encoding="utf-8")
                json_data = json.loads(content)
                logger.info(f"Parsed AI task result from file: {result_file}")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to parse result file: {e}")

        # Fallback: try to extract JSON from logs
        if json_data is None:
            json_data = self._extract_json_from_logs(logs)

        if json_data is None:
            logger.error("Could not find AI task result in file or logs")
            return None

        return self._parse_json_data(json_data)

    def _extract_json_from_logs(self, logs: list[str]) -> dict[str, Any] | None:
        """Extract JSON from execution logs."""
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
    ) -> tuple[list[dict[str, Any]], CodebaseAnalysis | None]:
        """Parse JSON data into structured models."""
        codebase_analysis: CodebaseAnalysis | None = None

        # Parse codebase analysis
        if "codebase_analysis" in data:
            ca = data["codebase_analysis"]
            codebase_analysis = CodebaseAnalysis(
                files_analyzed=ca.get("files_analyzed", 0),
                relevant_modules=ca.get("relevant_modules", []),
                tech_stack=ca.get("tech_stack", []),
            )

        # Return raw task dicts for flexible creation
        tasks = data.get("tasks", [])
        if not isinstance(tasks, list):
            tasks = []

        # Validate each task has required fields
        valid_tasks: list[dict[str, Any]] = []
        for task in tasks:
            if isinstance(task, dict) and "title" in task:
                valid_tasks.append(task)

        return valid_tasks, codebase_analysis
