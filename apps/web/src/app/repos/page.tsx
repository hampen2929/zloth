'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import type { RepoSummary, TaskKanbanStatus } from '@/types';
import { kanbanApi } from '@/lib/api';
import {
  FolderIcon,
  ArrowPathIcon,
  PlayIcon,
  ClockIcon,
  CheckCircleIcon,
  ArchiveBoxIcon,
  InboxIcon,
  DocumentCheckIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';

const STATUS_CONFIG: Record<
  TaskKanbanStatus,
  { label: string; color: string; bgColor: string; icon: React.ComponentType<{ className?: string }> }
> = {
  backlog: {
    label: 'Backlog',
    color: 'text-gray-400',
    bgColor: 'bg-gray-700',
    icon: InboxIcon,
  },
  todo: {
    label: 'To Do',
    color: 'text-blue-400',
    bgColor: 'bg-blue-900/50',
    icon: DocumentCheckIcon,
  },
  in_progress: {
    label: 'In Progress',
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-900/50',
    icon: PlayIcon,
  },
  gating: {
    label: 'Gating',
    color: 'text-orange-400',
    bgColor: 'bg-orange-900/50',
    icon: ClockIcon,
  },
  in_review: {
    label: 'In Review',
    color: 'text-purple-400',
    bgColor: 'bg-purple-900/50',
    icon: ExclamationTriangleIcon,
  },
  done: {
    label: 'Done',
    color: 'text-green-400',
    bgColor: 'bg-green-900/50',
    icon: CheckCircleIcon,
  },
  archived: {
    label: 'Archived',
    color: 'text-gray-500',
    bgColor: 'bg-gray-800',
    icon: ArchiveBoxIcon,
  },
};

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return 'No activity';

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

function StatusBadge({
  status,
  count,
}: {
  status: TaskKanbanStatus;
  count: number;
}) {
  if (count === 0) return null;

  const config = STATUS_CONFIG[status];
  const Icon = config.icon;

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${config.bgColor} ${config.color}`}
    >
      <Icon className="w-3 h-3" />
      {count}
    </span>
  );
}

function RepoCard({ repo }: { repo: RepoSummary }) {
  const { task_counts } = repo;

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 hover:border-gray-600 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <FolderIcon className="w-5 h-5 text-gray-400 flex-shrink-0" />
          <div className="min-w-0">
            <h3 className="font-medium text-white truncate">
              {repo.repo_name || 'Unknown Repository'}
            </h3>
            <p className="text-xs text-gray-500 truncate">{repo.default_branch}</p>
          </div>
        </div>
        <div className="text-right flex-shrink-0 ml-2">
          <div className="text-lg font-semibold text-white">{repo.total_tasks}</div>
          <div className="text-xs text-gray-500">tasks</div>
        </div>
      </div>

      {/* Status badges */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        <StatusBadge status="in_progress" count={task_counts.in_progress} />
        <StatusBadge status="gating" count={task_counts.gating} />
        <StatusBadge status="in_review" count={task_counts.in_review} />
        <StatusBadge status="todo" count={task_counts.todo} />
        <StatusBadge status="done" count={task_counts.done} />
        {task_counts.backlog > 0 && (
          <StatusBadge status="backlog" count={task_counts.backlog} />
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-2 border-t border-gray-700">
        <span className="text-xs text-gray-500">
          {formatRelativeTime(repo.latest_activity)}
        </span>
        <Link
          href={`/kanban?repo_id=${repo.id}`}
          className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
        >
          View Kanban
        </Link>
      </div>
    </div>
  );
}

export default function ReposPage() {
  const [repos, setRepos] = useState<RepoSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRepos = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await kanbanApi.getRepoSummaries();
      setRepos(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch repositories');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRepos();

    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchRepos, 30000);
    return () => clearInterval(interval);
  }, []);

  // Calculate totals
  const totalInProgress = repos.reduce((sum, r) => sum + r.task_counts.in_progress, 0);
  const totalInReview = repos.reduce((sum, r) => sum + r.task_counts.in_review, 0);
  const totalDone = repos.reduce((sum, r) => sum + r.task_counts.done, 0);

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/95 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Link href="/" className="text-gray-400 hover:text-white transition-colors">
                zloth
              </Link>
              <span className="text-gray-600">/</span>
              <h1 className="text-xl font-semibold">Repositories</h1>
            </div>
            <button
              onClick={fetchRepos}
              disabled={loading}
              className="flex items-center gap-1 px-3 py-1.5 text-sm text-gray-400 hover:text-white transition-colors disabled:opacity-50"
            >
              <ArrowPathIcon className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Summary stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="text-2xl font-bold text-white">{repos.length}</div>
            <div className="text-sm text-gray-400">Repositories</div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="text-2xl font-bold text-yellow-400">{totalInProgress}</div>
            <div className="text-sm text-gray-400">In Progress</div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="text-2xl font-bold text-purple-400">{totalInReview}</div>
            <div className="text-sm text-gray-400">In Review</div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="text-2xl font-bold text-green-400">{totalDone}</div>
            <div className="text-sm text-gray-400">Done</div>
          </div>
        </div>

        {/* Error state */}
        {error && (
          <div className="bg-red-900/50 border border-red-700 rounded-lg p-4 mb-6">
            <p className="text-red-400">{error}</p>
          </div>
        )}

        {/* Loading state */}
        {loading && repos.length === 0 && (
          <div className="text-center py-12">
            <ArrowPathIcon className="w-8 h-8 text-gray-500 animate-spin mx-auto mb-2" />
            <p className="text-gray-500">Loading repositories...</p>
          </div>
        )}

        {/* Empty state */}
        {!loading && repos.length === 0 && !error && (
          <div className="text-center py-12">
            <FolderIcon className="w-12 h-12 text-gray-600 mx-auto mb-3" />
            <h3 className="text-lg font-medium text-gray-400 mb-1">No repositories yet</h3>
            <p className="text-gray-500 mb-4">
              Create a new task to add a repository
            </p>
            <Link
              href="/"
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white transition-colors"
            >
              New Task
            </Link>
          </div>
        )}

        {/* Repository grid */}
        {repos.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {repos.map((repo) => (
              <RepoCard key={repo.id} repo={repo} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
