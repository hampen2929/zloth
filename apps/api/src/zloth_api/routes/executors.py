"""Executors status routes."""

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from zloth_api.config import settings

router = APIRouter(prefix="/executors", tags=["executors"])


class ExecutorStatus(BaseModel):
    """Status of a single executor CLI."""

    available: bool
    path: str
    version: str | None = None
    error: str | None = None


class ExecutorsStatusResponse(BaseModel):
    """Response containing status of all executors."""

    claude_code: ExecutorStatus
    codex_cli: ExecutorStatus
    gemini_cli: ExecutorStatus


async def _check_cli_availability(cli_path: str, version_args: list[str]) -> ExecutorStatus:
    """Check if a CLI is available and get its version.

    Args:
        cli_path: Path to the CLI executable.
        version_args: Arguments to get version (e.g., ["--version"]).

    Returns:
        ExecutorStatus with availability info.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            cli_path,
            *version_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)
            # Parse version from output
            output = stdout.decode("utf-8", errors="replace").strip()
            if not output:
                output = stderr.decode("utf-8", errors="replace").strip()

            # Extract first line as version
            version = output.split("\n")[0] if output else None

            return ExecutorStatus(
                available=True,
                path=cli_path,
                version=version,
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            return ExecutorStatus(
                available=False,
                path=cli_path,
                error="CLI timed out while checking version",
            )
    except FileNotFoundError:
        return ExecutorStatus(
            available=False,
            path=cli_path,
            error=f"CLI not found at: {cli_path}",
        )
    except Exception as e:
        return ExecutorStatus(
            available=False,
            path=cli_path,
            error=str(e),
        )


@router.get("/status", response_model=ExecutorsStatusResponse)
async def get_executors_status() -> ExecutorsStatusResponse:
    """Get availability status of all CLI executors.

    Checks if Claude Code, Codex, and Gemini CLIs are installed and available.
    """
    # Run all checks concurrently
    claude_task = _check_cli_availability(settings.claude_cli_path, ["--version"])
    codex_task = _check_cli_availability(settings.codex_cli_path, ["--version"])
    gemini_task = _check_cli_availability(settings.gemini_cli_path, ["--version"])

    claude_status, codex_status, gemini_status = await asyncio.gather(
        claude_task, codex_task, gemini_task
    )

    return ExecutorsStatusResponse(
        claude_code=claude_status,
        codex_cli=codex_status,
        gemini_cli=gemini_status,
    )
