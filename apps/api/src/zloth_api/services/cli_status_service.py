"""Service for checking CLI executor availability."""

import asyncio
import logging
import os
import shutil

from zloth_api.config import Settings
from zloth_api.domain.models import CLIStatus, CLIStatusResponse

logger = logging.getLogger(__name__)

# Timeout for version check commands (seconds)
VERSION_CHECK_TIMEOUT = 5


class CLIStatusService:
    """Service for checking CLI executor availability status."""

    def __init__(self, settings: Settings) -> None:
        """Initialize CLI status service.

        Args:
            settings: Application settings containing CLI paths.
        """
        self.settings = settings

    async def check_all_cli_status(self) -> CLIStatusResponse:
        """Check availability of all CLI executors.

        Returns:
            CLIStatusResponse containing status of all executors.
        """
        cli_configs = [
            ("claude_code", "Claude Code", self.settings.claude_cli_path, "--version"),
            ("codex", "Codex", self.settings.codex_cli_path, "--version"),
            ("gemini", "Gemini", self.settings.gemini_cli_path, "--version"),
        ]

        tasks = [
            self._check_cli(name, display_name, cli_path, version_flag)
            for name, display_name, cli_path, version_flag in cli_configs
        ]

        statuses = await asyncio.gather(*tasks)
        return CLIStatusResponse(executors=list(statuses))

    async def _check_cli(
        self, name: str, display_name: str, cli_path: str, version_flag: str
    ) -> CLIStatus:
        """Check availability of a single CLI.

        Args:
            name: Executor identifier.
            display_name: Human-friendly name.
            cli_path: Configured CLI path.
            version_flag: Flag to get version (e.g., "--version").

        Returns:
            CLIStatus with availability information.
        """
        # Resolve the CLI path
        resolved_path = self._resolve_path(cli_path)

        if resolved_path is None:
            return CLIStatus(
                name=name,
                display_name=display_name,
                available=False,
                configured_path=cli_path,
                resolved_path=None,
                version=None,
                error=f"CLI not found: '{cli_path}' is not in PATH or does not exist",
            )

        # Try to get version
        version, error = await self._get_version(resolved_path, version_flag)

        if error:
            return CLIStatus(
                name=name,
                display_name=display_name,
                available=False,
                configured_path=cli_path,
                resolved_path=resolved_path,
                version=None,
                error=error,
            )

        return CLIStatus(
            name=name,
            display_name=display_name,
            available=True,
            configured_path=cli_path,
            resolved_path=resolved_path,
            version=version,
            error=None,
        )

    def _resolve_path(self, cli_path: str) -> str | None:
        """Resolve CLI path to absolute path.

        Args:
            cli_path: Configured CLI path (absolute or command name).

        Returns:
            Absolute path if found, None otherwise.
        """
        # If absolute path, check if it exists and is executable
        if os.path.isabs(cli_path):
            if os.path.isfile(cli_path) and os.access(cli_path, os.X_OK):
                return cli_path
            return None

        # Otherwise, search in PATH
        resolved = shutil.which(cli_path)
        return resolved

    async def _get_version(self, cli_path: str, version_flag: str) -> tuple[str | None, str | None]:
        """Get CLI version by running version command.

        Args:
            cli_path: Resolved absolute path to CLI.
            version_flag: Flag to get version.

        Returns:
            Tuple of (version, error). One will be None.
        """
        try:
            process = await asyncio.create_subprocess_exec(
                cli_path,
                version_flag,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=VERSION_CHECK_TIMEOUT
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                return None, f"CLI did not respond within {VERSION_CHECK_TIMEOUT}s timeout"

            # Some CLIs output version to stderr
            output = stdout.decode().strip() or stderr.decode().strip()

            if process.returncode != 0:
                # Some CLIs return non-zero for --version, try to extract version anyway
                if output:
                    return self._extract_version(output), None
                return None, f"CLI returned exit code {process.returncode}"

            return self._extract_version(output), None

        except FileNotFoundError:
            return None, f"CLI executable not found at: {cli_path}"
        except PermissionError:
            return None, f"Permission denied executing: {cli_path}"
        except Exception as e:
            logger.warning(f"Error checking CLI {cli_path}: {e}")
            return None, f"Error executing CLI: {str(e)}"

    def _extract_version(self, output: str) -> str:
        """Extract version string from command output.

        Args:
            output: Raw output from version command.

        Returns:
            Cleaned version string or first line of output.
        """
        if not output:
            return "unknown"

        # Take first line and truncate if too long
        first_line = output.split("\n")[0].strip()
        if len(first_line) > 100:
            return first_line[:100] + "..."
        return first_line
