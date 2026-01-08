"""Claude Code CLI executor for running Claude Code in worktrees."""

import asyncio
import json
import logging
import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from dursor_api.domain.models import FileDiff

logger = logging.getLogger(__name__)


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
        # Use --print (-p) for non-interactive mode with instruction as argument
        # Note: Using create_subprocess_exec avoids shell escaping issues
        # Use --dangerously-skip-permissions to allow edits without prompts in automated mode
        # Note: We do NOT use --output-format json as it suppresses streaming output
        cmd = [
            self.options.claude_cli_path,
            "-p", instruction,  # Pass instruction directly as argument
            "--dangerously-skip-permissions",  # Allow file edits without permission prompts
        ]

        # Add --session-id flag if we have a previous session ID
        # Note: Use --session-id (not --resume) to continue conversation in -p mode
        if resume_session_id:
            cmd.extend(["--session-id", resume_session_id])
            logs.append(f"Continuing session: {resume_session_id}")

        # Don't log full instruction - it can be very long
        cmd_display = [self.options.claude_cli_path, "-p", f"<instruction:{len(instruction)} chars>"]
        logs.append(f"Executing: {' '.join(cmd_display)}")
        logs.append(f"Working directory: {worktree_path}")
        logs.append(f"Instruction length: {len(instruction)} chars")
        logger.info(f"Starting Claude Code CLI: {' '.join(cmd_display)}")
        logger.info(f"Working directory: {worktree_path}")
        logger.info(f"Instruction length: {len(instruction)} chars")

        try:
            logger.info("Creating subprocess...")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,  # Prevent interactive input waiting
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(worktree_path),
                env=env,
            )
            logger.info(f"Process created successfully with PID: {process.pid}")

            # Stream output from CLI
            async def read_output():
                line_count = 0
                logger.info("Starting to read output lines...")
                while True:
                    # Add timeout per line to detect hanging
                    try:
                        line = await asyncio.wait_for(
                            process.stdout.readline(),
                            timeout=300.0  # 5 min timeout per line
                        )
                    except TimeoutError:
                        logger.warning(f"No output for 5 minutes, checking if process is alive...")
                        if process.returncode is None:
                            logger.warning(f"Process still running (PID: {process.pid}), continuing to wait...")
                            continue
                        else:
                            logger.info(f"Process has exited with code: {process.returncode}")
                            break

                    if not line:
                        logger.info(f"EOF reached after {line_count} lines")
                        break

                    decoded = line.decode("utf-8", errors="replace").rstrip()
                    output_lines.append(decoded)
                    logs.append(decoded)
                    line_count += 1

                    # Log progress every 10 lines
                    if line_count % 10 == 0:
                        logger.info(f"Read {line_count} lines so far...")

                    if len(output_lines) <= self.options.max_output_lines:
                        if on_output:
                            await on_output(decoded)
                logger.info(f"Finished reading output: {line_count} lines total")

            try:
                logger.info("Reading output...")
                await asyncio.wait_for(
                    read_output(),
                    timeout=self.options.timeout_seconds,
                )
                logger.info("Output reading completed")
            except TimeoutError:
                logger.error(f"Execution timed out after {self.options.timeout_seconds} seconds")
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
            logger.info(f"Process exited with code: {process.returncode}")

            if process.returncode != 0:
                # Include last few lines of output for debugging
                tail_lines = logs[-20:] if logs else []
                tail = "\n".join(tail_lines)
                return ExecutorResult(
                    success=False,
                    summary="",
                    patch="",
                    files_changed=[],
                    logs=logs,
                    error=f"Claude Code exited with code {process.returncode}\n\nLast output:\n{tail}",
                )

            # Extract session ID from JSON output
            session_id = self._extract_session_id(output_lines)

            return ExecutorResult(
                success=True,
                summary="",
                patch="",
                files_changed=[],
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
        """Extract session ID from Claude CLI output.

        Claude CLI outputs session information in various formats:
        - JSON: {"session_id": "uuid"}
        - Text: "Session ID: uuid" or "session: uuid"
        - Hint: "To continue, use --session-id uuid"

        Args:
            output_lines: Output lines from Claude CLI execution.

        Returns:
            Session ID if found, None otherwise.
        """
        uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

        # Try JSON parsing first (in case output contains JSON)
        for line in output_lines:
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    if "session_id" in data:
                        return data["session_id"]
                    if "sessionId" in data:
                        return data["sessionId"]
            except json.JSONDecodeError:
                continue

        # Search for session ID patterns in text output
        patterns = [
            # "Session ID: <uuid>" or "session_id: <uuid>"
            re.compile(r"session[_\s]?id[:\s]+(" + uuid_pattern + r")", re.IGNORECASE),
            # "--session-id <uuid>" hint
            re.compile(r"--session-id\s+(" + uuid_pattern + r")", re.IGNORECASE),
            # "session: <uuid>"
            re.compile(r"\bsession[:\s]+(" + uuid_pattern + r")", re.IGNORECASE),
        ]

        for line in reversed(output_lines):  # Check recent lines first
            for pattern in patterns:
                match = pattern.search(line)
                if match:
                    return match.group(1)

        # Fallback: search combined output
        combined = "\n".join(output_lines[-500:])  # Limit to avoid huge joins
        for pattern in patterns:
            match = pattern.search(combined)
            if match:
                return match.group(1)

        return None

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
