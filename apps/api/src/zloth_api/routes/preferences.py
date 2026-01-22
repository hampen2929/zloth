"""User preferences routes."""

from fastapi import APIRouter, Depends

from zloth_api.dependencies import get_user_preferences_dao
from zloth_api.domain.models import UserPreferences, UserPreferencesSave
from zloth_api.storage.dao import UserPreferencesDAO

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", response_model=UserPreferences)
async def get_preferences(
    dao: UserPreferencesDAO = Depends(get_user_preferences_dao),
) -> UserPreferences:
    """Get user preferences."""
    prefs = await dao.get()
    if prefs is None:
        return UserPreferences()
    return prefs


@router.post("", response_model=UserPreferences)
async def save_preferences(
    data: UserPreferencesSave,
    dao: UserPreferencesDAO = Depends(get_user_preferences_dao),
) -> UserPreferences:
    """Save user preferences."""
    return await dao.save(
        default_repo_owner=data.default_repo_owner,
        default_repo_name=data.default_repo_name,
        default_branch=data.default_branch,
        default_branch_prefix=data.default_branch_prefix,
        default_pr_creation_mode=(
            data.default_pr_creation_mode.value if data.default_pr_creation_mode else None
        ),
        default_coding_mode=(data.default_coding_mode.value if data.default_coding_mode else None),
        auto_generate_pr_description=data.auto_generate_pr_description,
        worktrees_dir=data.worktrees_dir,
        data_dir=data.data_dir,
        enable_gating_status=data.enable_gating_status,
    )
