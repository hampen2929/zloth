'use client';

import type { Run, SummaryType } from '@/types';
import { cn } from '@/lib/utils';
import { deriveStructuredSummary, getSummaryTypeStyles } from '@/lib/summary-utils';
import { isCLIExecutor, getExecutorDisplayName } from '@/hooks';
import { StatusBadge, getStatusBorderColor, getStatusBackgroundColor } from './ui/StatusBadge';
import { DiffViewer } from './DiffViewer';
import { StreamingLogs } from './StreamingLogs';
import Markdown from 'react-markdown';
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
  ChatBubbleLeftRightIcon,
  MagnifyingGlassIcon,
  CheckCircleIcon,
  LightBulbIcon,
  DocumentMagnifyingGlassIcon,
  SparklesIcon,
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
  const modelLabel = isCLI
    ? getExecutorDisplayName(run.executor_type)
    : (run.model_name || 'Model');
  const headerLabel = `Implementation(${modelLabel})`;

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
            <div className="font-medium text-gray-200 text-sm">{headerLabel}</div>
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
          {/* Tabs - shown for running, queued, and succeeded states */}
          {(run.status === 'running' || run.status === 'queued' || run.status === 'succeeded') && (
            <>
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
                    {/* Streaming indicator for logs tab when running */}
                    {tab.id === 'logs' && run.status === 'running' && (
                      <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse ml-1" />
                    )}
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              <div className="p-4 max-h-96 overflow-y-auto" role="tabpanel">
                {activeTab === 'summary' && (
                  run.status === 'succeeded' ? (
                    <SummaryTab run={run} />
                  ) : (
                    <div className="flex flex-col items-center justify-center py-4">
                      <ClockIcon className="w-8 h-8 text-gray-500 mb-3" />
                      <p className="text-gray-400 font-medium text-sm">
                        {run.status === 'running' ? 'Running...' : 'Waiting in queue...'}
                      </p>
                      <p className="text-gray-500 text-xs mt-1">Summary will be available when completed</p>
                    </div>
                  )
                )}
                {activeTab === 'diff' && (
                  run.status === 'succeeded' ? (
                    <DiffViewer patch={run.patch || ''} />
                  ) : (
                    <div className="flex flex-col items-center justify-center py-4">
                      <ClockIcon className="w-8 h-8 text-gray-500 mb-3" />
                      <p className="text-gray-400 font-medium text-sm">
                        {run.status === 'running' ? 'Running...' : 'Waiting in queue...'}
                      </p>
                      <p className="text-gray-500 text-xs mt-1">Diff will be available when completed</p>
                    </div>
                  )
                )}
                {activeTab === 'logs' && (
                  <StreamingLogs
                    runId={run.id}
                    isRunning={run.status === 'running' || run.status === 'queued'}
                    initialLogs={run.logs}
                  />
                )}
              </div>
            </>
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
        </div>
      )}
    </div>
  );
}

/**
 * Get icon for summary type
 */
function getSummaryTypeIcon(type: SummaryType) {
  switch (type) {
    case 'code_change':
      return <CodeBracketIcon className="w-5 h-5" />;
    case 'qa_response':
      return <ChatBubbleLeftRightIcon className="w-5 h-5" />;
    case 'analysis':
      return <MagnifyingGlassIcon className="w-5 h-5" />;
    case 'no_action':
      return <CheckCircleIcon className="w-5 h-5" />;
  }
}

function SummaryTab({ run }: { run: Run }) {
  const structuredSummary = deriveStructuredSummary(run);
  const typeStyles = getSummaryTypeStyles(structuredSummary.type);
  const typeIcon = getSummaryTypeIcon(structuredSummary.type);

  return (
    <div className="space-y-4">
      {/* Summary Type Badge */}
      <div className={cn(
        'inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium',
        typeStyles.bgColor,
        typeStyles.color
      )}>
        {typeIcon}
        {typeStyles.label}
      </div>

      {/* Response (Agent's Answer) - Rendered as Markdown */}
      <div className={cn(
        'p-3 rounded-lg border',
        typeStyles.bgColor,
        typeStyles.borderColor
      )}>
        <div className="flex items-center gap-2 mb-2">
          <SparklesIcon className={cn('w-4 h-4', typeStyles.color)} />
          <h4 className={cn('text-xs font-medium', typeStyles.color)}>Response</h4>
        </div>
        <div className="prose prose-sm prose-invert max-w-none text-gray-300 prose-headings:text-gray-200 prose-p:text-gray-300 prose-strong:text-gray-200 prose-code:text-blue-300 prose-code:bg-gray-800 prose-code:px-1 prose-code:rounded prose-pre:bg-gray-800 prose-ul:text-gray-300 prose-ol:text-gray-300 prose-li:text-gray-300">
          <Markdown>{structuredSummary.response}</Markdown>
        </div>
      </div>

      {/* Key Points (if available) */}
      {structuredSummary.key_points.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <LightBulbIcon className="w-4 h-4 text-yellow-400" />
            <h4 className="text-xs font-medium text-gray-300">Key Points</h4>
          </div>
          <ul className="space-y-1.5">
            {structuredSummary.key_points.map((point, i) => (
              <li
                key={i}
                className="flex items-start gap-2 p-2 bg-gray-800/30 rounded text-xs text-gray-400"
              >
                <span className="text-gray-600 mt-0.5">•</span>
                <span>{point}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Analyzed Files (for Q&A/Analysis types) */}
      {structuredSummary.analyzed_files.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <DocumentMagnifyingGlassIcon className="w-4 h-4 text-gray-400" />
            <h4 className="text-xs font-medium text-gray-300">
              Files Analyzed ({structuredSummary.analyzed_files.length})
            </h4>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {structuredSummary.analyzed_files.map((file, i) => (
              <span
                key={i}
                className="px-2 py-1 bg-gray-800/50 rounded text-xs font-mono text-gray-400"
              >
                {file}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Warnings */}
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

      {/* Files Changed (for code changes) */}
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
