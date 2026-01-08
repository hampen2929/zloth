"""Commit message utilities.

This module enforces project conventions around commit messages.

Requirements:
- Commit messages MUST be in English.
"""

from __future__ import annotations

import re

from dursor_api.agents.llm_router import LLMConfig, LLMRouter
from dursor_api.domain.enums import Provider

_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f]")


def contains_cjk(text: str) -> bool:
    """Return True if the text contains CJK characters (Japanese/Chinese/Korean ranges)."""
    return bool(_CJK_RE.search(text or ""))


def _truncate_subject(subject: str, limit: int = 72) -> str:
    subject = (subject or "").strip().replace("\n", " ")
    if len(subject) <= limit:
        return subject
    return subject[: max(0, limit - 3)].rstrip() + "..."


def _normalize_commit_message(message: str) -> str:
    """Normalize commit message formatting (subject length, spacing)."""
    message = (message or "").strip()
    if not message:
        return "Update changes"

    lines = message.splitlines()
    subject = _truncate_subject(lines[0], 72)
    body = "\n".join(lines[1:]).strip()
    if body:
        return f"{subject}\n\n{body}"
    return subject


async def ensure_english_commit_message(
    message: str,
    *,
    llm_router: LLMRouter | None = None,
    hint: str | None = None,
) -> str:
    """Ensure commit message is English; rewrite if needed.

    If the message contains CJK characters, we attempt to rewrite it into an
    idiomatic English git commit message. If rewriting fails, we fall back to
    a safe English message.

    Args:
        message: Proposed commit message.
        llm_router: Optional shared LLMRouter instance.
        hint: Optional extra context to help rewriting.

    Returns:
        English commit message.
    """
    message = _normalize_commit_message(message)
    if not contains_cjk(message):
        return message

    router = llm_router or LLMRouter()
    prompt = "\n".join(
        [
            "Rewrite the following git commit message into idiomatic English.",
            "",
            "## Requirements",
            "- Output ONLY the commit message (no markdown, no quotes, no extra commentary)",
            "- First line (subject) must be <= 72 characters",
            "- Use imperative mood (e.g., 'Add', 'Fix', 'Update')",
            "- Keep it concise and specific",
            "",
            "## Original",
            message,
            "",
            "## Optional context (may be empty)",
            (hint or "").strip(),
        ]
    ).strip()

    try:
        config = LLMConfig(
            provider=Provider.ANTHROPIC,
            model_name="claude-3-haiku-20240307",
            api_key="",  # Loaded from environment
        )
        llm_client = router.get_client(config)
        rewritten = await llm_client.generate(
            prompt=prompt,
            system_prompt=(
                "You rewrite git commit messages into clear, idiomatic English. "
                "Output only the commit message text."
            ),
        )
        rewritten = _normalize_commit_message(rewritten)
        if not contains_cjk(rewritten):
            return rewritten
    except Exception:
        pass

    # Last resort: safe English fallback
    return "Update changes"

