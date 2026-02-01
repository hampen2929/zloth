'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { metricsApi, kanbanApi } from '@/lib/api';
import type { MetricsDetail, ExecutorType, RepoSummary, TaskKanbanStatus } from '@/types';
import { ProgressBar } from './components/ProgressBar';
import { MetricsSection } from './components/MetricsSection';
import {
  ArrowPathIcon,
  ChartBarIcon,
  CommandLineIcon,
  CheckCircleIcon,
  ClockIcon,
  CodeBracketIcon,
  CpuChipIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  StarIcon,
  ExclamationTriangleIcon,
  FolderIcon,
  PlayIcon,
  InboxIcon,
  DocumentCheckIcon,
  ArchiveBoxIcon,
} from '@heroicons/react/24/outline';

type PeriodOption = '1d' | '7d' | '30d' | '90d' | 'all';

const PERIOD_OPTIONS: { value: PeriodOption; label: string }[] = [
  { value: '1d', label: '1 Day' },
  { value: '7d', label: '7 Days' },
  { value: '30d', label: '30 Days' },
  { value: '90d', label: '90 Days' },
  { value: 'all', label: 'All Time' },
];

const EXECUTOR_LABELS: Record<ExecutorType, string> = {
  patch_agent: 'Patch Agent',
  claude_code: 'Claude Code',
  codex_cli: 'Codex CLI',
  gemini_cli: 'Gemini CLI',
};

// Repository status configuration
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

