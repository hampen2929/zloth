'use client';

import type { Run } from '@/types';
import { cn } from '@/lib/utils';
import { isCLIExecutor, getExecutorDisplayName } from '@/hooks';
import { StatusBadge, getStatusBorderColor, getStatusBackgroundColor } from './ui/StatusBadge';
import { DiffViewer } from './DiffViewer';
import { StreamingLogs } from './StreamingLogs';
import {
  CpuChipIcon,
  CommandLineIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  DocumentTextIcon,
  CodeBracketIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  DocumentDuplicateIcon,
} from '@heroicons/react/24/outline';

export type RunTab = 'summary' | 'diff' | 'logs';

const runTabConfig: { id: RunTab; label: string; icon: React.ReactNode }[] = [
  { id: 'summary', label: 'Summary', icon: <DocumentTextIcon className="w-4 h-4" /> },
  { id: 'diff', label: 'Diff', icon: <CodeBracketIcon className="w-4 h-4" /> },
  { id: 'logs', label: 'Logs', icon: <CommandLineIcon className="w-4 h-4" /> },
];

export interface RunResultCardProps {
  run: Run;
  expanded: boolean;
  onToggleExpand: () => void;
  activeTab: RunTab;
  onTabChange: (tab: RunTab) => void;
}

export function RunResultCard({
  run,
  expanded,
  onToggleExpand,
  activeTab,
  onTabChange,
}: RunResultCardProps) {
  const isCLI = isCLIExecutor(run.executor_type);
  const displayName = isCLI
    ? getExecutorDisplayName(run.executor_type)
    : run.model_name;

  return (
    <div
      className={cn(
        'rounded-lg border animate-in fade-in slide-in-from-top-2 duration-300',
        getStatusBorderColor(run.status, isCLI),
        getStatusBackgroundColor(run.status, isCLI)
      )}
    >
      {/* Header - Always visible */}
      <button
        onClick={onToggleExpand}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-800/30 transition-colors rounded-t-lg"
      >
        <div className="flex items-center gap-3">
          {isCLI ? (
            <CommandLineIcon className="w-5 h-5 text-purple-400" />
          ) : (
            <CpuChipIcon className="w-5 h-5 text-blue-400" />
          )}
          <div className="text-left">
            <div className="font-medium text-gray-200 text-sm">{displayName}</div>
            {isCLI && run.working_branch && (
              <div className="text-xs font-mono text-purple-400">{run.working_branch}</div>
            )}
            {!isCLI && run.provider && (
              <div className="text-xs text-gray-500">{run.provider}</div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={run.status} />
          {expanded ? (
            <ChevronUpIcon className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronDownIcon className="w-4 h-4 text-gray-400" />
          )}
        </div>
      </button>

      {/* Expanded Content */}
      {expanded && (
        <div className="border-t border-gray-700/50">
          {/* Running State - Show streaming logs */}
          {run.status === 'running' && (
            <div className="p-4">
              <StreamingLogs runId={run.id} isRunning={true} initialLogs={run.logs} />
            </div>
          )}

          {/* Queued State - Show waiting message with any existing logs */}
          {run.status === 'queued' && (
            <div className="p-4">
              <div className="flex flex-col items-center justify-center py-4 mb-4">
                <ClockIcon className="w-8 h-8 text-gray-500 mb-3" />
                <p className="text-gray-400 font-medium text-sm">Waiting in queue...</p>
                <p className="text-gray-500 text-xs mt-1">Your run will start soon</p>
              </div>
              {run.logs && run.logs.length > 0 && (
                <StreamingLogs runId={run.id} isRunning={false} initialLogs={run.logs} />
              )}
            </div>
          )}

          {/* Failed State */}
          {run.status === 'failed' && (
            <div className="p-4 space-y-4">
              <div className="p-3 bg-red-900/20 border border-red-800/50 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <ExclamationTriangleIcon className="w-4 h-4 text-red-400" />
                  <h3 className="font-medium text-red-400 text-sm">Execution Failed</h3>
                </div>
                <p className="text-sm text-red-300">{run.error}</p>
              </div>
              {/* Show logs if available */}
              {run.logs && run.logs.length > 0 && (
                <div className="font-mono text-xs space-y-0.5 bg-gray-800/50 rounded-lg p-3 max-h-64 overflow-y-auto">
                  {run.logs.map((log, i) => (
                    <div key={i} className="text-gray-400 leading-relaxed">
                      <span className="text-gray-600 mr-2 select-none">{i + 1}</span>
                      {log}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Succeeded State */}
          {run.status === 'succeeded' && (
            <>
              {/* Tabs */}
              <div className="flex border-b border-gray-700/50 mt-3 px-4" role="tablist">
                {runTabConfig.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => onTabChange(tab.id)}
                    role="tab"
                    aria-selected={activeTab === tab.id}
                    className={cn(
                      'flex items-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors',
                      'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset',
                      activeTab === tab.id
                        ? 'text-blue-400 border-b-2 border-blue-500 -mb-[1px]'
                        : 'text-gray-400 hover:text-gray-300'
                    )}
                  >
                    {tab.icon}
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              <div className="p-4 max-h-96 overflow-y-auto" role="tabpanel">
                {activeTab === 'summary' && <SummaryTab run={run} />}
                {activeTab === 'diff' && <DiffViewer patch={run.patch || ''} />}
                {activeTab === 'logs' && <LogsTab logs={run.logs} />}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function SummaryTab({ run }: { run: Run }) {
  return (
    <div className="space-y-4">
      <div>
        <h3 className="font-medium text-gray-200 text-sm mb-2 flex items-center gap-2">
          <DocumentTextIcon className="w-5 h-5 text-gray-400" />
          <span>Summary</span>
        </h3>
        <p className="text-gray-300 text-sm leading-relaxed">{run.summary}</p>
      </div>

      {run.warnings && run.warnings.length > 0 && (
        <div className="p-3 bg-yellow-900/20 border border-yellow-800/50 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <ExclamationTriangleIcon className="w-4 h-4 text-yellow-400" />
            <h4 className="text-xs font-medium text-yellow-400">
              Warnings ({run.warnings.length})
            </h4>
          </div>
          <ul className="list-disc list-inside text-xs text-yellow-300 space-y-1">
            {run.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {run.files_changed && run.files_changed.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <DocumentDuplicateIcon className="w-4 h-4 text-gray-400" />
            <h4 className="text-xs font-medium text-gray-300">
              Files Changed ({run.files_changed.length})
            </h4>
          </div>
          <ul className="space-y-1.5">
            {run.files_changed.map((f, i) => (
              <li
                key={i}
                className="flex items-center justify-between p-2 bg-gray-800/50 rounded text-xs"
              >
                <span className="font-mono text-gray-300 truncate mr-2">{f.path}</span>
                <span className="flex-shrink-0 text-xs font-medium">
                  <span className="text-green-400">+{f.added_lines}</span>
                  <span className="text-gray-600 mx-1">/</span>
                  <span className="text-red-400">-{f.removed_lines}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function LogsTab({ logs }: { logs?: string[] }) {
  if (!logs || logs.length === 0) {
    return <p className="text-gray-500 text-center py-4">No logs available.</p>;
  }

  return (
    <div className="font-mono text-xs space-y-0.5 bg-gray-800/50 rounded-lg p-3">
      {logs.map((log, i) => (
        <div key={i} className="text-gray-400 leading-relaxed">
          <span className="text-gray-600 mr-2 select-none">{i + 1}</span>
          {log}
        </div>
      ))}
    </div>
  );
}
