"""Patch Agent - generates unified diff patches from instructions."""

import fnmatch
import os
from pathlib import Path

from dursor_api.agents.base import BaseAgent
from dursor_api.agents.llm_router import LLMClient
from dursor_api.domain.models import AgentRequest, AgentResult, FileDiff


SYSTEM_PROMPT = """You are a code editing assistant that generates unified diff patches.

Your task is to analyze the provided codebase and instruction, then output ONLY \
a unified diff patch that implements the requested changes.

IMPORTANT RULES:
1. Output ONLY the unified diff patch - no explanations, no markdown code blocks, no other text
2. Use the standard unified diff format with --- and +++ headers
3. Each file change should be a separate diff hunk
4. Ensure the patch can be applied cleanly with `git apply` or `patch -p1`
5. Do not modify files in forbidden paths (like .git, .env, etc.)
6. Keep changes minimal and focused on the instruction

Example output format:
--- a/src/file.py
+++ b/src/file.py
@@ -10,3 +10,4 @@
 def existing_function():
     pass
+
+def new_function():
+    return True

If creating a new file:
--- /dev/null
+++ b/new_file.py
@@ -0,0 +1,5 @@
+# New file
+def hello():
+    print("Hello, world!")

If deleting a file:
--- a/old_file.py
+++ /dev/null
@@ -1,3 +0,0 @@
-# File to delete
-def old():
-    pass
"""