function formatRepoRelativeTime(dateStr: string | null): string {
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
          {formatRepoRelativeTime(repo.latest_activity)}
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

// Alert thresholds
const THRESHOLDS = {
  mergeRate: { warning: 60, critical: 40 },
  runSuccessRate: { warning: 75, critical: 50 },
  cycleTimeHours: { warning: 12, critical: 24 },
  firstTimeSuccess: { warning: 30, critical: 15 },
};

function getAlertLevel(
  value: number | null,
  threshold: { warning: number; critical: number },
  higherIsBetter = true
): 'normal' | 'warning' | 'critical' {
  if (value === null) return 'normal';
  if (higherIsBetter) {
    if (value < threshold.critical) return 'critical';
    if (value < threshold.warning) return 'warning';
  } else {
    if (value > threshold.critical) return 'critical';
    if (value > threshold.warning) return 'warning';
  }
  return 'normal';
}

function AlertBadge({ level }: { level: 'normal' | 'warning' | 'critical' }) {
  if (level === 'normal') return null;
  return (
    <span
      className={`ml-2 px-1.5 py-0.5 text-xs rounded ${
        level === 'critical'
          ? 'bg-red-500/20 text-red-400'
          : 'bg-yellow-500/20 text-yellow-400'
      }`}
    >
      {level === 'critical' ? 'Critical' : 'Warning'}
    </span>
  );
}

export default function MetricsPage() {
  const [metrics, setMetrics] = useState<MetricsDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<PeriodOption>('7d');
  const [showDiagnostic, setShowDiagnostic] = useState(false);
  const [showExploratory, setShowExploratory] = useState(false);
  const [showRepositories, setShowRepositories] = useState(true);
  const [repos, setRepos] = useState<RepoSummary[]>([]);
  const [reposLoading, setReposLoading] = useState(true);

  const fetchMetrics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await metricsApi.get(period);
      setMetrics(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load metrics');
    } finally {
      setLoading(false);
    }
  }, [period]);

  const fetchRepos = useCallback(async () => {
    try {
      setReposLoading(true);
      const data = await kanbanApi.getRepoSummaries();
      setRepos(data);
    } catch (err) {
      // Silently fail for repos, metrics is the main content
      console.error('Failed to fetch repositories:', err);
    } finally {
      setReposLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  useEffect(() => {
    fetchRepos();
    // Auto-refresh repos every 30 seconds
    const interval = setInterval(fetchRepos, 30000);
    return () => clearInterval(interval);
  }, [fetchRepos]);

  const formatDuration = (hours: number | null) => {
    if (hours === null) return '-';
    if (hours < 1) return `${Math.round(hours * 60)}m`;
    if (hours < 24) return `${hours.toFixed(1)}h`;
    return `${(hours / 24).toFixed(1)}d`;
  };

  const formatNumber = (num: number, decimals = 1) => {
    if (num === 0) return '0';
    if (num < 1) return num.toFixed(decimals);
    if (num >= 1000) return `${(num / 1000).toFixed(1)}k`;
    return num.toFixed(decimals);
  };

  // Calculate alert levels
  const alerts = metrics
    ? {
        mergeRate: getAlertLevel(metrics.summary.merge_rate, THRESHOLDS.mergeRate),
        runSuccess: getAlertLevel(metrics.summary.run_success_rate, THRESHOLDS.runSuccessRate),
        cycleTime: getAlertLevel(
          metrics.summary.avg_cycle_time_hours,
          THRESHOLDS.cycleTimeHours,
          false
        ),
        firstTimeSuccess: getAlertLevel(
          metrics.productivity_metrics.first_time_success_rate,
          THRESHOLDS.firstTimeSuccess
        ),
      }
    : null;

  const hasAlerts =
    alerts &&
    (alerts.mergeRate !== 'normal' ||
      alerts.runSuccess !== 'normal' ||
      alerts.cycleTime !== 'normal' ||
      alerts.firstTimeSuccess !== 'normal');

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="border-b border-gray-700 bg-gray-800/50">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <ChartBarIcon className="h-6 w-6 text-blue-400" />
              <h1 className="text-xl font-semibold">Development Metrics</h1>
              {hasAlerts && (
                <span className="flex items-center gap-1 px-2 py-1 bg-yellow-500/20 text-yellow-400 text-xs rounded">
                  <ExclamationTriangleIcon className="h-3.5 w-3.5" />
                  Alerts
                </span>
              )}
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-400">Period:</span>
                <select
                  value={period}
                  onChange={(e) => setPeriod(e.target.value as PeriodOption)}
                  className="bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {PERIOD_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              <button
                onClick={fetchMetrics}
                disabled={loading}
                className="flex items-center gap-2 px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 transition-colors disabled:opacity-50"
              >
                <ArrowPathIcon className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                <span className="text-sm">Refresh</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 py-6">
        {error && (
          <div className="mb-6 p-4 bg-red-900/50 border border-red-700 rounded-lg text-red-200">
            {error}
          </div>
        )}

        {/* ============================================ */}
        {/* NORTH STAR - Throughput */}
        {/* ============================================ */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-3">
            <StarIcon className="h-5 w-5 text-yellow-400" />
            <span className="text-sm font-medium text-yellow-400">NORTH STAR</span>
            <span className="text-xs text-gray-500">- 価値の定義</span>
          </div>
          <div className="bg-gradient-to-r from-blue-900/40 to-purple-900/40 border border-blue-700/50 rounded-xl p-6">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-gray-400 mb-1">Throughput</div>
                <div className="flex items-baseline gap-3">
                  <span className="text-5xl font-bold text-white">
                    {metrics ? formatNumber(metrics.summary.throughput) : '-'}
                  </span>
                  <span className="text-xl text-gray-400">PRs/week</span>
                </div>
                {metrics?.summary.throughput_change !== null &&
                  metrics?.summary.throughput_change !== undefined && (
                    <div
                      className={`mt-2 text-sm ${
                        metrics.summary.throughput_change > 0
                          ? 'text-green-400'
                          : metrics.summary.throughput_change < 0
                            ? 'text-red-400'
                            : 'text-gray-400'
                      }`}
                    >
                      {metrics.summary.throughput_change > 0 ? '+' : ''}
                      {metrics.summary.throughput_change.toFixed(1)} vs previous period
                    </div>
                  )}
              </div>
              <div className="text-right">
                <div className="text-xs text-gray-500 mb-2">Realtime</div>
                <div className="flex items-center gap-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-400">
                      {metrics?.realtime.prs_merged_today ?? '-'}
                    </div>
                    <div className="text-xs text-gray-500">Merged Today</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-400">
                      {metrics?.realtime.open_prs ?? '-'}
                    </div>
                    <div className="text-xs text-gray-500">Open PRs</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ============================================ */}
        {/* CORE KPI - 6 Metrics */}
        {/* ============================================ */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-3">
            <ChartBarIcon className="h-5 w-5 text-blue-400" />
            <span className="text-sm font-medium text-blue-400">CORE KPI</span>
            <span className="text-xs text-gray-500">- 改善の意思決定（6指標）</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {/* 1. Merge Rate */}
            <div
              className={`rounded-lg border p-4 ${
                alerts?.mergeRate === 'critical'
                  ? 'border-red-500/50 bg-red-900/20'
                  : alerts?.mergeRate === 'warning'
                    ? 'border-yellow-500/50 bg-yellow-900/20'
                    : 'border-gray-700 bg-gray-800'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-gray-400">Merge Rate</span>
                <AlertBadge level={alerts?.mergeRate ?? 'normal'} />
              </div>
              <div className="text-2xl font-bold">
                {metrics ? `${metrics.summary.merge_rate.toFixed(1)}%` : '-'}
              </div>
              <div className="text-xs text-gray-500 mt-1">↑ Higher is better</div>
            </div>

            {/* 2. Cycle Time */}
            <div
              className={`rounded-lg border p-4 ${
                alerts?.cycleTime === 'critical'
                  ? 'border-red-500/50 bg-red-900/20'
                  : alerts?.cycleTime === 'warning'
                    ? 'border-yellow-500/50 bg-yellow-900/20'
                    : 'border-gray-700 bg-gray-800'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-gray-400">Cycle Time</span>
                <AlertBadge level={alerts?.cycleTime ?? 'normal'} />
              </div>
              <div className="text-2xl font-bold">
                {metrics ? formatDuration(metrics.summary.avg_cycle_time_hours) : '-'}
              </div>
              <div className="text-xs text-gray-500 mt-1">↓ Lower is better</div>
            </div>

            {/* 3. Run Success Rate */}
            <div
              className={`rounded-lg border p-4 ${
                alerts?.runSuccess === 'critical'
                  ? 'border-red-500/50 bg-red-900/20'
                  : alerts?.runSuccess === 'warning'
                    ? 'border-yellow-500/50 bg-yellow-900/20'
                    : 'border-gray-700 bg-gray-800'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-gray-400">Run Success</span>
                <AlertBadge level={alerts?.runSuccess ?? 'normal'} />
              </div>
              <div className="text-2xl font-bold">
                {metrics ? `${metrics.summary.run_success_rate.toFixed(1)}%` : '-'}
              </div>
              <div className="text-xs text-gray-500 mt-1">↑ Higher is better</div>
            </div>

            {/* 4. First-Time Success Rate */}
            <div
              className={`rounded-lg border p-4 ${
                alerts?.firstTimeSuccess === 'critical'
                  ? 'border-red-500/50 bg-red-900/20'
                  : alerts?.firstTimeSuccess === 'warning'
                    ? 'border-yellow-500/50 bg-yellow-900/20'
                    : 'border-gray-700 bg-gray-800'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-gray-400">First-Time Success</span>
                <AlertBadge level={alerts?.firstTimeSuccess ?? 'normal'} />
              </div>
              <div className="text-2xl font-bold">
                {metrics
                  ? `${metrics.productivity_metrics.first_time_success_rate.toFixed(1)}%`
                  : '-'}
              </div>
              <div className="text-xs text-gray-500 mt-1">↑ Higher is better</div>
            </div>

            {/* 5. Agentic Completion Rate */}
            <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
              <div className="text-xs text-gray-400 mb-1">Agentic Completion</div>
              <div className="text-2xl font-bold">
                {metrics
                  ? `${metrics.agentic_metrics.agentic_completion_rate.toFixed(1)}%`
                  : '-'}
              </div>
              <div className="text-xs text-gray-500 mt-1">↑ Higher is better</div>
            </div>

            {/* 6. Messages per Task */}
            <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
              <div className="text-xs text-gray-400 mb-1">Messages/Task</div>
              <div className="text-2xl font-bold">
                {metrics
                  ? metrics.conversation_metrics.avg_messages_per_task.toFixed(1)
                  : '-'}
              </div>
              <div className="text-xs text-gray-500 mt-1">↓ Lower is better</div>
            </div>
          </div>
        </div>

        {/* Realtime Activity */}
        {metrics && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <div className="flex items-center gap-3 px-4 py-3 bg-gray-800 rounded-lg border border-gray-700">
              <div className="p-2 bg-blue-500/20 rounded-lg">
                <CommandLineIcon className="h-5 w-5 text-blue-400" />
              </div>
              <div>
                <div className="text-2xl font-bold">{metrics.realtime.running_runs}</div>
                <div className="text-xs text-gray-400">Running Runs</div>
              </div>
            </div>
            <div className="flex items-center gap-3 px-4 py-3 bg-gray-800 rounded-lg border border-gray-700">
              <div className="p-2 bg-yellow-500/20 rounded-lg">
                <ClockIcon className="h-5 w-5 text-yellow-400" />
              </div>
              <div>
                <div className="text-2xl font-bold">{metrics.realtime.pending_ci_checks}</div>
                <div className="text-xs text-gray-400">Pending CI</div>
              </div>
            </div>
            <div className="flex items-center gap-3 px-4 py-3 bg-gray-800 rounded-lg border border-gray-700">
              <div className="p-2 bg-purple-500/20 rounded-lg">
                <CodeBracketIcon className="h-5 w-5 text-purple-400" />
              </div>
              <div>
                <div className="text-2xl font-bold">{metrics.realtime.active_tasks}</div>
                <div className="text-xs text-gray-400">Active Tasks</div>
              </div>
            </div>
            <div className="flex items-center gap-3 px-4 py-3 bg-gray-800 rounded-lg border border-gray-700">
              <div className="p-2 bg-green-500/20 rounded-lg">
                <CheckCircleIcon className="h-5 w-5 text-green-400" />
              </div>
              <div>
                <div className="text-2xl font-bold">{metrics.realtime.runs_completed_today}</div>
                <div className="text-xs text-gray-400">Runs Today</div>
              </div>
            </div>
          </div>
        )}

        {/* ============================================ */}
        {/* DIAGNOSTIC KPI - Collapsible */}
        {/* ============================================ */}
        <div className="mb-6">
          <button
            onClick={() => setShowDiagnostic(!showDiagnostic)}
            className="flex items-center gap-2 mb-3 hover:opacity-80 transition-opacity"
          >
            {showDiagnostic ? (
              <ChevronDownIcon className="h-5 w-5 text-orange-400" />
            ) : (
              <ChevronRightIcon className="h-5 w-5 text-orange-400" />
            )}
            <span className="text-sm font-medium text-orange-400">DIAGNOSTIC KPI</span>
            <span className="text-xs text-gray-500">- 原因分析（7指標）</span>
          </button>

          {showDiagnostic && metrics && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 animate-in fade-in slide-in-from-top-2 duration-200">
              {/* 1. Time to Merge */}
              <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
                <div className="text-xs text-gray-400 mb-1">Time to Merge</div>
                <div className="text-xl font-bold">
                  {formatDuration(metrics.pr_metrics.avg_time_to_merge_hours)}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  Related: Merge Rate, Cycle Time
                </div>
              </div>

              {/* 2. CI Success Rate */}
              <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
                <div className="text-xs text-gray-400 mb-1">CI Success Rate</div>
                <div className="text-xl font-bold">
                  {metrics.ci_metrics.ci_success_rate.toFixed(1)}%
                </div>
                <div className="text-xs text-gray-500 mt-1">Related: Run Success Rate</div>
              </div>

              {/* 3. Avg Run Duration */}
              <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
                <div className="text-xs text-gray-400 mb-1">Avg Run Duration</div>
                <div className="text-xl font-bold">
                  {formatDuration(
                    metrics.run_metrics.avg_run_duration_seconds
                      ? metrics.run_metrics.avg_run_duration_seconds / 3600
                      : null
                  )}
                </div>
                <div className="text-xs text-gray-500 mt-1">Related: Cycle Time</div>
              </div>

              {/* 4. CI Fix Iterations */}
              <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
                <div className="text-xs text-gray-400 mb-1">CI Fix Iterations</div>
                <div className="text-xl font-bold">
                  {metrics.agentic_metrics.avg_ci_iterations.toFixed(1)}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  Related: Run Success Rate
                </div>
              </div>

              {/* 5. Review Fix Iterations */}
              <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
                <div className="text-xs text-gray-400 mb-1">Review Fix Iterations</div>
                <div className="text-xl font-bold">
                  {metrics.agentic_metrics.avg_review_iterations.toFixed(1)}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  Related: Run Success Rate
                </div>
              </div>

              {/* 6. Avg Review Score */}
              <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
                <div className="text-xs text-gray-400 mb-1">Avg Review Score</div>
                <div className="text-xl font-bold">
                  {metrics.review_metrics.avg_review_score !== null
                    ? `${(metrics.review_metrics.avg_review_score * 100).toFixed(0)}%`
                    : '-'}
                </div>
                <div className="text-xs text-gray-500 mt-1">Related: Merge Rate</div>
              </div>

              {/* 7. Queue Wait Time */}
              <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
                <div className="text-xs text-gray-400 mb-1">Queue Wait Time</div>
                <div className="text-xl font-bold">
                  {formatDuration(
                    metrics.run_metrics.avg_queue_wait_seconds
                      ? metrics.run_metrics.avg_queue_wait_seconds / 3600
                      : null
                  )}
                </div>
                <div className="text-xs text-gray-500 mt-1">Related: Cycle Time</div>
              </div>
            </div>
          )}
        </div>

        {/* ============================================ */}
        {/* EXPLORATORY - Collapsible */}
        {/* ============================================ */}
        <div className="mb-6">
          <button
            onClick={() => setShowExploratory(!showExploratory)}
            className="flex items-center gap-2 mb-3 hover:opacity-80 transition-opacity"
          >
            {showExploratory ? (
              <ChevronDownIcon className="h-5 w-5 text-gray-400" />
            ) : (
              <ChevronRightIcon className="h-5 w-5 text-gray-400" />
            )}
            <span className="text-sm font-medium text-gray-400">EXPLORATORY</span>
            <span className="text-xs text-gray-500">- 仮説検証（必要時）</span>
          </button>

          {showExploratory && metrics && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-in fade-in slide-in-from-top-2 duration-200">
              {/* Executor Distribution */}
              <MetricsSection title="Executor Distribution">
                <div className="space-y-3">
                  {metrics.executor_distribution.length > 0 ? (
                    metrics.executor_distribution.map((item) => (
                      <div key={item.executor_type} className="flex items-center gap-3">
                        <CpuChipIcon className="h-5 w-5 text-gray-400" />
                        <div className="flex-1">
                          <div className="flex justify-between text-sm mb-1">
                            <span className="text-gray-300">
                              {EXECUTOR_LABELS[item.executor_type] || item.executor_type}
                            </span>
                            <span className="text-gray-400">
                              {item.count} ({item.percentage.toFixed(1)}%)
                            </span>
                          </div>
                          <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-blue-500 transition-all duration-300"
                              style={{ width: `${item.percentage}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-gray-500 text-sm">No run data available</div>
                  )}
                </div>
              </MetricsSection>

              {/* PR Status Distribution */}
              <MetricsSection title="PR Status Distribution">
                <div className="space-y-4">
                  <ProgressBar
                    label="Merged"
                    value={metrics.pr_metrics.merged_prs}
                    total={metrics.pr_metrics.total_prs}
                    color="green"
                  />
                  <ProgressBar
                    label="Open"
                    value={metrics.pr_metrics.open_prs}
                    total={metrics.pr_metrics.total_prs}
                    color="blue"
                  />
                  <ProgressBar
                    label="Closed"
                    value={metrics.pr_metrics.closed_prs}
                    total={metrics.pr_metrics.total_prs}
                    color="red"
                  />
                </div>
              </MetricsSection>

              {/* Run Status */}
              <MetricsSection title="Run Status Distribution">
                <div className="grid grid-cols-3 gap-2">
                  <div className="text-center p-2 bg-gray-900/50 rounded">
                    <div className="text-xl font-bold text-green-400">
                      {metrics.run_metrics.succeeded_runs}
                    </div>
                    <div className="text-xs text-gray-400">Succeeded</div>
                  </div>
                  <div className="text-center p-2 bg-gray-900/50 rounded">
                    <div className="text-xl font-bold text-red-400">
                      {metrics.run_metrics.failed_runs}
                    </div>
                    <div className="text-xs text-gray-400">Failed</div>
                  </div>
                  <div className="text-center p-2 bg-gray-900/50 rounded">
                    <div className="text-xl font-bold text-gray-400">
                      {metrics.run_metrics.canceled_runs}
                    </div>
                    <div className="text-xs text-gray-400">Canceled</div>
                  </div>
                </div>
              </MetricsSection>

              {/* Review Issues by Severity */}
              <MetricsSection title="Review Issues by Severity">
                <div className="grid grid-cols-4 gap-2">
                  <div className="text-center p-2 bg-red-900/30 rounded">
                    <div className="text-lg font-bold text-red-400">
                      {metrics.review_metrics.critical_issues}
                    </div>
                    <div className="text-xs text-gray-400">Critical</div>
                  </div>
                  <div className="text-center p-2 bg-orange-900/30 rounded">
                    <div className="text-lg font-bold text-orange-400">
                      {metrics.review_metrics.high_issues}
                    </div>
                    <div className="text-xs text-gray-400">High</div>
                  </div>
                  <div className="text-center p-2 bg-yellow-900/30 rounded">
                    <div className="text-lg font-bold text-yellow-400">
                      {metrics.review_metrics.medium_issues}
                    </div>
                    <div className="text-xs text-gray-400">Medium</div>
                  </div>
                  <div className="text-center p-2 bg-gray-700/50 rounded">
                    <div className="text-lg font-bold text-gray-300">
                      {metrics.review_metrics.low_issues}
                    </div>
                    <div className="text-xs text-gray-400">Low</div>
                  </div>
                </div>
              </MetricsSection>
            </div>
          )}
        </div>

        {/* ============================================ */}
        {/* REPOSITORIES */}
        {/* ============================================ */}
        <div className="mb-6">
          <button
            onClick={() => setShowRepositories(!showRepositories)}
            className="flex items-center gap-2 mb-3 hover:opacity-80 transition-opacity"
          >
            {showRepositories ? (
              <ChevronDownIcon className="h-5 w-5 text-purple-400" />
            ) : (
              <ChevronRightIcon className="h-5 w-5 text-purple-400" />
            )}
            <FolderIcon className="h-5 w-5 text-purple-400" />
            <span className="text-sm font-medium text-purple-400">REPOSITORIES</span>
            <span className="text-xs text-gray-500">- リポジトリ一覧</span>
            {repos.length > 0 && (
              <span className="ml-2 px-1.5 py-0.5 text-xs rounded bg-purple-500/20 text-purple-400">
                {repos.length}
              </span>
            )}
          </button>

          {showRepositories && (
            <div className="animate-in fade-in slide-in-from-top-2 duration-200">
              {/* Repository summary stats */}
              {repos.length > 0 && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                  <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700">
                    <div className="text-xl font-bold text-white">{repos.length}</div>
                    <div className="text-xs text-gray-400">Repositories</div>
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700">
                    <div className="text-xl font-bold text-yellow-400">
                      {repos.reduce((sum, r) => sum + r.task_counts.in_progress, 0)}
                    </div>
                    <div className="text-xs text-gray-400">In Progress</div>
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700">
                    <div className="text-xl font-bold text-purple-400">
                      {repos.reduce((sum, r) => sum + r.task_counts.in_review, 0)}
                    </div>
                    <div className="text-xs text-gray-400">In Review</div>
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700">
                    <div className="text-xl font-bold text-green-400">
                      {repos.reduce((sum, r) => sum + r.task_counts.done, 0)}
                    </div>
                    <div className="text-xs text-gray-400">Done</div>
                  </div>
                </div>
              )}

              {/* Loading state */}
              {reposLoading && repos.length === 0 && (
                <div className="text-center py-8">
                  <ArrowPathIcon className="w-6 h-6 text-gray-500 animate-spin mx-auto mb-2" />
                  <p className="text-gray-500 text-sm">Loading repositories...</p>
                </div>
              )}

              {/* Empty state */}
              {!reposLoading && repos.length === 0 && (
                <div className="text-center py-8 bg-gray-800/30 rounded-lg border border-gray-700">
                  <FolderIcon className="w-10 h-10 text-gray-600 mx-auto mb-2" />
                  <h3 className="text-sm font-medium text-gray-400 mb-1">No repositories yet</h3>
                  <p className="text-gray-500 text-xs mb-3">
                    Create a new task to add a repository
                  </p>
                  <Link
                    href="/"
                    className="inline-flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded-lg text-white text-sm transition-colors"
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
            </div>
          )}
        </div>

        {/* Summary Stats */}
        {metrics && (
          <div className="p-4 bg-gray-800/50 border border-gray-700 rounded-lg">
            <div className="text-xs text-gray-500 mb-3">Period Summary</div>
            <div className="grid grid-cols-4 gap-4 text-center">
              <div>
                <div className="text-2xl font-bold">{metrics.summary.total_tasks}</div>
                <div className="text-xs text-gray-400">Total Tasks</div>
              </div>
              <div>
                <div className="text-2xl font-bold">{metrics.summary.total_prs}</div>
                <div className="text-xs text-gray-400">Total PRs</div>
              </div>
              <div>
                <div className="text-2xl font-bold">{metrics.summary.total_runs}</div>
                <div className="text-xs text-gray-400">Total Runs</div>
              </div>
              <div>
                <div className="text-2xl font-bold">{metrics.summary.total_messages}</div>
                <div className="text-xs text-gray-400">Total Messages</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
