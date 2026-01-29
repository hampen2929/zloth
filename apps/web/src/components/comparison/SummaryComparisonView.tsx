'use client';

import type { Run } from '@/types';
import { cn } from '@/lib/utils';
import { getExecutorDisplayName } from '@/hooks';
import { deriveStructuredSummary, getSummaryTypeStyles } from '@/lib/summary-utils';
import {
  DocumentTextIcon,
  FolderIcon,
  LightBulbIcon,
} from '@heroicons/react/24/outline';

export interface SummaryComparisonViewProps {
  runs: Run[];
}

export function SummaryComparisonView({ runs }: SummaryComparisonViewProps) {
  return (
    <div className="h-full overflow-auto p-4">
      <div
        className="grid gap-4"
        style={{
          gridTemplateColumns: `repeat(${runs.length}, minmax(300px, 1fr))`,
        }}
      >
        {runs.map((run) => (
          <SummaryColumn key={run.id} run={run} />
        ))}
      </div>
    </div>
  );
}

interface SummaryColumnProps {
  run: Run;
}

function SummaryColumn({ run }: SummaryColumnProps) {
  const displayName = getExecutorDisplayName(run.executor_type) || run.executor_type;
  const summary = deriveStructuredSummary(run);
  const typeStyles = getSummaryTypeStyles(summary.type);

  return (
    <div className="flex flex-col h-full bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 bg-gray-800/50">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-white">{displayName}</span>
          {run.model_name && (
            <span className="text-xs text-gray-500">({run.model_name})</span>
          )}
        </div>
        <span
          className={cn(
            'px-2 py-0.5 rounded-full text-xs font-medium',
            typeStyles.bgColor,
            typeStyles.color
          )}
        >
          {typeStyles.label}
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {/* Title */}
        <div>
          <h3 className="text-base font-medium text-gray-100">{summary.title}</h3>
        </div>

        {/* Response */}
        {summary.response && summary.response !== 'No response available' && (
          <div>
            <div className="flex items-center gap-1.5 mb-2 text-xs text-gray-500">
              <DocumentTextIcon className="w-3.5 h-3.5" />
              <span>Response</span>
            </div>
            <div className="text-sm text-gray-300 whitespace-pre-wrap max-h-48 overflow-auto bg-gray-950/50 rounded p-3">
              {summary.response.length > 500
                ? summary.response.slice(0, 500) + '...'
                : summary.response}
            </div>
          </div>
        )}

        {/* Key Points */}
        {summary.key_points.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 mb-2 text-xs text-gray-500">
              <LightBulbIcon className="w-3.5 h-3.5" />
              <span>Key Points</span>
            </div>
            <ul className="space-y-1.5">
              {summary.key_points.map((point, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 text-sm text-gray-300"
                >
                  <span className="text-purple-400 mt-1">-</span>
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Files Changed */}
        {run.files_changed && run.files_changed.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 mb-2 text-xs text-gray-500">
              <FolderIcon className="w-3.5 h-3.5" />
              <span>Files Changed ({run.files_changed.length})</span>
            </div>
            <ul className="space-y-1">
              {run.files_changed.slice(0, 10).map((file) => (
                <li
                  key={file.path}
                  className="flex items-center justify-between text-xs"
                >
                  <span className="font-mono text-gray-400 truncate flex-1">
                    {file.path}
                  </span>
                  <span className="ml-2 flex-shrink-0">
                    <span className="text-green-400">+{file.added_lines}</span>
                    <span className="text-gray-600 mx-1">/</span>
                    <span className="text-red-400">-{file.removed_lines}</span>
                  </span>
                </li>
              ))}
              {run.files_changed.length > 10 && (
                <li className="text-xs text-gray-500 italic">
                  ...and {run.files_changed.length - 10} more files
                </li>
              )}
            </ul>
          </div>
        )}

        {/* Analyzed Files (for no-change runs) */}
        {(!run.files_changed || run.files_changed.length === 0) &&
          summary.analyzed_files.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 mb-2 text-xs text-gray-500">
                <FolderIcon className="w-3.5 h-3.5" />
                <span>Analyzed Files</span>
              </div>
              <ul className="space-y-1">
                {summary.analyzed_files.map((file, i) => (
                  <li key={i} className="text-xs font-mono text-gray-400">
                    {file}
                  </li>
                ))}
              </ul>
            </div>
          )}
      </div>
    </div>
  );
}
