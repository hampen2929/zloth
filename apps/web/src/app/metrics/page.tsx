'use client';

import { useState, useEffect, useCallback } from 'react';
import { metricsApi } from '@/lib/api';
import type { MetricsDetail, ExecutorType } from '@/types';
import { MetricCard } from './components/MetricCard';
import { ProgressBar } from './components/ProgressBar';
import { MetricsSection } from './components/MetricsSection';
import {
  ArrowPathIcon,
  ChartBarIcon,
  ChatBubbleLeftRightIcon,
  CommandLineIcon,
  CheckCircleIcon,
  ClockIcon,
  CodeBracketIcon,
  CpuChipIcon,
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

export default function MetricsPage() {
  const [metrics, setMetrics] = useState<MetricsDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<PeriodOption>('30d');

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

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

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

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="border-b border-gray-700 bg-gray-800/50">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <ChartBarIcon className="h-6 w-6 text-blue-400" />
              <h1 className="text-xl font-semibold">Development Metrics</h1>
            </div>
            <div className="flex items-center gap-4">
              {/* Period Selector */}
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
              {/* Refresh Button */}
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

        {/* Headline Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <MetricCard
            title="Merge Rate"
            value={metrics ? `${metrics.summary.merge_rate.toFixed(1)}%` : '-'}
            change={metrics?.summary.merge_rate_change}
            loading={loading}
          />
          <MetricCard
            title="Cycle Time"
            value={metrics ? formatDuration(metrics.summary.avg_cycle_time_hours) : '-'}
            change={metrics?.summary.cycle_time_change}
            loading={loading}
          />
          <MetricCard
            title="Throughput"
            value={metrics ? formatNumber(metrics.summary.throughput) : '-'}
            unit="PRs/week"
            change={metrics?.summary.throughput_change}
            loading={loading}
          />
          <MetricCard
            title="Run Success Rate"
            value={metrics ? `${metrics.summary.run_success_rate.toFixed(1)}%` : '-'}
            loading={loading}
          />
        </div>

        {/* Realtime Stats */}
        {metrics && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
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
                <div className="text-2xl font-bold">{metrics.realtime.open_prs}</div>
                <div className="text-xs text-gray-400">Open PRs</div>
              </div>
            </div>
            <div className="flex items-center gap-3 px-4 py-3 bg-gray-800 rounded-lg border border-gray-700">
              <div className="p-2 bg-green-500/20 rounded-lg">
                <CheckCircleIcon className="h-5 w-5 text-green-400" />
              </div>
              <div>
                <div className="text-2xl font-bold">{metrics.realtime.prs_merged_today}</div>
                <div className="text-xs text-gray-400">Merged Today</div>
              </div>
            </div>
          </div>
        )}

        {/* Main Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* PR Metrics */}
          <MetricsSection title="Pull Requests">
            {metrics && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="text-center p-3 bg-gray-900/50 rounded">
                    <div className="text-2xl font-bold text-white">
                      {metrics.pr_metrics.total_prs}
                    </div>
                    <div className="text-xs text-gray-400">Total PRs</div>
                  </div>
                  <div className="text-center p-3 bg-gray-900/50 rounded">
                    <div className="text-2xl font-bold text-green-400">
                      {metrics.pr_metrics.merged_prs}
                    </div>
                    <div className="text-xs text-gray-400">Merged</div>
                  </div>
                </div>
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
                {metrics.pr_metrics.avg_time_to_merge_hours !== null && (
                  <div className="mt-4 text-sm text-gray-400">
                    Avg Time to Merge:{' '}
                    <span className="text-white">
                      {formatDuration(metrics.pr_metrics.avg_time_to_merge_hours)}
                    </span>
                  </div>
                )}
              </div>
            )}
          </MetricsSection>

          {/* Run Metrics */}
          <MetricsSection title="Run Execution">
            {metrics && (
              <div className="space-y-4">
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
                <ProgressBar
                  label="Success Rate"
                  value={metrics.run_metrics.succeeded_runs}
                  total={metrics.run_metrics.total_runs}
                  color="green"
                />
                {metrics.run_metrics.avg_run_duration_seconds !== null && (
                  <div className="text-sm text-gray-400">
                    Avg Duration:{' '}
                    <span className="text-white">
                      {formatDuration(metrics.run_metrics.avg_run_duration_seconds / 3600)}
                    </span>
                  </div>
                )}
              </div>
            )}
          </MetricsSection>

          {/* Conversation Metrics */}
          <MetricsSection title="Conversations">
            {metrics && (
              <div className="space-y-4">
                <div className="flex items-center gap-3 mb-4">
                  <ChatBubbleLeftRightIcon className="h-8 w-8 text-blue-400" />
                  <div>
                    <div className="text-2xl font-bold">
                      {metrics.conversation_metrics.total_messages}
                    </div>
                    <div className="text-xs text-gray-400">Total Messages</div>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 bg-gray-900/50 rounded">
                    <div className="text-lg font-semibold">
                      {metrics.conversation_metrics.avg_messages_per_task.toFixed(1)}
                    </div>
                    <div className="text-xs text-gray-400">Avg Messages/Task</div>
                  </div>
                  <div className="p-3 bg-gray-900/50 rounded">
                    <div className="text-lg font-semibold">
                      {metrics.conversation_metrics.avg_user_messages_per_task.toFixed(1)}
                    </div>
                    <div className="text-xs text-gray-400">Avg User Messages/Task</div>
                  </div>
                </div>
              </div>
            )}
          </MetricsSection>

          {/* Executor Distribution */}
          <MetricsSection title="Executor Distribution">
            {metrics && (
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
            )}
          </MetricsSection>

          {/* CI Metrics */}
          <MetricsSection title="CI/CD">
            {metrics && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="text-center p-3 bg-gray-900/50 rounded">
                    <div className="text-2xl font-bold">
                      {metrics.ci_metrics.total_ci_checks}
                    </div>
                    <div className="text-xs text-gray-400">Total Checks</div>
                  </div>
                  <div className="text-center p-3 bg-gray-900/50 rounded">
                    <div className="text-2xl font-bold text-green-400">
                      {metrics.ci_metrics.ci_success_rate.toFixed(1)}%
                    </div>
                    <div className="text-xs text-gray-400">Success Rate</div>
                  </div>
                </div>
                <ProgressBar
                  label="Passed"
                  value={metrics.ci_metrics.passed_ci_checks}
                  total={metrics.ci_metrics.total_ci_checks}
                  color="green"
                />
                <ProgressBar
                  label="Failed"
                  value={metrics.ci_metrics.failed_ci_checks}
                  total={metrics.ci_metrics.total_ci_checks}
                  color="red"
                />
              </div>
            )}
          </MetricsSection>

          {/* Review Metrics */}
          <MetricsSection title="Code Reviews">
            {metrics && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-2xl font-bold">
                      {metrics.review_metrics.total_reviews}
                    </div>
                    <div className="text-xs text-gray-400">Total Reviews</div>
                  </div>
                  {metrics.review_metrics.avg_review_score !== null && (
                    <div className="text-right">
                      <div className="text-2xl font-bold text-blue-400">
                        {(metrics.review_metrics.avg_review_score * 100).toFixed(0)}%
                      </div>
                      <div className="text-xs text-gray-400">Avg Score</div>
                    </div>
                  )}
                </div>
                <div className="text-sm text-gray-400">Issues by Severity</div>
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
              </div>
            )}
          </MetricsSection>

          {/* Agentic Metrics */}
          <MetricsSection title="Agentic Execution">
            {metrics && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="text-center p-3 bg-gray-900/50 rounded">
                    <div className="text-2xl font-bold">
                      {metrics.agentic_metrics.total_agentic_runs}
                    </div>
                    <div className="text-xs text-gray-400">Total Runs</div>
                  </div>
                  <div className="text-center p-3 bg-gray-900/50 rounded">
                    <div className="text-2xl font-bold text-green-400">
                      {metrics.agentic_metrics.agentic_completion_rate.toFixed(1)}%
                    </div>
                    <div className="text-xs text-gray-400">Completion Rate</div>
                  </div>
                </div>
                <div className="text-sm text-gray-400">Average Iterations</div>
                <div className="grid grid-cols-3 gap-2">
                  <div className="text-center p-2 bg-gray-900/50 rounded">
                    <div className="text-lg font-semibold">
                      {metrics.agentic_metrics.avg_total_iterations.toFixed(1)}
                    </div>
                    <div className="text-xs text-gray-400">Total</div>
                  </div>
                  <div className="text-center p-2 bg-gray-900/50 rounded">
                    <div className="text-lg font-semibold">
                      {metrics.agentic_metrics.avg_ci_iterations.toFixed(1)}
                    </div>
                    <div className="text-xs text-gray-400">CI Fix</div>
                  </div>
                  <div className="text-center p-2 bg-gray-900/50 rounded">
                    <div className="text-lg font-semibold">
                      {metrics.agentic_metrics.avg_review_iterations.toFixed(1)}
                    </div>
                    <div className="text-xs text-gray-400">Review Fix</div>
                  </div>
                </div>
              </div>
            )}
          </MetricsSection>

          {/* Productivity Metrics */}
          <MetricsSection title="Productivity">
            {metrics && (
              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-4">
                  <div className="text-center p-3 bg-gray-900/50 rounded">
                    <div className="text-xl font-bold">
                      {formatDuration(metrics.productivity_metrics.avg_cycle_time_hours)}
                    </div>
                    <div className="text-xs text-gray-400">Avg Cycle Time</div>
                  </div>
                  <div className="text-center p-3 bg-gray-900/50 rounded">
                    <div className="text-xl font-bold">
                      {metrics.productivity_metrics.throughput_per_week.toFixed(1)}
                    </div>
                    <div className="text-xs text-gray-400">PRs/Week</div>
                  </div>
                  <div className="text-center p-3 bg-gray-900/50 rounded">
                    <div className="text-xl font-bold text-green-400">
                      {metrics.productivity_metrics.first_time_success_rate.toFixed(1)}%
                    </div>
                    <div className="text-xs text-gray-400">First-Time Success</div>
                  </div>
                </div>
              </div>
            )}
          </MetricsSection>
        </div>

        {/* Summary Stats */}
        {metrics && (
          <div className="mt-6 p-4 bg-gray-800/50 border border-gray-700 rounded-lg">
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
