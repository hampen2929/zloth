"""Title generation service for tasks.

Generates concise titles for tasks using CLI executors based on
conversation messages and task context.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from zloth_api.config import settings
from zloth_api.domain.models import Message, Task
from zloth_api.executors.claude_code_executor import ClaudeCodeExecutor, ClaudeCodeOptions
from zloth_api.executors.codex_executor import CodexExecutor, CodexOptions
from zloth_api.executors.gemini_executor import GeminiExecutor, GeminiOptions
from zloth_api.storage.dao import MessageDAO, RepoDAO, TaskDAO

logger = logging.getLogger(__name__)

# Default max title length
MAX_TITLE_LENGTH = 50


class TitleService:
    """Service for generating task titles using CLI executors."""

    def __init__(
        self,
        task_dao: TaskDAO,
        message_dao: MessageDAO,
        repo_dao: RepoDAO,
    ) -> None:
        self.task_dao = task_dao
        self.message_dao = message_dao
        self.repo_dao = repo_dao
        self.claude_executor = ClaudeCodeExecutor(
            ClaudeCodeOptions(
                claude_cli_path=settings.claude_cli_path,
                timeout_seconds=120,
            )
        )
        self.codex_executor = CodexExecutor(
            CodexOptions(
                codex_cli_path=settings.codex_cli_path,
                timeout_seconds=120,
            )
        )
        self.gemini_executor = GeminiExecutor(
            GeminiOptions(
                gemini_cli_path=settings.gemini_cli_path,
                timeout_seconds=120,
            )
        )

    async def generate_title(
        self,
        task_id: str,
        instruction: str | None = None,
    ) -> str:
        """Generate a title for a task.

        Uses conversation messages and optional instruction to generate
        a concise title via a CLI executor.

        Args:
            task_id: Target task ID.
            instruction: Optional explicit instruction for title generation.
                If not provided, uses conversation messages as context.

        Returns:
            Generated title string.

        Raises:
            ValueError: If task not found.
        """
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        messages = await self.message_dao.list(task_id)

        # Build context from instruction or messages
        context = instruction or self._build_context_from_messages(messages, task)

        # Get repo workspace path for executor
        repo = await self.repo_dao.get(task.repo_id)
        if not repo:
            raise ValueError(f"Repo not found: {task.repo_id}")

        workspace_path = Path(repo.workspace_path)
        if not workspace_path.exists():
            # Fallback to heuristic title
            title = self._generate_fallback_title(context)
            await self.task_dao.update_title(task_id, title)
            return title

        # Generate title using executor
        title = await self._generate_with_executor(workspace_path, context)

        # Update task title
        await self.task_dao.update_title(task_id, title)
        return title

    async def _generate_with_executor(
        self,
        workspace_path: Path,
        context: str,
    ) -> str:
        """Generate title using a CLI executor.

        Tries Claude Code first, then falls back to other executors.

        Args:
            workspace_path: Working directory for executor.
            context: Context text for title generation.

        Returns:
            Generated title string.
        """
        temp_file = Path(f"/tmp/zloth_title_{uuid.uuid4().hex}.txt")

        prompt = f"""Generate a concise title for this development task/thread.

DO NOT edit any files in the repository.

## Context
{context}

## Rules
- Output ONLY the title to the file specified below
- Keep it under {MAX_TITLE_LENGTH} characters
- Use imperative mood (e.g., "Add feature X" not "Added feature X")
- Be specific but concise
- No quotes or extra text

Write ONLY the title to this file: {temp_file}
"""

        try:
            result = await self.claude_executor.execute(workspace_path, prompt)
            if result.success and temp_file.exists():
                title = temp_file.read_text().strip().strip("\"'")
                title = title.split("\n")[0].strip()
                return self._truncate_title(title)

            # Try extracting from summary if temp file wasn't created
            if result.success and result.summary:
                title = result.summary.strip().strip("\"'").split("\n")[0].strip()
                return self._truncate_title(title)

        except Exception as e:
            logger.warning(f"Claude Code executor failed for title generation: {e}")
        finally:
            if temp_file.exists():
                temp_file.unlink()

        # Fallback to heuristic
        return self._generate_fallback_title(context)

    def _build_context_from_messages(
        self,
        messages: list[Message],
        task: Task,
    ) -> str:
        """Build context string from task messages.

        Args:
            messages: List of messages in the task.
            task: Task object.

        Returns:
            Context string for title generation.
        """
        parts: list[str] = []

        if task.title:
            parts.append(f"Current title: {task.title}")

        # Use first few user messages as context
        user_messages = [m for m in messages if m.role.value == "user"]
        for msg in user_messages[:3]:
            # Truncate long messages
            content = msg.content[:500] if len(msg.content) > 500 else msg.content
            parts.append(content)

        return "\n\n".join(parts) if parts else "(No context available)"

    def _generate_fallback_title(self, context: str) -> str:
        """Generate a fallback title from context text.

        Extracts the first meaningful line from context.

        Args:
            context: Context text.

        Returns:
            Fallback title string.
        """
        if not context or context == "(No context available)":
            return "Untitled task"

        # Take the first non-empty line
        for line in context.split("\n"):
            line = line.strip()
            if line and not line.startswith("Current title:"):
                return self._truncate_title(line)

        return "Untitled task"

    def _truncate_title(self, title: str, max_length: int = MAX_TITLE_LENGTH) -> str:
        """Truncate title to max_length characters.

        Args:
            title: Title to truncate.
            max_length: Maximum length (default 50).

        Returns:
            Truncated title string.
        """
        if len(title) <= max_length:
            return title
        return title[: max_length - 3].rstrip() + "..."
