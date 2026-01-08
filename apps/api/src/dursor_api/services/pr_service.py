"""Pull Request management service.

This service manages PR creation and updates following the orchestrator
management pattern. PRs are created from branches that have already been
pushed by RunService, so this service only handles GitHub API operations.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from dursor_api.agents.llm_router import LLMConfig, LLMRouter
from dursor_api.domain.enums import Provider
from dursor_api.domain.models import PR, PRCreate, PRCreateAuto, PRUpdate, Repo
from dursor_api.services.commit_message import ensure_english_commit_message
from dursor_api.services.git_service import GitService
from dursor_api.services.repo_service import RepoService
from dursor_api.storage.dao import PRDAO, RunDAO, TaskDAO

if TYPE_CHECKING:
    from dursor_api.services.github_service import GitHubService

logger = logging.getLogger(__name__)


class GitHubPermissionError(Exception):
    """Raised when GitHub App lacks required permissions."""

    pass


class PRService:
    """Service for managing Pull Requests.

    Following the orchestrator management pattern, this service:
    - Creates PRs from pre-pushed branches (no commit/push operations)
    - Updates PR descriptions via GitHub API
    - Generates descriptions from diffs using LLM
    """

    def __init__(
        self,
        pr_dao: PRDAO,
        task_dao: TaskDAO,
        run_dao: RunDAO,
        repo_service: RepoService,
        github_service: GitHubService,
        git_service: GitService | None = None,
        llm_router: LLMRouter | None = None,
    ):
        self.pr_dao = pr_dao
        self.task_dao = task_dao
        self.run_dao = run_dao
        self.repo_service = repo_service
        self.github_service = github_service
        self.git_service = git_service or GitService()
        self.llm_router = llm_router or LLMRouter()

    def _parse_github_url(self, repo_url: str) -> tuple[str, str]:
        """Parse owner and repo from GitHub URL.

        Args:
            repo_url: GitHub repository URL.

        Returns:
            Tuple of (owner, repo_name).
        """
        # Handle different URL formats
        if repo_url.startswith("git@github.com:"):
            path = repo_url.replace("git@github.com:", "").replace(".git", "")
        else:
            parsed = urlparse(repo_url)
            path = parsed.path.strip("/").replace(".git", "")

        parts = path.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid GitHub URL: {repo_url}")

        return parts[0], parts[1]

    async def create(self, task_id: str, data: PRCreate) -> PR:
        """Create a Pull Request from an already-pushed branch.

        Following the orchestrator pattern, this method expects the branch
        to already be pushed by RunService. It only creates the PR via
        GitHub API.

        Args:
            task_id: Task ID.
            data: PR creation data.

        Returns:
            Created PR object.
        """
        # Get task and repo
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        repo_obj = await self.repo_service.get(task.repo_id)
        if not repo_obj:
            raise ValueError(f"Repo not found: {task.repo_id}")

        # Get run
        run = await self.run_dao.get(data.selected_run_id)
        if not run:
            raise ValueError(f"Run not found: {data.selected_run_id}")

        # Verify run has a branch and commit
        if not run.working_branch:
            raise ValueError(f"Run has no working branch: {data.selected_run_id}")
        if not run.commit_sha:
            raise ValueError(f"Run has no commits: {data.selected_run_id}")

        # Parse GitHub info
        owner, repo_name = self._parse_github_url(repo_obj.repo_url)

        # If branch hasn't been pushed yet, push it now
        if run.worktree_path:
            try:
                auth_url = await self.github_service.get_auth_url(owner, repo_name)
                await self.git_service.push(
                    Path(run.worktree_path),
                    branch=run.working_branch,
                    auth_url=auth_url,
                )
            except Exception as e:
                if "403" in str(e) or "Write access" in str(e):
                    raise GitHubPermissionError(
                        f"GitHub App lacks write access to {owner}/{repo_name}. "
                        "Please ensure the GitHub App has 'Contents' permission "
                        "set to 'Read and write' and is installed on this repository."
                    ) from e
                raise

        # Diagnostics: confirm PR branch is based on latest default (origin/<default>)
        await self._log_pr_branch_base_state(repo_obj, run)

        # Create PR body (apply pull_request_template if available)
        template = await self._load_pr_template(repo_obj)
        description_src = (data.body or run.summary or "").strip()
        if template:
            pr_body = self._render_pr_body_from_template(
                template=template,
                title=data.title,
                description=description_src,
            )
        else:
            pr_body = data.body or f"Generated by dursor\n\n{run.summary or ''}"

        pr_data = await self.github_service.create_pull_request(
            owner=owner,
            repo=repo_name,
            title=data.title,
            head=run.working_branch,
            base=repo_obj.default_branch,
            body=pr_body,
        )

        # Save to database
        return await self.pr_dao.create(
            task_id=task_id,
            number=pr_data["number"],
            url=pr_data["html_url"],
            branch=run.working_branch,
            title=data.title,
            body=pr_body,
            latest_commit=run.commit_sha,
        )

    async def create_auto(self, task_id: str, data: PRCreateAuto) -> PR:
        """Create a Pull Request with AI-generated title and description.

        This method automatically generates the PR title and description
        using LLM based on the diff and task context.

        Args:
            task_id: Task ID.
            data: PR auto-creation data (only run_id needed).

        Returns:
            Created PR object.
        """
        # Get task and repo
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        repo_obj = await self.repo_service.get(task.repo_id)
        if not repo_obj:
            raise ValueError(f"Repo not found: {task.repo_id}")

        # Get run
        run = await self.run_dao.get(data.selected_run_id)
        if not run:
            raise ValueError(f"Run not found: {data.selected_run_id}")

        # Verify run has a branch and commit
        if not run.working_branch:
            raise ValueError(f"Run has no working branch: {data.selected_run_id}")
        if not run.commit_sha:
            raise ValueError(f"Run has no commits: {data.selected_run_id}")

        # Parse GitHub info
        owner, repo_name = self._parse_github_url(repo_obj.repo_url)

        # If branch hasn't been pushed yet, push it now
        if run.worktree_path:
            try:
                auth_url = await self.github_service.get_auth_url(owner, repo_name)
                await self.git_service.push(
                    Path(run.worktree_path),
                    branch=run.working_branch,
                    auth_url=auth_url,
                )
            except Exception as e:
                if "403" in str(e) or "Write access" in str(e):
                    raise GitHubPermissionError(
                        f"GitHub App lacks write access to {owner}/{repo_name}. "
                        "Please ensure the GitHub App has 'Contents' permission "
                        "set to 'Read and write' and is installed on this repository."
                    ) from e
                raise

        # Diagnostics: confirm PR branch is based on latest default (origin/<default>)
        await self._log_pr_branch_base_state(repo_obj, run)

        # Get diff for AI generation
        diff = ""
        if run.worktree_path:
            worktree_path = Path(run.worktree_path)
            if worktree_path.exists():
                diff = await self.git_service.get_diff_from_base(
                    worktree_path,
                    base_ref=run.base_ref or repo_obj.default_branch,
                )
        if not diff and run.patch:
            diff = run.patch

        # Generate title and description with AI
        title = await self._generate_title(diff, task, run)
        template = await self._load_pr_template(repo_obj)
        description = await self._generate_description_for_new_pr(
            diff=diff,
            template=template,
            task=task,
            title=title,
            run=run,
        )

        # Create PR via GitHub API
        pr_data = await self.github_service.create_pull_request(
            owner=owner,
            repo=repo_name,
            title=title,
            head=run.working_branch,
            base=repo_obj.default_branch,
            body=description,
        )

        # Save to database
        return await self.pr_dao.create(
            task_id=task_id,
            number=pr_data["number"],
            url=pr_data["html_url"],
            branch=run.working_branch,
            title=title,
            body=description,
            latest_commit=run.commit_sha,
        )

    async def _generate_title(self, diff: str, task, run) -> str:
        """Generate PR title using LLM.

        Args:
            diff: Unified diff string.
            task: Task object.
            run: Run object.

        Returns:
            Generated title string.
        """
        # Truncate diff if too long
        truncated_diff = diff[:5000] if len(diff) > 5000 else diff

        prompt = f"""Generate a concise Pull Request title based on the following information.

