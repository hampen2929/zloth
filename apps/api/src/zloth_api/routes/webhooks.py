"""Webhook routes for CI integration."""

import hashlib
import hmac
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request

from zloth_api.config import settings
from zloth_api.domain.models import (
    CIJobResult,
    CIResult,
    CIWebhookPayload,
    CIWebhookResponse,
)

if TYPE_CHECKING:
    from zloth_api.services.agentic_orchestrator import AgenticOrchestrator
    from zloth_api.storage.dao import PRDAO, CICheckDAO

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def verify_signature(body: bytes, signature: str | None) -> bool:
    """Verify HMAC-SHA256 signature from GitHub.

    Args:
        body: Request body.
        signature: X-Hub-Signature-256 header value.

    Returns:
        True if signature is valid.
    """
    if not signature:
        return False

    if not settings.webhook_secret:
        logger.warning("Webhook secret not configured, skipping verification")
        return True

    secret = settings.webhook_secret.encode()
    expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def get_orchestrator() -> "AgenticOrchestrator":
    """Get agentic orchestrator dependency.

    Returns:
        AgenticOrchestrator instance.
    """
    from zloth_api.dependencies import get_agentic_orchestrator

    return await get_agentic_orchestrator()


@router.post("/ci", response_model=CIWebhookResponse)
async def handle_ci_webhook(
    request: Request,
    orchestrator: "AgenticOrchestrator" = Depends(get_orchestrator),
) -> CIWebhookResponse:
    """Receive CI completion webhook from GitHub Actions.

    Triggers auto-fix if CI failed, or proceeds to review/merge if passed.

    Args:
        request: FastAPI request.
        orchestrator: Agentic orchestrator service.

    Returns:
        Webhook response.

    Raises:
        HTTPException: If signature verification fails.
    """
    # Get request body
    body = await request.body()

    # Verify signature
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_signature(body, signature):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    try:
        payload = CIWebhookPayload.model_validate_json(body)
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid payload: {str(e)}")

    logger.info(
        f"Received CI webhook: repo={payload.repository}, "
        f"sha={payload.sha[:8]}, conclusion={payload.conclusion}"
    )

    # Find associated task
    if not payload.pr_number:
        return CIWebhookResponse(
            status="ignored",
            action_taken="No PR number in payload",
        )

    task_id = await orchestrator.find_task_by_pr(payload.pr_number)
    if not task_id:
        return CIWebhookResponse(
            status="ignored",
            action_taken="No associated task found",
        )

    # Build CI result
    success = payload.conclusion == "success"
    failed_jobs: list[CIJobResult] = []

    if not success:
        for job_name, result in payload.jobs.items():
            if result == "failure":
                failed_jobs.append(
                    CIJobResult(
                        job_name=job_name,
                        result=result,
                        error_log=None,  # Will be fetched by orchestrator if needed
                    )
                )

    ci_result = CIResult(
        success=success,
        workflow_run_id=payload.workflow_run_id,
        sha=payload.sha,
        jobs=payload.jobs,
        failed_jobs=failed_jobs,
    )

    # Handle CI result
    state = await orchestrator.handle_ci_result(task_id, ci_result)

    if not state:
        return CIWebhookResponse(
            status="ignored",
            action_taken="No active agentic state for task",
        )

    if success:
        return CIWebhookResponse(
            status="proceeding_to_review",
            action_taken="CI passed, proceeding to review phase",
        )
    else:
        return CIWebhookResponse(
            status="auto_fix_triggered",
            action_taken="CI failed, triggering auto-fix",
            failed_jobs=[job.job_name for job in failed_jobs],
        )


async def get_ci_check_dao() -> "CICheckDAO":
    """Get CI check DAO dependency."""
    from zloth_api.dependencies import get_ci_check_dao

    return await get_ci_check_dao()


