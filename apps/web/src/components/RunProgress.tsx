'use client';

import { useState, useEffect, useMemo } from 'react';
import { ClockIcon, CheckCircleIcon, XCircleIcon } from '@heroicons/react/24/outline';
import type { RunStatus } from '@/types';

interface RunProgressProps {
  status: RunStatus;
  startedAt?: string | null;
  logs?: string[];
  executorType?: string;
}

interface ProgressStep {
  id: string;
  label: string;
  status: 'pending' | 'active' | 'complete' | 'error';
}

const STEP_PATTERNS: Record<string, RegExp[]> = {
  prepare: [/workspace/i, /clone/i, /checkout/i, /setting up/i],
  analyze: [/analyz/i, /reading/i, /understanding/i, /scanning/i],
  generate: [/generat/i, /writing/i, /creating/i, /modifying/i],
  finalize: [/patch/i, /commit/i, /finaliz/i, /complet/i],
};

function inferCurrentStep(logs: string[]): number {
  if (!logs || logs.length === 0) return 0;

  // Check logs from newest to oldest
  for (let i = logs.length - 1; i >= 0; i--) {
    const log = logs[i].toLowerCase();

    if (STEP_PATTERNS.finalize.some((p) => p.test(log))) return 3;
    if (STEP_PATTERNS.generate.some((p) => p.test(log))) return 2;
    if (STEP_PATTERNS.analyze.some((p) => p.test(log))) return 1;
    if (STEP_PATTERNS.prepare.some((p) => p.test(log))) return 0;
  }

  return 0;
}

function formatElapsedTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function RunProgress({ status, startedAt, logs = [], executorType }: RunProgressProps) {
  const currentStep = useMemo(() => inferCurrentStep(logs), [logs]);

  // Calculate elapsed time using useMemo for initial value
  const startTime = useMemo(() => {
    if (status !== 'running' || !startedAt) return null;
    return new Date(startedAt).getTime();
  }, [status, startedAt]);

  const [elapsed, setElapsed] = useState(() => {
    if (!startTime) return 0;
    return Math.floor((Date.now() - startTime) / 1000);
  });

  // Update elapsed time periodically
  useEffect(() => {
    if (!startTime) return;

    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    return () => clearInterval(interval);
  }, [startTime]);

  const steps: ProgressStep[] = useMemo(() => {
    const baseSteps = [
      { id: 'prepare', label: 'Preparing workspace' },
      { id: 'analyze', label: 'Analyzing code' },
      { id: 'generate', label: 'Generating changes' },
      { id: 'finalize', label: 'Creating patch' },
    ];

    return baseSteps.map((step, index) => {
      let stepStatus: ProgressStep['status'] = 'pending';

      if (status === 'failed') {
        stepStatus = index <= currentStep ? 'error' : 'pending';
      } else if (status === 'succeeded') {
        stepStatus = 'complete';
      } else if (status === 'running') {
        if (index < currentStep) {
          stepStatus = 'complete';
        } else if (index === currentStep) {
          stepStatus = 'active';
        }
      }

      return { ...step, status: stepStatus };
    });
  }, [status, currentStep]);

  const lastLog = logs.length > 0 ? logs[logs.length - 1] : null;

  if (status !== 'running' && status !== 'queued') {
    return null;
  }

  return (
    <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {status === 'running' ? (
            <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          ) : (
            <div className="w-4 h-4 border-2 border-gray-500 rounded-full" />
          )}
          <span className="font-medium text-gray-200">
            {status === 'queued' ? 'Queued' : 'Running'}
            {executorType && <span className="text-gray-500 ml-1">({executorType})</span>}
          </span>
        </div>

        {status === 'running' && startedAt && (
          <div className="flex items-center gap-1 text-gray-400 text-sm">
            <ClockIcon className="w-4 h-4" />
            <span>{formatElapsedTime(elapsed)}</span>
          </div>
        )}
      </div>

      {/* Steps */}
      <div className="space-y-2">
        {steps.map((step) => (
          <div key={step.id} className="flex items-center gap-3">
            <div className="flex-shrink-0">
              {step.status === 'complete' ? (
                <CheckCircleIcon className="w-5 h-5 text-green-500" />
              ) : step.status === 'active' ? (
                <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              ) : step.status === 'error' ? (
                <XCircleIcon className="w-5 h-5 text-red-500" />
              ) : (
                <div className="w-5 h-5 rounded-full border border-gray-600" />
              )}
            </div>
            <span
              className={
                step.status === 'complete'
                  ? 'text-gray-400'
                  : step.status === 'active'
                    ? 'text-gray-200'
                    : step.status === 'error'
                      ? 'text-red-400'
                      : 'text-gray-500'
              }
            >
              {step.label}
            </span>
          </div>
        ))}
      </div>

      {/* Last log line */}
      {lastLog && (
        <div className="mt-4 pt-4 border-t border-gray-700/50">
          <p className="text-xs text-gray-500 mb-1">Latest output:</p>
          <code className="text-xs text-gray-400 font-mono block truncate">{lastLog}</code>
        </div>
      )}
    </div>
  );
}
