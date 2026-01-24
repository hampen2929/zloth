"""GitHub URL parsing utilities."""

from __future__ import annotations

import re
from urllib.parse import urlparse


def parse_github_owner_repo(repo_url: str) -> tuple[str, str]:
    """Parse a GitHub repository URL into (owner, repo).

    Supports common URL formats:
    - https://github.com/owner/repo
    - https://github.com/owner/repo.git
    - git@github.com:owner/repo
    - git@github.com:owner/repo.git

    Args:
        repo_url: GitHub repository URL.

    Returns:
        Tuple of (owner, repo_name).

    Raises:
        ValueError: If the URL cannot be parsed.
    """
    if not repo_url:
        raise ValueError("repo_url is empty")

    url = repo_url.strip()

    # SSH format: git@github.com:owner/repo(.git)
    ssh_match = re.search(r"github\.com:([^/]+)/([^/.]+)(?:\.git)?$", url)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)

    # HTTPS format: https://github.com/owner/repo(.git)
    parsed = urlparse(url)
    if parsed.netloc.endswith("github.com"):
        path = parsed.path.strip("/")
        if path.endswith(".git"):
            path = path[: -len(".git")]
        parts = path.split("/")
        if len(parts) == 2 and parts[0] and parts[1]:
            return parts[0], parts[1]

    raise ValueError(f"Could not parse GitHub URL: {repo_url}")
