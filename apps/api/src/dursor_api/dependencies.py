"""FastAPI dependency injection."""

from dursor_api.config import settings
from dursor_api.services.crypto_service import CryptoService
from dursor_api.services.git_service import GitService
from dursor_api.services.github_service import GitHubService
from dursor_api.services.model_service import ModelService
from dursor_api.services.output_manager import OutputManager
from dursor_api.services.pr_service import PRService
from dursor_api.services.repo_service import RepoService
from dursor_api.services.run_service import RunService
from dursor_api.storage.dao import (
    MessageDAO,
    ModelProfileDAO,
    PRDAO,
    RepoDAO,
    RunDAO,
    TaskDAO,
    UserPreferencesDAO,
)
from dursor_api.storage.db import get_db


# Singletons
_crypto_service: CryptoService | None = None
_run_service: RunService | None = None
_git_service: GitService | None = None
_output_manager: OutputManager | None = None


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


def get_git_service() -> GitService:
    """Get the git service singleton."""
    global _git_service
    if _git_service is None:
        _git_service = GitService()
    return _git_service


def get_output_manager() -> OutputManager:
    """Get the output manager singleton."""
    global _output_manager
    if _output_manager is None:
        _output_manager = OutputManager()
    return _output_manager


async def get_run_service() -> RunService:
    """Get the run service (singleton for queue management)."""
    global _run_service
    if _run_service is None:
        run_dao = await get_run_dao()
        task_dao = await get_task_dao()
        model_service = await get_model_service()
        repo_service = await get_repo_service()
        git_service = get_git_service()
        user_preferences_dao = await get_user_preferences_dao()
        github_service = await get_github_service()
        output_manager = get_output_manager()
        _run_service = RunService(
            run_dao,
            task_dao,
            model_service,
            repo_service,
            git_service,
            user_preferences_dao,
            github_service,
            output_manager,
        )
    return _run_service


async def get_pr_service() -> PRService:
    """Get the PR service."""
    pr_dao = await get_pr_dao()
    task_dao = await get_task_dao()
    run_dao = await get_run_dao()
    repo_service = await get_repo_service()
    github_service = await get_github_service()
    git_service = get_git_service()
    return PRService(
        pr_dao, task_dao, run_dao, repo_service, github_service, git_service
    )


async def get_github_service() -> GitHubService:
    """Get the GitHub service."""
    db = await get_db()
    return GitHubService(db)


async def get_user_preferences_dao() -> UserPreferencesDAO:
    """Get UserPreferences DAO."""
    db = await get_db()
    return UserPreferencesDAO(db)
