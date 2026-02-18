"""Tests for PRService fallback description generation with templates."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from zloth_api.domain.enums import ExecutorType
from zloth_api.domain.models import PR, Run
from zloth_api.services.pr_service import PRService


@pytest.fixture()
def pr_service() -> PRService:
    """Create a PRService with mocked dependencies."""
    return PRService(
        pr_dao=AsyncMock(),
        task_dao=AsyncMock(),
        run_dao=AsyncMock(),
        repo_service=AsyncMock(),
        github_service=AsyncMock(),
        git_service=MagicMock(),
    )


SAMPLE_DIFF = """\
diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -1,3 +1,4 @@
+import os
 def main():
-    pass
+    print(os.getcwd())
"""

SAMPLE_TEMPLATE = """\
## What

<!-- Describe what this PR does -->

## Why

<!-- Describe why this change is needed -->

## Test Plan

- [ ] Tests pass
"""

SAMPLE_TEMPLATE_NO_COMMENTS = """\
## What

## Why

## Test Plan

- [ ] Tests pass
"""


class TestFillTemplateFallback:
    """Tests for _fill_template_fallback."""

    def test_replaces_first_html_comment(self, pr_service: PRService) -> None:
        result = pr_service._fill_template_fallback(
            template=SAMPLE_TEMPLATE,
            summary="Add os import",
            diff=SAMPLE_DIFF,
        )
        # Template structure is preserved
        assert "## What" in result
        assert "## Why" in result
        assert "## Test Plan" in result
        # First HTML comment replaced with content
        assert "Add os import" in result
        assert "src/main.py" in result
        # At least one HTML comment remains (not all replaced)
        assert "<!--" in result

    def test_appends_when_no_html_comments(self, pr_service: PRService) -> None:
        result = pr_service._fill_template_fallback(
            template=SAMPLE_TEMPLATE_NO_COMMENTS,
            summary="Add os import",
            diff=SAMPLE_DIFF,
        )
        # Template structure is preserved
        assert "## What" in result
        assert "## Why" in result
        assert "## Test Plan" in result
        # Content appended at the end
        assert "Add os import" in result
        assert "src/main.py" in result


class TestFallbackDescriptionWithTemplate:
    """Tests that fallback methods use template when available."""

    def test_fallback_description_uses_template(self, pr_service: PRService) -> None:
        pr = MagicMock(spec=PR)
        pr.title = "Fix bug"

        result = pr_service._generate_fallback_description(
            diff=SAMPLE_DIFF,
            pr=pr,
            template=SAMPLE_TEMPLATE,
        )
        # Should use template structure, not zloth default
        assert "## What" in result
        assert "Fix bug" in result

    def test_fallback_description_without_template(self, pr_service: PRService) -> None:
        pr = MagicMock(spec=PR)
        pr.title = "Fix bug"

        result = pr_service._generate_fallback_description(
            diff=SAMPLE_DIFF,
            pr=pr,
            template=None,
        )
        # Should use zloth default format
        assert "## Summary" in result
        assert "Fix bug" in result

    def test_fallback_new_pr_uses_template(self, pr_service: PRService) -> None:
        run = MagicMock(spec=Run)
        run.summary = "Add new feature"
        run.executor_type = ExecutorType.CLAUDE_CODE

        result = pr_service._generate_fallback_description_for_new_pr(
            diff=SAMPLE_DIFF,
            title="Add feature",
            run=run,
            template=SAMPLE_TEMPLATE,
        )
        # Should use template structure
        assert "## What" in result
        assert "Add new feature" in result

    def test_fallback_new_pr_without_template(self, pr_service: PRService) -> None:
        run = MagicMock(spec=Run)
        run.summary = "Add new feature"
        run.executor_type = ExecutorType.CLAUDE_CODE

        result = pr_service._generate_fallback_description_for_new_pr(
            diff=SAMPLE_DIFF,
            title="Add feature",
            run=run,
            template=None,
        )
        # Should use zloth default format
        assert "## Summary" in result
