'use client';

import Link from 'next/link';
import type { TaskWithKanbanStatus, TaskKanbanStatus, ExecutorRunStatus, ExecutorType } from '@/types';
import { PlayIcon, CheckIcon, CodeBracketIcon, CheckCircleIcon, XCircleIcon, ClockIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';

interface KanbanCardProps {
  task: TaskWithKanbanStatus;
  columnStatus: TaskKanbanStatus;
  onMoveToTodo: (taskId: string) => void;
  onMoveToBacklog: (taskId: string) => void;
  onArchive: (taskId: string) => void;
  onUnarchive: (taskId: string) => void;
  onStartTask?: (task: TaskWithKanbanStatus) => void;
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();

  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString();
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg
      className={cn('animate-spin', className)}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

const EXECUTOR_DISPLAY_NAMES: Record<ExecutorType, string> = {
  claude_code: 'Claude',
  codex_cli: 'Codex',
  gemini_cli: 'Gemini',
  patch_agent: 'Patch',
};

/**
 * InReview status badge showing CI/PR status at a glance
 */
function InReviewStatusBadge({ task }: { task: TaskWithKanbanStatus }) {
  const { pr_count, latest_ci_status } = task;

  // No PR created
  if (pr_count === 0) {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-700 text-gray-300">
        <ExclamationTriangleIcon className="w-3 h-3" />
        No PR
      </span>
    );
  }

  // CI passed
  if (latest_ci_status === 'success') {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-green-900/50 text-green-400">
        <CheckCircleIcon className="w-3 h-3" />
        CI Passed
      </span>
    );
  }

  // CI failed
  if (latest_ci_status === 'failure' || latest_ci_status === 'error') {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-900/50 text-red-400">
        <XCircleIcon className="w-3 h-3" />
        CI Failed
      </span>
    );
  }

  // CI pending
  if (latest_ci_status === 'pending') {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-yellow-900/50 text-yellow-400">
        <ClockIcon className="w-3 h-3" />
        CI Running
      </span>
    );
  }

  // PR exists but no CI status (CI not checked yet)
  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-purple-900/50 text-purple-400">
      <CodeBracketIcon className="w-3 h-3" />
      PR Open
    </span>
  );
}

function ExecutorStatusIndicator({ status }: { status: ExecutorRunStatus }) {
  const displayName = EXECUTOR_DISPLAY_NAMES[status.executor_type];

  // No run exists for this executor
  if (!status.run_id || !status.status) {
    return (
      <div className="flex items-center gap-1 text-gray-600">
        <span className="w-2 h-2 rounded-full bg-gray-600" />
        <span className="text-[10px]">{displayName}</span>
      </div>
    );
  }

  // Running state
  if (status.status === 'running' || status.status === 'queued') {
    return (
      <div className="flex items-center gap-1 text-yellow-500">
        <SpinnerIcon className="w-2 h-2" />
        <span className="text-[10px]">{displayName}</span>
      </div>
    );
  }

  // Succeeded state
  if (status.status === 'succeeded') {
    return (
      <div className="flex items-center gap-1 text-green-500">
        <span className="w-2 h-2 rounded-full bg-green-500" />
        <span className="text-[10px]">{displayName}</span>
        {status.has_review && (
          <CheckCircleIcon className="w-3 h-3 text-purple-400" title="Reviewed" />
        )}
      </div>
    );
  }

  // Failed state
  if (status.status === 'failed') {
    return (
      <div className="flex items-center gap-1 text-red-500">
        <span className="w-2 h-2 rounded-full bg-red-500" />
        <span className="text-[10px]">{displayName}</span>
      </div>
    );
  }

  // Canceled state
  return (
    <div className="flex items-center gap-1 text-gray-500">
      <span className="w-2 h-2 rounded-full bg-gray-500" />
      <span className="text-[10px]">{displayName}</span>
    </div>
  );
}

