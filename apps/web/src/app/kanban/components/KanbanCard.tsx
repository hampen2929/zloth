'use client';

import Link from 'next/link';
import type { TaskWithKanbanStatus, TaskKanbanStatus } from '@/types';
import { PlayIcon, CheckIcon, CodeBracketIcon } from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';

interface KanbanCardProps {
  task: TaskWithKanbanStatus;
  columnStatus: TaskKanbanStatus;
  onMoveToTodo: (taskId: string) => void;
  onMoveToBacklog: (taskId: string) => void;
  onArchive: (taskId: string) => void;
  onUnarchive: (taskId: string) => void;
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

export function KanbanCard({
  task,
  columnStatus,
  onMoveToTodo,
  onMoveToBacklog,
  onArchive,
  onUnarchive,
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
            <span className="text-xs text-green-400">
              Start AI
            </span>
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
          <span className="text-xs text-yellow-400 flex items-center gap-1">
            <SpinnerIcon className="w-3 h-3" />
            Running...
          </span>
        );

      case 'in_review':
        return (
          <div className="flex gap-2">
            <span className="text-xs text-purple-400">
              Review
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

  return (
    <Link
      href={`/tasks/${task.id}`}
      className="block p-3 bg-gray-800 rounded-lg hover:bg-gray-750 transition-colors border border-gray-700 hover:border-gray-600"
    >
      <div className="font-medium text-sm text-white truncate">
        {task.title || 'Untitled Task'}
      </div>

      <div className="mt-2 flex items-center gap-2 text-xs text-gray-500">
        {task.run_count > 0 && (
          <span className="flex items-center gap-1">
            <PlayIcon className="w-3 h-3" />
            {task.run_count} runs
          </span>
        )}
        {task.running_count > 0 && (
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