## Task Description
{task.title or "(None)"}

## Run Summary
{run.summary or "(None)"}

## Diff (truncated)
```diff
{truncated_diff}
```

## Rules
- Output ONLY the title, no quotes or extra text
- Keep it under 72 characters
- Use imperative mood (e.g., "Add feature X" not "Added feature X")
- Be specific but concise
"""

        try:
            config = LLMConfig(
                provider=Provider.ANTHROPIC,
                model_name="claude-3-haiku-20240307",
                api_key="",  # Will be loaded from environment
            )
            llm_client = self.llm_router.get_client(config)
            response = await llm_client.generate(
                prompt=prompt,
                system_prompt=(
                    "You are a helpful assistant that generates clear and concise "
                    "PR titles. Output only the title text."
                ),
            )
            # Clean up the response - remove quotes and extra whitespace
            title = response.strip().strip('"\'')
            # Ensure title is not too long
            if len(title) > 72:
                title = title[:69] + "..."
            return title
        except Exception:
            # Fallback to a simple title
            if run.summary:
                summary_title = run.summary.split("\n")[0][:69]
                return summary_title if len(summary_title) <= 72 else summary_title[:69] + "..."
            return "Update code changes"

    async def _generate_description_for_new_pr(
        self,
        diff: str,
        template: str | None,
        task,
        title: str,
        run,
    ) -> str:
        """Generate PR description for new PR using LLM.

        Similar to _generate_description but takes title as input
        instead of PR object.

        Args:
            diff: Unified diff string.
            template: Optional PR template.
            task: Task object.
            title: Generated PR title.
            run: Run object.

        Returns:
            Generated description string.
        """
        prompt = self._build_description_prompt_for_new_pr(diff, template, task, title, run)

        try:
            config = LLMConfig(
                provider=Provider.ANTHROPIC,
                model_name="claude-3-haiku-20240307",
                api_key="",  # Will be loaded from environment
            )
            llm_client = self.llm_router.get_client(config)
            response = await llm_client.generate(
                prompt=prompt,
                system_prompt=(
                    "You are a helpful assistant that generates clear "
                    "and concise PR descriptions. Follow the provided template exactly."
                ),
            )
            return response
        except Exception:
            # Fallback to a simple description
            return self._generate_fallback_description_for_new_pr(diff, title, run, template)

    def _build_description_prompt_for_new_pr(
        self,
        diff: str,
        template: str | None,
        task,
        title: str,
        run,
    ) -> str:
        """Build prompt for description generation for new PR.

        Args:
            diff: Unified diff string.
            template: Optional PR template.
            task: Task object.
            title: Generated PR title.
            run: Run object.

        Returns:
            Prompt string.
        """
        # Truncate diff if too long
        truncated_diff = diff[:10000] if len(diff) > 10000 else diff

        prompt_parts = [
            "Generate a Pull Request Description based on the following information.",
            "",
            "## Task Description",
            task.title or "(None)",
            "",
            "## Run Summary",
            run.summary or "(None)",
            "",
            "## PR Title",
            title,
            "",
            "## Diff",
            "```diff",
            truncated_diff,
            "```",
        ]

        if template:
            prompt_parts.extend([
                "",
                "## Template (MUST FOLLOW EXACTLY)",
                "You MUST create the Description following this exact template structure.",
                "- Keep ALL section headings from the template.",
                "- Fill in each section with appropriate content based on the diff and context.",
                "- Do NOT add sections that are not in the template.",
                "- Do NOT remove or rename any sections from the template.",
                "- Replace HTML comments (<!-- ... -->) with actual content.",
                "",
                "Template:",
                "```markdown",
                template,
                "```",
            ])
        else:
            prompt_parts.extend([
                "",
                "## Output Format",
                "Create the Description in the following format:",
                "",
                "## Summary",
                "(Overview of changes in 1-3 sentences)",
                "",
                "## Changes",
                "(Main changes as bullet points)",
                "",
                "## Test Plan",
                "(Testing methods and verification items)",
            ])

        return "\n".join(prompt_parts)

    def _generate_fallback_description_for_new_pr(
        self, diff: str, title: str, run, template: str | None = None
    ) -> str:
        """Generate a simple fallback description for new PR.

        If a template is provided, fills in the template sections.
        Otherwise, uses a default format.

        Args:
            diff: Unified diff string.
            title: PR title.
            run: Run object.
            template: Optional PR template string.

        Returns:
            Simple description string.
        """
        # Count changes
        added_lines = len(re.findall(r"^\+[^+]", diff, re.MULTILINE))
        removed_lines = len(re.findall(r"^-[^-]", diff, re.MULTILINE))
        files = set(re.findall(r"^\+\+\+ b/(.+)$", diff, re.MULTILINE))

        summary = run.summary or title

        # Generate changes as simple bullet points (no sub-sections)
        files_list = [f"- {f}" for f in sorted(files)[:10]]
        if len(files) > 10:
            files_list.append("- ...")
        changes_text = "\n".join(files_list)
        changes_text += f"\n- Total: +{added_lines} -{removed_lines} lines"

        if template:
            return self._fill_template_sections(
                template=template,
                summary=summary,
                changes=changes_text,
            )

        # Default format if no template
        return f"""## Summary
{summary}

