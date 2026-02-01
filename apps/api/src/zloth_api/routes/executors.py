"""Executor status routes."""

from fastapi import APIRouter, Depends

from zloth_api.dependencies import get_cli_status_service
from zloth_api.domain.models import CLIStatusResponse
from zloth_api.services.cli_status_service import CLIStatusService

router = APIRouter(prefix="/executors", tags=["executors"])


@router.get("/status", response_model=CLIStatusResponse)
async def get_executor_status(
    cli_status_service: CLIStatusService = Depends(get_cli_status_service),
) -> CLIStatusResponse:
    """Get availability status of all CLI executors.

    Returns the availability, configured path, resolved path, version,
    and any errors for each CLI executor (Claude Code, Codex, Gemini).
    """
    return await cli_status_service.check_all_cli_status()
