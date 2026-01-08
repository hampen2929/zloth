"""Codex CLI executor for running OpenAI Codex in worktrees."""

import asyncio
import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from dursor_api.domain.models import FileDiff
from dursor_api.executors.claude_code_executor import ExecutorResult


@dataclass
class CodexOptions:
    """Options for Codex CLI execution."""

    timeout_seconds: int = 3600  # 1 hour default
    max_output_lines: int = 10000
    codex_cli_path: str = "codex"
    env_vars: dict[str, str] = field(default_factory=dict)


class CodexExecutor:
    """Executes Codex CLI in a worktree."""

    def __init__(self, options: CodexOptions | None = None):
        """Initialize executor with options.

        Args:
            options: Execution options. Uses defaults if not provided.
        """
        self.options = options or CodexOptions()

    async def execute(
        self,
        worktree_path: Path,
        instruction: str,
        on_output: Callable[[str], Awaitable[None]] | None = None,
        resume_session_id: str | None = None,
    ) -> ExecutorResult:
        """Execute codex CLI with the given instruction.

        Args:
            worktree_path: Path to the git worktree.
            instruction: Natural language instruction for Codex.
            on_output: Optional callback for streaming output.
            resume_session_id: Optional session ID to resume a previous conversation.

        Returns:
            ExecutorResult with success status, patch, and logs.
        """
        logs: list[str] = []

        # Prepare environment
        env = os.environ.copy()
        env.update(self.options.env_vars)

        async def _run_cmd(cmd: list[str]) -> tuple[int, list[str]]:
            """Run a single Codex command and capture output."""
            output_lines: list[str] = []

            logs.append(f"Executing: {' '.join(cmd)}")
            logs.append(f"Working directory: {worktree_path}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(worktree_path),
                env=env,
            )

            async def read_output() -> None:
                stdout = process.stdout
                if stdout is None:
                    return
                while True:
                    line = await stdout.readline()
                    if not line:
                        break
                    decoded = line.decode("utf-8", errors="replace").rstrip()
                    output_lines.append(decoded)
                    logs.append(decoded)
                    if len(output_lines) <= self.options.max_output_lines and on_output:
                        await on_output(decoded)

            try:
                await asyncio.wait_for(read_output(), timeout=self.options.timeout_seconds)
            except TimeoutError as te:
                process.kill()
                await process.wait()
                raise TimeoutError(
                    f"Execution timed out after {self.options.timeout_seconds} seconds"
                ) from te

            await process.wait()
            return process.returncode or 0, output_lines

        def _format_error_tail(output_lines: list[str], max_lines: int = 80) -> str:
            tail = output_lines[-max_lines:] if output_lines else []
            if not tail:
                return "(no output)"
            return "\n".join(tail)

        # Build candidate commands.
        #
        # Codex CLI has had different argument parsing behavior across versions.
        # Exit code 2 usually means a clap argument parse error, so we try a small
        # set of known-good orderings before giving up.
        base = [self.options.codex_cli_path, "exec"]
        cmds: list[list[str]] = []
        if resume_session_id:
            logs.append(f"Continuing session: {resume_session_id}")
            # Prefer this ordering (confirmed working with Codex v0.77.0):
            #   codex exec --full-auto <PROMPT> resume <SESSION_ID>
            cmds.append([*base, "--full-auto", instruction, "resume", resume_session_id])
            # Fallbacks for other parser behaviors:
            cmds.append([*base, instruction, "resume", resume_session_id, "--full-auto"])
            cmds.append([*base, "resume", resume_session_id, instruction, "--full-auto"])
            cmds.append([*base, "--full-auto", "resume", resume_session_id, instruction])
        else:
            cmds.append([*base, instruction, "--full-auto"])

        try:
            last_code: int | None = None
            last_out: list[str] = []

            for idx, cmd in enumerate(cmds, start=1):
                logs.append(f"--- codex attempt {idx}/{len(cmds)} ---")
                code, out = await _run_cmd(cmd)
                last_code = code
                last_out = out

                if code == 0:
                    session_id = self._extract_session_id(out)
                    return ExecutorResult(
                        success=True,
                        summary="",
                        patch="",
                        files_changed=[],
                        logs=logs,
                        session_id=session_id,
                    )

                # If it's not a parse error, don't keep retrying other permutations.
                if code != 2:
                    break

            # Failed all attempts
            tail = _format_error_tail(last_out)
            return ExecutorResult(
                success=False,
                summary="",
                patch="",
                files_changed=[],
                logs=logs,
                error=f"Codex CLI exited with code {last_code}\n\nLast output:\n{tail}",
            )

        except FileNotFoundError:
            return ExecutorResult(
                success=False,
                summary="",
                patch="",
                files_changed=[],
                logs=logs,
                error=f"Codex CLI not found at: {self.options.codex_cli_path}",
            )
        except TimeoutError as e:
            return ExecutorResult(
                success=False,
                summary="",
                patch="",
                files_changed=[],
                logs=logs,
                error=str(e),
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
        """Extract Codex session/conversation UUID from CLI output.

        Codex often prints a line like:
            "To continue this session, run codex resume <UUID>"
        Some versions also print:
            "session id: <UUID>"
        We capture that UUID so the next run can resume via `codex exec resume <UUID> ...`.
        """
        uuid_re = r"(?P<id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"

        # Prefer scanning line-by-line for the common hint.
        hint_re = re.compile(
            r"To continue this session,\s*run\s*codex\s+resume\s+"
            + uuid_re,
            re.IGNORECASE,
        )
        session_line_re = re.compile(r"\bsession id:\s*" + uuid_re + r"\b", re.IGNORECASE)

        for line in reversed(output_lines):
            m = hint_re.search(line)
            if m:
                return m.group("id")
            m = session_line_re.search(line)
            if m:
                return m.group("id")

        # Fallback: search combined output for any UUID that appears near "codex resume".
        combined = "\n".join(output_lines[-2000:])  # avoid massive joins
        m2 = hint_re.search(combined)
        if m2:
            return m2.group("id")
        m3 = session_line_re.search(combined)
        if m3:
            return m3.group("id")

        return None

    async def cancel(self, process: asyncio.subprocess.Process) -> None:
        """Cancel a running Codex process.

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
