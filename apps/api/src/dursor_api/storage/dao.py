"""Data Access Objects for dursor storage."""

from __future__ import annotations

import builtins
import json
import uuid
from datetime import datetime
from typing import Any

from dursor_api.domain.enums import (
    BacklogStatus,
    BrokenDownTaskType,
    EstimatedSize,
    ExecutorType,
    MessageRole,
    PRCreationMode,
    Provider,
    RunStatus,
    TaskBaseKanbanStatus,
)
from dursor_api.domain.models import (
    PR,
    BacklogItem,
    FileDiff,
    Message,
    ModelProfile,
    Repo,
    Run,
    SubTask,
    Task,
    UserPreferences,
)
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
            INSERT INTO model_profiles
            (id, provider, model_name, display_name, api_key_encrypted, created_at)
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
        cursor = await self.db.connection.execute("DELETE FROM model_profiles WHERE id = ?", (id,))
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
            INSERT INTO repos
            (id, repo_url, default_branch, latest_commit, workspace_path, created_at)
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
        cursor = await self.db.connection.execute("SELECT * FROM repos WHERE id = ?", (id,))
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
        cursor = await self.db.connection.execute("SELECT * FROM tasks WHERE id = ?", (id,))
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

    async def update_kanban_status(self, task_id: str, status: TaskBaseKanbanStatus) -> None:
        """Update task kanban status (backlog/todo/archived only)."""
        await self.db.connection.execute(
            "UPDATE tasks SET kanban_status = ?, updated_at = ? WHERE id = ?",
            (status.value, now_iso(), task_id),
        )
        await self.db.connection.commit()

    async def list_with_aggregates(
        self, repo_id: str | None = None
    ) -> builtins.list[dict[str, Any]]:
        """List tasks with run/PR aggregation for kanban status calculation.

        Returns tasks with:
        - run_count: total runs
        - running_count: runs with status='running'
        - completed_count: runs with status in (succeeded, failed, canceled)
        - pr_count: total PRs
        - latest_pr_status: most recent PR status
        """
        query = """
            SELECT
                t.*,
                COALESCE(r.run_count, 0) as run_count,
                COALESCE(r.running_count, 0) as running_count,
                COALESCE(r.completed_count, 0) as completed_count,
                COALESCE(p.pr_count, 0) as pr_count,
                p.latest_pr_status
            FROM tasks t
            LEFT JOIN (
                SELECT
                    task_id,
                    COUNT(*) as run_count,
                    SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END)
                        as running_count,
                    SUM(CASE WHEN status IN ('succeeded', 'failed', 'canceled')
                        THEN 1 ELSE 0 END) as completed_count
                FROM runs
                GROUP BY task_id
            ) r ON t.id = r.task_id
            LEFT JOIN (
                SELECT
                    task_id,
                    COUNT(*) as pr_count,
                    (SELECT status FROM prs WHERE task_id = p2.task_id
                        ORDER BY created_at DESC LIMIT 1) as latest_pr_status
                FROM prs p2
                GROUP BY task_id
            ) p ON t.id = p.task_id
        """
        params: list[Any] = []

        if repo_id:
            query += " WHERE t.repo_id = ?"
            params.append(repo_id)

        query += " ORDER BY t.updated_at DESC"

        cursor = await self.db.connection.execute(query, params)
        rows = await cursor.fetchall()

        result: builtins.list[dict[str, Any]] = []
        for row in rows:
            # Handle kanban_status for backward compatibility
            kanban_status = row["kanban_status"] if "kanban_status" in row.keys() else "backlog"
            result.append(
                {
                    "id": row["id"],
                    "repo_id": row["repo_id"],
                    "title": row["title"],
                    "kanban_status": kanban_status,
                    "created_at": datetime.fromisoformat(row["created_at"]),
                    "updated_at": datetime.fromisoformat(row["updated_at"]),
                    "run_count": row["run_count"],
                    "running_count": row["running_count"],
                    "completed_count": row["completed_count"],
                    "pr_count": row["pr_count"],
                    "latest_pr_status": row["latest_pr_status"],
                }
            )
        return result

    def _row_to_model(self, row: Any) -> Task:
        # Handle kanban_status for backward compatibility
        kanban_status = row["kanban_status"] if "kanban_status" in row.keys() else "backlog"
        return Task(
            id=row["id"],
            repo_id=row["repo_id"],
            title=row["title"],
            kanban_status=kanban_status,
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
        message_id: str | None = None,
        model_id: str | None = None,
        model_name: str | None = None,
        provider: Provider | None = None,
        base_ref: str | None = None,
        working_branch: str | None = None,
        worktree_path: str | None = None,
        session_id: str | None = None,
    ) -> Run:
        """Create a new run.

        Args:
            task_id: Task ID.
            instruction: Task instruction.
            executor_type: Type of executor (patch_agent or claude_code).
            message_id: ID of the triggering message.
            model_id: Model profile ID (required for patch_agent).
            model_name: Model name (required for patch_agent).
            provider: Model provider (required for patch_agent).
            base_ref: Base git ref.
            working_branch: Git branch for worktree (claude_code).
            worktree_path: Filesystem path to worktree (claude_code).
            session_id: CLI session ID for conversation persistence.

        Returns:
            Created Run object.
        """
        id = generate_id()
        created_at = now_iso()

        await self.db.connection.execute(
            """
            INSERT INTO runs (
                id, task_id, message_id, model_id, model_name, provider, executor_type,
                working_branch, worktree_path, session_id, instruction,
                base_ref, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id,
                task_id,
                message_id,
                model_id,
                model_name,
                provider.value if provider else None,
                executor_type.value,
                working_branch,
                worktree_path,
                session_id,
                instruction,
                base_ref,
                RunStatus.QUEUED.value,
                created_at,
            ),
        )
        await self.db.connection.commit()

        return Run(
            id=id,
            task_id=task_id,
            message_id=message_id,
            model_id=model_id,
            model_name=model_name,
            provider=provider,
            executor_type=executor_type,
            working_branch=working_branch,
            worktree_path=worktree_path,
            session_id=session_id,
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
        files_changed: builtins.list[FileDiff] | None = None,
        logs: builtins.list[str] | None = None,
        warnings: builtins.list[str] | None = None,
        error: str | None = None,
        commit_sha: str | None = None,
        session_id: str | None = None,
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
        if commit_sha is not None:
            updates.append("commit_sha = ?")
            params.append(commit_sha)
        if session_id is not None:
            updates.append("session_id = ?")
            params.append(session_id)

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

    async def update_session_id(self, id: str, session_id: str) -> None:
        """Update run with session ID.

        Args:
            id: Run ID.
            session_id: CLI session ID for conversation persistence.
        """
        await self.db.connection.execute(
            "UPDATE runs SET session_id = ? WHERE id = ?",
            (session_id, id),
        )
        await self.db.connection.commit()

    async def get_latest_session_id(
        self,
        task_id: str,
        executor_type: ExecutorType,
    ) -> str | None:
        """Get the latest session ID for a task and executor type.

        Args:
            task_id: Task ID.
            executor_type: Type of executor.

        Returns:
            Session ID if found, None otherwise.
        """
        cursor = await self.db.connection.execute(
            """
            SELECT session_id FROM runs
            WHERE task_id = ? AND executor_type = ? AND session_id IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (task_id, executor_type.value),
        )
        row = await cursor.fetchone()
        return row["session_id"] if row else None

    async def get_latest_worktree_run(
        self,
        task_id: str,
        executor_type: ExecutorType,
    ) -> Run | None:
        """Get the latest run with a valid worktree for a task and executor type.

        This is used to reuse an existing worktree for subsequent runs in the
        same task, enabling conversation continuation in the same working directory.

        Args:
            task_id: Task ID.
            executor_type: Type of executor.

        Returns:
            Run with worktree if found, None otherwise.
        """
        cursor = await self.db.connection.execute(
            """
            SELECT * FROM runs
            WHERE task_id = ? AND executor_type = ?
                AND worktree_path IS NOT NULL
                AND status IN ('succeeded', 'failed', 'running', 'queued')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (task_id, executor_type.value),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_model(row)

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
        executor_type = (
            ExecutorType(row["executor_type"]) if row["executor_type"] else ExecutorType.PATCH_AGENT
        )

        # Handle message_id for backward compatibility
        message_id = row["message_id"] if "message_id" in row.keys() else None

        return Run(
            id=row["id"],
            task_id=row["task_id"],
            message_id=message_id,
            model_id=row["model_id"],
            model_name=row["model_name"],
            provider=provider,
            executor_type=executor_type,
            working_branch=row["working_branch"],
            worktree_path=row["worktree_path"],
            session_id=row["session_id"],
            instruction=row["instruction"],
            base_ref=row["base_ref"],
            commit_sha=row["commit_sha"] if "commit_sha" in row.keys() else None,
            status=RunStatus(row["status"]),
            summary=row["summary"],
            patch=row["patch"],
            files_changed=files_changed,
            logs=logs,
            warnings=warnings,
            error=row["error"],
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=(datetime.fromisoformat(row["started_at"]) if row["started_at"] else None),
            completed_at=(
                datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
            ),
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
            INSERT INTO prs (
                id, task_id, number, url, branch, title, body,
                latest_commit, status, created_at, updated_at
            )
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
        cursor = await self.db.connection.execute("SELECT * FROM prs WHERE id = ?", (id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_model(row)

    async def get_by_task_and_number(self, task_id: str, number: int) -> PR | None:
        """Get a PR by task and PR number."""
        cursor = await self.db.connection.execute(
            "SELECT * FROM prs WHERE task_id = ? AND number = ? LIMIT 1",
            (task_id, number),
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

    async def update_body(self, id: str, body: str) -> None:
        """Update PR's body/description."""
        await self.db.connection.execute(
            "UPDATE prs SET body = ?, updated_at = ? WHERE id = ?",
            (body, now_iso(), id),
        )
        await self.db.connection.commit()

    async def update_status(self, id: str, status: str) -> None:
        """Update PR status (open/merged/closed)."""
        await self.db.connection.execute(
            "UPDATE prs SET status = ?, updated_at = ? WHERE id = ?",
            (status, now_iso(), id),
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


class UserPreferencesDAO:
    """DAO for UserPreferences (singleton)."""

    def __init__(self, db: Database):
        self.db = db

    async def get(self) -> UserPreferences | None:
        """Get user preferences."""
        cursor = await self.db.connection.execute("SELECT * FROM user_preferences WHERE id = 1")
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_model(row)

    async def save(
        self,
        default_repo_owner: str | None = None,
        default_repo_name: str | None = None,
        default_branch: str | None = None,
        default_branch_prefix: str | None = None,
        default_pr_creation_mode: str | None = None,
    ) -> UserPreferences:
        """Save user preferences (upsert)."""
        now = now_iso()

        # Try to update first
        cursor = await self.db.connection.execute("SELECT id FROM user_preferences WHERE id = 1")
        exists = await cursor.fetchone()

        if exists:
            await self.db.connection.execute(
                """
                UPDATE user_preferences
                SET default_repo_owner = ?,
                    default_repo_name = ?,
                    default_branch = ?,
                    default_branch_prefix = ?,
                    default_pr_creation_mode = ?,
                    updated_at = ?
                WHERE id = 1
                """,
                (
                    default_repo_owner,
                    default_repo_name,
                    default_branch,
                    default_branch_prefix,
                    default_pr_creation_mode,
                    now,
                ),
            )
        else:
            await self.db.connection.execute(
                """
                INSERT INTO user_preferences (
                    id,
                    default_repo_owner,
                    default_repo_name,
                    default_branch,
                    default_branch_prefix,
                    default_pr_creation_mode,
                    created_at,
                    updated_at
                )
                VALUES (1, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    default_repo_owner,
                    default_repo_name,
                    default_branch,
                    default_branch_prefix,
                    default_pr_creation_mode,
                    now,
                    now,
                ),
            )

        await self.db.connection.commit()

        return UserPreferences(
            default_repo_owner=default_repo_owner,
            default_repo_name=default_repo_name,
            default_branch=default_branch,
            default_branch_prefix=default_branch_prefix,
            default_pr_creation_mode=PRCreationMode(default_pr_creation_mode or "create"),
        )

    def _row_to_model(self, row: Any) -> UserPreferences:
        return UserPreferences(
            default_repo_owner=row["default_repo_owner"],
            default_repo_name=row["default_repo_name"],
            default_branch=row["default_branch"],
            default_branch_prefix=(
                row["default_branch_prefix"] if "default_branch_prefix" in row.keys() else None
            ),
            default_pr_creation_mode=PRCreationMode(
                row["default_pr_creation_mode"]
                if "default_pr_creation_mode" in row.keys() and row["default_pr_creation_mode"]
                else "create"
            ),
        )


class BacklogDAO:
    """DAO for BacklogItem."""

    def __init__(self, db: Database):
        self.db = db

    async def create(
        self,
        repo_id: str,
        title: str,
        description: str = "",
        type: BrokenDownTaskType = BrokenDownTaskType.FEATURE,
        estimated_size: EstimatedSize = EstimatedSize.MEDIUM,
        target_files: list[str] | None = None,
        implementation_hint: str | None = None,
        tags: list[str] | None = None,
        subtasks: list[dict[str, Any]] | None = None,
    ) -> BacklogItem:
        """Create a new backlog item.

        Args:
            repo_id: Repository ID.
            title: Item title.
            description: Item description.
            type: Task type.
            estimated_size: Size estimate.
            target_files: Target files list.
            implementation_hint: Implementation hints.
            tags: Tags list.
            subtasks: List of subtasks with title.

        Returns:
            Created BacklogItem.
        """
        id = generate_id()
        now = now_iso()

        # Generate IDs for subtasks
        subtask_list = []
        if subtasks:
            for st in subtasks:
                subtask_list.append(
                    {
                        "id": generate_id(),
                        "title": st.get("title", ""),
                        "completed": False,
                    }
                )

        await self.db.connection.execute(
            """
            INSERT INTO backlog_items (
                id, repo_id, title, description, type, estimated_size,
                target_files, implementation_hint, tags, subtasks,
                status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id,
                repo_id,
                title,
                description,
                type.value,
                estimated_size.value,
                json.dumps(target_files or []),
                implementation_hint,
                json.dumps(tags or []),
                json.dumps(subtask_list),
                BacklogStatus.DRAFT.value,
                now,
                now,
            ),
        )
        await self.db.connection.commit()

        return BacklogItem(
            id=id,
            repo_id=repo_id,
            title=title,
            description=description,
            type=type,
            estimated_size=estimated_size,
            target_files=target_files or [],
            implementation_hint=implementation_hint,
            tags=tags or [],
            subtasks=[SubTask(**st) for st in subtask_list],
            status=BacklogStatus.DRAFT,
            task_id=None,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    async def get(self, id: str) -> BacklogItem | None:
        """Get a backlog item by ID."""
        cursor = await self.db.connection.execute("SELECT * FROM backlog_items WHERE id = ?", (id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_model(row)

    async def list(
        self,
        repo_id: str | None = None,
        status: BacklogStatus | None = None,
    ) -> list[BacklogItem]:
        """List backlog items with optional filters.

        Args:
            repo_id: Filter by repository ID.
            status: Filter by status.

        Returns:
            List of BacklogItem.
        """
        query = "SELECT * FROM backlog_items WHERE 1=1"
        params: list[Any] = []

        if repo_id:
            query += " AND repo_id = ?"
            params.append(repo_id)

        if status:
            query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY created_at DESC"

        cursor = await self.db.connection.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_model(row) for row in rows]

    async def update(
        self,
        id: str,
        title: str | None = None,
        description: str | None = None,
        type: BrokenDownTaskType | None = None,
        estimated_size: EstimatedSize | None = None,
        target_files: builtins.list[str] | None = None,
        implementation_hint: str | None = None,
        tags: builtins.list[str] | None = None,
        subtasks: builtins.list[dict[str, Any]] | None = None,
        status: BacklogStatus | None = None,
        task_id: str | None = None,
    ) -> BacklogItem | None:
        """Update a backlog item.

        Args:
            id: Backlog item ID.
            **kwargs: Fields to update.

        Returns:
            Updated BacklogItem or None if not found.
        """
        updates = ["updated_at = ?"]
        params: list[Any] = [now_iso()]

        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if type is not None:
            updates.append("type = ?")
            params.append(type.value)
        if estimated_size is not None:
            updates.append("estimated_size = ?")
            params.append(estimated_size.value)
        if target_files is not None:
            updates.append("target_files = ?")
            params.append(json.dumps(target_files))
        if implementation_hint is not None:
            updates.append("implementation_hint = ?")
            params.append(implementation_hint)
        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags))
        if subtasks is not None:
            updates.append("subtasks = ?")
            params.append(json.dumps(subtasks))
        if status is not None:
            updates.append("status = ?")
            params.append(status.value)
        if task_id is not None:
            updates.append("task_id = ?")
            params.append(task_id)

        params.append(id)

        await self.db.connection.execute(
            f"UPDATE backlog_items SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await self.db.connection.commit()

        return await self.get(id)

    async def delete(self, id: str) -> bool:
        """Delete a backlog item.

        Args:
            id: Backlog item ID.

        Returns:
            True if deleted, False if not found.
        """
        cursor = await self.db.connection.execute("DELETE FROM backlog_items WHERE id = ?", (id,))
        await self.db.connection.commit()
        return cursor.rowcount > 0

    def _row_to_model(self, row: Any) -> BacklogItem:
        """Convert database row to BacklogItem model."""
        target_files = []
        if row["target_files"]:
            target_files = json.loads(row["target_files"])

        tags = []
        if row["tags"]:
            tags = json.loads(row["tags"])

        subtasks = []
        if row["subtasks"]:
            subtask_data = json.loads(row["subtasks"])
            subtasks = [SubTask(**st) for st in subtask_data]

        return BacklogItem(
            id=row["id"],
            repo_id=row["repo_id"],
            title=row["title"],
            description=row["description"],
            type=BrokenDownTaskType(row["type"]),
            estimated_size=EstimatedSize(row["estimated_size"]),
            target_files=target_files,
            implementation_hint=row["implementation_hint"],
            tags=tags,
            subtasks=subtasks,
            status=BacklogStatus(row["status"]),
            task_id=row["task_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
