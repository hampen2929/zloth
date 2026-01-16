"""Protocol definitions for AI Role services."""

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Protocol, TypeVar

from dursor_api.domain.models import AgentConstraints, RoleExecutionResult

TResult = TypeVar("TResult", bound=RoleExecutionResult, covariant=True)


class RoleExecutor(Protocol[TResult]):
    """Protocol for AI Role execution.

    Defines the common interface that all role executors must implement.
    This enables type-safe execution of different role types while
    maintaining a consistent API.
    """

    async def execute(
        self,
        workspace_path: Path,
        instruction: str,
        constraints: AgentConstraints | None = None,
        on_output: Callable[[str], Awaitable[None]] | None = None,
        **kwargs: Any,
    ) -> TResult:
        """Execute the role-specific processing.

        Args:
            workspace_path: Path to the working directory.
            instruction: Natural language instruction for the role.
            constraints: Optional constraints for execution.
            on_output: Optional callback for streaming output.
            **kwargs: Role-specific additional arguments.

        Returns:
            Role-specific result extending RoleExecutionResult.
        """
        ...