export function KanbanCard({
  task,
  columnStatus,
  onMoveToTodo,
  onMoveToBacklog,
  onArchive,
  onUnarchive,
  onStartTask,
}: KanbanCardProps) {
  const renderActions = () => {
    switch (columnStatus) {
      case 'backlog':
        return (
          <div className="flex gap-2">
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onMoveToTodo(task.id);
              }}
              className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
            >
              To ToDo
            </button>
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onArchive(task.id);
              }}
              className="text-xs text-gray-400 hover:text-gray-300 transition-colors"
            >
              Archive
            </button>
          </div>
        );

      case 'todo':
        return (
          <div className="flex gap-2">
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onStartTask?.(task);
              }}
              className="text-xs text-green-400 hover:text-green-300 transition-colors font-medium"
            >
              Start Task
            </button>
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onMoveToBacklog(task.id);
              }}
              className="text-xs text-gray-400 hover:text-gray-300 transition-colors"
            >
              To Backlog
            </button>
          </div>
        );

      case 'in_progress':
        return (
          <div className="flex gap-2">
            <span className="text-xs text-yellow-400 flex items-center gap-1">
              <SpinnerIcon className="w-3 h-3" />
              Running...
            </span>
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onArchive(task.id);
              }}
              className="text-xs text-gray-400 hover:text-gray-300 transition-colors"
            >
              Archive
            </button>
          </div>
        );

      case 'gating':
        return (
          <div className="flex gap-2">
            <span className="text-xs text-orange-400">
              Gating
            </span>
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onArchive(task.id);
              }}
              className="text-xs text-gray-400 hover:text-gray-300 transition-colors"
            >
              Archive
            </button>
          </div>
        );

      case 'in_review':
        return (
          <div className="flex items-center gap-2">
            <InReviewStatusBadge task={task} />
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onArchive(task.id);
              }}
              className="text-xs text-gray-400 hover:text-gray-300 transition-colors"
            >
              Archive
            </button>
          </div>
        );

      case 'done':
        return (
          <span className="text-xs text-green-400 flex items-center gap-1">
            <CheckIcon className="w-3 h-3" />
            Merged
          </span>
        );

      case 'archived':
        return (
          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onUnarchive(task.id);
            }}
            className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
          >
            Restore
          </button>
        );

      default:
        return null;
    }
  };

  // Check if any executor has a run
  const hasExecutorRuns = task.executor_statuses?.some(s => s.run_id);

  return (
    <Link
      href={`/tasks/${task.id}`}
      className="block p-3 bg-gray-800 rounded-lg hover:bg-gray-750 transition-colors border border-gray-700 hover:border-gray-600"
    >
      <div className="font-medium text-sm text-white truncate">
        {task.title || 'Untitled Task'}
      </div>

      {/* Executor status indicators */}
      {task.executor_statuses && task.executor_statuses.length > 0 && hasExecutorRuns && (
        <div className="mt-2 flex items-center gap-3">
          {task.executor_statuses.map((status) => (
            <ExecutorStatusIndicator key={status.executor_type} status={status} />
          ))}
        </div>
      )}

      <div className="mt-2 flex items-center gap-2 text-xs text-gray-500">
        {!hasExecutorRuns && task.run_count > 0 && (
          <span className="flex items-center gap-1">
            <PlayIcon className="w-3 h-3" />
            {task.run_count} runs
          </span>
        )}
        {!hasExecutorRuns && task.running_count > 0 && (
          <span className="flex items-center gap-1 text-yellow-500">
            <SpinnerIcon className="w-3 h-3" />
            {task.running_count}
          </span>
        )}
        {task.pr_count > 0 && (
          <span className="flex items-center gap-1">
            <CodeBracketIcon className="w-3 h-3" />
            {task.pr_count} PRs
          </span>
        )}
      </div>

      <div className="mt-2 flex items-center justify-between">
        <span className="text-xs text-gray-600">
          {formatRelativeTime(task.updated_at)}
        </span>

        {renderActions()}
      </div>
    </Link>
  );
}
