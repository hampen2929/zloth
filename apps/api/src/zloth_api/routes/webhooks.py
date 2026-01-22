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


@router.post("/github")
async def handle_github_webhook(
    request: Request,
) -> dict[str, str]:
    """Receive general GitHub webhook events.

    Currently handles:
    - check_suite events for CI status
    - pull_request events for PR status

    Args:
        request: FastAPI request.

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

    # Parse and handle based on event type
    # For now, just acknowledge
    # More specific handling can be added as needed

    return {"status": "received", "event": event_type}
