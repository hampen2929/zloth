'use client';

import { useState, useEffect, useCallback } from 'react';
import { analysisApi } from '@/lib/api';
import type { AnalysisDetail, ExecutorType } from '@/types';
import {
  LightBulbIcon,
  SparklesIcon,
  ChartBarIcon,
  ChatBubbleLeftRightIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  CheckCircleIcon,
  ArrowTrendingUpIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';

type PeriodOption = '7d' | '30d' | '90d' | 'all';

const PERIOD_OPTIONS: { value: PeriodOption; label: string }[] = [
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

const PATTERN_LABELS: Record<string, string> = {
  database_migration: 'Database Migrations',
  authentication: 'Authentication',
  api_changes: 'API Changes',
  testing: 'Testing',
  refactoring: 'Refactoring',
  other: 'Other',
};

function PriorityBadge({ priority }: { priority: 'high' | 'medium' | 'low' }) {
  const colors = {
    high: 'bg-red-500/20 text-red-400',
    medium: 'bg-yellow-500/20 text-yellow-400',
    low: 'bg-blue-500/20 text-blue-400',
  };
  return (
    <span className={`px-2 py-0.5 text-xs rounded ${colors[priority]}`}>
      {priority.charAt(0).toUpperCase() + priority.slice(1)}
    </span>
  );
}

function getCategoryIcon(category: string) {
  switch (category) {
    case 'prompt_quality':
      return ChatBubbleLeftRightIcon;
    case 'executor_selection':
      return SparklesIcon;
    case 'error_pattern':
      return ExclamationTriangleIcon;
    case 'efficiency':
      return ClockIcon;
    default:
      return LightBulbIcon;
  }
}

export default function AnalysisPage() {
  const [analysis, setAnalysis] = useState<AnalysisDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<PeriodOption>('30d');

  const fetchAnalysis = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await analysisApi.get(period);
      setAnalysis(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analysis');
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => {
    fetchAnalysis();
  }, [fetchAnalysis]);

  const formatDuration = (seconds: number | null) => {
    if (seconds === null) return '-';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${(seconds / 60).toFixed(1)}m`;
    return `${(seconds / 3600).toFixed(1)}h`;
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="border-b border-gray-700 bg-gray-800/50">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <LightBulbIcon className="h-6 w-6 text-yellow-400" />
              <h1 className="text-xl font-semibold">Prompt Analysis</h1>
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
                onClick={fetchAnalysis}
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

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <div className="bg-gradient-to-r from-purple-900/40 to-blue-900/40 border border-purple-700/50 rounded-xl p-6">
            <div className="flex items-center gap-2 mb-2">
              <ChatBubbleLeftRightIcon className="h-5 w-5 text-purple-400" />
              <span className="text-sm text-gray-400">Prompt Quality Score</span>
            </div>
            <div className="text-4xl font-bold text-white">
              {analysis ? `${analysis.summary.prompt_quality_score.toFixed(0)}%` : '-'}
            </div>
            <div className="text-sm text-gray-400 mt-1">
              Based on {analysis?.summary.total_tasks_analyzed ?? 0} tasks analyzed
            </div>
          </div>

          <div className="bg-gradient-to-r from-green-900/40 to-teal-900/40 border border-green-700/50 rounded-xl p-6">
            <div className="flex items-center gap-2 mb-2">
              <CheckCircleIcon className="h-5 w-5 text-green-400" />
              <span className="text-sm text-gray-400">Success Rate</span>
            </div>
            <div className="text-4xl font-bold text-white">
              {analysis ? `${analysis.summary.overall_success_rate.toFixed(1)}%` : '-'}
            </div>
            <div className="text-sm text-gray-400 mt-1">Run completion rate</div>
          </div>

          <div className="bg-gradient-to-r from-blue-900/40 to-cyan-900/40 border border-blue-700/50 rounded-xl p-6">
            <div className="flex items-center gap-2 mb-2">
              <ArrowTrendingUpIcon className="h-5 w-5 text-blue-400" />
              <span className="text-sm text-gray-400">Avg Iterations</span>
            </div>
            <div className="text-4xl font-bold text-white">
              {analysis ? analysis.summary.avg_iterations.toFixed(1) : '-'}
            </div>
            <div className="text-sm text-gray-400 mt-1">Messages per task</div>
          </div>
        </div>

        {/* Top Recommendations */}
        {analysis && analysis.recommendations.length > 0 && (
          <div className="mb-8">
            <div className="flex items-center gap-2 mb-4">
              <SparklesIcon className="h-5 w-5 text-yellow-400" />
              <h2 className="text-lg font-semibold">Top Recommendations</h2>
            </div>
            <div className="space-y-3">
              {analysis.recommendations.map((rec) => {
                const IconComponent = getCategoryIcon(rec.category);
                return (
                  <div
                    key={rec.id}
                    className="bg-gray-800 border border-gray-700 rounded-lg p-4 hover:border-gray-600 transition-colors"
                  >
                    <div className="flex items-start gap-4">
                      <div className="p-2 bg-gray-700 rounded-lg">
                        <IconComponent className="h-5 w-5 text-gray-300" />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-medium text-white">{rec.title}</h3>
                          <PriorityBadge priority={rec.priority} />
                        </div>
                        <p className="text-sm text-gray-400 mb-2">{rec.description}</p>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-500">Impact:</span>
                          <span className="text-xs text-green-400 font-medium">{rec.impact}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* No recommendations message */}
        {analysis && analysis.recommendations.length === 0 && (
          <div className="mb-8 p-6 bg-gray-800/50 border border-gray-700 rounded-lg text-center">
            <CheckCircleIcon className="h-8 w-8 text-green-400 mx-auto mb-3" />
            <h3 className="text-lg font-semibold mb-2">Great job!</h3>
            <p className="text-gray-400 text-sm">
              No specific recommendations at this time. Keep up the good work!
            </p>
          </div>
        )}

        {/* Analysis Categories */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Prompt Quality Analysis */}
          {analysis && (
            <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
              <div className="flex items-center gap-2 mb-4">
                <ChatBubbleLeftRightIcon className="h-5 w-5 text-blue-400" />
                <h3 className="font-semibold">Prompt Quality Analysis</h3>
              </div>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-400">Average Length</span>
                    <span className="text-white">
                      {analysis.prompt_analysis.avg_length.toFixed(0)} chars
                    </span>
                  </div>
                  <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500"
                      style={{
                        width: `${Math.min(100, (analysis.prompt_analysis.avg_length / 500) * 100)}%`,
                      }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-400">Specificity Score</span>
                    <span className="text-white">
                      {analysis.prompt_analysis.specificity_score.toFixed(0)}%
                    </span>
                  </div>
                  <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-purple-500"
                      style={{ width: `${analysis.prompt_analysis.specificity_score}%` }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-400">Context Score</span>
                    <span className="text-white">
                      {analysis.prompt_analysis.context_score.toFixed(0)}%
                    </span>
                  </div>
                  <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-green-500"
                      style={{ width: `${analysis.prompt_analysis.context_score}%` }}
                    />
                  </div>
                </div>
              </div>
              {analysis.prompt_analysis.common_missing_elements.length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-700">
                  <div className="text-xs text-gray-500 mb-2">Common Missing Elements:</div>
                  <div className="flex flex-wrap gap-2">
                    {analysis.prompt_analysis.common_missing_elements.map((element) => (
                      <span
                        key={element}
                        className="px-2 py-1 text-xs bg-gray-700 text-gray-300 rounded"
                      >
                        {element.replace(/_/g, ' ')}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Error Pattern Analysis */}
          {analysis && analysis.error_patterns.length > 0 && (
            <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
              <div className="flex items-center gap-2 mb-4">
                <ExclamationTriangleIcon className="h-5 w-5 text-red-400" />
                <h3 className="font-semibold">Error Pattern Analysis</h3>
              </div>
              <div className="space-y-3">
                {analysis.error_patterns.slice(0, 4).map((pattern) => {
                  const bgColor =
                    pattern.failure_rate > 30
                      ? 'bg-red-900/20 border-red-700/50'
                      : pattern.failure_rate > 20
                        ? 'bg-orange-900/20 border-orange-700/50'
                        : 'bg-yellow-900/20 border-yellow-700/50';
                  const textColor =
                    pattern.failure_rate > 30
                      ? 'text-red-400'
                      : pattern.failure_rate > 20
                        ? 'text-orange-400'
                        : 'text-yellow-400';
                  return (
                    <div
                      key={pattern.pattern}
                      className={`flex items-center justify-between p-3 ${bgColor} border rounded-lg`}
                    >
                      <span className="text-sm text-gray-300">
                        {PATTERN_LABELS[pattern.pattern] || pattern.pattern}
                      </span>
                      <span className={`text-sm ${textColor}`}>
                        {pattern.count} failures ({pattern.failure_rate.toFixed(0)}%)
                      </span>
                    </div>
                  );
                })}
              </div>
              <div className="mt-4 pt-4 border-t border-gray-700">
                <div className="text-xs text-gray-500">
                  Tip: Break complex tasks into smaller steps to reduce failures.
                </div>
              </div>
            </div>
          )}

          {/* No error patterns message */}
          {analysis && analysis.error_patterns.length === 0 && (
            <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
              <div className="flex items-center gap-2 mb-4">
                <ExclamationTriangleIcon className="h-5 w-5 text-red-400" />
                <h3 className="font-semibold">Error Pattern Analysis</h3>
              </div>
              <div className="flex flex-col items-center py-6 text-center">
                <CheckCircleIcon className="h-8 w-8 text-green-400 mb-2" />
                <p className="text-gray-400 text-sm">No significant error patterns detected</p>
              </div>
            </div>
          )}

          {/* Executor Comparison */}
          {analysis && analysis.executor_success_rates.length > 0 && (
            <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
              <div className="flex items-center gap-2 mb-4">
                <ChartBarIcon className="h-5 w-5 text-green-400" />
                <h3 className="font-semibold">Executor Comparison</h3>
              </div>
              <div className="space-y-4">
                {analysis.executor_success_rates.map((executor) => {
                  const color =
                    executor.success_rate >= 85
                      ? 'text-green-400'
                      : executor.success_rate >= 70
                        ? 'text-blue-400'
                        : 'text-yellow-400';
                  return (
                    <div key={executor.executor_type} className="flex items-center justify-between">
                      <span className="text-sm text-gray-300">
                        {EXECUTOR_LABELS[executor.executor_type] || executor.executor_type}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className={`text-sm ${color}`}>
                          {executor.success_rate.toFixed(0)}% success
                        </span>
                        <span className="text-xs text-gray-500">
                          avg {formatDuration(executor.avg_duration_seconds)}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="mt-4 pt-4 border-t border-gray-700">
                <div className="text-xs text-gray-500">
                  Choose the best executor for your task type to maximize success rate.
                </div>
              </div>
            </div>
          )}

          {/* Prompt Statistics */}
          {analysis && (
            <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
              <div className="flex items-center gap-2 mb-4">
                <ClockIcon className="h-5 w-5 text-yellow-400" />
                <h3 className="font-semibold">Prompt Statistics</h3>
              </div>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-400">Total Prompts Analyzed</span>
                    <span className="text-white">
                      {analysis.prompt_analysis.total_prompts_analyzed}
                    </span>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-400">Avg Word Count</span>
                    <span className="text-white">
                      {analysis.prompt_analysis.avg_word_count.toFixed(1)} words
                    </span>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-400">With File References</span>
                    <span className="text-white">
                      {analysis.prompt_analysis.prompts_with_file_refs}
                    </span>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-400">With Test Requirements</span>
                    <span className="text-white">
                      {analysis.prompt_analysis.prompts_with_test_req}
                    </span>
                  </div>
                </div>
              </div>
              <div className="mt-4 pt-4 border-t border-gray-700">
                <div className="text-xs text-gray-500">
                  Include file paths and test requirements for better results.
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Loading State */}
        {loading && !analysis && (
          <div className="flex items-center justify-center py-12">
            <ArrowPathIcon className="h-8 w-8 text-gray-400 animate-spin" />
          </div>
        )}

        {/* Empty State */}
        {!loading && !analysis && !error && (
          <div className="text-center py-12">
            <LightBulbIcon className="h-12 w-12 text-gray-600 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-400 mb-2">No Analysis Data</h3>
            <p className="text-gray-500 text-sm">
              Start creating tasks to generate analysis data.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
