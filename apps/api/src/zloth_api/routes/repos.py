"""Repository routes."""

from fastapi import APIRouter, Depends

from zloth_api.dependencies import get_github_service, get_repo_service
from zloth_api.domain.models import Repo, RepoCloneRequest, RepoSelectRequest
from zloth_api.errors import NotFoundError
from zloth_api.services.github_service import GitHubService
from zloth_api.services.repo_service import RepoService

router = APIRouter(prefix="/repos", tags=["repos"])


@router.post("/clone", response_model=Repo, status_code=201)
async def clone_repo(
    data: RepoCloneRequest,
    repo_service: RepoService = Depends(get_repo_service),
) -> Repo:
    """Clone a repository."""
    return await repo_service.clone(data)


@router.post("/select", response_model=Repo, status_code=201)
async def select_repo(
    data: RepoSelectRequest,
    repo_service: RepoService = Depends(get_repo_service),
    github_service: GitHubService = Depends(get_github_service),
) -> Repo:
    """Select and clone a repository by owner/repo name using GitHub App authentication."""
    return await repo_service.select(data, github_service)


@router.get("/{repo_id}", response_model=Repo)
async def get_repo(
    repo_id: str,
    repo_service: RepoService = Depends(get_repo_service),
) -> Repo:
    """Get a repository by ID."""
    repo = await repo_service.get(repo_id)
    if not repo:
        raise NotFoundError("Repository not found", details={"repo_id": repo_id})
    return repo
