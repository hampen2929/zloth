"""Pull Request routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from dursor_api.dependencies import get_ci_check_service, get_pr_service
from dursor_api.domain.models import (
    PR,
    CICheck,
    CICheckResponse,
    PRCreate,
    PRCreateAuto,
    PRCreated,
    PRCreateLink,
    PRLinkJob,
    PRLinkJobResult,
    PRSyncRequest,
    PRSyncResult,
    PRUpdate,
    PRUpdated,
)
from dursor_api.services.ci_check_service import CICheckService
from dursor_api.services.pr_service import GitHubPermissionError, PRService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["prs"])


@router.post("/tasks/{task_id}/prs", response_model=PRCreated, status_code=201)
async def create_pr(
    task_id: str,
    data: PRCreate,
    pr_service: PRService = Depends(get_pr_service),
) -> PRCreated:
    """Create a Pull Request from a run."""
    try:
        pr = await pr_service.create(task_id, data)
        return PRCreated(
            pr_id=pr.id,
            url=pr.url,
            branch=pr.branch,
            number=pr.number,
        )
    except GitHubPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/prs/auto", response_model=PRCreated, status_code=201)
async def create_pr_auto(
    task_id: str,
    data: PRCreateAuto,
    pr_service: PRService = Depends(get_pr_service),
) -> PRCreated:
    """Create a Pull Request with AI-generated title and description.

    This endpoint automatically generates the PR title and description
    using AI based on the diff and task context.
    """
    try:
        pr = await pr_service.create_auto(task_id, data)
        return PRCreated(
            pr_id=pr.id,
            url=pr.url,
            branch=pr.branch,
            number=pr.number,
        )
    except GitHubPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/prs/link", response_model=PRCreateLink)
async def create_pr_link(
    task_id: str,
    data: PRCreate,
    pr_service: PRService = Depends(get_pr_service),
) -> PRCreateLink:
    """Generate a GitHub compare link for manual PR creation."""
    try:
        return await pr_service.create_link(task_id, data)
    except GitHubPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/prs/auto/link", response_model=PRCreateLink)
async def create_pr_link_auto(
    task_id: str,
    data: PRCreateAuto,
    pr_service: PRService = Depends(get_pr_service),
) -> PRCreateLink:
    """Generate a GitHub compare link for manual PR creation (auto flow)."""
    try:
        return await pr_service.create_link_auto(task_id, data)
    except GitHubPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/prs/auto/link/job", response_model=PRLinkJob)
async def start_pr_link_auto_job(
    task_id: str,
    data: PRCreateAuto,
    pr_service: PRService = Depends(get_pr_service),
) -> PRLinkJob:
    """Start async PR link generation (returns immediately with job ID).

    Use this endpoint for long-running PR link generation to avoid timeout.
    Poll GET /prs/jobs/{job_id} to check status and get result.
    """
    try:
        return pr_service.start_link_auto_job(task_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/prs/jobs/{job_id}", response_model=PRLinkJobResult)
async def get_pr_link_job(
    job_id: str,
    pr_service: PRService = Depends(get_pr_service),
) -> PRLinkJobResult:
    """Get status of PR link generation job.

    Poll this endpoint until status is 'completed' or 'failed'.
    """
    result = pr_service.get_link_auto_job(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Job not found")
    return result


@router.post("/tasks/{task_id}/prs/sync", response_model=PRSyncResult)
async def sync_manual_pr(
    task_id: str,
    data: PRSyncRequest,
    pr_service: PRService = Depends(get_pr_service),
) -> PRSyncResult:
    """Sync a manually created PR (created via the GitHub compare UI)."""
    try:
        return await pr_service.sync_manual_pr(task_id, data.selected_run_id)
    except GitHubPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/prs/{pr_id}/update", response_model=PRUpdated)
async def update_pr(
    task_id: str,
    pr_id: str,
    data: PRUpdate,
    pr_service: PRService = Depends(get_pr_service),
) -> PRUpdated:
    """Update a Pull Request with a new run."""
    try:
        pr = await pr_service.update(task_id, pr_id, data)
        return PRUpdated(
            url=pr.url,
            latest_commit=pr.latest_commit,
        )
    except GitHubPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tasks/{task_id}/prs/{pr_id}", response_model=PR)
async def get_pr(
    task_id: str,
    pr_id: str,
    pr_service: PRService = Depends(get_pr_service),
) -> PR:
    """Get a Pull Request by ID."""
    pr = await pr_service.get(task_id, pr_id)
    if not pr:
        raise HTTPException(status_code=404, detail="PR not found")
    return pr


@router.get("/tasks/{task_id}/prs", response_model=list[PR])
async def list_prs(
    task_id: str,
    pr_service: PRService = Depends(get_pr_service),
) -> list[PR]:
    """List Pull Requests for a task."""
    return await pr_service.list(task_id)


@router.post("/tasks/{task_id}/prs/{pr_id}/regenerate-description", response_model=PR)
async def regenerate_pr_description(
    task_id: str,
    pr_id: str,
    update_title: bool = True,
    pr_service: PRService = Depends(get_pr_service),
) -> PR:
    """Regenerate PR description from current diff.

    This endpoint:
    1. Gets cumulative diff from base branch
    2. Loads pull_request_template if available
    3. Generates title (optional) and description using LLM
    4. Updates PR via GitHub API

    Args:
        update_title: If True, also regenerate and update the PR title. Defaults to True.
    """
    try:
        return await pr_service.regenerate_description(task_id, pr_id, update_title=update_title)
    except GitHubPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/prs/{pr_id}/check-ci", response_model=CICheckResponse)
async def check_ci(
    task_id: str,
    pr_id: str,
    ci_check_service: CICheckService = Depends(get_ci_check_service),
) -> CICheckResponse:
    """Check CI status for a PR.

    Fetches current CI status from GitHub and returns the result.
    If CI is still pending, is_complete will be false - poll again to check.
    """
    try:
        return await ci_check_service.check_ci(task_id, pr_id)
    except ValueError as e:
        logger.warning(f"CI check validation error for task={task_id}, pr={pr_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"CI check failed for task={task_id}, pr={pr_id}: {e}")
        raise HTTPException(status_code=500, detail=f"CI check failed: {e}")


@router.get("/tasks/{task_id}/ci-checks", response_model=list[CICheck])
async def list_ci_checks(
    task_id: str,
    ci_check_service: CICheckService = Depends(get_ci_check_service),
) -> list[CICheck]:
    """List all CI checks for a task."""
    return await ci_check_service.get_ci_checks(task_id)