async def get_pr_dao() -> "PRDAO":
    """Get PR DAO dependency."""
    from zloth_api.dependencies import get_pr_dao

    return await get_pr_dao()


@router.post("/github")
async def handle_github_webhook(
    request: Request,
    ci_check_dao: "CICheckDAO" = Depends(get_ci_check_dao),
    pr_dao: "PRDAO" = Depends(get_pr_dao),
) -> dict[str, str]:
    """Receive general GitHub webhook events.

    Currently handles:
    - check_suite events for CI status
    - check_run events for CI job status
    - workflow_run events for CI workflow status
    - pull_request events for PR status

    Args:
        request: FastAPI request.
        ci_check_dao: CI check DAO.
        pr_dao: PR DAO.

    Returns:
        Acknowledgement response.
    """
    body = await request.body()

    # Verify signature
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event_type = request.headers.get("X-GitHub-Event", "unknown")
    logger.info(f"Received GitHub webhook: event={event_type}")

    # Parse and handle CI-related events to update ci_checks table
    if event_type in ("check_run", "check_suite", "workflow_run"):
        try:
            import json

            payload = json.loads(body)
            await _handle_ci_webhook_for_checks(event_type, payload, ci_check_dao, pr_dao)
        except Exception as e:
            logger.warning(f"Failed to handle CI webhook for ci_checks: {e}")

    return {"status": "received", "event": event_type}


async def _handle_ci_webhook_for_checks(
    event_type: str,
    payload: dict,
    ci_check_dao: "CICheckDAO",
    pr_dao: "PRDAO",
) -> None:
    """Handle CI webhook events to update ci_checks table.

    Args:
        event_type: GitHub event type.
        payload: Webhook payload.
        ci_check_dao: CI check DAO.
        pr_dao: PR DAO.
    """
    # Extract SHA from various event types
    sha: str | None = None
    status: str | None = None
    conclusion: str | None = None

    if event_type == "check_run":
        check_run = payload.get("check_run", {})
        sha = check_run.get("head_sha")
        status = check_run.get("status")  # queued, in_progress, completed
        conclusion = check_run.get("conclusion")  # success, failure, etc.
    elif event_type == "check_suite":
        check_suite = payload.get("check_suite", {})
        sha = check_suite.get("head_sha")
        status = check_suite.get("status")
        conclusion = check_suite.get("conclusion")
    elif event_type == "workflow_run":
        workflow_run = payload.get("workflow_run", {})
        sha = workflow_run.get("head_sha")
        status = workflow_run.get("status")
        conclusion = workflow_run.get("conclusion")

    if not sha:
        logger.debug(f"No SHA found in {event_type} webhook")
        return

    # Derive CI status from GitHub status/conclusion
    ci_status: str
    if status == "completed":
        if conclusion == "success":
            ci_status = "success"
        elif conclusion in ("failure", "timed_out", "cancelled"):
            ci_status = "failure"
        else:
            ci_status = "error"
    elif status in ("queued", "in_progress", "pending"):
        ci_status = "pending"
    else:
        ci_status = "pending"

    # Find PR by SHA to get the ci_check record
    # We need to find the PR that has this SHA
    # For now, we'll look for existing ci_checks with this SHA and update them
    from zloth_api.storage.dao import now_iso

    # Update all ci_checks with this SHA
    cursor = await ci_check_dao.db.connection.execute(
        "SELECT id FROM ci_checks WHERE sha = ?",
        (sha,),
    )
    rows = list(await cursor.fetchall())

    if not rows:
        logger.debug(f"No ci_checks found for SHA {sha[:8]}")
        return

    for row in rows:
        check_id = row["id"]
        await ci_check_dao.db.connection.execute(
            """
            UPDATE ci_checks
            SET status = ?, updated_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (ci_status, now_iso(), check_id),
        )

    await ci_check_dao.db.connection.commit()
    logger.info(f"Updated {len(rows)} ci_check(s) for SHA {sha[:8]} with status={ci_status}")
