"""Base service class for all AI Role services.

This module provides the abstract base class that all AI Role services
(RunService, ReviewService, BreakdownService, etc.) inherit from.
It consolidates common patterns like executor management, queue-based
execution, log streaming, and status lifecycle management.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Coroutine
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from tazuna_api.config import settings
from tazuna_api.domain.enums import ExecutorType, RoleExecutionStatus
from tazuna_api.domain.models import RoleExecutionResult
from tazuna_api.executors.claude_code_executor import ClaudeCodeExecutor, ClaudeCodeOptions
from tazuna_api.executors.codex_executor import CodexExecutor, CodexOptions
from tazuna_api.executors.gemini_executor import GeminiExecutor, GeminiOptions

if TYPE_CHECKING:
    from tazuna_api.services.output_manager import OutputLine, OutputManager

logger = logging.getLogger(__name__)

# Type variables for generic role service
TRecord = TypeVar("TRecord")  # Role record type (Run, Review, etc.)
TCreate = TypeVar("TCreate")  # Role creation request type
TResult = TypeVar("TResult", bound=RoleExecutionResult)  # Role result type


class RoleQueueAdapter:
    """In-memory queue adapter for role execution with concurrency control.

    Features:
    - Concurrency limit via semaphore to prevent resource exhaustion
    - Execution timeout to prevent tasks from hanging indefinitely
    - Automatic cleanup of completed tasks to prevent memory leaks

    Can be replaced with distributed task queues (Celery/RQ/Redis) for scaling.
    """

    def __init__(
        self,
        max_concurrent: int | None = None,
        default_timeout: int | None = None,
    ) -> None:
        """Initialize the queue adapter.

        Args:
            max_concurrent: Maximum concurrent task executions.
                           Defaults to settings.queue_max_concurrent_tasks.
            default_timeout: Default timeout in seconds for task execution.
                            Defaults to settings.queue_task_timeout_seconds.
        """
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._max_concurrent = max_concurrent or settings.queue_max_concurrent_tasks
        self._default_timeout = default_timeout or settings.queue_task_timeout_seconds
        self._semaphore = asyncio.Semaphore(self._max_concurrent)

    def enqueue(
        self,
        record_id: str,
        coro: Callable[[], Coroutine[Any, Any, None]],
        timeout: int | None = None,
    ) -> None:
        """Enqueue a role execution with concurrency control and timeout.

        Args:
            record_id: Unique identifier for the execution record.
            coro: Coroutine factory to execute.
            timeout: Optional timeout override in seconds.
        """
        task_timeout = timeout or self._default_timeout

        async def wrapped_execution() -> None:
            """Execute with semaphore-based concurrency control and timeout."""
            async with self._semaphore:
                try:
                    await asyncio.wait_for(coro(), timeout=task_timeout)
                except TimeoutError:
                    logger.error(f"Role execution {record_id} timed out after {task_timeout}s")
                    raise
                except asyncio.CancelledError:
                    logger.info(f"Role execution {record_id} was cancelled")
                    raise
                except Exception as e:
                    logger.error(f"Role execution {record_id} failed with error: {e}")
                    raise
                finally:
                    # Cleanup completed task from memory if configured
                    if settings.queue_cleanup_completed_tasks:
                        self._cleanup_task(record_id)

        task: asyncio.Task[None] = asyncio.create_task(wrapped_execution())
        self._tasks[record_id] = task

    def _cleanup_task(self, record_id: str) -> None:
        """Remove completed task from internal tracking.

        Args:
            record_id: Record ID to clean up.
        """
        if record_id in self._tasks:
            del self._tasks[record_id]
            logger.debug(f"Cleaned up role execution {record_id} from queue")

    def cancel(self, record_id: str) -> bool:
        """Cancel a queued execution.

        Args:
            record_id: Record ID to cancel.

        Returns:
            True if cancelled, False if not found or already completed.
        """
        task = self._tasks.get(record_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def is_running(self, record_id: str) -> bool:
        """Check if an execution is currently running.

        Args:
            record_id: Record ID to check.

        Returns:
            True if running.
        """
        task = self._tasks.get(record_id)
        return task is not None and not task.done()

    def get_queue_stats(self) -> dict[str, int]:
        """Get queue statistics for monitoring.

        Returns:
            Dictionary with queue statistics.
        """
        running = sum(1 for t in self._tasks.values() if not t.done())
        pending = len(self._tasks) - running
        return {
            "max_concurrent": self._max_concurrent,
            "running": running,
            "pending": pending,
            "total_tracked": len(self._tasks),
        }


# Type alias for executor types
BaseExecutor = ClaudeCodeExecutor | CodexExecutor | GeminiExecutor


class BaseRoleService(ABC, Generic[TRecord, TCreate, TResult]):
    """Abstract base class for all AI Role services.

    Provides common functionality:
    - Executor management (Claude Code, Codex, Gemini CLIs)
    - Queue-based async execution
    - Log streaming via OutputManager
    - Status lifecycle management (QUEUED → RUNNING → SUCCEEDED/FAILED)

    Subclasses must implement:
    - create(): Create a record and enqueue execution
    - get(): Retrieve a record by ID
    - list_by_task(): List records for a task
    - _execute(): Role-specific execution logic
    - _update_status(): Update record status
    - _get_record_id(): Extract ID from record
    - _create_error_result(): Create error result
    """

    def __init__(
        self,
        output_manager: OutputManager | None = None,
        claude_executor: ClaudeCodeExecutor | None = None,
        codex_executor: CodexExecutor | None = None,
        gemini_executor: GeminiExecutor | None = None,
    ):
        """Initialize the base role service.

        Args:
            output_manager: Manager for log streaming.
            claude_executor: Claude Code CLI executor (created if not provided).
            codex_executor: Codex CLI executor (created if not provided).
            gemini_executor: Gemini CLI executor (created if not provided).
        """
        self.output_manager = output_manager

        # Initialize executors
        self._executors: dict[ExecutorType, BaseExecutor] = {}

        # Create default executors if not provided
        if claude_executor:
            self._executors[ExecutorType.CLAUDE_CODE] = claude_executor
        else:
            self._executors[ExecutorType.CLAUDE_CODE] = ClaudeCodeExecutor(
                ClaudeCodeOptions(claude_cli_path=settings.claude_cli_path)
            )

        if codex_executor:
            self._executors[ExecutorType.CODEX_CLI] = codex_executor
        else:
            self._executors[ExecutorType.CODEX_CLI] = CodexExecutor(
                CodexOptions(codex_cli_path=settings.codex_cli_path)
            )

        if gemini_executor:
            self._executors[ExecutorType.GEMINI_CLI] = gemini_executor
        else:
            self._executors[ExecutorType.GEMINI_CLI] = GeminiExecutor(
                GeminiOptions(gemini_cli_path=settings.gemini_cli_path)
            )

        # Queue for async execution
        self._queue = RoleQueueAdapter()

    # ==========================================
    # Common Methods (available to subclasses)
    # ==========================================

    def get_executor(self, executor_type: ExecutorType) -> BaseExecutor:
        """Get the executor for the specified type.

        Args:
            executor_type: Type of executor to retrieve.

        Returns:
            The executor instance.

        Raises:
            ValueError: If executor type is not available.
        """
        executor = self._executors.get(executor_type)
        if not executor:
            raise ValueError(f"Executor not available: {executor_type}")
        return executor

    def enqueue_execution(
        self,
        record_id: str,
        coro_factory: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        """Enqueue an execution to the queue.

        Args:
            record_id: Unique identifier for the execution.
            coro_factory: Factory that creates the coroutine to execute.
        """
        self._queue.enqueue(record_id, coro_factory)

    def cancel_execution(self, record_id: str) -> bool:
        """Cancel a queued or running execution.

        Args:
            record_id: ID of the execution to cancel.

        Returns:
            True if cancelled successfully.
        """
        return self._queue.cancel(record_id)

    def is_execution_running(self, record_id: str) -> bool:
        """Check if an execution is currently running.

        Args:
            record_id: ID to check.

        Returns:
            True if running.
        """
        return self._queue.is_running(record_id)

    async def publish_log(self, record_id: str, message: str) -> None:
        """Publish a log message for streaming.

        Args:
            record_id: ID of the record.
            message: Log message to publish.
        """
        if self.output_manager:
            await self.output_manager.publish_async(record_id, message)

    async def mark_log_complete(self, record_id: str) -> None:
        """Mark log streaming as complete.

        Args:
            record_id: ID of the record.
        """
        if self.output_manager:
            await self.output_manager.mark_complete(record_id)

    async def get_streaming_logs(
        self,
        record_id: str,
        from_line: int = 0,
    ) -> tuple[list[OutputLine], bool]:
        """Get log history for a record from OutputManager.

        This is a utility method for accessing streaming logs.
        Subclasses may implement their own `get_logs` method with
        different return types.

        Args:
            record_id: ID of the record.
            from_line: Line number to start from.

        Returns:
            Tuple of (log lines, is_complete).
        """
        if not self.output_manager:
            return [], True

        history = await self.output_manager.get_history(record_id, from_line)
        is_complete = await self.output_manager.is_complete(record_id)
        return history, is_complete

    def create_log_callback(self, record_id: str) -> Callable[[str], Awaitable[None]]:
        """Create a callback for logging output.

        Args:
            record_id: ID of the record.

        Returns:
            Async callback function for logging.
        """

        async def callback(message: str) -> None:
            await self.publish_log(record_id, message)

        return callback

    # ==========================================
    # Template Method (execution lifecycle)
    # ==========================================

    async def _execute_with_lifecycle(self, record: TRecord) -> None:
        """Execute with common lifecycle management.

        This template method implements the common execution pattern:
        1. Update status to RUNNING
        2. Execute role-specific logic
        3. Update status based on result (SUCCEEDED/FAILED)
        4. Mark log streaming complete

        Args:
            record: The record to execute.
        """
        record_id = self._get_record_id(record)

        try:
            # Update status to RUNNING
            await self._update_status(record_id, RoleExecutionStatus.RUNNING)
            await self.publish_log(record_id, "Execution started...")

            # Execute role-specific logic
            result = await self._execute(record)

            # Update status based on result
            if result.success:
                await self._update_status(record_id, RoleExecutionStatus.SUCCEEDED, result)
                await self.publish_log(record_id, "Execution completed successfully.")
            else:
                await self._update_status(record_id, RoleExecutionStatus.FAILED, result)
                error_msg = result.error or "Unknown error"
                await self.publish_log(record_id, f"Execution failed: {error_msg}")

        except asyncio.CancelledError:
            # Handle cancellation
            error_result = self._create_error_result("Execution cancelled")
            await self._update_status(record_id, RoleExecutionStatus.CANCELED, error_result)
            await self.publish_log(record_id, "Execution cancelled.")
            raise

        except Exception as e:
            # Handle unexpected errors
            logger.exception(f"Execution error for {record_id}: {e}")
            error_result = self._create_error_result(str(e))
            await self._update_status(record_id, RoleExecutionStatus.FAILED, error_result)
            await self.publish_log(record_id, f"Execution error: {e}")

        finally:
            await self.mark_log_complete(record_id)

    # ==========================================
    # Abstract Methods (must be implemented)
    # ==========================================

    @abstractmethod
    async def create(self, task_id: str, data: TCreate) -> TRecord:
        """Create a record and enqueue execution.

        Args:
            task_id: ID of the parent task.
            data: Creation request data.

        Returns:
            The created record.
        """
        ...

    @abstractmethod
    async def get(self, record_id: str) -> TRecord | None:
        """Get a record by ID.

        Args:
            record_id: ID of the record.

        Returns:
            The record if found, None otherwise.
        """
        ...

    @abstractmethod
    async def list_by_task(self, task_id: str) -> list[TRecord]:
        """List all records for a task.

        Args:
            task_id: ID of the task.

        Returns:
            List of records.
        """
        ...

    @abstractmethod
    async def _execute(self, record: TRecord) -> TResult:
        """Execute role-specific logic.

        Args:
            record: The record to execute.

        Returns:
            Role-specific result.
        """
        ...

    @abstractmethod
    async def _update_status(
        self,
        record_id: str,
        status: RoleExecutionStatus,
        result: TResult | None = None,
    ) -> None:
        """Update record status and optionally save result.

        Args:
            record_id: ID of the record.
            status: New status.
            result: Optional result to save.
        """
        ...

    @abstractmethod
    def _get_record_id(self, record: TRecord) -> str:
        """Extract ID from a record.

        Args:
            record: The record.

        Returns:
            The record's ID.
        """
        ...

    @abstractmethod
    def _create_error_result(self, error: str) -> TResult:
        """Create an error result.

        Args:
            error: Error message.

        Returns:
            Error result instance.
        """
        ...
