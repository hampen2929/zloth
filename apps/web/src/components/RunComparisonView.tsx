'use client';

import React, { useState } from 'react';
import type { Run } from '@/types';
import { Button } from '@/components/ui/Button';
import {
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ArrowsRightLeftIcon,
  DocumentTextIcon,
  CodeBracketIcon,
} from '@heroicons/react/24/outline';

interface RunComparisonViewProps {
  runs: Run[];
  onSelect: (runId: string) => void;
  selectedRunId?: string;
}

interface MetricsSummary {
  linesAdded: number;
  linesRemoved: number;
  filesChanged: number;
}

function getMetrics(run: Run): MetricsSummary {
  let linesAdded = 0;
  let linesRemoved = 0;

  for (const file of run.files_changed) {
    linesAdded += file.added_lines;
    linesRemoved += file.removed_lines;
  }

  return {
    linesAdded,
    linesRemoved,
    filesChanged: run.files_changed.length,
  };
}

function getStatusIcon(status: Run['status']) {
  switch (status) {
    case 'succeeded':
      return <CheckCircleIcon className="h-5 w-5 text-green-400" />;
    case 'failed':
      return <XCircleIcon className="h-5 w-5 text-red-400" />;
    case 'running':
      return <ClockIcon className="h-5 w-5 text-blue-400 animate-spin" />;
    default:
      return <ClockIcon className="h-5 w-5 text-gray-400" />;
  }
}

function RunCard({
  run,
  isSelected,
  onSelect,
}: {
  run: Run;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const metrics = getMetrics(run);
  const modelLabel = run.model_name || run.executor_type || 'Unknown';

  return (
    <div
      className={`border rounded-lg p-4 transition-all cursor-pointer ${
        isSelected
          ? 'border-blue-500 bg-blue-900/20 ring-2 ring-blue-500/50'
          : 'border-gray-700 bg-gray-800/50 hover:border-gray-600'
      }`}
      onClick={onSelect}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {getStatusIcon(run.status)}
          <span className="font-medium text-gray-200">{modelLabel}</span>
        </div>
        {isSelected && (
          <span className="px-2 py-0.5 bg-blue-600 text-white text-xs rounded-full">
            Selected
          </span>
        )}
      </div>

      {/* Instruction Preview */}
      <p className="text-sm text-gray-400 line-clamp-2 mb-4">{run.instruction}</p>

      {/* Metrics */}
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="bg-gray-900/50 rounded p-2">
          <div className="text-lg font-semibold text-gray-200">
            {metrics.filesChanged}
          </div>
          <div className="text-xs text-gray-500">Files</div>
        </div>
        <div className="bg-gray-900/50 rounded p-2">
          <div className="text-lg font-semibold text-green-400">
            +{metrics.linesAdded}
          </div>
          <div className="text-xs text-gray-500">Added</div>
        </div>
        <div className="bg-gray-900/50 rounded p-2">
          <div className="text-lg font-semibold text-red-400">
            -{metrics.linesRemoved}
          </div>
          <div className="text-xs text-gray-500">Removed</div>
        </div>
      </div>

      {/* Summary Preview */}
      {run.summary && (
        <div className="mt-4 pt-4 border-t border-gray-700">
          <div className="flex items-center gap-1 text-xs text-gray-500 mb-1">
            <DocumentTextIcon className="h-3 w-3" />
            Summary
          </div>
          <p className="text-sm text-gray-400 line-clamp-3">{run.summary}</p>
        </div>
      )}

      {/* Files Changed Preview */}
      {run.files_changed.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-700">
          <div className="flex items-center gap-1 text-xs text-gray-500 mb-2">
            <CodeBracketIcon className="h-3 w-3" />
            Changed Files
          </div>
          <div className="space-y-1">
            {run.files_changed.slice(0, 3).map((file) => (
              <div
                key={file.path}
                className="flex items-center justify-between text-xs"
              >
                <span className="text-gray-400 font-mono truncate flex-1">
                  {file.path}
                </span>
                <span className="ml-2 text-gray-500">
                  <span className="text-green-400">+{file.added_lines}</span>
                  <span className="mx-1">/</span>
                  <span className="text-red-400">-{file.removed_lines}</span>
                </span>
              </div>
            ))}
            {run.files_changed.length > 3 && (
              <div className="text-xs text-gray-500">
                +{run.files_changed.length - 3} more files
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function RunComparisonView({
  runs,
  onSelect,
  selectedRunId,
}: RunComparisonViewProps) {
  const [showAll, setShowAll] = useState(false);

  const displayedRuns = showAll ? runs : runs.slice(0, 3);
  const hasMore = runs.length > 3;

  if (runs.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No runs available for comparison
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-gray-300">
          <ArrowsRightLeftIcon className="h-5 w-5" />
          <span className="font-medium">Compare Runs</span>
          <span className="text-gray-500">({runs.length} runs)</span>
        </div>
      </div>

      {/* Comparison Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {displayedRuns.map((run) => (
          <RunCard
            key={run.id}
            run={run}
            isSelected={run.id === selectedRunId}
            onSelect={() => onSelect(run.id)}
          />
        ))}
      </div>

      {/* Show More */}
      {hasMore && (
        <div className="text-center">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowAll(!showAll)}
          >
            {showAll ? 'Show Less' : `Show ${runs.length - 3} More Runs`}
          </Button>
        </div>
      )}

      {/* Comparison Summary */}
      {runs.length > 1 && (
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
          <h4 className="text-sm font-medium text-gray-300 mb-3">
            Comparison Summary
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-left">
                  <th className="pb-2">Run</th>
                  <th className="pb-2 text-center">Files</th>
                  <th className="pb-2 text-center">Lines Changed</th>
                  <th className="pb-2 text-center">Status</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => {
                  const metrics = getMetrics(run);
                  return (
                    <tr
                      key={run.id}
                      className={`border-t border-gray-700 ${
                        run.id === selectedRunId ? 'bg-blue-900/20' : ''
                      }`}
                    >
                      <td className="py-2 text-gray-300">
                        {run.model_name || run.executor_type}
                      </td>
                      <td className="py-2 text-center text-gray-400">
                        {metrics.filesChanged}
                      </td>
                      <td className="py-2 text-center">
                        <span className="text-green-400">+{metrics.linesAdded}</span>
                        <span className="text-gray-600 mx-1">/</span>
                        <span className="text-red-400">-{metrics.linesRemoved}</span>
                      </td>
                      <td className="py-2 text-center">
                        {getStatusIcon(run.status)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
