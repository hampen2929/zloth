"""Base agent interface for dursor."""

from abc import ABC, abstractmethod

from dursor_api.domain.models import AgentRequest, AgentResult


class BaseAgent(ABC):
    """Abstract base class for agents."""

    @abstractmethod
    async def run(self, request: AgentRequest) -> AgentResult:
        """Execute the agent with the given request.

        Args:
            request: The agent request containing workspace, instruction, etc.

        Returns:
            AgentResult containing summary, patch, and logs.
        """
        pass

    def validate_request(self, request: AgentRequest) -> list[str]:
        """Validate the agent request.

        Args:
            request: The agent request to validate.

        Returns:
            List of validation error messages (empty if valid).
        """
        errors = []

        if not request.workspace_path:
            errors.append("workspace_path is required")
        if not request.instruction:
            errors.append("instruction is required")
        if not request.base_ref:
            errors.append("base_ref is required")

        return errors
