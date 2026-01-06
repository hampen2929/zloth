"""User preferences routes."""

from fastapi import APIRouter, Depends

from dursor_api.domain.models import UserPreferences, UserPreferencesSave
from dursor_api.dependencies import get_user_preferences_dao
from dursor_api.storage.dao import UserPreferencesDAO

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
    )
