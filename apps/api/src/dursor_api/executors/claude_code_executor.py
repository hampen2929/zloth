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

    def _extract_display_text(self, json_line: str) -> str | None:
        """Extract human-readable text from a stream-json line.

        Stream-json format outputs JSON objects with different types:
        - {"type": "assistant", "message": {"content": [{"text": "..."}]}}
        - {"type": "system", "message": "..."}
        - {"type": "result", ...}

        Args:
            json_line: A single line of stream-json output.

        Returns:
            Human-readable text for display, or None if not displayable.
        """
        try:
            data = json.loads(json_line)
            if not isinstance(data, dict):
                return json_line

            msg_type = data.get("type")

            # Assistant messages contain the main content
            if msg_type == "assistant":
                message = data.get("message", {})
                if isinstance(message, dict):
                    content = message.get("content", [])
                    if isinstance(content, list):
                        texts = []
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                texts.append(block.get("text", ""))
                        if texts:
                            return "".join(texts)
                return None

            # System messages (e.g., init info)
            if msg_type == "system":
                message = data.get("message", "")
                if isinstance(message, str) and message:
                    return f"[system] {message}"
                return None

            # Result message - don't display raw JSON
            if msg_type == "result":
                return None

            # Unknown type - return as-is for debugging
            return None

        except json.JSONDecodeError:
            # Not JSON, return as-is
            return json_line

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
        # Use --output-format stream-json for streaming output with structured JSON
        # This enables session_id extraction from the result message
        # Note: --verbose is required when using --output-format=stream-json with -p
        cmd = [
            self.options.claude_cli_path,
            "-p",
            instruction,  # Pass instruction directly as argument
            "--dangerously-skip-permissions",  # Allow file edits without permission prompts
            "--verbose",  # Required for stream-json with -p mode
            "--output-format",
            "stream-json",  # Streaming JSON for session_id extraction
        ]

        # Add --resume flag if we have a previous session ID
        # Note: Use --resume (not --session-id) to continue conversation
        if resume_session_id:
            cmd.extend(["--resume", resume_session_id])
            logs.append(f"Continuing session: {resume_session_id}")

        # Don't log full instruction - it can be very long
        cmd_display = [
            self.options.claude_cli_path,
            "-p",
            f"<instruction:{len(instruction)} chars>",
        ]
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
            async def read_output() -> None:
                line_count = 0
                logger.info("Starting to read output lines...")
                if process.stdout is None:
                    logger.error("Process stdout is None")
                    return
                while True:
                    # Add timeout per line to detect hanging
                    try:
                        line = await asyncio.wait_for(
                            process.stdout.readline(),
                            timeout=300.0,  # 5 min timeout per line
                        )
                    except TimeoutError:
                        logger.warning("No output for 5 minutes, checking if process is alive...")
                        if process.returncode is None:
                            logger.warning(
                                f"Process still running (PID: {process.pid}), continuing to wait..."
                            )
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
                            # Extract human-readable text from stream-json
                            display_text = self._extract_display_text(decoded)
                            if display_text:
                                await on_output(display_text)
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
                    error=(
                        f"Claude Code exited with code {process.returncode}\n\nLast output:\n{tail}"
                    ),
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

        With --output-format stream-json, Claude CLI outputs JSON lines:
        - {"type": "system", "message": "..."}
        - {"type": "assistant", "message": {...}}
        - {"type": "result", "session_id": "uuid", ...}

        The session_id is in the final "result" type message.

        Args:
            output_lines: Output lines from Claude CLI execution.

        Returns:
            Session ID if found, None otherwise.
        """
        # Primary: Look for stream-json "result" message with session_id
        # Search from the end since "result" is the final message
        for line in reversed(output_lines):
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    # stream-json format: {"type": "result", "session_id": "..."}
                    if data.get("type") == "result" and "session_id" in data:
                        session_id = data["session_id"]
                        logger.info(f"Extracted session_id from result: {session_id}")
                        return str(session_id)
                    # Alternative field names
                    if "session_id" in data:
                        return str(data["session_id"])
                    if "sessionId" in data:
                        return str(data["sessionId"])
            except json.JSONDecodeError:
                continue

        # Fallback: Search for session ID patterns in text output
        uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        patterns = [
            # "Session ID: <uuid>" or "session_id: <uuid>"
            re.compile(r"session[_\s]?id[:\s]+(" + uuid_pattern + r")", re.IGNORECASE),
            # "--resume <uuid>" or "--session-id <uuid>" hint
            re.compile(r"--(?:resume|session-id)\s+(" + uuid_pattern + r")", re.IGNORECASE),
            # "session: <uuid>"
            re.compile(r"\bsession[:\s]+(" + uuid_pattern + r")", re.IGNORECASE),
        ]

        for line in reversed(output_lines):  # Check recent lines first
            for pattern in patterns:
                match = pattern.search(line)
                if match:
                    return match.group(1)

        logger.warning("Could not extract session_id from CLI output")
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
