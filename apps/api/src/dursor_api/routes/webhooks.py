"""Webhook routes for external service integration."""

import hashlib
import hmac
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from dursor_api.config import settings
from dursor_api.domain.models import (
    CIResult,
    CIWebhookPayload,
    CIWebhookResponse,
    JobFailure,
)
from dursor_api.services.agentic_orchestrator import AgenticOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def verify_signature(body: bytes, signature: str | None) -> bool:
    """Verify HMAC-SHA256 signature from GitHub.

    Args:
        body: Request body bytes.
        signature: X-Hub-Signature-256 header value.

    Returns:
        True if signature is valid, False otherwise.
    """
    if not signature:
        return False

    if not settings.webhook_secret:
        logger.warning("Webhook secret not configured, skipping verification")
        return True

    secret = settings.webhook_secret.encode()
    expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def fetch_job_logs(workflow_run_id: int, job_name: str) -> str | None:
    """Fetch job logs from GitHub Actions API.

    Args:
        workflow_run_id: Workflow run ID.
        job_name: Job name.

    Returns:
        Job logs or None if not available.
    """
    # TODO: Implement GitHub API call to fetch logs
    # GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs
    # GET /repos/{owner}/{repo}/actions/jobs/{job_id}/logs
    return None


# Placeholder for dependency injection
async def get_orchestrator() -> AgenticOrchestrator:
    """Get the agentic orchestrator.

    This is a placeholder - actual implementation will be in dependencies.py.
    """
    from dursor_api.dependencies import get_agentic_orchestrator

    return await get_agentic_orchestrator()


@router.post("/ci", response_model=CIWebhookResponse)
async def handle_ci_webhook(
    request: Request,
    orchestrator: AgenticOrchestrator = Depends(get_orchestrator),
) -> CIWebhookResponse:
    """Receive CI completion webhook from GitHub Actions.

    Triggers auto-fix if CI failed, proceeds to merge/review if passed.

    Args:
        request: FastAPI request object.
        orchestrator: Agentic orchestrator service.

    Returns:
        CIWebhookResponse with processing status.
    """
    # Verify signature
    signature = request.headers.get("X-Hub-Signature-256")
    body = await request.body()

    if not verify_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    try:
        payload = CIWebhookPayload.model_validate_json(body)
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")

    # Find associated task
    if payload.pr_number is None:
        return CIWebhookResponse(
            status="ignored",
            reason="No PR number in payload",
        )

    task = await orchestrator.find_task_by_pr(payload.pr_number)
    if not task:
        return CIWebhookResponse(
            status="ignored",
            reason="No associated task found",
        )

    # Build CI result
    failed_jobs: list[JobFailure] = []
    for job_name, result in payload.jobs.items():
        if result == "failure":
            # Fetch error logs for failed jobs
            error_log = await fetch_job_logs(payload.workflow_run_id, job_name)
            failed_jobs.append(
                JobFailure(
                    job_name=job_name,
                    result=result,
                    error_log=error_log,
                )
            )

    ci_result = CIResult(
        success=payload.conclusion == "success",
        workflow_run_id=payload.workflow_run_id,
        conclusion=payload.conclusion,
        failed_jobs=failed_jobs,
        jobs=payload.jobs,
    )

    # Get workspace path from task (simplified)
    workspace_path = Path(settings.workspaces_dir or ".") / task.repo_id

    if ci_result.success:
        # All CI passed - proceed to review/merge
        await orchestrator.proceed_to_merge(task, workspace_path)
        return CIWebhookResponse(
            status="proceeding_to_merge",
            action_taken="Proceeding to review and merge",
        )
    else:
        # CI failed - trigger auto-fix
        await orchestrator.trigger_auto_fix(
            task=task,
            failed_jobs=failed_jobs,
            commit_sha=payload.sha,
            workspace_path=workspace_path,
        )
        return CIWebhookResponse(
            status="auto_fix_triggered",
            action_taken=f"Triggered auto-fix for {len(failed_jobs)} failed jobs",
        )


@router.post("/github")
async def handle_github_webhook(request: Request) -> dict[str, str]:
    """Handle general GitHub webhooks.

    This endpoint can handle various GitHub events like:
    - check_run.completed
    - check_suite.completed
    - pull_request.synchronize

    Args:
        request: FastAPI request object.

    Returns:
        Status response.
    """
    # Verify signature
    signature = request.headers.get("X-Hub-Signature-256")
    body = await request.body()

    if not verify_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Get event type
    event = request.headers.get("X-GitHub-Event", "unknown")
    logger.info(f"Received GitHub webhook: {event}")

    # TODO: Handle different event types
    # - check_run.completed: Check if all checks passed
    # - pull_request.synchronize: New commits pushed to PR
    # - workflow_run.completed: Workflow completed

    return {"status": "received", "event": event}
