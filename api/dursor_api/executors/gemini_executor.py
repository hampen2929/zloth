"""Gemini CLI executor for running Google Gemini CLI in worktrees."""

import asyncio
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from dursor_api.domain.models import FileDiff
from dursor_api.executors.claude_code_executor import ExecutorResult


@dataclass
class GeminiOptions:
    """Options for Gemini CLI execution."""

    timeout_seconds: int = 3600  # 1 hour default
    max_output_lines: int = 10000
    gemini_cli_path: str = "gemini"
    env_vars: dict[str, str] = field(default_factory=dict)


class GeminiExecutor:
    """Executes Gemini CLI in a worktree."""

    def __init__(self, options: GeminiOptions | None = None):
        """Initialize executor with options.

        Args:
            options: Execution options. Uses defaults if not provided.
        """
        self.options = options or GeminiOptions()

    async def execute(
        self,
        worktree_path: Path,
        instruction: str,
        on_output: Callable[[str], Awaitable[None]] | None = None,
        resume_session_id: str | None = None,
    ) -> ExecutorResult:
        """Execute gemini CLI with the given instruction.

        Args:
            worktree_path: Path to the git worktree.
            instruction: Natural language instruction for Gemini.
            on_output: Optional callback for streaming output.
            resume_session_id: Optional session ID (not yet supported by Gemini CLI).

        Returns:
            ExecutorResult with success status, patch, and logs.
        """
        # Note: Gemini CLI does not currently support session persistence
        # The resume_session_id parameter is included for interface compatibility
        logs: list[str] = []
        output_lines: list[str] = []

        # Prepare environment
        env = os.environ.copy()
        env.update(self.options.env_vars)

        # Build command
        # Gemini CLI: gemini "prompt" --yolo
        # --yolo = auto-approve all actions
        # See: https://github.com/google-gemini/gemini-cli
        cmd = [
            self.options.gemini_cli_path,
            instruction,  # Pass instruction as positional argument
            "--yolo",
        ]

        # Don't log full instruction - it can be very long
        cmd_display = [self.options.gemini_cli_path, f"<instruction:{len(instruction)} chars>", "--yolo"]
        logs.append(f"Executing: {' '.join(cmd_display)}")
        logs.append(f"Working directory: {worktree_path}")
        logs.append(f"Instruction length: {len(instruction)} chars")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,  # Prevent interactive input waiting
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(worktree_path),
                env=env,
            )

            # Stream output from CLI
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
                # Include last few lines of output for debugging
                tail_lines = logs[-20:] if logs else []
                tail = "\n".join(tail_lines)
                return ExecutorResult(
                    success=False,
                    summary="",
                    patch="",
                    files_changed=[],
                    logs=logs,
                    error=f"Gemini CLI exited with code {process.returncode}\n\nLast output:\n{tail}",
                )

            return ExecutorResult(
                success=True,
                summary="",
                patch="",
                files_changed=[],
                logs=logs,
            )

        except FileNotFoundError:
            return ExecutorResult(
                success=False,
                summary="",
                patch="",
                files_changed=[],
                logs=logs,
                error=f"Gemini CLI not found at: {self.options.gemini_cli_path}",
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

    async def cancel(self, process: asyncio.subprocess.Process) -> None:
        """Cancel a running Gemini process.

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
