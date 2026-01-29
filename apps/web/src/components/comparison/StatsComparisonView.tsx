'use client';

import { useMemo } from 'react';
import type { Run } from '@/types';
import { cn } from '@/lib/utils';
import { getExecutorDisplayName } from '@/hooks';
import { getRunStats, analyzeFileOverlap } from '@/lib/comparison-utils';
import {
  DocumentIcon,
  PlusIcon,
  MinusIcon,
  FolderIcon,
} from '@heroicons/react/24/outline';

export interface StatsComparisonViewProps {
  runs: Run[];
}

export function StatsComparisonView({ runs }: StatsComparisonViewProps) {
  // Compute stats for each run
  const statsMap = useMemo(() => {
    const map = new Map<string, ReturnType<typeof getRunStats>>();
    for (const run of runs) {
      map.set(run.id, getRunStats(run));
    }
    return map;
  }, [runs]);

  // Analyze file overlap
  const fileAnalysis = useMemo(() => analyzeFileOverlap(runs), [runs]);

  // Find max values for bar chart scaling
  const maxFiles = Math.max(...runs.map((r) => statsMap.get(r.id)?.filesChanged || 0), 1);
  const maxAdded = Math.max(...runs.map((r) => statsMap.get(r.id)?.linesAdded || 0), 1);
  const maxRemoved = Math.max(...runs.map((r) => statsMap.get(r.id)?.linesRemoved || 0), 1);

  return (
    <div className="h-full overflow-auto p-6">
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Stats Comparison Table */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Metric
                </th>
                {runs.map((run) => (
                  <th
                    key={run.id}
                    className="px-4 py-3 text-center text-xs font-medium text-gray-400 uppercase tracking-wider"
                  >
                    {getExecutorDisplayName(run.executor_type) || run.executor_type}
                    {run.model_name && (
                      <span className="block text-gray-600 font-normal normal-case">
                        {run.model_name}
                      </span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {/* Files Changed */}
              <tr>
                <td className="px-4 py-3 text-sm text-gray-300 flex items-center gap-2">
                  <DocumentIcon className="w-4 h-4 text-gray-500" />
                  Files Changed
                </td>
                {runs.map((run) => {
                  const stats = statsMap.get(run.id);
                  const value = stats?.filesChanged || 0;
                  const percentage = (value / maxFiles) * 100;
                  return (
                    <td key={run.id} className="px-4 py-3">
                      <div className="flex items-center justify-center gap-2">
                        <span className="text-sm font-medium text-gray-200 w-8 text-right">
                          {value}
                        </span>
                        <div className="flex-1 max-w-24 h-2 bg-gray-800 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-blue-500 rounded-full"
                            style={{ width: `${percentage}%` }}
                          />
                        </div>
                      </div>
                    </td>
                  );
                })}
              </tr>

              {/* Lines Added */}
              <tr>
                <td className="px-4 py-3 text-sm text-gray-300 flex items-center gap-2">
                  <PlusIcon className="w-4 h-4 text-green-500" />
                  Lines Added
                </td>
                {runs.map((run) => {
                  const stats = statsMap.get(run.id);
                  const value = stats?.linesAdded || 0;
                  const percentage = (value / maxAdded) * 100;
                  return (
                    <td key={run.id} className="px-4 py-3">
                      <div className="flex items-center justify-center gap-2">
                        <span className="text-sm font-medium text-green-400 w-8 text-right">
                          +{value}
                        </span>
                        <div className="flex-1 max-w-24 h-2 bg-gray-800 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-green-500 rounded-full"
                            style={{ width: `${percentage}%` }}
                          />
                        </div>
                      </div>
                    </td>
                  );
                })}
              </tr>

              {/* Lines Removed */}
              <tr>
                <td className="px-4 py-3 text-sm text-gray-300 flex items-center gap-2">
                  <MinusIcon className="w-4 h-4 text-red-500" />
                  Lines Removed
                </td>
                {runs.map((run) => {
                  const stats = statsMap.get(run.id);
                  const value = stats?.linesRemoved || 0;
                  const percentage = (value / maxRemoved) * 100;
                  return (
                    <td key={run.id} className="px-4 py-3">
                      <div className="flex items-center justify-center gap-2">
                        <span className="text-sm font-medium text-red-400 w-8 text-right">
                          -{value}
                        </span>
                        <div className="flex-1 max-w-24 h-2 bg-gray-800 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-red-500 rounded-full"
                            style={{ width: `${percentage}%` }}
                          />
                        </div>
                      </div>
                    </td>
                  );
                })}
              </tr>

              {/* Net Change */}
              <tr className="bg-gray-800/30">
                <td className="px-4 py-3 text-sm text-gray-300 font-medium">
                  Net Change
                </td>
                {runs.map((run) => {
                  const stats = statsMap.get(run.id);
                  const net = (stats?.linesAdded || 0) - (stats?.linesRemoved || 0);
                  return (
                    <td key={run.id} className="px-4 py-3 text-center">
                      <span
                        className={cn(
                          'text-sm font-medium',
                          net > 0 ? 'text-green-400' : net < 0 ? 'text-red-400' : 'text-gray-500'
                        )}
                      >
                        {net > 0 ? '+' : ''}{net}
                      </span>
                    </td>
                  );
                })}
              </tr>
            </tbody>
          </table>
        </div>

        {/* File Overlap Analysis */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-800 bg-gray-800/30">
            <div className="flex items-center gap-2">
              <FolderIcon className="w-4 h-4 text-gray-500" />
              <span className="text-sm font-medium text-gray-200">File Analysis</span>
            </div>
          </div>

          <div className="p-4 space-y-4">
            {/* Common Files */}
            {fileAnalysis.commonFiles.length > 0 && (
              <div>
                <div className="text-xs text-gray-500 mb-2">
                  Common Files ({fileAnalysis.commonFiles.length})
                </div>
                <div className="flex flex-wrap gap-2">
                  {fileAnalysis.commonFiles.map((file) => (
                    <span
                      key={file}
                      className="px-2 py-1 bg-purple-500/10 border border-purple-500/30 rounded text-xs font-mono text-purple-300"
                    >
                      {getFileName(file)}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Unique Files per Executor */}
            {[...fileAnalysis.uniqueFiles.entries()].map(([executor, files]) => {
              if (files.length === 0) return null;
              const displayName = getExecutorDisplayName(executor) || executor;
              return (
                <div key={executor}>
                  <div className="text-xs text-gray-500 mb-2">
                    Only in {displayName} ({files.length})
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {files.map((file) => (
                      <span
                        key={file}
                        className="px-2 py-1 bg-gray-800 border border-gray-700 rounded text-xs font-mono text-gray-400"
                      >
                        {getFileName(file)}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}

            {/* No changes case */}
            {fileAnalysis.allFiles.length === 0 && (
              <div className="text-sm text-gray-500 text-center py-4">
                No file changes to analyze
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function getFileName(path: string): string {
  const parts = path.split('/');
  return parts[parts.length - 1];
}
