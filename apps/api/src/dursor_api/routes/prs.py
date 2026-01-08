"""Pull Request routes."""

from fastapi import APIRouter, Depends, HTTPException

from dursor_api.dependencies import get_pr_service
from dursor_api.domain.models import (
    PR,
    PRCreate,
    PRCreateAuto,
    PRCreated,
    PRCreateLink,
    PRSyncRequest,
    PRSyncResult,
    PRUpdate,
    PRUpdated,
)
from dursor_api.services.pr_service import GitHubPermissionError, PRService

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
    pr_service: PRService = Depends(get_pr_service),
) -> PR:
    """Regenerate PR description from current diff.

    This endpoint:
    1. Gets cumulative diff from base branch
    2. Loads pull_request_template if available
    3. Generates description using LLM
    4. Updates PR via GitHub API
    """
    try:
        return await pr_service.regenerate_description(task_id, pr_id)
    except GitHubPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
