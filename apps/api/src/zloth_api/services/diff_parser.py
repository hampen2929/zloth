"""Unified diff parsing utilities."""

from __future__ import annotations

from zloth_api.domain.models import FileDiff


def parse_unified_diff(diff: str) -> list[FileDiff]:
    """Parse a unified diff and extract per-file change metadata.

    Args:
        diff: Unified diff string.

    Returns:
        List of FileDiff objects.
    """
    files: list[FileDiff] = []
    current_file: str | None = None
    current_patch_lines: list[str] = []
    added_lines = 0
    removed_lines = 0

    for line in (diff or "").split("\n"):
        if line.startswith("--- a/"):
            # Save previous file if exists
            if current_file:
                files.append(
                    FileDiff(
                        path=current_file,
                        added_lines=added_lines,
                        removed_lines=removed_lines,
                        patch="\n".join(current_patch_lines),
                    )
                )
            # Reset for new file
            current_patch_lines = [line]
            current_file = None
            added_lines = 0
            removed_lines = 0
        elif line.startswith("+++ b/"):
            current_file = line[6:]
            current_patch_lines.append(line)
        elif line.startswith("--- /dev/null"):
            # New file
            current_patch_lines = [line]
            current_file = None
            added_lines = 0
            removed_lines = 0
        elif line.startswith("+++ b/") and current_file is None:
            # New file path
            current_file = line[6:]
            current_patch_lines.append(line)
        elif current_file:
            current_patch_lines.append(line)
            if line.startswith("+") and not line.startswith("+++"):
                added_lines += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed_lines += 1

    # Save last file
    if current_file:
        files.append(
            FileDiff(
                path=current_file,
                added_lines=added_lines,
                removed_lines=removed_lines,
                patch="\n".join(current_patch_lines),
            )
        )

    return files
