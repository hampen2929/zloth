"""Repository routes."""

from fastapi import APIRouter, Depends, HTTPException

from dursor_api.dependencies import get_github_service, get_repo_service
from dursor_api.domain.models import Repo, RepoCloneRequest, RepoSelectRequest
from dursor_api.services.github_service import GitHubService
from dursor_api.services.repo_service import RepoService

router = APIRouter(prefix="/repos", tags=["repos"])


@router.post("/clone", response_model=Repo, status_code=201)
async def clone_repo(
    data: RepoCloneRequest,
    repo_service: RepoService = Depends(get_repo_service),
) -> Repo:
    """Clone a repository."""
    try:
        return await repo_service.clone(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to clone: {str(e)}")


@router.post("/select", response_model=Repo, status_code=201)
async def select_repo(
    data: RepoSelectRequest,
    repo_service: RepoService = Depends(get_repo_service),
    github_service: GitHubService = Depends(get_github_service),
) -> Repo:
    """Select and clone a repository by owner/repo name using GitHub App authentication."""
    try:
        return await repo_service.select(data, github_service)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to select repository: {str(e)}")


@router.get("/{repo_id}", response_model=Repo)
async def get_repo(
    repo_id: str,
    repo_service: RepoService = Depends(get_repo_service),
) -> Repo:
    """Get a repository by ID."""
    repo = await repo_service.get(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo
