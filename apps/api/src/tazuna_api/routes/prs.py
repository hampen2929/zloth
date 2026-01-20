"""Pull Request routes."""

import asyncio
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from tazuna_api.dependencies import (
    get_ci_check_service,
    get_pr_service,
    get_run_dao,
    get_user_preferences_dao,
)
from tazuna_api.domain.enums import PRUpdateMode, RunStatus
from tazuna_api.domain.models import (
    PR,
    CICheck,
    CICheckResponse,
    PRCreate,
    PRCreateAuto,
    PRCreated,
    PRCreateLink,
    PRLinkJob,
    PRLinkJobResult,
    PRSyncRequest,
    PRSyncResult,
    PRUpdate,
    PRUpdated,
)
from tazuna_api.services.ci_check_service import CICheckService
from tazuna_api.services.pr_service import GitHubPermissionError, PRService
from tazuna_api.storage.dao import RunDAO, UserPreferencesDAO

logger = logging.getLogger(__name__)

router = APIRouter(tags=["prs"])

# Cooldown period for CI checks per task (in seconds)
CI_CHECK_COOLDOWN_SECONDS = 10

# Track last CI check time per task to prevent duplicate triggers
_last_ci_check_times: dict[str, datetime] = {}


def _can_trigger_ci_check(task_id: str) -> bool:
    """Check if enough time has passed since last CI check for this task."""
    last_time = _last_ci_check_times.get(task_id)
    if last_time is None:
        return True
    elapsed = datetime.utcnow() - last_time
    return elapsed >= timedelta(seconds=CI_CHECK_COOLDOWN_SECONDS)


def _record_ci_check_time(task_id: str) -> None:
    """Record the current time as the last CI check time for this task."""
    _last_ci_check_times[task_id] = datetime.utcnow()


async def _trigger_ci_check_if_enabled(
    task_id: str,
    pr_id: str,
    ci_check_service: CICheckService,
    user_preferences_dao: UserPreferencesDAO,
    run_dao: RunDAO | None = None,
) -> None:
    """Trigger CI check in background if enable_gating_status is enabled.

    CI check is only triggered if:
    1. enable_gating_status preference is enabled
    2. No runs are currently running for this task (AI implementation is complete)
    3. Cooldown period has passed since last CI check for this task
    """
    try:
        prefs = await user_preferences_dao.get()
        if not prefs or not prefs.enable_gating_status:
            return

        # Check cooldown to prevent duplicate triggers
        if not _can_trigger_ci_check(task_id):
            logger.debug(f"CI check skipped due to cooldown: task={task_id}")
            return

        # Check if any runs are still in progress
        if run_dao:
            runs = await run_dao.list(task_id)
            running_runs = [r for r in runs if r.status in (RunStatus.RUNNING, RunStatus.QUEUED)]
            if running_runs:
                logger.info(
                    f"CI check deferred: {len(running_runs)} run(s) still in progress "
                    f"for task={task_id}"
                )
                return

        # Record the check time and trigger CI check
        _record_ci_check_time(task_id)

        # Run CI check in background (don't block the response)
        asyncio.create_task(_run_ci_check(task_id, pr_id, ci_check_service))
    except Exception as e:
        logger.warning(f"Failed to check gating preference: {e}")


async def _run_ci_check(task_id: str, pr_id: str, ci_check_service: CICheckService) -> None:
    """Run CI check in background."""
    try:
        await ci_check_service.check_ci(task_id, pr_id)
        logger.info(f"Auto CI check completed for task={task_id}, pr={pr_id}")
    except Exception as e:
        logger.warning(f"Auto CI check failed for task={task_id}, pr={pr_id}: {e}")


@router.post("/tasks/{task_id}/prs", response_model=PRCreated, status_code=201)
async def create_pr(
    task_id: str,
    data: PRCreate,
    pr_service: PRService = Depends(get_pr_service),
    ci_check_service: CICheckService = Depends(get_ci_check_service),
    user_preferences_dao: UserPreferencesDAO = Depends(get_user_preferences_dao),
    run_dao: RunDAO = Depends(get_run_dao),
) -> PRCreated:
    """Create a Pull Request from a run."""
    try:
        pr = await pr_service.create(task_id, data)

        # Trigger CI check in background if gating is enabled
        await _trigger_ci_check_if_enabled(
            task_id, pr.id, ci_check_service, user_preferences_dao, run_dao
        )

        return PRCreated(
            pr_id=pr.id,
            url=pr.url,
            branch=pr.branch,
            number=pr.number,
        )
    except GitHubPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/prs/auto", response_model=PRCreated, status_code=201)
async def create_pr_auto(
    task_id: str,
    data: PRCreateAuto,
    pr_service: PRService = Depends(get_pr_service),
    ci_check_service: CICheckService = Depends(get_ci_check_service),
    user_preferences_dao: UserPreferencesDAO = Depends(get_user_preferences_dao),
    run_dao: RunDAO = Depends(get_run_dao),
) -> PRCreated:
    """Create a Pull Request with AI-generated title and description.

    This endpoint automatically generates the PR title and description
    using AI based on the diff and task context.
    """
    try:
        pr = await pr_service.create_auto(task_id, data)

        # Trigger CI check in background if gating is enabled
        await _trigger_ci_check_if_enabled(
            task_id, pr.id, ci_check_service, user_preferences_dao, run_dao
        )

        return PRCreated(
            pr_id=pr.id,
            url=pr.url,
            branch=pr.branch,
            number=pr.number,
        )
    except GitHubPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/prs/link", response_model=PRCreateLink)
