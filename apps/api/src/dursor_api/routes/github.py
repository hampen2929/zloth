"""GitHub App routes."""

from fastapi import APIRouter, Depends, HTTPException

from dursor_api.dependencies import get_github_service
from dursor_api.domain.models import (
    GitHubAppConfig,
    GitHubAppConfigSave,
    GitHubRepository,
)
from dursor_api.services.github_service import GitHubService

router = APIRouter(prefix="/github", tags=["github"])


@router.get("/config", response_model=GitHubAppConfig)
async def get_config(
    github_service: GitHubService = Depends(get_github_service),
) -> GitHubAppConfig:
    """Get GitHub App configuration status."""
    return await github_service.get_config()


@router.post("/config", response_model=GitHubAppConfig)
async def save_config(
    data: GitHubAppConfigSave,
    github_service: GitHubService = Depends(get_github_service),
) -> GitHubAppConfig:
    """Save GitHub App configuration."""
    try:
        return await github_service.save_config(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/repos", response_model=list[GitHubRepository])
async def list_repos(
    github_service: GitHubService = Depends(get_github_service),
) -> list[GitHubRepository]:
    """List repositories accessible to the GitHub App."""
    try:
        return await github_service.list_repos()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list repos: {str(e)}")


@router.get("/repos/{owner}/{repo}/branches", response_model=list[str])
async def list_branches(
    owner: str,
    repo: str,
    github_service: GitHubService = Depends(get_github_service),
) -> list[str]:
    """List branches for a repository."""
    try:
        return await github_service.list_branches(owner, repo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list branches: {str(e)}")