## Changes
{changes_text}

## Test Plan
- [ ] Manual testing
- [ ] Unit tests
"""

    def _fill_template_sections(
        self, template: str, summary: str, changes: str
    ) -> str:
        """Fill in template sections with provided content.

        Preserves the exact template structure, only replacing the content
        under each section heading. Does not add any sections not in the template.

        Args:
            template: PR template string.
            summary: Summary text to insert.
            changes: Changes text to insert.

        Returns:
            Filled template string.
        """
        result = template.replace("\r\n", "\n")

        # Remove HTML comments (<!-- ... -->) but keep the structure
        result = re.sub(r"<!--.*?-->", "", result, flags=re.DOTALL)

        # Define section mappings: heading pattern -> content to insert
        section_mappings = [
            (r"(#{1,6}\s+(?:summary|description)\s*\n)", summary),
            (r"(#{1,6}\s+changes\s*\n)", changes),
            # Review Notes, Test Plan, etc. - leave placeholder if no content
            (r"(#{1,6}\s+(?:review\s*notes?|test\s*plan)\s*\n)", "N/A"),
        ]

        for pattern, content in section_mappings:
            result = self._replace_section_content(result, pattern, content)

        # Clean up multiple blank lines and leading/trailing whitespace
        result = re.sub(r"\n{3,}", "\n\n", result)
        result = result.strip()

        return result + "\n" if result else ""

    def _replace_section_content(
        self, template: str, heading_pattern: str, new_content: str
    ) -> str:
        """Replace content under a section heading.

        Finds a heading matching the pattern and replaces everything between
        it and the next heading (or end of file) with the new content.

        Args:
            template: Template string.
            heading_pattern: Regex pattern for the section heading.
            new_content: Content to insert after the heading.

        Returns:
            Modified template string.
        """
        heading_re = re.compile(heading_pattern, re.IGNORECASE | re.MULTILINE)
        match = heading_re.search(template)
        if not match:
            return template

        heading_end = match.end()
        heading_level_match = re.match(r"(#{1,6})", match.group(1))
        if not heading_level_match:
            return template

        level = len(heading_level_match.group(1))

        # Find the next heading with level <= current level
        next_heading_re = re.compile(rf"^#{{1,{level}}}\s+\S", re.MULTILINE)
        next_match = next_heading_re.search(template, pos=heading_end)
        section_end = next_match.start() if next_match else len(template)

        # Build the result: before + heading + new content + after
        before = template[: heading_end]
        after = template[section_end:]

        return f"{before}{new_content}\n\n{after}".strip() + "\n"

    async def update(self, task_id: str, pr_id: str, data: PRUpdate) -> PR:
        """Update an existing Pull Request with a new run.

        This method applies the patch from the selected run to the PR branch.
        Note: This method still applies patches for backward compatibility,
        but new runs with CLI executors should already have committed/pushed.

        Args:
            task_id: Task ID.
            pr_id: PR ID.
            data: PR update data.

        Returns:
            Updated PR object.
        """
        # Get PR
        pr = await self.pr_dao.get(pr_id)
        if not pr or pr.task_id != task_id:
            raise ValueError(f"PR not found: {pr_id}")

        # Get task and repo
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        repo_obj = await self.repo_service.get(task.repo_id)
        if not repo_obj:
            raise ValueError(f"Repo not found: {task.repo_id}")

        # Get run
        run = await self.run_dao.get(data.selected_run_id)
        if not run:
            raise ValueError(f"Run not found: {data.selected_run_id}")

        # For CLI executor runs, the commit should already be on the branch
        # The branch should be the same as the PR branch
        if run.commit_sha and run.working_branch == pr.branch:
            # Commit is already on the PR branch, just update the database
            await self.pr_dao.update(pr_id, run.commit_sha)
            return await self.pr_dao.get(pr_id)

        # For PatchAgent runs or different branches, we need to apply the patch
        # This is backward compatibility code
        if not run.patch:
            raise ValueError("Run has no patch to apply")

        # Parse GitHub info
        owner, repo_name = self._parse_github_url(repo_obj.repo_url)

        # Apply patch to PR branch using GitService
        workspace_path = Path(repo_obj.workspace_path)

        # Checkout PR branch, apply patch, commit, and push
        await self.git_service.checkout(workspace_path, pr.branch)

        # Apply patch manually
        import subprocess
        patch_file = workspace_path / ".dursor_patch.diff"
        try:
            patch_file.write_text(run.patch)
            result = subprocess.run(
                ["git", "apply", "--whitespace=fix", str(patch_file)],
                cwd=workspace_path,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                await self.git_service.checkout(workspace_path, repo_obj.default_branch)
                error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                raise ValueError(f"Failed to apply patch: {error_msg}")
        finally:
            patch_file.unlink(missing_ok=True)

        # Stage and commit
        await self.git_service.stage_all(workspace_path)
        commit_message = data.message or f"Update: {run.summary or ''}"
        commit_message = await ensure_english_commit_message(
            commit_message,
            llm_router=self.llm_router,
            hint=run.summary or "",
        )
        commit_sha = await self.git_service.commit(workspace_path, commit_message)

        # Push
        auth_url = await self.github_service.get_auth_url(owner, repo_name)
        try:
            await self.git_service.push(workspace_path, pr.branch, auth_url)
        except Exception as e:
            if "403" in str(e) or "Write access" in str(e):
                raise GitHubPermissionError(
                    f"GitHub App lacks write access to {owner}/{repo_name}. "
                    "Please ensure the GitHub App has 'Contents' permission "
                    "set to 'Read and write' and is installed on this repository."
                ) from e
            raise

        # Switch back to default branch
        await self.git_service.checkout(workspace_path, repo_obj.default_branch)

        # Update database
        await self.pr_dao.update(pr_id, commit_sha)

        return await self.pr_dao.get(pr_id)

    async def regenerate_description(self, task_id: str, pr_id: str) -> PR:
        """Regenerate PR description from current diff.

        This method:
        1. Gets cumulative diff from base branch
        2. Loads pull_request_template if available
        3. Generates description using LLM
        4. Updates PR via GitHub API

        Args:
            task_id: Task ID.
            pr_id: PR ID.

        Returns:
            Updated PR object.
        """
        # Get PR
        pr = await self.pr_dao.get(pr_id)
        if not pr or pr.task_id != task_id:
            raise ValueError(f"PR not found: {pr_id}")

        # Get task and repo
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        repo_obj = await self.repo_service.get(task.repo_id)
        if not repo_obj:
            raise ValueError(f"Repo not found: {task.repo_id}")

        # Parse GitHub info
        owner, repo_name = self._parse_github_url(repo_obj.repo_url)

        # Get cumulative diff from the worktree or repo
        # Find the latest run associated with this PR
        runs = await self.run_dao.list(task_id)
        latest_run = next(
            (r for r in runs if r.working_branch == pr.branch and r.worktree_path),
            None,
        )

        cumulative_diff = ""
        if latest_run and latest_run.worktree_path:
            worktree_path = Path(latest_run.worktree_path)
            if worktree_path.exists():
                cumulative_diff = await self.git_service.get_diff_from_base(
                    worktree_path,
                    base_ref=latest_run.base_ref or repo_obj.default_branch,
                )

        # Fallback to using patch from latest run
        if not cumulative_diff and latest_run and latest_run.patch:
            cumulative_diff = latest_run.patch

        if not cumulative_diff:
            raise ValueError("Could not get diff for PR description generation")

        # Load pull_request_template
        template = await self._load_pr_template(repo_obj)

        # Generate description with LLM
        new_description = await self._generate_description(
            diff=cumulative_diff,
            template=template,
            task=task,
            pr=pr,
        )

        # Update PR via GitHub API
        await self.github_service.update_pull_request(
            owner=owner,
            repo=repo_name,
            pr_number=pr.number,
            body=new_description,
        )

        # Update database
        await self.pr_dao.update_body(pr_id, new_description)

        return await self.pr_dao.get(pr_id)

    async def _load_pr_template(self, repo: Repo) -> str | None:
        """Load repository's pull_request_template.

        Args:
            repo: Repository object.

        Returns:
            Template content or None if not found.
        """
        workspace_path = Path(repo.workspace_path)

        # Template candidate paths (in priority order)
        template_paths = [
            workspace_path / ".github" / "pull_request_template.md",
            workspace_path / ".github" / "PULL_REQUEST_TEMPLATE.md",
            workspace_path / "pull_request_template.md",
            workspace_path / "PULL_REQUEST_TEMPLATE.md",
            workspace_path / ".github" / "PULL_REQUEST_TEMPLATE" / "default.md",
        ]

        for path in template_paths:
            if path.exists():
                return path.read_text()

        return None

    async def _log_pr_branch_base_state(self, repo_obj: Repo, run) -> None:
        """Log merge-base diagnostics for PR branches.

        This helps confirm whether the PR branch includes the latest default branch.
        The check uses remote refs: origin/<default> and origin/<working_branch>.
        """
        try:
            if not repo_obj.default_branch or not run.working_branch:
                return

            repo_path = Path(repo_obj.workspace_path)
            base_ref = f"origin/{repo_obj.default_branch}"
            head_ref = f"origin/{run.working_branch}"

            base_sha = await self.git_service.get_ref_sha(repo_path, base_ref)
            head_sha = await self.git_service.get_ref_sha(repo_path, head_ref)
            merge_base = await self.git_service.get_merge_base(repo_path, base_ref, head_ref)
            base_is_ancestor = await self.git_service.is_ancestor(
                repo_path=repo_path,
                ancestor=base_ref,
                descendant=head_ref,
            )

            logger.info(
                "PR base diagnostics: "
                f"base_ref={base_ref} base_sha={base_sha} "
                f"head_ref={head_ref} head_sha={head_sha} "
                f"merge_base={merge_base} base_is_ancestor={base_is_ancestor}"
            )
        except Exception as e:
            logger.warning(f"PR base diagnostics failed: {e}")

    def _render_pr_body_from_template(self, template: str, title: str, description: str) -> str:
        """Render PR body using pull_request_template.

        Strategy:
        - If the template has a 'Summary' (or 'Description') heading, replace the section body
          with the provided description.
        - Otherwise, prepend a Summary section and include the template below it.
        """
        tmpl = (template or "").replace("\r\n", "\n").strip()
        desc = (description or "").strip()

        if not tmpl:
            return desc

        if not desc:
            # No description to inject; keep the template as-is.
            return tmpl

        # Find an injection target heading.
        # Matches e.g. "## Summary" / "# Summary" (case-insensitive).
        heading_re = re.compile(
            r"^(#{1,6})\s+(summary|description)\s*$",
            re.IGNORECASE | re.MULTILINE,
        )
        m = heading_re.search(tmpl)
        if not m:
            # No obvious section; prepend a Summary and keep the template.
            return f"## Summary\n{desc}\n\n{tmpl}"

        level = len(m.group(1))
        start = m.end()

        # Find the next heading with level <= current to determine section end.
        next_heading_re = re.compile(rf"^#{{1,{level}}}\s+\S.*$", re.MULTILINE)
        m2 = next_heading_re.search(tmpl, pos=start)
        end = m2.start() if m2 else len(tmpl)

        before = tmpl[:start].rstrip()
        after = tmpl[end:].lstrip()
        injected = f"{before}\n\n{desc}\n\n{after}".strip()
        return injected

    async def _generate_description(
        self,
        diff: str,
        template: str | None,
        task,
        pr: PR,
    ) -> str:
        """Generate PR description using LLM.

        Args:
            diff: Unified diff string.
            template: Optional PR template.
            task: Task object.
            pr: PR object.

        Returns:
            Generated description string.
        """
        prompt = self._build_description_prompt(diff, template, task, pr)

        # Generate with LLM using a default model
        # In production, this could be configurable
        try:
            config = LLMConfig(
                provider=Provider.ANTHROPIC,
                model_name="claude-3-haiku-20240307",
                api_key="",  # Will be loaded from environment
            )
            llm_client = self.llm_router.get_client(config)
            response = await llm_client.generate(
                prompt=prompt,
                system_prompt=(
                    "You are a helpful assistant that generates clear "
                    "and concise PR descriptions. Follow the provided template exactly."
                ),
            )
            return response
        except Exception:
            # Fallback to a simple description if LLM fails
            return self._generate_fallback_description(diff, pr, template)

    def _build_description_prompt(
        self,
        diff: str,
        template: str | None,
        task,
        pr: PR,
    ) -> str:
        """Build prompt for description generation.

        Args:
            diff: Unified diff string.
            template: Optional PR template.
            task: Task object.
            pr: PR object.

        Returns:
            Prompt string.
        """
        # Truncate diff if too long
        truncated_diff = diff[:10000] if len(diff) > 10000 else diff

        prompt_parts = [
            "Generate a Pull Request Description based on the following information.",
            "",
            "## Task Description",
            task.title or "(None)",
            "",
            "## PR Title",
            pr.title,
            "",
            "## Diff",
            "```diff",
            truncated_diff,
            "```",
        ]

        if template:
            prompt_parts.extend([
                "",
                "## Template (MUST FOLLOW EXACTLY)",
                "You MUST create the Description following this exact template structure.",
                "- Keep ALL section headings from the template.",
                "- Fill in each section with appropriate content based on the diff and context.",
                "- Do NOT add sections that are not in the template.",
                "- Do NOT remove or rename any sections from the template.",
                "- Replace HTML comments (<!-- ... -->) with actual content.",
                "",
                "Template:",
                "```markdown",
                template,
                "```",
            ])
        else:
            prompt_parts.extend([
                "",
                "## Output Format",
                "Create the Description in the following format:",
                "",
                "## Summary",
                "(Overview of changes in 1-3 sentences)",
                "",
                "## Changes",
                "(Main changes as bullet points)",
                "",
                "## Test Plan",
                "(Testing methods and verification items)",
            ])

        return "\n".join(prompt_parts)

    def _generate_fallback_description(
        self, diff: str, pr: PR, template: str | None = None
    ) -> str:
        """Generate a simple fallback description.

        If a template is provided, fills in the template sections.
        Otherwise, uses a default format.

        Args:
            diff: Unified diff string.
            pr: PR object.
            template: Optional PR template string.

        Returns:
            Simple description string.
        """
        # Count changes
        added_lines = len(re.findall(r"^\+[^+]", diff, re.MULTILINE))
        removed_lines = len(re.findall(r"^-[^-]", diff, re.MULTILINE))
        files = set(re.findall(r"^\+\+\+ b/(.+)$", diff, re.MULTILINE))

        # Generate changes as simple bullet points (no sub-sections)
        files_list = [f"- {f}" for f in sorted(files)[:10]]
        if len(files) > 10:
            files_list.append("- ...")
        changes_text = "\n".join(files_list)
        changes_text += f"\n- Total: +{added_lines} -{removed_lines} lines"

        if template:
            return self._fill_template_sections(
                template=template,
                summary=pr.title,
                changes=changes_text,
            )

        # Default format if no template
        return f"""## Summary
{pr.title}

## Changes
{changes_text}

## Test Plan
- [ ] Manual testing
- [ ] Unit tests
"""

    async def get(self, task_id: str, pr_id: str) -> PR | None:
        """Get a PR by ID.

        Args:
            task_id: Task ID.
            pr_id: PR ID.

        Returns:
            PR object or None if not found.
        """
        pr = await self.pr_dao.get(pr_id)
        if pr and pr.task_id == task_id:
            return pr
        return None

    async def list(self, task_id: str) -> list[PR]:
        """List PRs for a task.

        Args:
            task_id: Task ID.

        Returns:
            List of PR objects.
        """
        return await self.pr_dao.list(task_id)
