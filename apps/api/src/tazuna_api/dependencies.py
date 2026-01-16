"""FastAPI dependency injection."""

from tazuna_api.config import settings
from tazuna_api.services.agentic_orchestrator import AgenticOrchestrator
from tazuna_api.services.breakdown_service import BreakdownService
from tazuna_api.services.ci_check_service import CICheckService
from tazuna_api.services.ci_polling_service import CIPollingService
from tazuna_api.services.crypto_service import CryptoService
from tazuna_api.services.git_service import GitService
from tazuna_api.services.github_service import GitHubService
from tazuna_api.services.kanban_service import KanbanService
from tazuna_api.services.merge_gate_service import MergeGateService
from tazuna_api.services.model_service import ModelService
from tazuna_api.services.notification_service import NotificationService
from tazuna_api.services.output_manager import OutputManager
from tazuna_api.services.pr_service import PRService
from tazuna_api.services.pr_status_poller import PRStatusPoller
from tazuna_api.services.repo_service import RepoService
from tazuna_api.services.review_service import ReviewService
from tazuna_api.services.run_service import RunService
from tazuna_api.storage.dao import (
    PRDAO,
    AgenticRunDAO,
    BacklogDAO,
    CICheckDAO,
    MessageDAO,
    ModelProfileDAO,
    RepoDAO,
    ReviewDAO,
    RunDAO,
    TaskDAO,
    UserPreferencesDAO,
)
from tazuna_api.storage.db import get_db

# Singletons
_crypto_service: CryptoService | None = None
_run_service: RunService | None = None
_git_service: GitService | None = None
_output_manager: OutputManager | None = None
_breakdown_service: BreakdownService | None = None
_review_service: ReviewService | None = None
_notification_service: NotificationService | None = None
_ci_polling_service: CIPollingService | None = None
_agentic_orchestrator: AgenticOrchestrator | None = None
_pr_status_poller: PRStatusPoller | None = None
_pr_service: PRService | None = None


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
    """Get the PR service singleton."""
    global _pr_service
    if _pr_service is None:
        pr_dao = await get_pr_dao()
        task_dao = await get_task_dao()
        run_dao = await get_run_dao()
        repo_service = await get_repo_service()
        github_service = await get_github_service()
        model_service = await get_model_service()
        git_service = get_git_service()
        _pr_service = PRService(
            pr_dao, task_dao, run_dao, repo_service, github_service, model_service, git_service
        )
    return _pr_service


async def get_github_service() -> GitHubService:
    """Get the GitHub service."""
    db = await get_db()
    return GitHubService(db)


async def get_user_preferences_dao() -> UserPreferencesDAO:
    """Get UserPreferences DAO."""
    db = await get_db()
    return UserPreferencesDAO(db)


async def get_backlog_dao() -> BacklogDAO:
    """Get Backlog DAO."""
    db = await get_db()
    return BacklogDAO(db)


async def get_breakdown_service() -> BreakdownService:
    """Get the breakdown service singleton."""
    global _breakdown_service
    if _breakdown_service is None:
        repo_dao = await get_repo_dao()
        output_manager = get_output_manager()
        backlog_dao = await get_backlog_dao()
        _breakdown_service = BreakdownService(repo_dao, output_manager, backlog_dao)
    return _breakdown_service


async def get_kanban_service() -> KanbanService:
    """Get the kanban service."""
    task_dao = await get_task_dao()
    run_dao = await get_run_dao()
    pr_dao = await get_pr_dao()
    review_dao = await get_review_dao()
    github_service = await get_github_service()
    user_preferences_dao = await get_user_preferences_dao()
    return KanbanService(
        task_dao,
        run_dao,
        pr_dao,
        review_dao,
        github_service,
        user_preferences_dao,
    )


async def get_review_dao() -> ReviewDAO:
    """Get Review DAO."""
    db = await get_db()
    return ReviewDAO(db)


async def get_review_service() -> ReviewService:
    """Get the review service singleton."""
    global _review_service
    if _review_service is None:
        review_dao = await get_review_dao()
        run_dao = await get_run_dao()
        task_dao = await get_task_dao()
        message_dao = await get_message_dao()
        output_manager = get_output_manager()
        _review_service = ReviewService(
            review_dao,
            run_dao,
            task_dao,
            message_dao,
            output_manager,
        )
    return _review_service


async def get_agentic_run_dao() -> AgenticRunDAO:
    """Get AgenticRun DAO."""
    db = await get_db()
    return AgenticRunDAO(db)


def get_notification_service() -> NotificationService:
    """Get the notification service singleton."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


async def get_merge_gate_service() -> MergeGateService:
    """Get the merge gate service."""
    github_service = await get_github_service()
    review_dao = await get_review_dao()
    return MergeGateService(github_service, review_dao)


async def get_ci_polling_service() -> CIPollingService:
    """Get the CI polling service singleton."""
    global _ci_polling_service
    if _ci_polling_service is None:
        github_service = await get_github_service()
        _ci_polling_service = CIPollingService(github_service)
    return _ci_polling_service


async def get_agentic_orchestrator() -> AgenticOrchestrator:
    """Get the agentic orchestrator singleton."""
    global _agentic_orchestrator
    if _agentic_orchestrator is None:
        run_service = await get_run_service()
        review_service = await get_review_service()
        merge_gate_service = await get_merge_gate_service()
        git_service = get_git_service()
        github_service = await get_github_service()
        notification_service = get_notification_service()
        ci_polling_service = await get_ci_polling_service()
        task_dao = await get_task_dao()
        pr_dao = await get_pr_dao()
        agentic_dao = await get_agentic_run_dao()
        _agentic_orchestrator = AgenticOrchestrator(
            run_service=run_service,
            review_service=review_service,
            merge_gate_service=merge_gate_service,
            git_service=git_service,
            github_service=github_service,
            notification_service=notification_service,
            ci_polling_service=ci_polling_service,
            task_dao=task_dao,
            pr_dao=pr_dao,
            agentic_dao=agentic_dao,
        )
    return _agentic_orchestrator


async def get_pr_status_poller() -> PRStatusPoller:
    """Get the PR status poller singleton."""
    global _pr_status_poller
    if _pr_status_poller is None:
        pr_dao = await get_pr_dao()
        github_service = await get_github_service()
        _pr_status_poller = PRStatusPoller(pr_dao, github_service)
    return _pr_status_poller


async def get_ci_check_dao() -> CICheckDAO:
    """Get CICheck DAO."""
    db = await get_db()
    return CICheckDAO(db)


async def get_ci_check_service() -> CICheckService:
    """Get the CI check service."""
    ci_check_dao = await get_ci_check_dao()
    pr_dao = await get_pr_dao()
    task_dao = await get_task_dao()
    repo_dao = await get_repo_dao()
    github_service = await get_github_service()
    return CICheckService(ci_check_dao, pr_dao, task_dao, repo_dao, github_service)
