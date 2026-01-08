'use client';

import { useMemo } from 'react';
import type { Run } from '@/types';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/i18n';
import {
  ClockIcon,
  PlayIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowPathIcon,
  DocumentDuplicateIcon,
} from '@heroicons/react/24/outline';

interface RunTimelineProps {
  run: Run;
  onFileClick?: (filePath: string) => void;
}

interface TimelineStep {
  id: string;
  labelKey: string;
  labelFallback: string;
  icon: React.ReactNode;
  status: 'completed' | 'in_progress' | 'pending' | 'error';
  timestamp?: string;
  details?: string;
}

function formatTime(dateString: string | null): string {
  if (!dateString) return '';
  const date = new Date(dateString);
  return date.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatDuration(startDate: string | null, endDate: string | null): string {
  if (!startDate) return '';
  const start = new Date(startDate).getTime();
  const end = endDate ? new Date(endDate).getTime() : Date.now();
  const durationMs = end - start;

  if (durationMs < 1000) return '<1s';

  const seconds = Math.floor(durationMs / 1000);
  if (seconds < 60) return `${seconds}s`;

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) return `${minutes}m ${remainingSeconds}s`;

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}

export function RunTimeline({ run, onFileClick }: RunTimelineProps) {
  const { t } = useTranslation();

  const steps = useMemo((): TimelineStep[] => {
    const result: TimelineStep[] = [];

    // Step 1: Queued
    result.push({
      id: 'queued',
      labelKey: 'timeline.queued',
      labelFallback: 'Queued',
      icon: <ClockIcon className="w-4 h-4" />,
      status: 'completed',
      timestamp: formatTime(run.created_at),
    });

    // Step 2: Started
    if (run.started_at) {
      result.push({
        id: 'started',
        labelKey: 'timeline.started',
        labelFallback: 'Started',
        icon: <PlayIcon className="w-4 h-4" />,
        status: run.status === 'running' ? 'in_progress' : 'completed',
        timestamp: formatTime(run.started_at),
      });
    } else if (run.status === 'queued') {
      result.push({
        id: 'started',
        labelKey: 'timeline.started',
        labelFallback: 'Waiting to start...',
        icon: <PlayIcon className="w-4 h-4" />,
        status: 'pending',
      });
    }

    // Step 3: Processing (show for running or completed runs)
    if (run.status === 'running') {
      result.push({
        id: 'processing',
        labelKey: 'timeline.processing',
        labelFallback: 'Processing...',
        icon: <ArrowPathIcon className="w-4 h-4 animate-spin" />,
        status: 'in_progress',
        details: run.started_at ? formatDuration(run.started_at, null) : undefined,
      });
    }

    // Step 4: Completed
    if (run.status === 'succeeded' || run.status === 'failed' || run.status === 'canceled') {
      const isSuccess = run.status === 'succeeded';
      const isFailed = run.status === 'failed';

      result.push({
        id: 'completed',
        labelKey: isSuccess ? 'timeline.completed' : isFailed ? 'timeline.failed' : 'timeline.canceled',
        labelFallback: isSuccess ? 'Completed' : isFailed ? 'Failed' : 'Canceled',
        icon: isSuccess
          ? <CheckCircleIcon className="w-4 h-4" />
          : <XCircleIcon className="w-4 h-4" />,
        status: isSuccess ? 'completed' : 'error',
        timestamp: formatTime(run.completed_at),
        details: run.started_at && run.completed_at
          ? formatDuration(run.started_at, run.completed_at)
          : undefined,
      });
    }

    return result;
  }, [run]);

  const getStepTextWithFallback = (step: TimelineStep): string => {
    try {
      const translated = t(step.labelKey);
      return translated === step.labelKey ? step.labelFallback : translated;
    } catch {
      return step.labelFallback;
    }
  };

  return (
    <div className="space-y-4">
      {/* Timeline */}
      <div className="relative">
        <div className="flex items-start gap-2">
          {steps.map((step, index) => (
            <div key={step.id} className="flex items-center">
              {/* Step indicator */}
              <div className="flex flex-col items-center">
                <div
                  className={cn(
                    'w-8 h-8 rounded-full flex items-center justify-center transition-colors',
                    step.status === 'completed' && 'bg-green-600 text-white',
                    step.status === 'in_progress' && 'bg-blue-600 text-white',
                    step.status === 'pending' && 'bg-gray-700 text-gray-400',
                    step.status === 'error' && 'bg-red-600 text-white'
                  )}
                >
                  {step.icon}
                </div>
                <div className="mt-2 text-center">
                  <div className={cn(
                    'text-xs font-medium',
                    step.status === 'completed' && 'text-gray-200',
                    step.status === 'in_progress' && 'text-blue-400',
                    step.status === 'pending' && 'text-gray-500',
                    step.status === 'error' && 'text-red-400'
                  )}>
                    {getStepTextWithFallback(step)}
                  </div>
                  {step.timestamp && (
                    <div className="text-xs text-gray-500 mt-0.5">{step.timestamp}</div>
                  )}
                  {step.details && (
                    <div className="text-xs text-gray-400 mt-0.5">{step.details}</div>
                  )}
                </div>
              </div>

              {/* Connector line */}
              {index < steps.length - 1 && (
                <div
                  className={cn(
                    'h-0.5 w-8 mx-2 mt-[-1rem]',
                    step.status === 'completed' || step.status === 'error'
                      ? 'bg-gray-600'
                      : 'bg-gray-700'
                  )}
                />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Changed files summary with click-to-navigate */}
      {run.status === 'succeeded' && run.files_changed && run.files_changed.length > 0 && (
        <div className="pt-4 border-t border-gray-800">
          <div className="flex items-center gap-2 mb-2">
            <DocumentDuplicateIcon className="w-4 h-4 text-gray-400" />
            <span className="text-sm font-medium text-gray-300">
              Changed Files ({run.files_changed.length})
            </span>
          </div>
          <div className="space-y-1">
            {run.files_changed.slice(0, 5).map((file) => (
              <button
                key={file.path}
                onClick={() => onFileClick?.(file.path)}
                className={cn(
                  'w-full flex items-center justify-between px-2 py-1 rounded text-left',
                  'hover:bg-gray-800 transition-colors',
                  'text-xs font-mono text-gray-400 hover:text-gray-200'
                )}
              >
                <span className="truncate flex-1">{file.path}</span>
                <span className="flex items-center gap-1 ml-2 text-xs">
                  <span className="text-green-500">+{file.added_lines}</span>
                  <span className="text-red-500">-{file.removed_lines}</span>
                </span>
              </button>
            ))}
            {run.files_changed.length > 5 && (
              <div className="text-xs text-gray-500 px-2">
                +{run.files_changed.length - 5} more files
              </div>
            )}
          </div>
        </div>
      )}

      {/* Run metadata */}
      <div className="pt-4 border-t border-gray-800 grid grid-cols-2 gap-4 text-xs">
        {run.model_name && (
          <div>
            <span className="text-gray-500">Model: </span>
            <span className="text-gray-300">{run.model_name}</span>
          </div>
        )}
        {run.working_branch && (
          <div>
            <span className="text-gray-500">Branch: </span>
            <span className="text-gray-300 font-mono">{run.working_branch}</span>
          </div>
        )}
        {run.executor_type && (
          <div>
            <span className="text-gray-500">Executor: </span>
            <span className="text-gray-300">{run.executor_type.replace('_', ' ')}</span>
          </div>
        )}
        {run.commit_sha && (
          <div>
            <span className="text-gray-500">Commit: </span>
            <span className="text-gray-300 font-mono">{run.commit_sha.slice(0, 7)}</span>
          </div>
        )}
      </div>
    </div>
  );
}
