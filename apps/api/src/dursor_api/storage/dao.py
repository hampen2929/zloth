"""Data Access Objects for dursor storage."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from dursor_api.domain.enums import ExecutorType, MessageRole, Provider, RunStatus
from dursor_api.domain.models import FileDiff, Message, ModelProfile, PR, Repo, Run, Task
from dursor_api.storage.db import Database


def generate_id() -> str:
    """Generate a unique ID."""
    return str(uuid.uuid4())


def now_iso() -> str:
    """Get current time as ISO string."""
    return datetime.utcnow().isoformat()


class ModelProfileDAO:
    """DAO for ModelProfile."""

    def __init__(self, db: Database):
        self.db = db

    async def create(
        self,
        provider: Provider,
        model_name: str,
        api_key_encrypted: str,
        display_name: str | None = None,
    ) -> ModelProfile:
        """Create a new model profile."""
        id = generate_id()
        created_at = now_iso()

        await self.db.connection.execute(
            """
            INSERT INTO model_profiles (id, provider, model_name, display_name, api_key_encrypted, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (id, provider.value, model_name, display_name, api_key_encrypted, created_at),
        )
        await self.db.connection.commit()

        return ModelProfile(
            id=id,
            provider=provider,
            model_name=model_name,
            display_name=display_name,
            created_at=datetime.fromisoformat(created_at),
        )

    async def get(self, id: str) -> ModelProfile | None:
        """Get a model profile by ID."""
        cursor = await self.db.connection.execute(
            "SELECT * FROM model_profiles WHERE id = ?", (id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_model(row)

    async def list(self) -> list[ModelProfile]:
        """List all model profiles."""
        cursor = await self.db.connection.execute(
            "SELECT * FROM model_profiles ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [self._row_to_model(row) for row in rows]

    async def delete(self, id: str) -> bool:
        """Delete a model profile."""
        cursor = await self.db.connection.execute(
            "DELETE FROM model_profiles WHERE id = ?", (id,)
        )
        await self.db.connection.commit()
        return cursor.rowcount > 0

    async def get_encrypted_key(self, id: str) -> str | None:
        """Get the encrypted API key for a model profile."""
        cursor = await self.db.connection.execute(
            "SELECT api_key_encrypted FROM model_profiles WHERE id = ?", (id,)
        )
        row = await cursor.fetchone()
        return row["api_key_encrypted"] if row else None

    def _row_to_model(self, row: Any) -> ModelProfile:
        return ModelProfile(
            id=row["id"],
            provider=Provider(row["provider"]),
            model_name=row["model_name"],
            display_name=row["display_name"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class RepoDAO:
    """DAO for Repo."""

    def __init__(self, db: Database):
        self.db = db

    async def create(
        self,
        repo_url: str,
        default_branch: str,
        latest_commit: str,
        workspace_path: str,
    ) -> Repo:
        """Create a new repo."""
        id = generate_id()
        created_at = now_iso()

        await self.db.connection.execute(
            """
            INSERT INTO repos (id, repo_url, default_branch, latest_commit, workspace_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (id, repo_url, default_branch, latest_commit, workspace_path, created_at),
        )
        await self.db.connection.commit()

        return Repo(
            id=id,
            repo_url=repo_url,
            default_branch=default_branch,
            latest_commit=latest_commit,
            workspace_path=workspace_path,
            created_at=datetime.fromisoformat(created_at),
        )

    async def get(self, id: str) -> Repo | None:
        """Get a repo by ID."""
        cursor = await self.db.connection.execute(
            "SELECT * FROM repos WHERE id = ?", (id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_model(row)

    async def find_by_url(self, repo_url: str) -> Repo | None:
        """Find a repo by URL."""
        cursor = await self.db.connection.execute(
            "SELECT * FROM repos WHERE repo_url = ? ORDER BY created_at DESC LIMIT 1",
            (repo_url,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_model(row)

    def _row_to_model(self, row: Any) -> Repo:
        return Repo(
            id=row["id"],
            repo_url=row["repo_url"],
            default_branch=row["default_branch"],
            latest_commit=row["latest_commit"],
            workspace_path=row["workspace_path"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class TaskDAO:
    """DAO for Task."""

    def __init__(self, db: Database):
        self.db = db

    async def create(self, repo_id: str, title: str | None = None) -> Task:
        """Create a new task."""
        id = generate_id()
        now = now_iso()

        await self.db.connection.execute(
            """
            INSERT INTO tasks (id, repo_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (id, repo_id, title, now, now),
        )
        await self.db.connection.commit()

        return Task(
            id=id,
            repo_id=repo_id,
            title=title,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    async def get(self, id: str) -> Task | None:
        """Get a task by ID."""
        cursor = await self.db.connection.execute(
            "SELECT * FROM tasks WHERE id = ?", (id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_model(row)

    async def list(self, repo_id: str | None = None) -> list[Task]:
        """List tasks, optionally filtered by repo."""
        if repo_id:
            cursor = await self.db.connection.execute(
                "SELECT * FROM tasks WHERE repo_id = ? ORDER BY updated_at DESC",
                (repo_id,),
            )
        else:
            cursor = await self.db.connection.execute(
                "SELECT * FROM tasks ORDER BY updated_at DESC"
            )
        rows = await cursor.fetchall()
        return [self._row_to_model(row) for row in rows]

    async def update_timestamp(self, id: str) -> None:
        """Update the task's updated_at timestamp."""
        await self.db.connection.execute(
            "UPDATE tasks SET updated_at = ? WHERE id = ?",
            (now_iso(), id),
        )
        await self.db.connection.commit()

    def _row_to_model(self, row: Any) -> Task:
        return Task(
            id=row["id"],
            repo_id=row["repo_id"],
            title=row["title"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


class MessageDAO:
    """DAO for Message."""

    def __init__(self, db: Database):
        self.db = db

    async def create(self, task_id: str, role: MessageRole, content: str) -> Message:
        """Create a new message."""
        id = generate_id()
        created_at = now_iso()

        await self.db.connection.execute(
            """
            INSERT INTO messages (id, task_id, role, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (id, task_id, role.value, content, created_at),
        )
        await self.db.connection.commit()

        return Message(
            id=id,
            task_id=task_id,
            role=role,
            content=content,
            created_at=datetime.fromisoformat(created_at),
        )

    async def list(self, task_id: str) -> list[Message]:
        """List messages for a task."""
        cursor = await self.db.connection.execute(
            "SELECT * FROM messages WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_model(row) for row in rows]

    def _row_to_model(self, row: Any) -> Message:
        return Message(
            id=row["id"],
            task_id=row["task_id"],
            role=MessageRole(row["role"]),
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class RunDAO:
    """DAO for Run."""

    def __init__(self, db: Database):
        self.db = db

    async def create(
        self,
        task_id: str,
        instruction: str,
        executor_type: ExecutorType = ExecutorType.PATCH_AGENT,
        model_id: str | None = None,
        model_name: str | None = None,
        provider: Provider | None = None,
        base_ref: str | None = None,
        working_branch: str | None = None,
        worktree_path: str | None = None,
    ) -> Run:
        """Create a new run.

        Args:
            task_id: Task ID.
            instruction: Task instruction.
            executor_type: Type of executor (patch_agent or claude_code).
            model_id: Model profile ID (required for patch_agent).
            model_name: Model name (required for patch_agent).
            provider: Model provider (required for patch_agent).
            base_ref: Base git ref.
            working_branch: Git branch for worktree (claude_code).
            worktree_path: Filesystem path to worktree (claude_code).

        Returns:
            Created Run object.
        """
        id = generate_id()
        created_at = now_iso()

        await self.db.connection.execute(
            """
            INSERT INTO runs (id, task_id, model_id, model_name, provider, executor_type, working_branch, worktree_path, instruction, base_ref, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id, task_id, model_id, model_name,
                provider.value if provider else None,
                executor_type.value, working_branch, worktree_path,
                instruction, base_ref, RunStatus.QUEUED.value, created_at
            ),
        )
        await self.db.connection.commit()

        return Run(
            id=id,
            task_id=task_id,
            model_id=model_id,
            model_name=model_name,
            provider=provider,
            executor_type=executor_type,
            working_branch=working_branch,
            worktree_path=worktree_path,
            instruction=instruction,
            base_ref=base_ref,
            status=RunStatus.QUEUED,
            created_at=datetime.fromisoformat(created_at),
        )

    async def get(self, id: str) -> Run | None:
        """Get a run by ID."""
        cursor = await self.db.connection.execute(
            "SELECT * FROM runs WHERE id = ?",
            (id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_model(row)

    async def list(self, task_id: str) -> list[Run]:
        """List runs for a task."""
        cursor = await self.db.connection.execute(
            "SELECT * FROM runs WHERE task_id = ? ORDER BY created_at DESC",
            (task_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_model(row) for row in rows]

    async def update_status(
        self,
        id: str,
        status: RunStatus,
        summary: str | None = None,
        patch: str | None = None,
        files_changed: list[FileDiff] | None = None,
        logs: list[str] | None = None,
        warnings: list[str] | None = None,
        error: str | None = None,
    ) -> None:
        """Update run status and results."""
        updates = ["status = ?"]
        params: list[Any] = [status.value]

        if status == RunStatus.RUNNING:
            updates.append("started_at = ?")
            params.append(now_iso())
        elif status in (RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELED):
            updates.append("completed_at = ?")
            params.append(now_iso())

        if summary is not None:
            updates.append("summary = ?")
            params.append(summary)
        if patch is not None:
            updates.append("patch = ?")
            params.append(patch)
        if files_changed is not None:
            updates.append("files_changed = ?")
            params.append(json.dumps([f.model_dump() for f in files_changed]))
        if logs is not None:
            updates.append("logs = ?")
            params.append(json.dumps(logs))
        if warnings is not None:
            updates.append("warnings = ?")
            params.append(json.dumps(warnings))
        if error is not None:
            updates.append("error = ?")
            params.append(error)

        params.append(id)

        await self.db.connection.execute(
            f"UPDATE runs SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await self.db.connection.commit()

    async def update_worktree(
        self,
        id: str,
        working_branch: str,
        worktree_path: str,
    ) -> None:
        """Update run with worktree information.

        Args:
            id: Run ID.
            working_branch: Git branch name.
            worktree_path: Filesystem path to worktree.
        """
        await self.db.connection.execute(
            "UPDATE runs SET working_branch = ?, worktree_path = ? WHERE id = ?",
            (working_branch, worktree_path, id),
        )
        await self.db.connection.commit()

    def _row_to_model(self, row: Any) -> Run:
        files_changed = []
        if row["files_changed"]:
            files_changed = [FileDiff(**f) for f in json.loads(row["files_changed"])]

        logs = []
        if row["logs"]:
            logs = json.loads(row["logs"])

        warnings = []
        if row["warnings"]:
            warnings = json.loads(row["warnings"])

        # Handle nullable provider
        provider = Provider(row["provider"]) if row["provider"] else None

        # Handle executor_type with default for backward compatibility
        executor_type = ExecutorType(row["executor_type"]) if row["executor_type"] else ExecutorType.PATCH_AGENT

        return Run(
            id=row["id"],
            task_id=row["task_id"],
            model_id=row["model_id"],
            model_name=row["model_name"],
            provider=provider,
            executor_type=executor_type,
            working_branch=row["working_branch"],
            worktree_path=row["worktree_path"],
            instruction=row["instruction"],
            base_ref=row["base_ref"],
            status=RunStatus(row["status"]),
            summary=row["summary"],
            patch=row["patch"],
            files_changed=files_changed,
            logs=logs,
            warnings=warnings,
            error=row["error"],
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        )


class PRDAO:
    """DAO for PR."""

    def __init__(self, db: Database):
        self.db = db

    async def create(
        self,
        task_id: str,
        number: int,
        url: str,
        branch: str,
        title: str,
        body: str | None,
        latest_commit: str,
    ) -> PR:
        """Create a new PR record."""
        id = generate_id()
        now = now_iso()

        await self.db.connection.execute(
            """
            INSERT INTO prs (id, task_id, number, url, branch, title, body, latest_commit, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (id, task_id, number, url, branch, title, body, latest_commit, "open", now, now),
        )
        await self.db.connection.commit()

        return PR(
            id=id,
            task_id=task_id,
            number=number,
            url=url,
            branch=branch,
            title=title,
            body=body,
            latest_commit=latest_commit,
            status="open",
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    async def get(self, id: str) -> PR | None:
        """Get a PR by ID."""
        cursor = await self.db.connection.execute(
            "SELECT * FROM prs WHERE id = ?", (id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_model(row)

    async def list(self, task_id: str) -> list[PR]:
        """List PRs for a task."""
        cursor = await self.db.connection.execute(
            "SELECT * FROM prs WHERE task_id = ? ORDER BY created_at DESC",
            (task_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_model(row) for row in rows]

    async def update(self, id: str, latest_commit: str) -> None:
        """Update PR's latest commit."""
        await self.db.connection.execute(
            "UPDATE prs SET latest_commit = ?, updated_at = ? WHERE id = ?",
            (latest_commit, now_iso(), id),
        )
        await self.db.connection.commit()

    def _row_to_model(self, row: Any) -> PR:
        return PR(
            id=row["id"],
            task_id=row["task_id"],
            number=row["number"],
            url=row["url"],
            branch=row["branch"],
            title=row["title"],
            body=row["body"],
            latest_commit=row["latest_commit"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
