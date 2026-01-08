"""API routes for dursor."""

from dursor_api.routes.github import router as github_router
from dursor_api.routes.models import router as models_router
from dursor_api.routes.preferences import router as preferences_router
from dursor_api.routes.prs import router as prs_router
from dursor_api.routes.repos import router as repos_router
from dursor_api.routes.runs import router as runs_router
from dursor_api.routes.tasks import router as tasks_router

__all__ = [
    "github_router",
    "models_router",
    "preferences_router",
    "repos_router",
    "tasks_router",
    "runs_router",
    "prs_router",
]
