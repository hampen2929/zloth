'use client';

import { useState, useEffect, useMemo } from 'react';
import { cn } from '@/lib/utils';
import {
  ClockIcon,
  CheckIcon,
  ArrowPathIcon,
  FolderIcon,
  MagnifyingGlassIcon,
  CodeBracketIcon,
  DocumentTextIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';

interface ProgressDisplayProps {
  /** Run status */
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled';
  /** When the run started (ISO string) */
  startedAt: string | null;
  /** Recent log lines */
  logs: string[];
  /** Callback when user wants to cancel */
  onCancel?: () => void;
  /** Callback when user wants to view logs tab */
  onViewLogs?: () => void;
}

type StepStatus = 'pending' | 'running' | 'completed' | 'failed';

interface Step {
  id: string;
  label: string;
  icon: React.ReactNode;
  status: StepStatus;
}

// Keywords that indicate steps in the execution
const STEP_PATTERNS = {
  workspace: ['workspace', 'worktree', 'checkout', 'clone', 'preparing'],
  analysis: ['analyzing', 'analysis', 'scanning', 'reading', 'understanding'],
  generation: ['generating', 'writing', 'modifying', 'editing', 'creating'],
  patch: ['patch', 'diff', 'commit', 'staging', 'staged'],
} as const;

function detectCurrentStep(logs: string[]): string | null {
  // Check logs from most recent to oldest
  for (let i = logs.length - 1; i >= 0; i--) {
    const log = logs[i].toLowerCase();

    for (const [step, patterns] of Object.entries(STEP_PATTERNS)) {
      if (patterns.some((p) => log.includes(p))) {
        return step;
      }
    }
  }
  return null;
}

function getStepStatus(
  stepId: string,
  currentStep: string | null,
  runStatus: string
): StepStatus {
  const steps = ['workspace', 'analysis', 'generation', 'patch'];
  const currentIndex = currentStep ? steps.indexOf(currentStep) : -1;
  const stepIndex = steps.indexOf(stepId);

  if (runStatus === 'succeeded') {
    return 'completed';
  }
  if (runStatus === 'failed') {
    if (stepIndex <= currentIndex) {
      return stepIndex === currentIndex ? 'failed' : 'completed';
    }
    return 'pending';
  }

  if (stepIndex < currentIndex) {
    return 'completed';
  }
  if (stepIndex === currentIndex) {
    return 'running';
  }
  return 'pending';
}

function formatElapsedTime(startedAt: string): string {
  const start = new Date(startedAt).getTime();
  const now = Date.now();
  const elapsed = Math.floor((now - start) / 1000);

  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;

  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

export function ProgressDisplay({
  status,
  startedAt,
  logs,
  onCancel,
  onViewLogs,
}: ProgressDisplayProps) {
  const [elapsedTime, setElapsedTime] = useState('0:00');

  // Update elapsed time every second
  useEffect(() => {
    if (!startedAt || status !== 'running') return;

    const updateTime = () => {
      setElapsedTime(formatElapsedTime(startedAt));
    };

    updateTime();
    const interval = setInterval(updateTime, 1000);

    return () => clearInterval(interval);
  }, [startedAt, status]);

  // Detect current step from logs
  const currentStep = useMemo(() => detectCurrentStep(logs), [logs]);

  // Build steps array with status
  const steps: Step[] = useMemo(
    () => [
      {
        id: 'workspace',
        label: 'Preparing workspace',
        icon: <FolderIcon className="w-4 h-4" />,
        status: getStepStatus('workspace', currentStep, status),
      },
      {
        id: 'analysis',
        label: 'Analyzing code',
        icon: <MagnifyingGlassIcon className="w-4 h-4" />,
        status: getStepStatus('analysis', currentStep, status),
      },
      {
        id: 'generation',
        label: 'Generating changes',
        icon: <CodeBracketIcon className="w-4 h-4" />,
        status: getStepStatus('generation', currentStep, status),
      },
      {
        id: 'patch',
        label: 'Creating patch',
        icon: <DocumentTextIcon className="w-4 h-4" />,
        status: getStepStatus('patch', currentStep, status),
      },
    ],
    [currentStep, status]
  );

  // Get latest log lines for display
  const latestLogs = useMemo(() => {
    return logs.slice(-3).filter(Boolean);
  }, [logs]);

  return (
    <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          {status === 'running' && (
            <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          )}
          {status === 'queued' && (
            <ClockIcon className="w-8 h-8 text-gray-400" />
          )}
          <div>
            <h3 className="text-gray-100 font-medium">
              {status === 'running' ? 'Running...' : 'Queued'}
            </h3>
            {status === 'running' && startedAt && (
              <div className="flex items-center gap-1.5 text-sm text-gray-400 mt-0.5">
                <ClockIcon className="w-3.5 h-3.5" />
                <span>Elapsed: {elapsedTime}</span>
              </div>
            )}
          </div>
        </div>

        {onCancel && status === 'running' && (
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-sm text-red-400 hover:text-red-300 hover:bg-red-900/20 rounded transition-colors flex items-center gap-1.5"
          >
            <XMarkIcon className="w-4 h-4" />
            Cancel
          </button>
        )}
      </div>

      {/* Progress Steps */}
      {status === 'running' && (
        <div className="mb-4">
          <div className="text-xs text-gray-500 mb-2">Progress</div>
          <div className="space-y-2">
            {steps.map((step) => (
              <div
                key={step.id}
                className={cn(
                  'flex items-center gap-2 text-sm',
                  step.status === 'completed' && 'text-green-400',
                  step.status === 'running' && 'text-blue-400',
                  step.status === 'pending' && 'text-gray-600',
                  step.status === 'failed' && 'text-red-400'
                )}
              >
                <div className="w-5 h-5 flex items-center justify-center">
                  {step.status === 'completed' && (
                    <CheckIcon className="w-4 h-4" />
                  )}
                  {step.status === 'running' && (
                    <ArrowPathIcon className="w-4 h-4 animate-spin" />
                  )}
                  {step.status === 'pending' && (
                    <span className="w-2 h-2 bg-gray-600 rounded-full" />
                  )}
                  {step.status === 'failed' && (
                    <XMarkIcon className="w-4 h-4" />
                  )}
                </div>
                <span>{step.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Latest Logs */}
      {latestLogs.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-700">
          <div className="text-xs text-gray-500 mb-2">Latest output</div>
          <div className="font-mono text-xs text-gray-400 space-y-1 max-h-24 overflow-hidden">
            {latestLogs.map((log, i) => (
              <div key={i} className="truncate">
                &gt; {log}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* View Logs Button */}
      {onViewLogs && (
        <button
          onClick={onViewLogs}
          className="mt-4 text-sm text-blue-400 hover:text-blue-300 underline"
        >
          View full logs
        </button>
      )}
    </div>
  );
}
