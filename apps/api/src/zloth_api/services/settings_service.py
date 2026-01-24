"""Settings service for merging environment and user preferences."""

from __future__ import annotations

import os
from dataclasses import dataclass

from zloth_api.config import settings
from zloth_api.storage.dao import UserPreferencesDAO


@dataclass(frozen=True)
class UserRuntimeSettings:
    """Resolved settings for user-tunable runtime behaviors."""

    notify_on_ready: bool
    notify_on_complete: bool
    notify_on_failure: bool
    notify_on_warning: bool
    merge_method: str
    review_min_score: float


class SettingsService:
    """Resolves settings with env > DB > defaults precedence."""

    def __init__(self, user_preferences_dao: UserPreferencesDAO | None = None):
        self.user_preferences_dao = user_preferences_dao

    async def get_user_runtime_settings(self) -> UserRuntimeSettings:
        """Get user-tunable settings with precedence rules applied."""
        prefs = await self.user_preferences_dao.get() if self.user_preferences_dao else None

        return UserRuntimeSettings(
            notify_on_ready=self._resolve_bool(
                "notify_on_ready",
                prefs.notify_on_ready if prefs else None,
                settings.notify_on_ready,
            ),
            notify_on_complete=self._resolve_bool(
                "notify_on_complete",
                prefs.notify_on_complete if prefs else None,
                settings.notify_on_complete,
            ),
            notify_on_failure=self._resolve_bool(
                "notify_on_failure",
                prefs.notify_on_failure if prefs else None,
                settings.notify_on_failure,
            ),
            notify_on_warning=self._resolve_bool(
                "notify_on_warning",
                prefs.notify_on_warning if prefs else None,
                settings.notify_on_warning,
            ),
            merge_method=self._resolve_value(
                "merge_method",
                prefs.merge_method if prefs else None,
                settings.merge_method,
            ),
            review_min_score=self._resolve_value(
                "review_min_score",
                prefs.review_min_score if prefs else None,
                settings.review_min_score,
            ),
        )

    def _resolve_bool(self, field_name: str, db_value: bool | None, default: bool) -> bool:
        return bool(self._resolve_value(field_name, db_value, default))

    def _resolve_value(
        self, field_name: str, db_value: str | float | None, default: str | float
    ) -> str | float:
        if self._env_override(field_name):
            return default
        if db_value is not None:
            return db_value
        return default

    @staticmethod
    def _env_override(field_name: str) -> bool:
        env_key = f"ZLOTH_{field_name.upper()}"
        return env_key in os.environ
