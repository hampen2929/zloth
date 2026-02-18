"""Tests for PR description fallback template handling.

Ensures that fallback descriptions use the repository's pull_request_template
when one is available, rather than always using zloth's built-in template.
"""

from __future__ import annotations

from datetime import UTC, datetime

from zloth_api.domain.enums import ExecutorType, RunStatus
from zloth_api.domain.models import PR, Run
from zloth_api.services.pr_service import PRService

SAMPLE_DIFF = """\
diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,4 @@
 import os
+import sys

 def main():
-    pass
+    print("hello")
"""

REPO_TEMPLATE = """\
## What

<!-- Describe what this PR does -->

## Why

<!-- Explain the motivation -->

## How to test

- [ ] Step 1
- [ ] Step 2
"""


def _make_run(*, summary: str = "Fix the thing") -> Run:
    now = datetime.now(tz=UTC)
    return Run(
        id="run-1",
        task_id="task-1",
        model_id="m-1",
        model_name="test",
        provider=None,
        executor_type=ExecutorType.CLAUDE_CODE,
        instruction="fix it",
        base_ref="main",
        status=RunStatus.SUCCEEDED,
        summary=summary,
        created_at=now,
    )


def _make_pr(*, title: str = "Fix the thing") -> PR:
    now = datetime.now(tz=UTC)
    return PR(
        id="pr-1",
        task_id="task-1",
        number=42,
        url="https://github.com/org/repo/pull/42",
        branch="fix-branch",
        title=title,
        body=None,
        latest_commit="abc123",
        status="open",
        created_at=now,
        updated_at=now,
    )


def _make_service() -> PRService:
    """Create a minimal PRService for unit-testing helper methods."""
    # PRService.__init__ requires several DAO/service dependencies, but
    # the helper methods under test only use `self`, so we bypass __init__.
    svc = object.__new__(PRService)
    return svc


class TestBuildChangesInfo:
    def test_basic(self) -> None:
        svc = _make_service()
        info = svc._build_changes_info(SAMPLE_DIFF)
        assert "foo.py" in info
        assert "+2" in info
        assert "-1" in info


class TestFillTemplate:
    def test_prepends_context_to_template(self) -> None:
        svc = _make_service()
        result = svc._fill_template(
            REPO_TEMPLATE,
            summary="Fix the thing",
            changes_info="- foo.py\n- Total: +2 -1 lines",
        )
        # Template headings are preserved
        assert "## What" in result
        assert "## Why" in result
        assert "## How to test" in result
        # Context is prepended
        assert result.index("Fix the thing") < result.index("## What")


class TestFallbackDescriptionForNewPR:
    def test_without_template_uses_zloth_format(self) -> None:
        svc = _make_service()
        run = _make_run()
        result = svc._generate_fallback_description_for_new_pr(
            SAMPLE_DIFF, "Fix the thing", run, template=None
        )
        assert "## Summary" in result
        assert "## Changes" in result
        assert "## Test Plan" in result

    def test_with_template_uses_repo_template(self) -> None:
        svc = _make_service()
        run = _make_run()
        result = svc._generate_fallback_description_for_new_pr(
            SAMPLE_DIFF, "Fix the thing", run, template=REPO_TEMPLATE
        )
        # Repo template headings must be present
        assert "## What" in result
        assert "## Why" in result
        assert "## How to test" in result
        # zloth's hardcoded headings must NOT appear
        assert "## Summary" not in result
        assert "## Test Plan" not in result
        # Context info is included
        assert "Fix the thing" in result
        assert "foo.py" in result


class TestFallbackDescription:
    def test_without_template_uses_zloth_format(self) -> None:
        svc = _make_service()
        pr = _make_pr()
        result = svc._generate_fallback_description(SAMPLE_DIFF, pr, template=None)
        assert "## Summary" in result
        assert "## Changes" in result
        assert "## Test Plan" in result

    def test_with_template_uses_repo_template(self) -> None:
        svc = _make_service()
        pr = _make_pr()
        result = svc._generate_fallback_description(SAMPLE_DIFF, pr, template=REPO_TEMPLATE)
        # Repo template headings must be present
        assert "## What" in result
        assert "## Why" in result
        assert "## How to test" in result
        # zloth's hardcoded headings must NOT appear
        assert "## Summary" not in result
        assert "## Test Plan" not in result
        # Context info is included
        assert "Fix the thing" in result
        assert "foo.py" in result
