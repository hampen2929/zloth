"""FastAPI dependency injection."""

from functools import lru_cache

from dursor_api.config import settings
from dursor_api.services.crypto_service import CryptoService
from dursor_api.services.github_service import GitHubService
from dursor_api.services.model_service import ModelService
from dursor_api.services.repo_service import RepoService
from dursor_api.services.run_service import RunService
from dursor_api.services.pr_service import PRService
from dursor_api.services.worktree_service import WorktreeService
from dursor_api.storage.db import Database, get_db
from dursor_api.storage.dao import (
    MessageDAO,
    ModelProfileDAO,
    PRDAO,
    RepoDAO,
    RunDAO,
    TaskDAO,
)


# Singletons
_crypto_service: CryptoService | None = None
_run_service: RunService | None = None
_worktree_service: WorktreeService | None = None


def get_crypto_service() -> CryptoService:
    """Get the crypto service singleton."""
    global _crypto_service
    if _crypto_service is None:
        _crypto_service = CryptoService(settings.encryption_key)
    return _crypto_service


async def get_model_profile_dao() -> ModelProfileDAO:
    """Get ModelProfile DAO."""
    db = await get_db()
    return ModelProfileDAO(db)


async def get_repo_dao() -> RepoDAO:
    """Get Repo DAO."""
    db = await get_db()
    return RepoDAO(db)


async def get_task_dao() -> TaskDAO:
    """Get Task DAO."""
    db = await get_db()
    return TaskDAO(db)


async def get_message_dao() -> MessageDAO:
    """Get Message DAO."""
    db = await get_db()
    return MessageDAO(db)


async def get_run_dao() -> RunDAO:
    """Get Run DAO."""
    db = await get_db()
    return RunDAO(db)


async def get_pr_dao() -> PRDAO:
    """Get PR DAO."""
    db = await get_db()
    return PRDAO(db)


async def get_model_service() -> ModelService:
    """Get the model service."""
    dao = await get_model_profile_dao()
    crypto = get_crypto_service()
    return ModelService(dao, crypto)


async def get_repo_service() -> RepoService:
    """Get the repo service."""
    dao = await get_repo_dao()
    return RepoService(dao)


def get_worktree_service() -> WorktreeService:
    """Get the worktree service singleton."""
    global _worktree_service
    if _worktree_service is None:
        _worktree_service = WorktreeService()
    return _worktree_service


async def get_run_service() -> RunService:
    """Get the run service (singleton for queue management)."""
    global _run_service
    if _run_service is None:
        run_dao = await get_run_dao()
        task_dao = await get_task_dao()
        model_service = await get_model_service()
        repo_service = await get_repo_service()
        worktree_service = get_worktree_service()
        _run_service = RunService(run_dao, task_dao, model_service, repo_service, worktree_service)
    return _run_service


async def get_pr_service() -> PRService:
    """Get the PR service."""
    pr_dao = await get_pr_dao()
    task_dao = await get_task_dao()
    run_dao = await get_run_dao()
    repo_service = await get_repo_service()
    github_service = await get_github_service()
    return PRService(pr_dao, task_dao, run_dao, repo_service, github_service)


async def get_github_service() -> GitHubService:
    """Get the GitHub service."""
    db = await get_db()
    return GitHubService(db)
