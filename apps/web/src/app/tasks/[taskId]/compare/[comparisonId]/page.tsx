'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import useSWR from 'swr';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import type { Comparison, OutputLine, Run } from '@/types';
import { compareApi, runsApi } from '@/lib/api';

const EXECUTOR_NAMES: Record<string, string> = {
  claude_code: 'Claude Code',
  codex_cli: 'Codex',
  gemini_cli: 'Gemini CLI',
  patch_agent: 'Patch Agent',
};

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300',
  running: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300',
  succeeded: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300',
  failed: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300',
};

function ComparisonContent({ taskId, comparisonId }: { taskId: string; comparisonId: string }) {
  const [logs, setLogs] = useState<OutputLine[]>([]);
  const [activeTab, setActiveTab] = useState<'analysis' | 'metrics' | 'logs'>('analysis');

  // Fetch comparison data
  const { data: comparison, mutate: refreshComparison } = useSWR<Comparison>(
    comparisonId ? `comparison-${comparisonId}` : null,
    () => compareApi.get(comparisonId),
    {
      refreshInterval: (data) =>
        data?.status === 'running' || data?.status === 'pending' ? 2000 : 0,
    }
  );

  // Fetch runs for the comparison
  const { data: runs } = useSWR<Run[]>(
    comparison?.run_ids ? `runs-for-comparison-${comparisonId}` : null,
    async () => {
      if (!comparison?.run_ids) return [];
      const runPromises = comparison.run_ids.map((id) => runsApi.get(id));
      return Promise.all(runPromises);
    }
  );

  // Stream logs while running
  useEffect(() => {
    if (!comparison || comparison.status !== 'running') return;

    const cleanup = compareApi.streamLogs(comparisonId, {
      onLine: (line) => {
        setLogs((prev) => [...prev, line]);
      },
      onComplete: () => {
        refreshComparison();
      },
      onError: (error) => {
        console.error('Log streaming error:', error);
      },
    });

    return cleanup;
  }, [comparison, comparisonId, refreshComparison]);

  const getExecutorName = useCallback((run: Run) => {
    const baseName = EXECUTOR_NAMES[run.executor_type] || run.executor_type;
    if (run.model_name) {
      return `${baseName} (${run.model_name})`;
    }
    return baseName;
  }, []);

  if (!comparison) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                href={`/tasks/${taskId}`}
                className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M10 19l-7-7m0 0l7-7m-7 7h18"
                  />
                </svg>
                <span>Back to Task</span>
              </Link>
              <div className="h-6 w-px bg-gray-300 dark:bg-gray-600" />
              <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
                Comparison Results
              </h1>
            </div>

            <span
              className={`px-3 py-1 rounded-full text-sm font-medium ${STATUS_COLORS[comparison.status]}`}
            >
              {comparison.status}
            </span>
          </div>

          {/* Tabs */}
          <div className="mt-4 border-b border-gray-200 dark:border-gray-700">
            <nav className="-mb-px flex space-x-8">
              <button
                onClick={() => setActiveTab('analysis')}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'analysis'
                    ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                }`}
              >
                Analysis
              </button>
              <button
                onClick={() => setActiveTab('metrics')}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'metrics'
                    ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                }`}
              >
                Metrics
              </button>
              <button
                onClick={() => setActiveTab('logs')}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'logs'
                    ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                }`}
              >
                Logs
              </button>
            </nav>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Analysis Tab */}
        {activeTab === 'analysis' && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            {comparison.status === 'pending' && (
              <div className="text-center py-8">
                <div className="animate-pulse text-gray-500 dark:text-gray-400">
                  Waiting to start comparison...
                </div>
              </div>
            )}

            {comparison.status === 'running' && (
              <div className="text-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4" />
                <div className="text-gray-500 dark:text-gray-400">
                  Analyzing outputs...
                </div>
              </div>
            )}

            {comparison.status === 'failed' && (
              <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <svg
                    className="w-5 h-5 text-red-500 mt-0.5"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                  <div>
                    <h3 className="text-red-800 dark:text-red-300 font-medium">
                      Comparison Failed
                    </h3>
                    <p className="text-red-700 dark:text-red-400 mt-1">
                      {comparison.error || 'An unknown error occurred'}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {comparison.status === 'succeeded' && comparison.analysis && (
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown>{comparison.analysis}</ReactMarkdown>
              </div>
            )}
          </div>
        )}

        {/* Metrics Tab */}
        {activeTab === 'metrics' && (
          <div className="space-y-6">
            {/* Summary Table */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
                <h2 className="text-lg font-medium text-gray-900 dark:text-white">
                  Run Comparison
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                  <thead className="bg-gray-50 dark:bg-gray-700">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        Executor
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        Files
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        Lines Added
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        Lines Removed
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        Duration
                      </th>
                      <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                    {comparison.run_metrics.map((metric) => {
                      const run = runs?.find((r) => r.id === metric.run_id);
                      return (
                        <tr key={metric.run_id}>
                          <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                            {run ? getExecutorName(run) : EXECUTOR_NAMES[metric.executor_type] || metric.executor_type}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-500 dark:text-gray-400">
                            {metric.files_changed}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-green-600 dark:text-green-400">
                            +{metric.lines_added}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-red-600 dark:text-red-400">
                            -{metric.lines_removed}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-500 dark:text-gray-400">
                            {metric.execution_time_seconds
                              ? `${metric.execution_time_seconds.toFixed(1)}s`
                              : '-'}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-center">
                            <span
                              className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[metric.status]}`}
                            >
                              {metric.status}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* File Overlap */}
            {comparison.file_overlaps.length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
                  <h2 className="text-lg font-medium text-gray-900 dark:text-white">
                    File Changes
                  </h2>
                </div>
                <div className="divide-y divide-gray-200 dark:divide-gray-700">
                  {comparison.file_overlaps.map((overlap) => (
                    <div key={overlap.file_path} className="px-4 py-3">
                      <div className="flex items-center justify-between">
                        <code className="text-sm text-gray-900 dark:text-white font-mono">
                          {overlap.file_path}
                        </code>
                        <span className="text-sm text-gray-500 dark:text-gray-400">
                          Modified by {overlap.appears_in_count} run
                          {overlap.appears_in_count > 1 ? 's' : ''}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Logs Tab */}
        {activeTab === 'logs' && (
          <div className="bg-gray-900 rounded-lg shadow overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-700 flex items-center justify-between">
              <h2 className="text-lg font-medium text-white">Execution Logs</h2>
              <span className="text-sm text-gray-400">{logs.length} lines</span>
            </div>
            <div className="p-4 font-mono text-sm max-h-[600px] overflow-auto">
              {logs.length === 0 ? (
                <div className="text-gray-500">
                  {comparison.status === 'pending' || comparison.status === 'running'
                    ? 'Waiting for logs...'
                    : 'No logs available'}
                </div>
              ) : (
                logs.map((log, index) => (
                  <div key={index} className="text-gray-300 hover:bg-gray-800 px-2 py-0.5">
                    <span className="text-gray-500 mr-3 select-none">{log.line_number}</span>
                    {log.content}
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default function ComparisonPage() {
  const params = useParams();
  const taskId = params.taskId as string;
  const comparisonId = params.comparisonId as string;

  // Use key to reset state when comparisonId changes
  return <ComparisonContent key={comparisonId} taskId={taskId} comparisonId={comparisonId} />;
}
