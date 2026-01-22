"""System routes for CLI tools status and configuration."""

import asyncio
import shutil

from fastapi import APIRouter

from zloth_api.config import settings
from zloth_api.domain.models import CLIToolsStatus, CLIToolStatus

router = APIRouter(prefix="/system", tags=["system"])


async def _check_cli_tool(name: str, cli_path: str) -> CLIToolStatus:
    """Check if a CLI tool is available and get its version.

    Args:
        name: CLI tool name (claude, codex, gemini).
        cli_path: Configured path for the CLI tool.

    Returns:
        CLIToolStatus with availability and version info.
    """
    # First check if the command exists
    resolved_path = shutil.which(cli_path)
    if not resolved_path:
        return CLIToolStatus(
            name=name,
            available=False,
            version=None,
            path=cli_path,
            error=f"Command '{cli_path}' not found in PATH",
        )

    # Try to get version
    try:
        # Use --version flag (common for most CLI tools)
        process = await asyncio.create_subprocess_exec(
            cli_path,
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10.0)

        if process.returncode == 0:
            version_str = stdout.decode().strip()
            # Take only first line if multiple lines
            version: str | None = version_str.split("\n")[0] if version_str else None
            return CLIToolStatus(
                name=name,
                available=True,
                version=version,
                path=resolved_path,
                error=None,
            )
        else:
            # Command exists but --version failed, still consider it available
            return CLIToolStatus(
                name=name,
                available=True,
                version=None,
                path=resolved_path,
                error=None,
            )
    except TimeoutError:
        return CLIToolStatus(
            name=name,
            available=True,
            version=None,
            path=resolved_path,
            error="Version check timed out",
        )
    except Exception as e:
        return CLIToolStatus(
            name=name,
            available=False,
            version=None,
            path=cli_path,
            error=str(e),
        )


@router.get("/cli-tools", response_model=CLIToolsStatus)
async def get_cli_tools_status() -> CLIToolsStatus:
    """Get status of all CLI tools (claude, codex, gemini).

    Checks if each CLI tool is available and returns version information.
    """
    # Check all tools concurrently
    claude_task = _check_cli_tool("claude", settings.claude_cli_path)
    codex_task = _check_cli_tool("codex", settings.codex_cli_path)
    gemini_task = _check_cli_tool("gemini", settings.gemini_cli_path)

    claude_status, codex_status, gemini_status = await asyncio.gather(
        claude_task, codex_task, gemini_task
    )

    return CLIToolsStatus(
        claude=claude_status,
        codex=codex_status,
        gemini=gemini_status,
    )