async def create_pr_link(
    task_id: str,
    data: PRCreate,
    pr_service: PRService = Depends(get_pr_service),
) -> PRCreateLink:
    """Generate a GitHub compare link for manual PR creation."""
    try:
        return await pr_service.create_link(task_id, data)
    except GitHubPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/prs/auto/link", response_model=PRCreateLink)
async def create_pr_link_auto(
    task_id: str,
    data: PRCreateAuto,
    pr_service: PRService = Depends(get_pr_service),
) -> PRCreateLink:
    """Generate a GitHub compare link for manual PR creation (auto flow)."""
    try:
        return await pr_service.create_link_auto(task_id, data)
    except GitHubPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/prs/auto/link/job", response_model=PRLinkJob)
async def start_pr_link_auto_job(
    task_id: str,
    data: PRCreateAuto,
    pr_service: PRService = Depends(get_pr_service),
) -> PRLinkJob:
    """Start async PR link generation (returns immediately with job ID).

    Use this endpoint for long-running PR link generation to avoid timeout.
    Poll GET /prs/jobs/{job_id} to check status and get result.
    """
    try:
        return pr_service.start_link_auto_job(task_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/prs/jobs/{job_id}", response_model=PRLinkJobResult)
async def get_pr_link_job(
    job_id: str,
    pr_service: PRService = Depends(get_pr_service),
) -> PRLinkJobResult:
    """Get status of PR link generation job.

    Poll this endpoint until status is 'completed' or 'failed'.
    """
    result = pr_service.get_link_auto_job(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Job not found")
    return result


@router.post("/tasks/{task_id}/prs/sync", response_model=PRSyncResult)
async def sync_manual_pr(
    task_id: str,
    data: PRSyncRequest,
    pr_service: PRService = Depends(get_pr_service),
    ci_check_service: CICheckService = Depends(get_ci_check_service),
    user_preferences_dao: UserPreferencesDAO = Depends(get_user_preferences_dao),
    run_dao: RunDAO = Depends(get_run_dao),
) -> PRSyncResult:
    """Sync a manually created PR (created via the GitHub compare UI)."""
    try:
        result = await pr_service.sync_manual_pr(task_id, data.selected_run_id)

        # Trigger CI check in background if gating is enabled and PR was found
        if result.found and result.pr:
            await _trigger_ci_check_if_enabled(
                task_id, result.pr.pr_id, ci_check_service, user_preferences_dao, run_dao
            )

        return result
    except GitHubPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/prs/{pr_id}/update", response_model=PRUpdated)
async def update_pr(
    task_id: str,
    pr_id: str,
    data: PRUpdate,
    pr_service: PRService = Depends(get_pr_service),
    ci_check_service: CICheckService = Depends(get_ci_check_service),
    user_preferences_dao: UserPreferencesDAO = Depends(get_user_preferences_dao),
    run_dao: RunDAO = Depends(get_run_dao),
) -> PRUpdated:
    """Update a Pull Request with a new run."""
    try:
        pr = await pr_service.update(task_id, pr_id, data)

        # Trigger CI check in background if gating is enabled
        await _trigger_ci_check_if_enabled(
            task_id, pr_id, ci_check_service, user_preferences_dao, run_dao
        )

        return PRUpdated(
            url=pr.url,
            latest_commit=pr.latest_commit,
        )
    except GitHubPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tasks/{task_id}/prs/{pr_id}", response_model=PR)
async def get_pr(
    task_id: str,
    pr_id: str,
    pr_service: PRService = Depends(get_pr_service),
) -> PR:
    """Get a Pull Request by ID."""
    pr = await pr_service.get(task_id, pr_id)
    if not pr:
        raise HTTPException(status_code=404, detail="PR not found")
    return pr


@router.get("/tasks/{task_id}/prs", response_model=list[PR])
async def list_prs(
    task_id: str,
    pr_service: PRService = Depends(get_pr_service),
) -> list[PR]:
    """List Pull Requests for a task."""
    return await pr_service.list(task_id)


@router.post("/tasks/{task_id}/prs/{pr_id}/regenerate-description", response_model=PR)
async def regenerate_pr_description(
    task_id: str,
    pr_id: str,
    mode: PRUpdateMode = PRUpdateMode.BOTH,
    pr_service: PRService = Depends(get_pr_service),
) -> PR:
    """Regenerate PR description and/or title from current diff.

    This endpoint:
    1. Gets cumulative diff from base branch
    2. Loads pull_request_template if available
    3. Generates title and/or description using LLM based on mode
    4. Updates PR via GitHub API

    Args:
        mode: What to update - "both", "description", or "title". Defaults to "both".
    """
    try:
        return await pr_service.regenerate_description(task_id, pr_id, mode=mode)
    except GitHubPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/prs/{pr_id}/check-ci", response_model=CICheckResponse)
async def check_ci(
    task_id: str,
    pr_id: str,
    ci_check_service: CICheckService = Depends(get_ci_check_service),
) -> CICheckResponse:
    """Check CI status for a PR.

    Fetches current CI status from GitHub and returns the result.
    If CI is still pending, is_complete will be false - poll again to check.
    """
    try:
        return await ci_check_service.check_ci(task_id, pr_id)
    except ValueError as e:
        logger.warning(f"CI check validation error for task={task_id}, pr={pr_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"CI check failed for task={task_id}, pr={pr_id}: {e}")
        raise HTTPException(status_code=500, detail=f"CI check failed: {e}")


@router.get("/tasks/{task_id}/ci-checks", response_model=list[CICheck])
async def list_ci_checks(
    task_id: str,
    ci_check_service: CICheckService = Depends(get_ci_check_service),
) -> list[CICheck]:
    """List all CI checks for a task."""
    return await ci_check_service.get_ci_checks(task_id)
