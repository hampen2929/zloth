from __future__ import annotations

import pytest

from zloth_api.domain.enums import JobKind, JobStatus
from zloth_api.storage.dao import JobDAO
from zloth_api.storage.db import Database


@pytest.mark.asyncio
async def test_job_create_and_claim_order(test_db: Database) -> None:
    job_dao = JobDAO(test_db)

    j1 = await job_dao.create(kind=JobKind.RUN_EXECUTE, ref_id="run-1", payload={"a": 1})
    j2 = await job_dao.create(kind=JobKind.RUN_EXECUTE, ref_id="run-2", payload={"a": 2})

    claimed1 = await job_dao.claim_next(locked_by="worker-test")
    assert claimed1 is not None
    assert claimed1.id == j1.id
    assert claimed1.status == JobStatus.RUNNING

    claimed2 = await job_dao.claim_next(locked_by="worker-test")
    assert claimed2 is not None
    assert claimed2.id == j2.id
    assert claimed2.status == JobStatus.RUNNING

    claimed3 = await job_dao.claim_next(locked_by="worker-test")
    assert claimed3 is None


@pytest.mark.asyncio
async def test_cancel_queued_by_ref(test_db: Database) -> None:
    job_dao = JobDAO(test_db)

    j = await job_dao.create(kind=JobKind.REVIEW_EXECUTE, ref_id="review-1", payload={})
    assert j.status == JobStatus.QUEUED

    cancelled = await job_dao.cancel_queued_by_ref(kind=JobKind.REVIEW_EXECUTE, ref_id="review-1")
    assert cancelled is True

    updated = await job_dao.get(j.id)
    assert updated is not None
    assert updated.status == JobStatus.CANCELED
