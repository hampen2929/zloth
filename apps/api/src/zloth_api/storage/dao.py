"""Data Access Objects for zloth storage."""

from __future__ import annotations

import builtins
import json
import uuid
from datetime import datetime
from typing import Any

from zloth_api.domain.enums import (
    BrokenDownTaskType,
    CodingMode,
    EstimatedSize,
    ExecutorType,
    JobKind,
    JobStatus,
    MessageRole,
    PRCreationMode,
    Provider,
    ReviewCategory,
    ReviewSeverity,
    ReviewStatus,
    RunStatus,
    TaskBaseKanbanStatus,
)
from zloth_api.domain.models import (
    PR,
    AgenticState,
    BacklogItem,
    CICheck,
    CIJobResult,
    FileDiff,
    Job,
    Message,
    ModelProfile,
    Repo,
    Review,
    ReviewFeedbackItem,
    ReviewSummary,
    Run,
    SubTask,
    Task,
    UserPreferences,
)
from zloth_api.storage.db import Database
from zloth_api.storage.row_mapping import row_to_model


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
        return row_to_model(ModelProfile, row)


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
        selected_branch: str | None = None,
    ) -> Repo:
        """Create a new repo."""
        id = generate_id()
        created_at = now_iso()

        await self.db.connection.execute(
            """
            INSERT INTO repos
            (id, repo_url, default_branch, selected_branch,
             latest_commit, workspace_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id,
                repo_url,
                default_branch,
                selected_branch,
                latest_commit,
                workspace_path,
                created_at,
            ),
        )
        await self.db.connection.commit()

        return Repo(
            id=id,
            repo_url=repo_url,
            default_branch=default_branch,
            selected_branch=selected_branch,
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

    async def update_selected_branch(self, id: str, selected_branch: str | None) -> None:
        """Update the selected branch for a repo."""
        await self.db.connection.execute(
            "UPDATE repos SET selected_branch = ? WHERE id = ?",
            (selected_branch, id),
        )
        await self.db.connection.commit()

    async def list(self) -> builtins.list[Repo]:
        """List all repos."""
        cursor = await self.db.connection.execute("SELECT * FROM repos ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [self._row_to_model(row) for row in rows]

    def _row_to_model(self, row: Any) -> Repo:
        return row_to_model(Repo, row)


class TaskDAO:
    """DAO for Task."""

    def __init__(self, db: Database):
        self.db = db

    async def create(
        self,
        repo_id: str,
        title: str | None = None,
        coding_mode: CodingMode = CodingMode.INTERACTIVE,
    ) -> Task:
        """Create a new task."""
        id = generate_id()
        now = now_iso()

        await self.db.connection.execute(
            """
            INSERT INTO tasks (id, repo_id, title, coding_mode, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (id, repo_id, title, coding_mode.value, now, now),
        )
        await self.db.connection.commit()

        return Task(
            id=id,
            repo_id=repo_id,
            title=title,
            coding_mode=coding_mode,
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

    async def update_title(self, id: str, title: str) -> None:
        """Update the task's title."""
        await self.db.connection.execute(
            "UPDATE tasks SET title = ?, updated_at = ? WHERE id = ?",
            (title, now_iso(), id),
        )
        await self.db.connection.commit()

    async def list_with_aggregates(
        self, repo_id: str | None = None
    ) -> builtins.list[dict[str, Any]]:
        """List tasks with run/PR/CI aggregation for kanban status calculation.

        Returns tasks with:
        - run_count: total runs
        - running_count: runs with status='running'
        - completed_count: runs with status in (succeeded, failed, canceled)
        - pr_count: total PRs
        - latest_pr_status: most recent PR status
        - latest_ci_status: most recent CI check status for the latest PR
        """
        query = """
            SELECT
                t.*,
                repos.repo_url,
                COALESCE(r.run_count, 0) as run_count,
                COALESCE(r.running_count, 0) as running_count,
                COALESCE(r.completed_count, 0) as completed_count,
                COALESCE(p.pr_count, 0) as pr_count,
                p.latest_pr_status,
                p.latest_pr_id,
                ci.latest_ci_status
            FROM tasks t
            LEFT JOIN repos ON t.repo_id = repos.id
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
                        ORDER BY created_at DESC LIMIT 1) as latest_pr_status,
                    (SELECT id FROM prs WHERE task_id = p2.task_id
                        ORDER BY created_at DESC LIMIT 1) as latest_pr_id
                FROM prs p2
                GROUP BY task_id
            ) p ON t.id = p.task_id
            LEFT JOIN (
                SELECT
                    c1.pr_id,
                    c1.status as latest_ci_status
                FROM ci_checks c1
                WHERE c1.created_at = (
                    SELECT MAX(c2.created_at)
                    FROM ci_checks c2
                    WHERE c2.pr_id = c1.pr_id
                )
            ) ci ON p.latest_pr_id = ci.pr_id
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
            # Handle coding_mode for backward compatibility
            coding_mode_str = (
                row["coding_mode"]
                if "coding_mode" in row.keys() and row["coding_mode"]
                else "interactive"
            )
            # Parse repo_name from repo_url (e.g., "https://github.com/owner/repo" -> "owner/repo")
            repo_url = row["repo_url"] if "repo_url" in row.keys() else None
            repo_name = None
            if repo_url:
                # Handle https://github.com/owner/repo format
                if "github.com/" in repo_url:
                    repo_name = repo_url.split("github.com/")[-1].rstrip("/").rstrip(".git")

            result.append(
                {
                    "id": row["id"],
                    "repo_id": row["repo_id"],
                    "repo_name": repo_name,
                    "title": row["title"],
                    "coding_mode": CodingMode(coding_mode_str),
                    "kanban_status": kanban_status,
                    "created_at": datetime.fromisoformat(row["created_at"]),
                    "updated_at": datetime.fromisoformat(row["updated_at"]),
                    "run_count": row["run_count"],
                    "running_count": row["running_count"],
                    "completed_count": row["completed_count"],
                    "pr_count": row["pr_count"],
                    "latest_pr_status": row["latest_pr_status"],
                    "latest_pr_id": row["latest_pr_id"] if "latest_pr_id" in row.keys() else None,
                    "latest_ci_status": (
                        row["latest_ci_status"] if "latest_ci_status" in row.keys() else None
                    ),
                }
            )
        return result

    def _row_to_model(self, row: Any) -> Task:
        # Backward-compatible defaults for older DBs (missing columns / NULL values)
        return row_to_model(
            Task,
            row,
            defaults={"kanban_status": "backlog", "coding_mode": CodingMode.INTERACTIVE.value},
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
        return row_to_model(Message, row)


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

    async def fail_all_running(self, *, error: str) -> int:
        """Mark all RUNNING runs as FAILED (used during startup recovery)."""
        now = now_iso()
        cursor = await self.db.connection.execute(
            """
            UPDATE runs
            SET status = ?, error = ?, completed_at = ?
            WHERE status = ?
            """,
            (RunStatus.FAILED.value, error, now, RunStatus.RUNNING.value),
        )
        await self.db.connection.commit()
        return cursor.rowcount

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
        # JSON fields are stored as TEXT in SQLite; decode before model validation.
        # For backward compatibility / NULL handling, coalesce to empty list.
        return row_to_model(
            Run,
            row,
            json_fields={"files_changed", "logs", "warnings"},
            defaults={
                "executor_type": ExecutorType.PATCH_AGENT.value,
                "files_changed": [],
                "logs": [],
                "warnings": [],
            },
        )

    async def get_latest_runs_by_executor_for_tasks(
        self, task_ids: builtins.list[str]
    ) -> dict[str, dict[str, dict[str, Any]]]:
        """Get latest run per executor type for each task.

        For kanban board display, fetches the most recent run for each
        executor type (claude_code, codex_cli, gemini_cli) per task.

        Args:
            task_ids: List of task IDs to fetch runs for.

        Returns:
            Dict mapping task_id -> executor_type -> run info dict
            {
                "task_id_1": {
                    "claude_code": {"run_id": "...", "status": "succeeded"},
                    "codex_cli": {"run_id": "...", "status": "running"},
                },
                ...
            }
        """
        if not task_ids:
            return {}

        placeholders = ",".join("?" * len(task_ids))
        query = f"""
            SELECT r.task_id, r.id as run_id, r.executor_type, r.status
            FROM runs r
            INNER JOIN (
                SELECT task_id, executor_type, MAX(created_at) as max_created
                FROM runs
                WHERE task_id IN ({placeholders})
                GROUP BY task_id, executor_type
            ) latest
            ON r.task_id = latest.task_id
                AND r.executor_type = latest.executor_type
                AND r.created_at = latest.max_created
        """
        cursor = await self.db.connection.execute(query, task_ids)
        rows = await cursor.fetchall()

        result: dict[str, dict[str, dict[str, Any]]] = {}
        for row in rows:
            task_id = row["task_id"]
            executor_type = row["executor_type"]
            if task_id not in result:
                result[task_id] = {}
            result[task_id][executor_type] = {
                "run_id": row["run_id"],
                "status": row["status"],
            }
        return result


class JobDAO:
    """DAO for persistent jobs (SQLite-backed queue)."""

    def __init__(self, db: Database):
        self.db = db

    async def create(
        self,
        *,
        kind: JobKind,
        ref_id: str,
        payload: dict[str, Any] | None = None,
        max_attempts: int = 1,
        available_at: datetime | None = None,
    ) -> Job:
        """Create a new job in QUEUED state."""
        job_id = generate_id()
        now = now_iso()
        payload_str = json.dumps(payload or {})
        available_at_iso = available_at.isoformat() if available_at else now

        await self.db.connection.execute(
            """
            INSERT INTO jobs (
                id, kind, ref_id, status, payload,
                attempts, max_attempts,
                available_at, locked_at, locked_by,
                last_error, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                kind.value,
                ref_id,
                JobStatus.QUEUED.value,
                payload_str,
                0,
                max_attempts,
                available_at_iso,
                None,
                None,
                None,
                now,
                now,
            ),
        )
        await self.db.connection.commit()
        created = await self.get(job_id)
        if not created:
            raise RuntimeError(f"Job not found after create: {job_id}")
        return created

    async def get(self, job_id: str) -> Job | None:
        cursor = await self.db.connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_model(row)

    async def claim_next(
        self,
        *,
        locked_by: str,
    ) -> Job | None:
        """Atomically claim the next available queued job.

        This uses a short IMMEDIATE transaction to avoid double-claims.
        """
        conn = self.db.connection
        now = now_iso()

        await conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = await conn.execute(
                """
                SELECT id FROM jobs
                WHERE status = ?
                  AND available_at <= ?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (JobStatus.QUEUED.value, now),
            )
            row = await cursor.fetchone()
            if not row:
                await conn.execute("COMMIT")
                return None

            job_id = row["id"]
            await conn.execute(
                """
                UPDATE jobs
                SET status = ?,
                    attempts = attempts + 1,
                    locked_at = ?,
                    locked_by = ?,
                    updated_at = ?
                WHERE id = ?
                  AND status = ?
                """,
                (
                    JobStatus.RUNNING.value,
                    now,
                    locked_by,
                    now,
                    job_id,
                    JobStatus.QUEUED.value,
                ),
            )
            await conn.execute("COMMIT")
        except Exception:
            await conn.execute("ROLLBACK")
            raise

        return await self.get(job_id)

    async def complete(self, job_id: str) -> None:
        """Mark job succeeded and release the lock."""
        now = now_iso()
        await self.db.connection.execute(
            """
            UPDATE jobs
            SET status = ?,
                locked_at = NULL,
                locked_by = NULL,
                last_error = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (JobStatus.SUCCEEDED.value, now, job_id),
        )
        await self.db.connection.commit()

    async def cancel(self, *, job_id: str, reason: str | None = None) -> None:
        """Mark a job canceled and release the lock."""
        now = now_iso()
        await self.db.connection.execute(
            """
            UPDATE jobs
            SET status = ?,
                locked_at = NULL,
                locked_by = NULL,
                last_error = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (JobStatus.CANCELED.value, reason, now, job_id),
        )
        await self.db.connection.commit()

    async def fail(self, job_id: str, *, error: str, retry_delay_seconds: int = 10) -> None:
        """Record a failure and optionally requeue if attempts remain."""
        job = await self.get(job_id)
        if not job:
            return

        now_dt = datetime.utcnow()
        now_iso_str = now_dt.isoformat()

        if job.attempts < job.max_attempts:
            # Requeue with simple linear delay.
            available_at_iso = datetime.utcfromtimestamp(
                now_dt.timestamp() + retry_delay_seconds
            ).isoformat()
            await self.db.connection.execute(
                """
                UPDATE jobs
                SET status = ?,
                    available_at = ?,
                    locked_at = NULL,
                    locked_by = NULL,
                    last_error = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (JobStatus.QUEUED.value, available_at_iso, error, now_iso_str, job_id),
            )
        else:
            await self.db.connection.execute(
                """
                UPDATE jobs
                SET status = ?,
                    locked_at = NULL,
                    locked_by = NULL,
                    last_error = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (JobStatus.FAILED.value, error, now_iso_str, job_id),
            )
        await self.db.connection.commit()

    async def get_latest_by_ref(self, *, kind: JobKind, ref_id: str) -> Job | None:
        """Get the most recent job for a referenced record."""
        cursor = await self.db.connection.execute(
            """
            SELECT * FROM jobs
            WHERE kind = ? AND ref_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (kind.value, ref_id),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_model(row)

    async def cancel_queued_by_ref(self, *, kind: JobKind, ref_id: str) -> bool:
        """Cancel a queued job for a referenced record."""
        now = now_iso()
        cursor = await self.db.connection.execute(
            """
            UPDATE jobs
            SET status = ?, updated_at = ?
            WHERE kind = ?
              AND ref_id = ?
              AND status = ?
            """,
            (JobStatus.CANCELED.value, now, kind.value, ref_id, JobStatus.QUEUED.value),
        )
        await self.db.connection.commit()
        return cursor.rowcount > 0

    async def fail_all_running(self, *, error: str) -> int:
        """Fail all running jobs (used during startup recovery)."""
        now = now_iso()
        cursor = await self.db.connection.execute(
            """
            UPDATE jobs
            SET status = ?,
                locked_at = NULL,
                locked_by = NULL,
                last_error = ?,
                updated_at = ?
            WHERE status = ?
            """,
            (JobStatus.FAILED.value, error, now, JobStatus.RUNNING.value),
        )
        await self.db.connection.commit()
        return cursor.rowcount

    def _row_to_model(self, row: Any) -> Job:
        payload: dict[str, Any] = {}
        if row["payload"]:
            try:
                payload = json.loads(row["payload"])
            except Exception:
                payload = {}

        def _parse_dt(value: Any) -> datetime | None:
            if not value:
                return None
            return datetime.fromisoformat(value)

        return Job(
            id=row["id"],
            kind=JobKind(row["kind"]),
            ref_id=row["ref_id"],
            status=JobStatus(row["status"]),
            payload=payload,
            attempts=int(row["attempts"] or 0),
            max_attempts=int(row["max_attempts"] or 1),
            available_at=_parse_dt(row["available_at"]),
            locked_at=_parse_dt(row["locked_at"]),
            locked_by=row["locked_by"],
            last_error=row["last_error"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
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

    async def get_by_number(self, number: int) -> PR | None:
        """Get a PR by PR number (across all tasks)."""
        cursor = await self.db.connection.execute(
            "SELECT * FROM prs WHERE number = ? ORDER BY created_at DESC LIMIT 1",
            (number,),
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

    async def update_title_and_body(self, id: str, title: str, body: str) -> None:
        """Update PR's title and body/description."""
        await self.db.connection.execute(
            "UPDATE prs SET title = ?, body = ?, updated_at = ? WHERE id = ?",
            (title, body, now_iso(), id),
        )
        await self.db.connection.commit()

    async def update_title(self, id: str, title: str) -> None:
        """Update PR's title only."""
        await self.db.connection.execute(
            "UPDATE prs SET title = ?, updated_at = ? WHERE id = ?",
            (title, now_iso(), id),
        )
        await self.db.connection.commit()

    async def update_status(self, id: str, status: str) -> None:
        """Update PR status (open/merged/closed)."""
        await self.db.connection.execute(
            "UPDATE prs SET status = ?, updated_at = ? WHERE id = ?",
            (status, now_iso(), id),
        )
        await self.db.connection.commit()

    async def list_open(self) -> builtins.list[PR]:
        """List all PRs with status='open'.

        Used by the PR status poller to check for merge status updates.
        """
        cursor = await self.db.connection.execute(
            "SELECT * FROM prs WHERE status = 'open' ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [self._row_to_model(row) for row in rows]

    def _row_to_model(self, row: Any) -> PR:
        return row_to_model(PR, row)


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
        default_coding_mode: str | None = None,
        auto_generate_pr_description: bool | None = None,
        enable_gating_status: bool | None = None,
        # Optional overrides (nullable)
        notify_on_ready: bool | None = None,
        notify_on_complete: bool | None = None,
        notify_on_failure: bool | None = None,
        notify_on_warning: bool | None = None,
        merge_method: str | None = None,
        merge_delete_branch: bool | None = None,
        review_min_score: float | None = None,
    ) -> UserPreferences:
        """Save user preferences (upsert)."""
        now = now_iso()
        auto_gen = 1 if auto_generate_pr_description else 0
        gating_status = 1 if enable_gating_status else 0
        ready_int = None if notify_on_ready is None else (1 if notify_on_ready else 0)
        complete_int = None if notify_on_complete is None else (1 if notify_on_complete else 0)
        failure_int = None if notify_on_failure is None else (1 if notify_on_failure else 0)
        warning_int = None if notify_on_warning is None else (1 if notify_on_warning else 0)
        delete_branch_int = (
            None if merge_delete_branch is None else (1 if merge_delete_branch else 0)
        )

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
                    default_coding_mode = ?,
                    auto_generate_pr_description = ?,
                    enable_gating_status = ?,
                    notify_on_ready = ?,
                    notify_on_complete = ?,
                    notify_on_failure = ?,
                    notify_on_warning = ?,
                    merge_method = ?,
                    merge_delete_branch = ?,
                    review_min_score = ?,
                    updated_at = ?
                WHERE id = 1
                """,
                (
                    default_repo_owner,
                    default_repo_name,
                    default_branch,
                    default_branch_prefix,
                    default_pr_creation_mode,
                    default_coding_mode,
                    auto_gen,
                    gating_status,
                    ready_int,
                    complete_int,
                    failure_int,
                    warning_int,
                    merge_method,
                    delete_branch_int,
                    review_min_score,
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
                    default_coding_mode,
                    auto_generate_pr_description,
                    enable_gating_status,
                    notify_on_ready,
                    notify_on_complete,
                    notify_on_failure,
                    notify_on_warning,
                    merge_method,
                    merge_delete_branch,
                    review_min_score,
                    created_at,
                    updated_at
                )
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    default_repo_owner,
                    default_repo_name,
                    default_branch,
                    default_branch_prefix,
                    default_pr_creation_mode,
                    default_coding_mode,
                    auto_gen,
                    gating_status,
                    ready_int,
                    complete_int,
                    failure_int,
                    warning_int,
                    merge_method,
                    delete_branch_int,
                    review_min_score,
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
            default_coding_mode=CodingMode(default_coding_mode or "interactive"),
            auto_generate_pr_description=auto_generate_pr_description or False,
            enable_gating_status=enable_gating_status or False,
            notify_on_ready=notify_on_ready,
            notify_on_complete=notify_on_complete,
            notify_on_failure=notify_on_failure,
            notify_on_warning=notify_on_warning,
            merge_method=merge_method,
            merge_delete_branch=merge_delete_branch,
            review_min_score=review_min_score,
        )

    def _row_to_model(self, row: Any) -> UserPreferences:
        # Backward-compatible defaults for older DBs (missing columns / NULL values).
        # Note: default_pr_creation_mode fallback intentionally uses "create"
        # to preserve existing behavior in this DAO.
        return row_to_model(
            UserPreferences,
            row,
            defaults={
                "default_pr_creation_mode": PRCreationMode.CREATE.value,
                "default_coding_mode": CodingMode.INTERACTIVE.value,
                "auto_generate_pr_description": 0,
                "enable_gating_status": 0,
                # keep notify_* and merge_* and review_min_score as None when absent
            },
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
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    ) -> list[BacklogItem]:
        """List backlog items with optional filters.

        Args:
            repo_id: Filter by repository ID.

        Returns:
            List of BacklogItem.
        """
        query = "SELECT * FROM backlog_items WHERE 1=1"
        params: list[Any] = []

        if repo_id:
            query += " AND repo_id = ?"
            params.append(repo_id)

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
        return row_to_model(
            BacklogItem,
            row,
            json_fields={"target_files", "tags", "subtasks"},
            defaults={"target_files": [], "tags": [], "subtasks": []},
        )


class ReviewDAO:
    """DAO for Review."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def create(self, review: Review) -> Review:
        """Create a new review."""
        await self.db.connection.execute(
            """
            INSERT INTO reviews (
                id, task_id, target_run_ids, executor_type, model_id, model_name,
                status, logs, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review.id,
                review.task_id,
                json.dumps(review.target_run_ids),
                review.executor_type.value,
                review.model_id,
                review.model_name,
                review.status.value,
                json.dumps(review.logs),
                review.created_at.isoformat(),
            ),
        )
        await self.db.connection.commit()
        return review

    async def get(self, review_id: str) -> Review | None:
        """Get a review by ID."""
        cursor = await self.db.connection.execute(
            "SELECT * FROM reviews WHERE id = ?", (review_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None

        # Get feedbacks
        feedbacks = await self._get_feedbacks(review_id)
        return self._row_to_model(row, feedbacks)

    async def list_by_task(self, task_id: str) -> builtins.list[ReviewSummary]:
        """List reviews for a task."""
        cursor = await self.db.connection.execute(
            """
            SELECT r.*, COUNT(f.id) as feedback_count,
                SUM(CASE WHEN f.severity = 'critical' THEN 1 ELSE 0 END) as critical_count,
                SUM(CASE WHEN f.severity = 'high' THEN 1 ELSE 0 END) as high_count,
                SUM(CASE WHEN f.severity = 'medium' THEN 1 ELSE 0 END) as medium_count,
                SUM(CASE WHEN f.severity = 'low' THEN 1 ELSE 0 END) as low_count
            FROM reviews r
            LEFT JOIN review_feedbacks f ON r.id = f.review_id
            WHERE r.task_id = ?
            GROUP BY r.id
            ORDER BY r.created_at DESC
            """,
            (task_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_summary(row) for row in rows]

    async def update_status(
        self,
        review_id: str,
        status: ReviewStatus,
        summary: str | None = None,
        score: float | None = None,
        feedbacks: builtins.list[ReviewFeedbackItem] | None = None,
        logs: builtins.list[str] | None = None,
        error: str | None = None,
    ) -> None:
        """Update review status and results."""
        updates = ["status = ?"]
        params: builtins.list[Any] = [status.value]

        if status == ReviewStatus.RUNNING:
            updates.append("started_at = ?")
            params.append(now_iso())
        elif status in (ReviewStatus.SUCCEEDED, ReviewStatus.FAILED):
            updates.append("completed_at = ?")
            params.append(now_iso())

        if summary is not None:
            updates.append("overall_summary = ?")
            params.append(summary)
        if score is not None:
            updates.append("overall_score = ?")
            params.append(score)
        if logs is not None:
            updates.append("logs = ?")
            params.append(json.dumps(logs))
        if error is not None:
            updates.append("error = ?")
            params.append(error)

        params.append(review_id)

        await self.db.connection.execute(
            f"UPDATE reviews SET {', '.join(updates)} WHERE id = ?",
            params,
        )

        # Save feedbacks if provided
        if feedbacks is not None:
            # Clear existing feedbacks
            await self.db.connection.execute(
                "DELETE FROM review_feedbacks WHERE review_id = ?",
                (review_id,),
            )
            # Insert new feedbacks
            for fb in feedbacks:
                await self.db.connection.execute(
                    """
                    INSERT INTO review_feedbacks (
                        id, review_id, file_path, line_start, line_end,
                        severity, category, title, description, suggestion, code_snippet
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fb.id,
                        review_id,
                        fb.file_path,
                        fb.line_start,
                        fb.line_end,
                        fb.severity.value,
                        fb.category.value,
                        fb.title,
                        fb.description,
                        fb.suggestion,
                        fb.code_snippet,
                    ),
                )

        await self.db.connection.commit()

    async def fail_all_running(self, *, error: str) -> int:
        """Mark all RUNNING reviews as FAILED (used during startup recovery)."""
        now = now_iso()
        cursor = await self.db.connection.execute(
            """
            UPDATE reviews
            SET status = ?, error = ?, completed_at = ?
            WHERE status = ?
            """,
            (ReviewStatus.FAILED.value, error, now, ReviewStatus.RUNNING.value),
        )
        await self.db.connection.commit()
        return cursor.rowcount

    async def _get_feedbacks(self, review_id: str) -> builtins.list[ReviewFeedbackItem]:
        """Get feedbacks for a review."""
        cursor = await self.db.connection.execute(
            "SELECT * FROM review_feedbacks WHERE review_id = ? ORDER BY severity",
            (review_id,),
        )
        rows = await cursor.fetchall()
        return [
            ReviewFeedbackItem(
                id=row["id"],
                file_path=row["file_path"],
                line_start=row["line_start"],
                line_end=row["line_end"],
                severity=ReviewSeverity(row["severity"]),
                category=ReviewCategory(row["category"]),
                title=row["title"],
                description=row["description"],
                suggestion=row["suggestion"],
                code_snippet=row["code_snippet"],
            )
            for row in rows
        ]

    def _row_to_model(self, row: Any, feedbacks: builtins.list[ReviewFeedbackItem]) -> Review:
        """Convert database row to Review model."""
        return row_to_model(
            Review,
            row,
            json_fields={"target_run_ids", "logs"},
            defaults={"target_run_ids": [], "logs": []},
            overrides={"feedbacks": feedbacks},
        )

    def _row_to_summary(self, row: Any) -> ReviewSummary:
        """Convert database row to ReviewSummary model."""
        return row_to_model(
            ReviewSummary,
            row,
            defaults={
                "feedback_count": 0,
                "critical_count": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0,
            },
        )

    async def get_reviewed_run_ids(self, run_ids: builtins.list[str]) -> set[str]:
        """Get the set of run IDs that have been reviewed.

        Args:
            run_ids: List of run IDs to check.

        Returns:
            Set of run IDs that have completed reviews.
        """
        if not run_ids:
            return set()

        # Get all reviews that have succeeded
        cursor = await self.db.connection.execute(
            "SELECT target_run_ids FROM reviews WHERE status = 'succeeded'"
        )
        rows = await cursor.fetchall()

        reviewed_run_ids: set[str] = set()
        run_ids_set = set(run_ids)
        for row in rows:
            target_ids = json.loads(row["target_run_ids"]) if row["target_run_ids"] else []
            for target_id in target_ids:
                if target_id in run_ids_set:
                    reviewed_run_ids.add(target_id)

        return reviewed_run_ids


class AgenticRunDAO:
    """DAO for AgenticRun (agentic execution state)."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def create(self, state: AgenticState) -> AgenticState:
        """Create a new agentic run record."""
        await self.db.connection.execute(
            """
            INSERT INTO agentic_runs (
                id, task_id, mode, phase, iteration, ci_iterations, review_iterations,
                started_at, last_activity, pr_number, current_sha, last_ci_result,
                last_review_score, error, human_approved
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                state.id,
                state.task_id,
                state.mode.value,
                state.phase.value,
                state.iteration,
                state.ci_iterations,
                state.review_iterations,
                state.started_at.isoformat(),
                state.last_activity.isoformat(),
                state.pr_number,
                state.current_sha,
                json.dumps(state.last_ci_result.model_dump()) if state.last_ci_result else None,
                state.last_review_score,
                state.error,
                1 if state.human_approved else 0,
            ),
        )
        await self.db.connection.commit()
        return state

    async def get(self, id: str) -> AgenticState | None:
        """Get an agentic run by ID."""
        cursor = await self.db.connection.execute("SELECT * FROM agentic_runs WHERE id = ?", (id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_model(row)

    async def get_by_task_id(self, task_id: str) -> AgenticState | None:
        """Get the latest agentic run for a task."""
        cursor = await self.db.connection.execute(
            """
            SELECT * FROM agentic_runs
            WHERE task_id = ?
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (task_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_model(row)

    async def get_by_pr_number(self, pr_number: int) -> AgenticState | None:
        """Get an agentic run by PR number."""
        cursor = await self.db.connection.execute(
            "SELECT * FROM agentic_runs WHERE pr_number = ? ORDER BY started_at DESC LIMIT 1",
            (pr_number,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_model(row)

    async def update(self, state: AgenticState) -> None:
        """Update an agentic run record."""
        await self.db.connection.execute(
            """
            UPDATE agentic_runs SET
                mode = ?, phase = ?, iteration = ?, ci_iterations = ?, review_iterations = ?,
                last_activity = ?, pr_number = ?, current_sha = ?, last_ci_result = ?,
                last_review_score = ?, error = ?, human_approved = ?
            WHERE id = ?
            """,
            (
                state.mode.value,
                state.phase.value,
                state.iteration,
                state.ci_iterations,
                state.review_iterations,
                state.last_activity.isoformat(),
                state.pr_number,
                state.current_sha,
                json.dumps(state.last_ci_result.model_dump()) if state.last_ci_result else None,
                state.last_review_score,
                state.error,
                1 if state.human_approved else 0,
                state.id,
            ),
        )
        await self.db.connection.commit()

    async def list_active(self) -> builtins.list[AgenticState]:
        """List all active (non-completed, non-failed) agentic runs."""
        cursor = await self.db.connection.execute(
            """
            SELECT * FROM agentic_runs
            WHERE phase NOT IN ('completed', 'failed')
            ORDER BY started_at DESC
            """
        )
        rows = await cursor.fetchall()
        return [self._row_to_model(row) for row in rows]

    def _row_to_model(self, row: Any) -> AgenticState:
        """Convert database row to AgenticState model."""
        return row_to_model(
            AgenticState,
            row,
            json_fields={"last_ci_result"},
            defaults={"human_approved": 0},
        )


class CICheckDAO:
    """DAO for CICheck."""

    def __init__(self, db: Database):
        self.db = db

    async def create(
        self,
        task_id: str,
        pr_id: str,
        status: str,
        workflow_run_id: int | None = None,
        sha: str | None = None,
        jobs: dict[str, str] | None = None,
        failed_jobs: builtins.list[CIJobResult] | None = None,
    ) -> CICheck:
        """Create a new CI check record."""
        id = generate_id()
        now = now_iso()

        await self.db.connection.execute(
            """
            INSERT INTO ci_checks (
                id, task_id, pr_id, status, workflow_run_id, sha,
                jobs, failed_jobs, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id,
                task_id,
                pr_id,
                status,
                workflow_run_id,
                sha,
                json.dumps(jobs or {}),
                json.dumps([fj.model_dump() for fj in (failed_jobs or [])]),
                now,
                now,
            ),
        )
        await self.db.connection.commit()

        return CICheck(
            id=id,
            task_id=task_id,
            pr_id=pr_id,
            status=status,
            workflow_run_id=workflow_run_id,
            sha=sha,
            jobs=jobs or {},
            failed_jobs=failed_jobs or [],
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    async def get(self, id: str) -> CICheck | None:
        """Get a CI check by ID."""
        cursor = await self.db.connection.execute("SELECT * FROM ci_checks WHERE id = ?", (id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_model(row)

    async def get_latest_by_pr_id(self, pr_id: str) -> CICheck | None:
        """Get the latest CI check for a PR."""
        cursor = await self.db.connection.execute(
            "SELECT * FROM ci_checks WHERE pr_id = ? ORDER BY created_at DESC LIMIT 1",
            (pr_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_model(row)

    async def get_by_pr_and_sha(self, pr_id: str, sha: str) -> CICheck | None:
        """Get a CI check for a specific PR and SHA combination."""
        cursor = await self.db.connection.execute(
            "SELECT * FROM ci_checks WHERE pr_id = ? AND sha = ? LIMIT 1",
            (pr_id, sha),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_model(row)

    async def get_latest_pending_by_pr_id(self, pr_id: str) -> CICheck | None:
        """Get the latest pending CI check for a PR (regardless of SHA).

        This is used when SHA is not yet available to avoid creating duplicate
        pending records.
        """
        cursor = await self.db.connection.execute(
            """
            SELECT * FROM ci_checks
            WHERE pr_id = ? AND status = 'pending'
            ORDER BY created_at DESC LIMIT 1
            """,
            (pr_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_model(row)

    async def list_by_task_id(self, task_id: str) -> builtins.list[CICheck]:
        """List all CI checks for a task.

        Note: Deduplication by SHA is handled in the frontend to avoid
        complex SQL that may cause issues in some scenarios.
        """
        cursor = await self.db.connection.execute(
            "SELECT * FROM ci_checks WHERE task_id = ? ORDER BY created_at DESC",
            (task_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_model(row) for row in rows]

    async def update(
        self,
        id: str,
        status: str,
        workflow_run_id: int | None = None,
        sha: str | None = None,
        jobs: dict[str, str] | None = None,
        failed_jobs: builtins.list[CIJobResult] | None = None,
    ) -> CICheck | None:
        """Update a CI check record."""
        updates = ["status = ?", "updated_at = ?"]
        params: builtins.list[Any] = [status, now_iso()]

        if workflow_run_id is not None:
            updates.append("workflow_run_id = ?")
            params.append(workflow_run_id)
        if sha is not None:
            updates.append("sha = ?")
            params.append(sha)
        if jobs is not None:
            updates.append("jobs = ?")
            params.append(json.dumps(jobs))
        if failed_jobs is not None:
            updates.append("failed_jobs = ?")
            params.append(json.dumps([fj.model_dump() for fj in failed_jobs]))

        params.append(id)

        await self.db.connection.execute(
            f"UPDATE ci_checks SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await self.db.connection.commit()

        return await self.get(id)

    def _row_to_model(self, row: Any) -> CICheck:
        """Convert database row to CICheck model."""
        return row_to_model(
            CICheck,
            row,
            json_fields={"jobs", "failed_jobs"},
            defaults={"jobs": {}, "failed_jobs": []},
        )


class MetricsDAO:
    """DAO for aggregating metrics data from various tables."""

    def __init__(self, db: Database):
        self.db = db

    async def get_pr_metrics(
        self,
        period_start: datetime,
        period_end: datetime,
        repo_id: str | None = None,
    ) -> dict[str, Any]:
        """Get PR metrics for a period."""
        params: builtins.list[Any] = [period_start.isoformat(), period_end.isoformat()]
        repo_filter = ""
        if repo_id:
            repo_filter = " AND task_id IN (SELECT id FROM tasks WHERE repo_id = ?)"
            params.append(repo_id)

        query = f"""
            SELECT
                COUNT(*) as total_prs,
                SUM(CASE WHEN status = 'merged' THEN 1 ELSE 0 END) as merged_prs,
                SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed_prs,
                SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_prs,
                AVG(
                    CASE WHEN status = 'merged'
                    THEN (julianday(updated_at) - julianday(created_at)) * 24
                    END
                ) as avg_time_to_merge_hours
            FROM prs
            WHERE created_at >= ? AND created_at < ?{repo_filter}
        """
        cursor = await self.db.connection.execute(query, params)
        row = await cursor.fetchone()
        if row is None:
            return {
                "total_prs": 0,
                "merged_prs": 0,
                "closed_prs": 0,
                "open_prs": 0,
                "avg_time_to_merge_hours": None,
            }
        return {
            "total_prs": row["total_prs"] or 0,
            "merged_prs": row["merged_prs"] or 0,
            "closed_prs": row["closed_prs"] or 0,
            "open_prs": row["open_prs"] or 0,
            "avg_time_to_merge_hours": row["avg_time_to_merge_hours"],
        }

    async def get_message_metrics(
        self,
        period_start: datetime,
        period_end: datetime,
        repo_id: str | None = None,
    ) -> dict[str, Any]:
        """Get message/conversation metrics for a period."""
        params: builtins.list[Any] = [period_start.isoformat(), period_end.isoformat()]
        repo_filter = ""
        if repo_id:
            repo_filter = " AND task_id IN (SELECT id FROM tasks WHERE repo_id = ?)"
            params.append(repo_id)

        query = f"""
            SELECT
                COUNT(*) as total_messages,
                SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) as user_messages,
                SUM(CASE WHEN role = 'assistant' THEN 1 ELSE 0 END) as assistant_messages
            FROM messages
            WHERE created_at >= ? AND created_at < ?{repo_filter}
        """
        cursor = await self.db.connection.execute(query, params)
        row = await cursor.fetchone()
        if row is None:
            return {
                "total_messages": 0,
                "user_messages": 0,
                "assistant_messages": 0,
            }
        return {
            "total_messages": row["total_messages"] or 0,
            "user_messages": row["user_messages"] or 0,
            "assistant_messages": row["assistant_messages"] or 0,
        }

    async def get_run_metrics(
        self,
        period_start: datetime,
        period_end: datetime,
        repo_id: str | None = None,
    ) -> dict[str, Any]:
        """Get run execution metrics for a period."""
        params: builtins.list[Any] = [period_start.isoformat(), period_end.isoformat()]
        repo_filter = ""
        if repo_id:
            repo_filter = " AND task_id IN (SELECT id FROM tasks WHERE repo_id = ?)"
            params.append(repo_id)

        query = f"""
            SELECT
                COUNT(*) as total_runs,
                SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END) as succeeded_runs,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_runs,
                SUM(CASE WHEN status = 'canceled' THEN 1 ELSE 0 END) as canceled_runs,
                AVG(
                    CASE WHEN completed_at IS NOT NULL AND started_at IS NOT NULL
                    THEN (julianday(completed_at) - julianday(started_at)) * 24 * 3600
                    END
                ) as avg_run_duration_seconds,
                AVG(
                    CASE WHEN started_at IS NOT NULL
                    THEN (julianday(started_at) - julianday(created_at)) * 24 * 3600
                    END
                ) as avg_queue_wait_seconds
            FROM runs
            WHERE created_at >= ? AND created_at < ?{repo_filter}
        """
        cursor = await self.db.connection.execute(query, params)
        row = await cursor.fetchone()
        if row is None:
            return {
                "total_runs": 0,
                "succeeded_runs": 0,
                "failed_runs": 0,
                "canceled_runs": 0,
                "avg_run_duration_seconds": None,
                "avg_queue_wait_seconds": None,
            }
        return {
            "total_runs": row["total_runs"] or 0,
            "succeeded_runs": row["succeeded_runs"] or 0,
            "failed_runs": row["failed_runs"] or 0,
            "canceled_runs": row["canceled_runs"] or 0,
            "avg_run_duration_seconds": row["avg_run_duration_seconds"],
            "avg_queue_wait_seconds": row["avg_queue_wait_seconds"],
        }

    async def get_executor_distribution(
        self,
        period_start: datetime,
        period_end: datetime,
        repo_id: str | None = None,
    ) -> builtins.list[dict[str, Any]]:
        """Get distribution of runs by executor type."""
        params: builtins.list[Any] = [period_start.isoformat(), period_end.isoformat()]
        repo_filter = ""
        if repo_id:
            repo_filter = " AND task_id IN (SELECT id FROM tasks WHERE repo_id = ?)"
            params.append(repo_id)

        query = f"""
            SELECT
                executor_type,
                COUNT(*) as count
            FROM runs
            WHERE created_at >= ? AND created_at < ?{repo_filter}
            GROUP BY executor_type
        """
        cursor = await self.db.connection.execute(query, params)
        rows = await cursor.fetchall()
        return [{"executor_type": row["executor_type"], "count": row["count"]} for row in rows]

    async def get_ci_metrics(
        self,
        period_start: datetime,
        period_end: datetime,
        repo_id: str | None = None,
    ) -> dict[str, Any]:
        """Get CI check metrics for a period."""
        params: builtins.list[Any] = [period_start.isoformat(), period_end.isoformat()]
        repo_filter = ""
        if repo_id:
            repo_filter = " AND task_id IN (SELECT id FROM tasks WHERE repo_id = ?)"
            params.append(repo_id)

        query = f"""
            SELECT
                COUNT(*) as total_ci_checks,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as passed_ci_checks,
                SUM(CASE WHEN status = 'failure' THEN 1 ELSE 0 END) as failed_ci_checks
            FROM ci_checks
            WHERE created_at >= ? AND created_at < ?{repo_filter}
        """
        cursor = await self.db.connection.execute(query, params)
        row = await cursor.fetchone()
        if row is None:
            return {
                "total_ci_checks": 0,
                "passed_ci_checks": 0,
                "failed_ci_checks": 0,
            }
        return {
            "total_ci_checks": row["total_ci_checks"] or 0,
            "passed_ci_checks": row["passed_ci_checks"] or 0,
            "failed_ci_checks": row["failed_ci_checks"] or 0,
        }

    async def get_review_metrics(
        self,
        period_start: datetime,
        period_end: datetime,
        repo_id: str | None = None,
    ) -> dict[str, Any]:
        """Get code review metrics for a period."""
        params: builtins.list[Any] = [period_start.isoformat(), period_end.isoformat()]
        repo_filter = ""
        if repo_id:
            repo_filter = " AND task_id IN (SELECT id FROM tasks WHERE repo_id = ?)"
            params.append(repo_id)

        query = f"""
            SELECT
                COUNT(*) as total_reviews,
                AVG(overall_score) as avg_review_score
            FROM reviews
            WHERE created_at >= ? AND created_at < ?{repo_filter}
        """
        cursor = await self.db.connection.execute(query, params)
        row = await cursor.fetchone()

        # Get severity distribution from feedbacks
        feedback_query = f"""
            SELECT
                SUM(CASE WHEN f.severity = 'critical' THEN 1 ELSE 0 END) as critical_issues,
                SUM(CASE WHEN f.severity = 'high' THEN 1 ELSE 0 END) as high_issues,
                SUM(CASE WHEN f.severity = 'medium' THEN 1 ELSE 0 END) as medium_issues,
                SUM(CASE WHEN f.severity = 'low' THEN 1 ELSE 0 END) as low_issues
            FROM review_feedbacks f
            JOIN reviews r ON f.review_id = r.id
            WHERE r.created_at >= ? AND r.created_at < ?{repo_filter}
        """
        feedback_cursor = await self.db.connection.execute(feedback_query, params)
        feedback_row = await feedback_cursor.fetchone()

        if row is None or feedback_row is None:
            return {
                "total_reviews": 0,
                "avg_review_score": None,
                "critical_issues": 0,
                "high_issues": 0,
                "medium_issues": 0,
                "low_issues": 0,
            }
        return {
            "total_reviews": row["total_reviews"] or 0,
            "avg_review_score": row["avg_review_score"],
            "critical_issues": feedback_row["critical_issues"] or 0,
            "high_issues": feedback_row["high_issues"] or 0,
            "medium_issues": feedback_row["medium_issues"] or 0,
            "low_issues": feedback_row["low_issues"] or 0,
        }

    async def get_agentic_metrics(
        self,
        period_start: datetime,
        period_end: datetime,
        repo_id: str | None = None,
    ) -> dict[str, Any]:
        """Get agentic execution metrics for a period."""
        params: builtins.list[Any] = [period_start.isoformat(), period_end.isoformat()]
        repo_filter = ""
        if repo_id:
            repo_filter = " AND task_id IN (SELECT id FROM tasks WHERE repo_id = ?)"
            params.append(repo_id)

        query = f"""
            SELECT
                COUNT(*) as total_agentic_runs,
                SUM(CASE WHEN phase = 'completed' THEN 1 ELSE 0 END) as completed_agentic_runs,
                SUM(CASE WHEN phase = 'failed' THEN 1 ELSE 0 END) as failed_agentic_runs,
                AVG(iteration) as avg_total_iterations,
                AVG(ci_iterations) as avg_ci_iterations,
                AVG(review_iterations) as avg_review_iterations
            FROM agentic_runs
            WHERE started_at >= ? AND started_at < ?{repo_filter}
        """
        cursor = await self.db.connection.execute(query, params)
        row = await cursor.fetchone()
        if row is None:
            return {
                "total_agentic_runs": 0,
                "completed_agentic_runs": 0,
                "failed_agentic_runs": 0,
                "avg_total_iterations": 0.0,
                "avg_ci_iterations": 0.0,
                "avg_review_iterations": 0.0,
            }
        return {
            "total_agentic_runs": row["total_agentic_runs"] or 0,
            "completed_agentic_runs": row["completed_agentic_runs"] or 0,
            "failed_agentic_runs": row["failed_agentic_runs"] or 0,
            "avg_total_iterations": row["avg_total_iterations"] or 0.0,
            "avg_ci_iterations": row["avg_ci_iterations"] or 0.0,
            "avg_review_iterations": row["avg_review_iterations"] or 0.0,
        }

    async def get_task_count(
        self,
        period_start: datetime,
        period_end: datetime,
        repo_id: str | None = None,
    ) -> int:
        """Get task count for a period."""
        params: builtins.list[Any] = [period_start.isoformat(), period_end.isoformat()]
        repo_filter = ""
        if repo_id:
            repo_filter = " AND repo_id = ?"
            params.append(repo_id)

        query = f"""
            SELECT COUNT(*) as count
            FROM tasks
            WHERE created_at >= ? AND created_at < ?{repo_filter}
        """
        cursor = await self.db.connection.execute(query, params)
        row = await cursor.fetchone()
        if row is None:
            return 0
        return row["count"] or 0

    async def get_tasks_with_single_run_count(
        self,
        period_start: datetime,
        period_end: datetime,
        repo_id: str | None = None,
    ) -> int:
        """Get count of tasks that succeeded with single run."""
        params: builtins.list[Any] = [period_start.isoformat(), period_end.isoformat()]
        repo_filter = ""
        if repo_id:
            repo_filter = " AND t.repo_id = ?"
            params.append(repo_id)

        query = f"""
            SELECT COUNT(*) as count
            FROM tasks t
            WHERE t.created_at >= ? AND t.created_at < ?{repo_filter}
            AND (
                SELECT COUNT(*) FROM runs r WHERE r.task_id = t.id
            ) = 1
            AND EXISTS (
                SELECT 1 FROM runs r WHERE r.task_id = t.id AND r.status = 'succeeded'
            )
        """
        cursor = await self.db.connection.execute(query, params)
        row = await cursor.fetchone()
        if row is None:
            return 0
        return row["count"] or 0

    async def get_cycle_times(
        self,
        period_start: datetime,
        period_end: datetime,
        repo_id: str | None = None,
    ) -> builtins.list[float]:
        """Get cycle times (task creation to PR merge) in hours."""
        params: builtins.list[Any] = [period_start.isoformat(), period_end.isoformat()]
        repo_filter = ""
        if repo_id:
            repo_filter = " AND t.repo_id = ?"
            params.append(repo_id)

        query = f"""
            SELECT
                (julianday(p.updated_at) - julianday(t.created_at)) * 24 as cycle_time_hours
            FROM tasks t
            JOIN prs p ON p.task_id = t.id
            WHERE p.status = 'merged'
            AND p.updated_at >= ? AND p.updated_at < ?{repo_filter}
        """
        cursor = await self.db.connection.execute(query, params)
        rows = await cursor.fetchall()
        return [row["cycle_time_hours"] for row in rows if row["cycle_time_hours"] is not None]

    async def get_realtime_metrics(self, repo_id: str | None = None) -> dict[str, Any]:
        """Get current real-time metrics."""
        repo_filter = ""
        task_repo_filter = ""
        if repo_id:
            repo_filter = " AND task_id IN (SELECT id FROM tasks WHERE repo_id = ?)"
            task_repo_filter = " AND repo_id = ?"

        # Active tasks (kanban_status = 'todo' or computed in_progress)
        active_query = f"""
            SELECT COUNT(*) as count
            FROM tasks
            WHERE kanban_status = 'todo'{task_repo_filter}
        """
        cursor = await self.db.connection.execute(active_query, [repo_id] if repo_id else [])
        active_row = await cursor.fetchone()

        # Running runs
        running_query = f"""
            SELECT COUNT(*) as count
            FROM runs
            WHERE status = 'running'{repo_filter}
        """
        cursor = await self.db.connection.execute(running_query, [repo_id] if repo_id else [])
        running_row = await cursor.fetchone()

        # Pending CI checks
        ci_query = f"""
            SELECT COUNT(*) as count
            FROM ci_checks
            WHERE status = 'pending'{repo_filter}
        """
        cursor = await self.db.connection.execute(ci_query, [repo_id] if repo_id else [])
        ci_row = await cursor.fetchone()

        # Open PRs
        open_pr_query = f"""
            SELECT COUNT(*) as count
            FROM prs
            WHERE status = 'open'{repo_filter}
        """
        cursor = await self.db.connection.execute(open_pr_query, [repo_id] if repo_id else [])
        open_pr_row = await cursor.fetchone()

        # Today's stats
        today = datetime.utcnow().date().isoformat()
        today_task_params = [today]
        today_params = [today]
        if repo_id:
            today_task_params.append(repo_id)
            today_params.append(repo_id)

        tasks_today_query = f"""
            SELECT COUNT(*) as count
            FROM tasks
            WHERE date(created_at) = ?{task_repo_filter}
        """
        cursor = await self.db.connection.execute(tasks_today_query, today_task_params)
        tasks_today_row = await cursor.fetchone()

        runs_today_query = f"""
            SELECT COUNT(*) as count
            FROM runs
            WHERE date(completed_at) = ?
            AND status IN ('succeeded', 'failed', 'canceled'){repo_filter}
        """
        cursor = await self.db.connection.execute(runs_today_query, today_params)
        runs_today_row = await cursor.fetchone()

        prs_merged_query = f"""
            SELECT COUNT(*) as count
            FROM prs
            WHERE status = 'merged'
            AND date(updated_at) = ?{repo_filter}
        """
        cursor = await self.db.connection.execute(prs_merged_query, today_params)
        prs_merged_row = await cursor.fetchone()

        return {
            "active_tasks": (active_row["count"] or 0) if active_row else 0,
            "running_runs": (running_row["count"] or 0) if running_row else 0,
            "pending_ci_checks": (ci_row["count"] or 0) if ci_row else 0,
            "open_prs": (open_pr_row["count"] or 0) if open_pr_row else 0,
            "tasks_created_today": (tasks_today_row["count"] or 0) if tasks_today_row else 0,
            "runs_completed_today": (runs_today_row["count"] or 0) if runs_today_row else 0,
            "prs_merged_today": (prs_merged_row["count"] or 0) if prs_merged_row else 0,
        }

    async def get_trend_data(
        self,
        metric_name: str,
        period_start: datetime,
        period_end: datetime,
        granularity: str = "day",
        repo_id: str | None = None,
    ) -> builtins.list[dict[str, Any]]:
        """Get trend data for a specific metric.

        Args:
            metric_name: Name of the metric (e.g., 'merge_rate', 'run_success_rate')
            period_start: Start of the period
            period_end: End of the period
            granularity: 'hour', 'day', or 'week'
            repo_id: Optional repository filter

        Returns:
            List of data points with timestamp and value
        """
        date_format = {
            "hour": "%Y-%m-%d %H:00:00",
            "day": "%Y-%m-%d",
            "week": "%Y-%W",
        }.get(granularity, "%Y-%m-%d")

        params: builtins.list[Any] = [period_start.isoformat(), period_end.isoformat()]
        repo_filter = ""
        if repo_id:
            repo_filter = " AND task_id IN (SELECT id FROM tasks WHERE repo_id = ?)"
            params.append(repo_id)

        if metric_name == "merge_rate":
            query = f"""
                SELECT
                    strftime('{date_format}', created_at) as period,
                    CAST(SUM(CASE WHEN status = 'merged' THEN 1 ELSE 0 END) AS REAL) /
                        NULLIF(COUNT(*), 0) * 100 as value
                FROM prs
                WHERE created_at >= ? AND created_at < ?{repo_filter}
                GROUP BY period
                ORDER BY period
            """
        elif metric_name == "run_success_rate":
            query = f"""
                SELECT
                    strftime('{date_format}', created_at) as period,
                    CAST(SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END) AS REAL) /
                        NULLIF(COUNT(*), 0) * 100 as value
                FROM runs
                WHERE created_at >= ? AND created_at < ?{repo_filter}
                GROUP BY period
                ORDER BY period
            """
        elif metric_name == "throughput":
            query = f"""
                SELECT
                    strftime('{date_format}', updated_at) as period,
                    COUNT(*) as value
                FROM prs
                WHERE status = 'merged'
                AND updated_at >= ? AND updated_at < ?{repo_filter}
                GROUP BY period
                ORDER BY period
            """
        elif metric_name == "messages_per_task":
            query = f"""
                SELECT
                    strftime('{date_format}', m.created_at) as period,
                    CAST(COUNT(*) AS REAL) /
                        NULLIF((SELECT COUNT(DISTINCT task_id) FROM messages
                         WHERE created_at >= ? AND created_at < ?), 0) as value
                FROM messages m
                WHERE m.created_at >= ? AND m.created_at < ?{repo_filter}
                GROUP BY period
                ORDER BY period
            """
            # For messages_per_task, we need extra params
            params = [
                period_start.isoformat(),
                period_end.isoformat(),
                period_start.isoformat(),
                period_end.isoformat(),
            ]
            if repo_id:
                params.append(repo_id)
        else:
            return []

        cursor = await self.db.connection.execute(query, params)
        rows = await cursor.fetchall()
        return [{"timestamp": row["period"], "value": row["value"] or 0.0} for row in rows]
