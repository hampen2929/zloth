"""API routes for tazuna."""

from tazuna_api.routes.backlog import router as backlog_router
from tazuna_api.routes.breakdown import router as breakdown_router
from tazuna_api.routes.github import router as github_router
from tazuna_api.routes.kanban import router as kanban_router
from tazuna_api.routes.models import router as models_router
from tazuna_api.routes.preferences import router as preferences_router
from tazuna_api.routes.prs import router as prs_router
from tazuna_api.routes.repos import router as repos_router
from tazuna_api.routes.reviews import router as reviews_router
from tazuna_api.routes.runs import router as runs_router
from tazuna_api.routes.tasks import router as tasks_router

# Note: webhooks router removed - using CI polling instead (see ci_polling_service.py)

__all__ = [
    "backlog_router",
    "breakdown_router",
    "github_router",
    "kanban_router",
    "models_router",
    "preferences_router",
    "repos_router",
    "reviews_router",
    "tasks_router",
    "runs_router",
    "prs_router",
]
