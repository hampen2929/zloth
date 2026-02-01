'use client';

import { useMemo } from 'react';
import {
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  DocumentDuplicateIcon,
} from '@heroicons/react/24/outline';
import type { Run, RunStatus } from '@/types';
import { Button } from './ui/Button';

interface RunComparisonPanelProps {
  runs: Run[];
  onSelectRun: (runId: string) => void;
  selectedRunId?: string | null;
}

interface RunSummary {
  id: string;
  executorType: string;
  modelName: string | null;
  status: RunStatus;
  filesChanged: number;
  additions: number;
  deletions: number;
  hasWarnings: boolean;
}

function getStatusIcon(status: RunStatus, hasWarnings: boolean) {
  if (status === 'succeeded' && hasWarnings) {
    return <ExclamationTriangleIcon className="w-5 h-5 text-yellow-500" />;
  }
  switch (status) {
    case 'succeeded':
      return <CheckCircleIcon className="w-5 h-5 text-green-500" />;
    case 'failed':
      return <XCircleIcon className="w-5 h-5 text-red-500" />;
    case 'running':
      return (
        <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      );
    case 'queued':
      return <div className="w-5 h-5 rounded-full border-2 border-gray-500" />;
    default:
      return <div className="w-5 h-5 rounded-full border-2 border-gray-600" />;
  }
}

function getStatusLabel(status: RunStatus, hasWarnings: boolean): string {
  if (status === 'succeeded' && hasWarnings) return 'Completed with warnings';
  switch (status) {
    case 'succeeded':
      return 'Succeeded';
    case 'failed':
      return 'Failed';
    case 'running':
      return 'Running';
    case 'queued':
      return 'Queued';
    case 'canceled':
      return 'Canceled';
    default:
      return status;
  }
}

export function RunComparisonPanel({
  runs,
  onSelectRun,
  selectedRunId,
}: RunComparisonPanelProps) {
  const summaries: RunSummary[] = useMemo(() => {
    return runs.map((run) => ({
      id: run.id,
      executorType: run.executor_type,
      modelName: run.model_name,
      status: run.status,
      filesChanged: run.files_changed?.length ?? 0,
      additions: run.files_changed?.reduce((sum, f) => sum + f.added_lines, 0) ?? 0,
      deletions: run.files_changed?.reduce((sum, f) => sum + f.removed_lines, 0) ?? 0,
      hasWarnings: (run.warnings?.length ?? 0) > 0,
    }));
  }, [runs]);

  // Count by status
  const statusCounts = useMemo(() => {
    return summaries.reduce(
      (acc, run) => {
        acc[run.status] = (acc[run.status] || 0) + 1;
        return acc;
      },
      {} as Record<string, number>
    );
  }, [summaries]);

  if (runs.length < 2) {
    return null;
  }

  return (
    <div className="border border-gray-700 rounded-lg overflow-hidden bg-gray-800/30">
      {/* Header */}
      <div className="px-4 py-3 bg-gray-800/50 border-b border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <DocumentDuplicateIcon className="w-5 h-5 text-gray-400" />
          <h3 className="font-medium text-gray-200">Compare Results</h3>
        </div>
        <div className="flex items-center gap-3 text-sm">
          {statusCounts.succeeded && (
            <span className="text-green-400">{statusCounts.succeeded} succeeded</span>
          )}
          {statusCounts.failed && (
            <span className="text-red-400">{statusCounts.failed} failed</span>
          )}
          {statusCounts.running && (
            <span className="text-blue-400">{statusCounts.running} running</span>
          )}
        </div>
      </div>

      {/* Comparison grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 divide-x divide-gray-700">
        {summaries.map((run) => (
          <div
            key={run.id}
            className={`p-4 transition-colors ${
              selectedRunId === run.id
                ? 'bg-blue-900/20 ring-2 ring-blue-500/50 ring-inset'
                : 'hover:bg-gray-800/30'
            }`}
          >
            {/* Executor name */}
            <div className="flex items-center gap-2 mb-3">
              <span className="font-medium text-gray-200 truncate">
                {run.modelName || run.executorType}
              </span>
            </div>

            {/* Status */}
            <div className="flex items-center gap-2 mb-3">
              {getStatusIcon(run.status, run.hasWarnings)}
              <span
                className={`text-sm ${
                  run.status === 'succeeded'
                    ? run.hasWarnings
                      ? 'text-yellow-400'
                      : 'text-green-400'
                    : run.status === 'failed'
                      ? 'text-red-400'
                      : run.status === 'running'
                        ? 'text-blue-400'
                        : 'text-gray-400'
                }`}
              >
                {getStatusLabel(run.status, run.hasWarnings)}
              </span>
            </div>

            {/* Stats */}
            {run.status === 'succeeded' && (
              <div className="text-sm text-gray-400 space-y-1 mb-3">
                <div>Files: {run.filesChanged}</div>
                <div>
                  <span className="text-green-400">+{run.additions}</span>
                  {' / '}
                  <span className="text-red-400">-{run.deletions}</span>
                </div>
              </div>
            )}

            {/* Action button */}
            <Button
              size="sm"
              variant={selectedRunId === run.id ? 'primary' : 'secondary'}
              onClick={() => onSelectRun(run.id)}
              className="w-full"
              disabled={run.status === 'running' || run.status === 'queued'}
            >
              {selectedRunId === run.id ? 'Selected' : 'View'}
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}
