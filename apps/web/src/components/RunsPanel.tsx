'use client';

import type { Run, RunStatus } from '@/types';
import { cn } from '@/lib/utils';
import { truncate } from '@/lib/utils';
import { RunListSkeleton } from './ui/Skeleton';
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  ClockIcon,
  ArrowPathIcon,
  XCircleIcon,
  InboxIcon,
  CommandLineIcon,
} from '@heroicons/react/24/outline';

interface RunsPanelProps {
  runs: Run[];
  selectedRunId: string | null;
  onSelectRun: (runId: string) => void;
  isLoading?: boolean;
}

const STATUS_CONFIG: Record<
  RunStatus,
  { color: string; icon: React.ReactNode; label: string }
> = {
  queued: {
    color: 'text-gray-400',
    icon: <ClockIcon className="w-4 h-4" />,
    label: 'Queued',
  },
  running: {
    color: 'text-yellow-400',
    icon: <ArrowPathIcon className="w-4 h-4 animate-spin" />,
    label: 'Running',
  },
  succeeded: {
    color: 'text-green-400',
    icon: <CheckCircleIcon className="w-4 h-4" />,
    label: 'Completed',
  },
  failed: {
    color: 'text-red-400',
    icon: <ExclamationCircleIcon className="w-4 h-4" />,
    label: 'Failed',
  },
  canceled: {
    color: 'text-gray-500',
    icon: <XCircleIcon className="w-4 h-4" />,
    label: 'Canceled',
  },
};

export function RunsPanel({
  runs,
  selectedRunId,
  onSelectRun,
  isLoading = false,
}: RunsPanelProps) {
  // Group runs by instruction (same batch)
  const groupedRuns: { instruction: string; runs: Run[] }[] = [];
  let currentInstruction = '';
  let currentGroup: Run[] = [];

  for (const run of runs) {
    if (run.instruction !== currentInstruction) {
      if (currentGroup.length > 0) {
        groupedRuns.push({ instruction: currentInstruction, runs: currentGroup });
      }
      currentInstruction = run.instruction;
      currentGroup = [run];
    } else {
      currentGroup.push(run);
    }
  }
  if (currentGroup.length > 0) {
    groupedRuns.push({ instruction: currentInstruction, runs: currentGroup });
  }

  if (isLoading) {
    return (
      <div className="flex flex-col h-full bg-gray-900 rounded-lg border border-gray-800">
        <div className="p-4 border-b border-gray-800">
          <h2 className="font-semibold text-gray-100">Runs</h2>
        </div>
        <RunListSkeleton count={3} />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-gray-900 rounded-lg border border-gray-800">
      <div className="p-4 border-b border-gray-800 flex items-center justify-between">
        <h2 className="font-semibold text-gray-100">Runs</h2>
        {runs.length > 0 && (
          <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">
            {runs.length}
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {groupedRuns.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <InboxIcon className="w-10 h-10 text-gray-700 mb-3" />
            <p className="text-gray-500 text-sm">No runs yet</p>
            <p className="text-gray-600 text-xs mt-1">
              Enter instructions to start
            </p>
          </div>
        ) : (
          groupedRuns.map((group, groupIndex) => (
            <div key={groupIndex} className="space-y-2">
              <div
                className="text-xs text-gray-500 px-1 font-medium"
                title={group.instruction}
              >
                {truncate(group.instruction, 60)}
              </div>
              <div className="space-y-1.5">
                {group.runs.map((run) => {
                  const statusConfig = STATUS_CONFIG[run.status];
                  const isSelected = selectedRunId === run.id;

                  return (
                    <button
                      key={run.id}
                      onClick={() => onSelectRun(run.id)}
                      className={cn(
                        'w-full p-3 rounded-lg text-left transition-all duration-150',
                        'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 focus:ring-offset-gray-900',
                        isSelected
                          ? 'bg-blue-900/40 border border-blue-700 shadow-sm'
                          : 'bg-gray-800 hover:bg-gray-750 border border-transparent hover:border-gray-700'
                      )}
                      aria-selected={isSelected}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-sm text-gray-100 flex items-center gap-1.5">
                          {run.executor_type === 'claude_code' ? (
                            <>
                              <CommandLineIcon className="w-4 h-4 text-purple-400" />
                              <span>Claude Code</span>
                            </>
                          ) : (
                            run.model_name
                          )}
                        </span>
                        <span
                          className={cn('flex items-center', statusConfig.color)}
                          title={statusConfig.label}
                          role="status"
                          aria-label={statusConfig.label}
                        >
                          {statusConfig.icon}
                        </span>
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        {run.executor_type === 'claude_code' ? (
                          run.working_branch ? (
                            <span className="font-mono text-purple-400">{run.working_branch}</span>
                          ) : (
                            'CLI Executor'
                          )
                        ) : (
                          run.provider
                        )}
                      </div>
                      {run.status === 'succeeded' && run.summary && (
                        <div className="text-xs text-gray-400 mt-2 line-clamp-2">
                          {run.summary}
                        </div>
                      )}
                      {run.status === 'failed' && run.error && (
                        <div className="text-xs text-red-400 mt-2 line-clamp-2">
                          {run.error}
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