class PatchAgent(BaseAgent):
    """Agent that generates unified diff patches."""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    async def run(self, request: AgentRequest) -> AgentResult:
        """Execute the agent to generate a patch.

        Args:
            request: The agent request.

        Returns:
            AgentResult with the generated patch.
        """
        logs: list[str] = []
        warnings: list[str] = []

        # Validate request
        validation_errors = self.validate_request(request)
        if validation_errors:
            return AgentResult(
                summary="Validation failed",
                patch="",
                files_changed=[],
                logs=validation_errors,
                warnings=["Request validation failed"],
            )

        logs.append(f"Starting patch generation for: {request.instruction[:100]}...")

        # Read relevant files from workspace
        workspace_path = Path(request.workspace_path)
        if not workspace_path.exists():
            return AgentResult(
                summary="Workspace not found",
                patch="",
                files_changed=[],
                logs=[f"Workspace path does not exist: {workspace_path}"],
                warnings=["Workspace not found"],
            )

        # Gather file contents (limited to reasonable size)
        file_contents = await self._gather_files(
            workspace_path,
            request.constraints.forbidden_paths,
            logs,
        )
        logs.append(f"Read {len(file_contents)} files from workspace")

        # Build prompt with file context
        user_prompt = self._build_prompt(request.instruction, file_contents)

        # Generate patch from LLM
        logs.append("Calling LLM to generate patch...")
        try:
            raw_response = await self.llm_client.generate(
                messages=[{"role": "user", "content": user_prompt}],
                system=SYSTEM_PROMPT,
            )
        except Exception as e:
            return AgentResult(
                summary=f"LLM error: {str(e)}",
                patch="",
                files_changed=[],
                logs=logs + [f"LLM error: {str(e)}"],
                warnings=["LLM generation failed"],
            )

        # Extract and validate patch
        patch = self._extract_patch(raw_response)
        logs.append(f"Generated patch with {len(patch)} characters")

        # Parse patch to get file changes
        files_changed = self._parse_patch(patch)
        logs.append(f"Patch affects {len(files_changed)} files")

        # Check for forbidden path modifications
        for file_diff in files_changed:
            if self._is_forbidden(file_diff.path, request.constraints.forbidden_paths):
                warnings.append(f"Patch modifies forbidden path: {file_diff.path}")

        # Generate summary
        summary = await self._generate_summary(request.instruction, files_changed)

        return AgentResult(
            summary=summary,
            patch=patch,
            files_changed=files_changed,
            logs=logs,
            warnings=warnings,
        )

    async def _gather_files(
        self,
        workspace_path: Path,
        forbidden_paths: list[str],
        logs: list[str],
    ) -> dict[str, str]:
        """Gather file contents from workspace.

        Args:
            workspace_path: Path to the workspace.
            forbidden_paths: Patterns of paths to skip.
            logs: Log list to append to.

        Returns:
            Dict of file path to content.
        """
        file_contents: dict[str, str] = {}
        max_files = 100
        max_file_size = 100_000  # 100KB per file
        total_size = 0
        max_total_size = 1_000_000  # 1MB total

        # Common code file extensions
        code_extensions = {
            ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".rb",
            ".php", ".c", ".cpp", ".h", ".hpp", ".cs", ".swift", ".kt", ".scala",
            ".vue", ".svelte", ".html", ".css", ".scss", ".sass", ".less",
            ".json", ".yaml", ".yml", ".toml", ".xml", ".md", ".txt",
            ".sh", ".bash", ".zsh", ".fish", ".sql", ".graphql",
        }

        for root, dirs, files in os.walk(workspace_path):
            # Skip hidden directories and common non-code directories
            excluded_dirs = {
                "node_modules", "venv", ".venv", "__pycache__", "dist", "build", "target"
            }
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".")
                and d not in excluded_dirs
            ]

            for file in files:
                if len(file_contents) >= max_files:
                    logs.append(f"Reached max files limit ({max_files})")
                    break

                if total_size >= max_total_size:
                    logs.append(f"Reached total size limit ({max_total_size} bytes)")
                    break

                file_path = Path(root) / file
                rel_path = str(file_path.relative_to(workspace_path))

                # Skip forbidden paths
                if self._is_forbidden(rel_path, forbidden_paths):
                    continue

                # Skip non-code files
                if file_path.suffix.lower() not in code_extensions:
                    continue

                try:
                    stat = file_path.stat()
                    if stat.st_size > max_file_size:
                        logs.append(f"Skipping large file: {rel_path} ({stat.st_size} bytes)")
                        continue

                    content = file_path.read_text(errors="ignore")
                    file_contents[rel_path] = content
                    total_size += len(content)
                except Exception as e:
                    logs.append(f"Error reading {rel_path}: {e}")

        return file_contents

    def _is_forbidden(self, path: str, forbidden_paths: list[str]) -> bool:
        """Check if a path matches any forbidden pattern.

        Args:
            path: Path to check.
            forbidden_paths: List of glob patterns.

        Returns:
            True if path is forbidden.
        """
        for pattern in forbidden_paths:
            if fnmatch.fnmatch(path, pattern):
                return True
            # Also check if any path component matches
            parts = Path(path).parts
            for part in parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
        return False

    def _build_prompt(self, instruction: str, file_contents: dict[str, str]) -> str:
        """Build the user prompt with file context.

        Args:
            instruction: The user's instruction.
            file_contents: Dict of file paths to contents.

        Returns:
            Formatted prompt string.
        """
        parts = [
            "## Instruction",
            instruction,
            "",
            "## Current Codebase",
            "",
        ]

        for path, content in file_contents.items():
            parts.append(f"### {path}")
            parts.append("```")
            parts.append(content)
            parts.append("```")
            parts.append("")

        parts.append("## Task")
        parts.append("Generate a unified diff patch to implement the instruction above.")
        parts.append("Output ONLY the patch, no other text.")

        return "\n".join(parts)

    def _extract_patch(self, response: str) -> str:
        """Extract unified diff patch from LLM response.

        Args:
            response: Raw LLM response.

        Returns:
            Extracted patch string.
        """
        # Remove markdown code blocks if present
        response = response.strip()

        if response.startswith("```diff"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]

        if response.endswith("```"):
            response = response[:-3]

        return response.strip()

    def _parse_patch(self, patch: str) -> list[FileDiff]:
        """Parse unified diff patch to extract file changes.

        Args:
            patch: Unified diff patch string.

        Returns:
            List of FileDiff objects.
        """
        files: list[FileDiff] = []
        current_file: str | None = None
        current_patch_lines: list[str] = []
        added = 0
        removed = 0

        for line in patch.split("\n"):
            if line.startswith("--- "):
                # Save previous file
                if current_file:
                    files.append(FileDiff(
                        path=current_file,
                        added_lines=added,
                        removed_lines=removed,
                        patch="\n".join(current_patch_lines),
                    ))

                # Start new file
                current_patch_lines = [line]
                added = 0
                removed = 0

            elif line.startswith("+++ "):
                # Extract file path
                path = line[4:].strip()
                if path.startswith("b/"):
                    path = path[2:]
                elif path == "/dev/null":
                    # File deletion - use previous file path
                    pass
                else:
                    current_file = path

                if current_file is None and path != "/dev/null":
                    current_file = path

                current_patch_lines.append(line)

            elif line.startswith("@@"):
                current_patch_lines.append(line)

            elif line.startswith("+") and not line.startswith("+++"):
                added += 1
                current_patch_lines.append(line)

            elif line.startswith("-") and not line.startswith("---"):
                removed += 1
                current_patch_lines.append(line)

            else:
                current_patch_lines.append(line)

        # Save last file
        if current_file:
            files.append(FileDiff(
                path=current_file,
                added_lines=added,
                removed_lines=removed,
                patch="\n".join(current_patch_lines),
            ))

        return files

    async def _generate_summary(
        self,
        instruction: str,
        files_changed: list[FileDiff],
    ) -> str:
        """Generate a human-readable summary.

        Args:
            instruction: Original instruction.
            files_changed: List of file changes.

        Returns:
            Summary string.
        """
        if not files_changed:
            return "No changes generated"

        file_list = ", ".join(f.path for f in files_changed[:5])
        if len(files_changed) > 5:
            file_list += f" and {len(files_changed) - 5} more"

        total_added = sum(f.added_lines for f in files_changed)
        total_removed = sum(f.removed_lines for f in files_changed)

        return (
            f"Modified {len(files_changed)} file(s): {file_list}. "
            f"(+{total_added}/-{total_removed} lines)"
        )
