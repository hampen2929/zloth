"""Claude Code CLI executor for running Claude Code in worktrees."""

import asyncio
import json
import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from dursor_api.domain.models import FileDiff


@dataclass
class ClaudeCodeOptions:
    """Options for Claude Code execution."""

    timeout_seconds: int = 3600  # 1 hour default
    max_output_lines: int = 10000
    claude_cli_path: str = "claude"
    env_vars: dict[str, str] = field(default_factory=dict)


@dataclass
class ExecutorResult:
    """Result from Claude Code execution."""

    success: bool
    summary: str
    patch: str
    files_changed: list[FileDiff]
    logs: list[str]
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    session_id: str | None = None  # CLI session ID for conversation persistence


class ClaudeCodeExecutor:
    """Executes Claude Code CLI in a worktree."""

    def __init__(self, options: ClaudeCodeOptions | None = None):
        """Initialize executor with options.

        Args:
            options: Execution options. Uses defaults if not provided.
        """
        self.options = options or ClaudeCodeOptions()

    async def execute(
        self,
        worktree_path: Path,
        instruction: str,
        on_output: Callable[[str], Awaitable[None]] | None = None,
        resume_session_id: str | None = None,
    ) -> ExecutorResult:
        """Execute claude CLI with the given instruction.

        Args:
            worktree_path: Path to the git worktree.
            instruction: Natural language instruction for Claude Code.
            on_output: Optional callback for streaming output.
            resume_session_id: Optional session ID to resume a previous conversation.

        Returns:
            ExecutorResult with success status, patch, and logs.
        """
        logs: list[str] = []
        output_lines: list[str] = []

        # Prepare environment
        env = os.environ.copy()
        env.update(self.options.env_vars)
        # Note: Don't change HOME as Claude CLI needs access to ~/.claude for auth

        # Build command
        # Use --print (-p) for non-interactive mode with instruction
        # Use --output-format json to get session ID in response
        cmd = [
            self.options.claude_cli_path,
            "-p", instruction,
            "--output-format", "json",
        ]

        # Add --session-id flag if we have a previous session ID
        # Note: Use --session-id (not --resume) to continue conversation in -p mode
        if resume_session_id:
            cmd.extend(["--session-id", resume_session_id])
            logs.append(f"Continuing session: {resume_session_id}")

        logs.append(f"Executing: {' '.join(cmd)}")
        logs.append(f"Working directory: {worktree_path}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(worktree_path),
                env=env,
            )

            # Stream output
            async def read_output():
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    decoded = line.decode("utf-8", errors="replace").rstrip()
                    output_lines.append(decoded)
                    logs.append(decoded)

                    if len(output_lines) <= self.options.max_output_lines:
                        if on_output:
                            await on_output(decoded)

            try:
                await asyncio.wait_for(
                    read_output(),
                    timeout=self.options.timeout_seconds,
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                return ExecutorResult(
                    success=False,
                    summary="",
                    patch="",
                    files_changed=[],
                    logs=logs,
                    error=f"Execution timed out after {self.options.timeout_seconds} seconds",
                )

            await process.wait()

            if process.returncode != 0:
                return ExecutorResult(
                    success=False,
                    summary="",
                    patch="",
                    files_changed=[],
                    logs=logs,
                    error=f"Claude Code exited with code {process.returncode}",
                )

            # Extract session ID from JSON output
            session_id = self._extract_session_id(output_lines)

            # Generate diff from git changes
            patch, files_changed = await self._generate_diff(worktree_path)

            # Generate summary
            summary = self._generate_summary(files_changed, output_lines)

            return ExecutorResult(
                success=True,
                summary=summary,
                patch=patch,
                files_changed=files_changed,
                logs=logs,
                session_id=session_id,
            )

        except FileNotFoundError:
            return ExecutorResult(
                success=False,
                summary="",
                patch="",
                files_changed=[],
                logs=logs,
                error=f"Claude CLI not found at: {self.options.claude_cli_path}",
            )
        except Exception as e:
            return ExecutorResult(
                success=False,
                summary="",
                patch="",
                files_changed=[],
                logs=logs,
                error=str(e),
            )

    def _extract_session_id(self, output_lines: list[str]) -> str | None:
        """Extract session ID from Claude CLI JSON output.

        Args:
            output_lines: Output lines from Claude CLI execution.

        Returns:
            Session ID if found, None otherwise.
        """
        # Claude CLI with --output-format json outputs JSON objects
        # Look for session_id in the output
        for line in output_lines:
            try:
                data = json.loads(line)
                # Check for session_id in various possible formats
                if isinstance(data, dict):
                    if "session_id" in data:
                        return data["session_id"]
                    if "sessionId" in data:
                        return data["sessionId"]
            except json.JSONDecodeError:
                continue

        # Fallback: try to find session ID in combined output
        combined = "\n".join(output_lines)
        # Look for UUID pattern that might be a session ID
        uuid_pattern = r'"session_id":\s*"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"'
        match = re.search(uuid_pattern, combined, re.IGNORECASE)
        if match:
            return match.group(1)

        return None

    async def _generate_diff(self, worktree_path: Path) -> tuple[str, list[FileDiff]]:
        """Generate diff from git changes in worktree.

        Args:
            worktree_path: Path to the worktree.

        Returns:
            Tuple of (unified diff string, list of FileDiff objects).
        """
        import git

        def _get_diff():
            repo = git.Repo(worktree_path)

            # Stage all changes
            repo.git.add("-A")

            # Get diff against HEAD
            try:
                diff_output = repo.git.diff("HEAD", "--cached", "--unified=3")
            except git.GitCommandError:
                diff_output = ""

            # Parse diff to get file changes
            files_changed = self._parse_diff(diff_output)

            return diff_output, files_changed

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_diff)

    def _parse_diff(self, diff: str) -> list[FileDiff]:
        """Parse unified diff to extract file change information.

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
            # Match file header: --- a/path or +++ b/path
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
        output_lines: list[str],
    ) -> str:
        """Generate a human-readable summary of changes.

        Args:
            files_changed: List of changed files.
            output_lines: Output from Claude Code execution.

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

    async def cancel(self, process: asyncio.subprocess.Process) -> None:
        """Cancel a running Claude Code process.

        Args:
            process: The subprocess to cancel.
        """
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except TimeoutError:
                process.kill()
                await process.wait()
