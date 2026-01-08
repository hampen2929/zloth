"""Base executor interface for all CLI executors.

This module defines the abstract base class for all executors in dursor,
following the orchestrator management pattern where AI Agents only edit
files and dursor manages git operations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from dursor_api.domain.models import AgentConstraints, FileDiff


@dataclass
class ExecutorResult:
    """Result from CLI executor execution.

    This is the standard result type returned by all executors after
    running an AI Agent CLI (Claude Code, Codex, Gemini, etc.).
    """

    success: bool
    summary: str
    patch: str
    files_changed: list[FileDiff]
    logs: list[str]
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    session_id: str | None = None  # CLI session ID for conversation persistence


class BaseExecutor(ABC):
    """Abstract base class for all CLI executors.

    Executors are responsible for running AI Agent CLIs (Claude Code, Codex,
    Gemini, etc.) in isolated worktrees. Following the orchestrator management
    pattern, executors should:

    1. Only allow agents to edit files
    2. Pass constraints to agents via instructions
    3. Not perform any git commit/push operations
    4. Return ExecutorResult with file changes for dursor to process

    Git operations (commit, push, etc.) are handled by GitService after
    executor completion.
    """

    @abstractmethod
    async def execute(
        self,
        worktree_path: Path,
        instruction: str,
        constraints: AgentConstraints | None = None,
        on_output: Callable[[str], Awaitable[None]] | None = None,
        resume_session_id: str | None = None,
    ) -> ExecutorResult:
        """Execute the CLI with the given instruction.

        Args:
            worktree_path: Working directory for the execution.
            instruction: Natural language instruction for the agent.
            constraints: Agent constraints (git ops forbidden, etc.).
            on_output: Callback for output streaming.
            resume_session_id: Session ID for conversation continuation.

        Returns:
            ExecutorResult with execution results.
        """
        pass

    def _build_instruction_with_constraints(
        self,
        instruction: str,
        constraints: AgentConstraints | None,
    ) -> str:
        """Build instruction with constraints appended.

        This method appends the constraint prompt to the user's instruction,
        ensuring the agent knows about forbidden operations.

        Args:
            instruction: Original user instruction.
            constraints: Agent constraints to append.

        Returns:
            Combined instruction with constraints.
        """
        if constraints is None:
            return instruction

        return f"""{constraints.to_prompt()}

## Task
{instruction}"""

    def _parse_diff(self, diff: str) -> list[FileDiff]:
        """Parse unified diff to extract file change information.

        This is a shared utility method for parsing git diff output
        into structured FileDiff objects.

        Args:
            diff: Unified diff string.

        Returns:
            List of FileDiff objects.
        """
        files: list[FileDiff] = []
        current_file: str | None = None
        current_patch_lines: list[str] = []
        added_lines = 0
        removed_lines = 0

        for line in diff.split("\n"):
            if line.startswith("--- a/"):
                # Save previous file if exists
                if current_file:
                    files.append(FileDiff(
                        path=current_file,
                        added_lines=added_lines,
                        removed_lines=removed_lines,
                        patch="\n".join(current_patch_lines),
                    ))
                # Reset for new file
                current_patch_lines = [line]
                added_lines = 0
                removed_lines = 0
            elif line.startswith("+++ b/"):
                current_file = line[6:]
                current_patch_lines.append(line)
            elif line.startswith("--- /dev/null"):
                # New file
                current_patch_lines = [line]
                added_lines = 0
                removed_lines = 0
            elif line.startswith("+++ b/") and current_file is None:
                # New file path
                current_file = line[6:]
                current_patch_lines.append(line)
            elif current_file:
                current_patch_lines.append(line)
                if line.startswith("+") and not line.startswith("+++"):
                    added_lines += 1
                elif line.startswith("-") and not line.startswith("---"):
                    removed_lines += 1

        # Save last file
        if current_file:
            files.append(FileDiff(
                path=current_file,
                added_lines=added_lines,
                removed_lines=removed_lines,
                patch="\n".join(current_patch_lines),
            ))

        return files

    def _generate_summary(
        self,
        files_changed: list[FileDiff],
        output_lines: list[str] | None = None,
    ) -> str:
        """Generate a human-readable summary of changes.

        Args:
            files_changed: List of changed files.
            output_lines: Output from CLI execution (optional).

        Returns:
            Summary string.
        """
        if not files_changed:
            return "No files were modified."

        total_added = sum(f.added_lines for f in files_changed)
        total_removed = sum(f.removed_lines for f in files_changed)

        summary_parts = [
            f"Modified {len(files_changed)} file(s)",
            f"+{total_added} -{total_removed} lines",
        ]

        # List files
        file_list = ", ".join(f.path for f in files_changed[:5])
        if len(files_changed) > 5:
            file_list += f" and {len(files_changed) - 5} more"

        summary_parts.append(f"Files: {file_list}")

        return ". ".join(summary_parts) + "."
