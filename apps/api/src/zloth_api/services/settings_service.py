"""Unified settings accessor that merges env settings with DB preferences.

This service defines explicit precedence and a single place to read
"effective" runtime settings used by other services.

Precedence:
  1) Environment variables (`ZLOTH_*`, strict system-level)
  2) Database preferences (`user_preferences` table, user-tunable)
  3) Code defaults (pydantic model defaults)
"""

from __future__ import annotations

from dataclasses import dataclass

from zloth_api.config import settings
from zloth_api.storage.dao import UserPreferencesDAO


@dataclass
class NotifyFlags:
    ready: bool
    complete: bool
    failure: bool
    warning: bool


@dataclass

class MergePolicy:
    method: str  # merge | squash | rebase
    delete_branch: bool



class SettingsService:
    """Provides effective settings by merging env and DB preferences."""

    def __init__(self, user_prefs_dao: UserPreferencesDAO):
        self._prefs = user_prefs_dao

    async def get_notify_flags(self) -> NotifyFlags:
        prefs = await self._prefs.get()

        # If DB has explicit values (0/1), use them; otherwise fall back to env
        ready = (
            prefs.notify_on_ready if prefs and prefs.notify_on_ready is not None else None
        )
        complete = (
            prefs.notify_on_complete if prefs and prefs.notify_on_complete is not None else None
        )
        failure = (
            prefs.notify_on_failure if prefs and prefs.notify_on_failure is not None else None
        )
        warning = (
            prefs.notify_on_warning if prefs and prefs.notify_on_warning is not None else None
        )

        return NotifyFlags(
            ready=bool(ready) if ready is not None else settings.notify_on_ready,
            complete=bool(complete) if complete is not None else settings.notify_on_complete,
            failure=bool(failure) if failure is not None else settings.notify_on_failure,
            warning=bool(warning) if warning is not None else settings.notify_on_warning,
        )

    async def get_merge_policy(self) -> MergePolicy:
        prefs = await self._prefs.get()
        method = (
            prefs.merge_method if prefs and prefs.merge_method else settings.merge_method
        )
        delete_branch = (
            prefs.merge_delete_branch
            if prefs and prefs.merge_delete_branch is not None
            else settings.merge_delete_branch
        )
        return MergePolicy(method=method, delete_branch=bool(delete_branch))

    async def get_review_min_score(self) -> float:
        prefs = await self._prefs.get()
        if prefs and prefs.review_min_score is not None:
            return float(prefs.review_min_score)
        return float(settings.review_min_score)
