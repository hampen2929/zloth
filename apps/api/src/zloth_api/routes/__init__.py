"""API routes for zloth."""

from zloth_api.routes.backlog import router as backlog_router
from zloth_api.routes.breakdown import router as breakdown_router
from zloth_api.routes.compare import router as compare_router
from zloth_api.routes.github import router as github_router
from zloth_api.routes.kanban import router as kanban_router
from zloth_api.routes.metrics import router as metrics_router
from zloth_api.routes.models import router as models_router
from zloth_api.routes.preferences import router as preferences_router
from zloth_api.routes.prs import router as prs_router
from zloth_api.routes.repos import router as repos_router
from zloth_api.routes.reviews import router as reviews_router
from zloth_api.routes.runs import router as runs_router
from zloth_api.routes.tasks import router as tasks_router

# Note: webhooks router removed - using CI polling instead (see ci_polling_service.py)

__all__ = [
    "backlog_router",
    "breakdown_router",
    "compare_router",
    "github_router",
    "kanban_router",
    "metrics_router",
    "models_router",
    "preferences_router",
    "repos_router",
    "reviews_router",
    "tasks_router",
    "runs_router",
    "prs_router",
]
