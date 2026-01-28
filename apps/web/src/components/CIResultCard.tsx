'use client';

import { useState } from 'react';
import type { CICheck } from '@/types';
import { cn } from '@/lib/utils';
import {
  ChevronDownIcon,
  ChevronUpIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';

interface CIResultCardProps {
  ciCheck: CICheck;
  expanded?: boolean;
  onToggleExpand?: () => void;
}

export function CIResultCard({
  ciCheck,
  expanded: controlledExpanded,
  onToggleExpand,
}: CIResultCardProps) {
  const [internalExpanded, setInternalExpanded] = useState(true);
  const expanded = controlledExpanded ?? internalExpanded;

  const handleToggle = () => {
    if (onToggleExpand) {
      onToggleExpand();
    } else {
      setInternalExpanded((prev) => !prev);
    }
  };

  const getStatusColor = () => {
    switch (ciCheck.status) {
      case 'success':
        return 'border-green-500/30 bg-green-900/10';
      case 'failure':
        return 'border-red-500/30 bg-red-900/10';
      case 'pending':
        return 'border-yellow-500/30 bg-yellow-900/10';
      case 'error':
      case 'timeout':
        return 'border-red-500/30 bg-red-900/10';
      case 'superseded':
        return 'border-gray-500/30 bg-gray-900/10';
      default:
        return 'border-gray-700 bg-gray-800/50';
    }
  };

  const getStatusIcon = () => {
    switch (ciCheck.status) {
      case 'success':
        return <CheckCircleIcon className="w-5 h-5 text-green-400" />;
      case 'failure':
        return <XCircleIcon className="w-5 h-5 text-red-400" />;
      case 'pending':
        return <ClockIcon className="w-5 h-5 text-yellow-400 animate-pulse" />;
      case 'error':
      case 'timeout':
        return <ExclamationTriangleIcon className="w-5 h-5 text-red-400" />;
      case 'superseded':
        return <span className="w-5 h-5 text-gray-500">○</span>;
      default:
        return <ClockIcon className="w-5 h-5 text-gray-400" />;
    }
  };

  const getStatusBadge = () => {
    const statusConfig: Record<string, { bg: string; text: string; label: string }> = {
      success: { bg: 'bg-green-500/20', text: 'text-green-400', label: 'Success' },
      failure: { bg: 'bg-red-500/20', text: 'text-red-400', label: 'Failure' },
      pending: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: 'Pending' },
      error: { bg: 'bg-red-500/20', text: 'text-red-400', label: 'Error' },
      timeout: { bg: 'bg-orange-500/20', text: 'text-orange-400', label: 'Timeout' },
      superseded: { bg: 'bg-gray-500/20', text: 'text-gray-400', label: 'Superseded' },
    };
    const config = statusConfig[ciCheck.status] || statusConfig.pending;
    return (
      <span className={cn('px-2 py-0.5 text-xs font-medium rounded', config.bg, config.text)}>
        {config.label}
      </span>
    );
  };

  const getJobIcon = (result: string) => {
    switch (result) {
      case 'success':
        return <CheckCircleIcon className="w-4 h-4 text-green-400" />;
      case 'failure':
      case 'cancelled':
      case 'timed_out':
        return <XCircleIcon className="w-4 h-4 text-red-400" />;
      case 'skipped':
        return <span className="w-4 h-4 text-gray-500">○</span>;
      case 'in_progress':
      case 'queued':
        return <ClockIcon className="w-4 h-4 text-yellow-400 animate-pulse" />;
      default:
        return <span className="w-4 h-4 text-gray-500">•</span>;
    }
  };

  const jobs = Object.entries(ciCheck.jobs);
  const successCount = jobs.filter(([, result]) => result === 'success').length;
  const failureCount = jobs.filter(
    ([, result]) => result === 'failure' || result === 'cancelled' || result === 'timed_out'
  ).length;
  const skippedCount = jobs.filter(([, result]) => result === 'skipped').length;
  const pendingCount = jobs.filter(
    ([, result]) => result === 'in_progress' || result === 'queued' || result === 'pending'
  ).length;

  return (
    <div
      className={cn(
        'rounded-lg border animate-in fade-in slide-in-from-top-2 duration-300',
        getStatusColor()
      )}
    >
      {/* Header */}
      <button
        onClick={handleToggle}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-800/30 transition-colors rounded-t-lg"
      >
        <div className="flex items-center gap-3">
          {getStatusIcon()}
          <div className="text-left">
            <div className="font-medium text-gray-200 text-sm">CI Check</div>
            {ciCheck.sha && (
              <div className="text-xs text-gray-500 font-mono">
                {ciCheck.sha.substring(0, 7)}
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {getStatusBadge()}
          {expanded ? (
            <ChevronUpIcon className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronDownIcon className="w-4 h-4 text-gray-400" />
          )}
        </div>
      </button>

      {/* Expanded Content */}
      {expanded && (
        <div className="border-t border-gray-700/50 p-4">
          {/* Job Summary */}
          {jobs.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center gap-4 text-xs text-gray-400">
                <span className="flex items-center gap-1">
                  <CheckCircleIcon className="w-3.5 h-3.5 text-green-400" />
                  {successCount} passed
                </span>
                {failureCount > 0 && (
                  <span className="flex items-center gap-1">
                    <XCircleIcon className="w-3.5 h-3.5 text-red-400" />
                    {failureCount} failed
                  </span>
                )}
                {skippedCount > 0 && (
                  <span className="flex items-center gap-1">
                    <span className="text-gray-500">○</span>
                    {skippedCount} skipped
                  </span>
                )}
                {pendingCount > 0 && (
                  <span className="flex items-center gap-1">
                    <ClockIcon className="w-3.5 h-3.5 text-yellow-400" />
                    {pendingCount} running
                  </span>
                )}
              </div>

              {/* Job List */}
              <div className="space-y-1">
                <h4 className="text-xs font-medium text-gray-400">Jobs</h4>
                <div className="bg-gray-800/50 rounded-lg p-2 space-y-1 max-h-40 overflow-y-auto">
                  {jobs.map(([jobName, result]) => (
                    <div
                      key={jobName}
                      className="flex items-center justify-between py-1 px-2 rounded hover:bg-gray-700/50"
                    >
                      <div className="flex items-center gap-2">
                        {getJobIcon(result)}
                        <span className="text-sm text-gray-300">{jobName}</span>
                      </div>
                      <span
                        className={cn(
                          'text-xs',
                          result === 'success' && 'text-green-400',
                          (result === 'failure' || result === 'cancelled' || result === 'timed_out') && 'text-red-400',
                          result === 'skipped' && 'text-gray-500',
                          (result === 'in_progress' || result === 'queued' || result === 'pending') && 'text-yellow-400'
                        )}
                      >
                        {result}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* No jobs (pending or error) */}
          {jobs.length === 0 && (
            <div className="text-center py-4">
              {ciCheck.status === 'pending' ? (
                <div className="flex flex-col items-center">
                  <ClockIcon className="w-8 h-8 text-yellow-400 animate-pulse" />
                  <p className="mt-2 text-gray-400 text-sm">Waiting for CI to start...</p>
                </div>
              ) : ciCheck.status === 'error' ? (
                <div className="flex flex-col items-center">
                  <ExclamationTriangleIcon className="w-8 h-8 text-red-400" />
                  <p className="mt-2 text-gray-400 text-sm">Failed to check CI status</p>
                </div>
              ) : ciCheck.status === 'timeout' ? (
                <div className="flex flex-col items-center">
                  <ExclamationTriangleIcon className="w-8 h-8 text-orange-400" />
                  <p className="mt-2 text-gray-400 text-sm">CI check timed out</p>
                </div>
              ) : ciCheck.status === 'superseded' ? (
                <div className="flex flex-col items-center">
                  <span className="text-gray-500 text-3xl">○</span>
                  <p className="mt-2 text-gray-400 text-sm">Superseded by newer commit</p>
                </div>
              ) : (
                <p className="text-gray-400 text-sm">No CI jobs found</p>
              )}
            </div>
          )}

          {/* Failed Jobs with Error Logs */}
          {ciCheck.failed_jobs.length > 0 && (
            <div className="mt-4 space-y-2">
              <h4 className="text-xs font-medium text-red-400 flex items-center gap-1">
                <XCircleIcon className="w-3.5 h-3.5" />
                Failed Jobs ({ciCheck.failed_jobs.length})
              </h4>
              <div className="space-y-2">
                {ciCheck.failed_jobs.map((job) => (
                  <div
                    key={job.job_name}
                    className="bg-red-900/20 border border-red-800/50 rounded-lg p-3"
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <XCircleIcon className="w-4 h-4 text-red-400" />
                      <span className="text-sm font-medium text-red-300">{job.job_name}</span>
                      <span className="text-xs text-red-400/70">{job.result}</span>
                    </div>
                    {job.error_log && (
                      <pre className="text-xs text-gray-400 bg-gray-900/50 rounded p-2 overflow-x-auto max-h-32 overflow-y-auto whitespace-pre-wrap">
                        {job.error_log}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Timestamp */}
          <div className="mt-3 pt-3 border-t border-gray-700/50 text-xs text-gray-500">
            Checked at: {new Date(ciCheck.updated_at).toLocaleString()}
          </div>
        </div>
      )}
    </div>
  );
}
