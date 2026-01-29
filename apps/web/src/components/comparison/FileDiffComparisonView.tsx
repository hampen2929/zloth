'use client';

import { useState, useMemo } from 'react';
import type { Run } from '@/types';
import { cn } from '@/lib/utils';
import { getExecutorDisplayName } from '@/hooks';
import { analyzeFileOverlap, getFileDiff, parseDiff } from '@/lib/comparison-utils';
import {
  ChevronDownIcon,
  DocumentIcon,
} from '@heroicons/react/24/outline';

export interface FileDiffComparisonViewProps {
  runs: Run[];
}

export function FileDiffComparisonView({ runs }: FileDiffComparisonViewProps) {
  // Get all files across all runs
  const fileAnalysis = useMemo(() => analyzeFileOverlap(runs), [runs]);
  const allFiles = fileAnalysis.allFiles;

  // Selected file state
  const [selectedFile, setSelectedFile] = useState<string | null>(
    allFiles.length > 0 ? allFiles[0] : null
  );

  // Dropdown open state
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  if (allFiles.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500">
        <div className="text-center">
          <DocumentIcon className="w-12 h-12 mx-auto mb-3 text-gray-700" />
          <p>No file changes to compare</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* File Selector */}
      <div className="flex items-center gap-4 px-4 py-3 border-b border-gray-800 bg-gray-900/50">
        <span className="text-xs text-gray-500">File:</span>
        <div className="relative">
          <button
            onClick={() => setIsDropdownOpen(!isDropdownOpen)}
            className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-md text-sm font-mono text-gray-200 min-w-[200px] justify-between transition-colors"
          >
            <span className="truncate">{selectedFile || 'Select a file'}</span>
            <ChevronDownIcon
              className={cn(
                'w-4 h-4 text-gray-500 transition-transform',
                isDropdownOpen && 'rotate-180'
              )}
            />
          </button>

          {isDropdownOpen && (
            <div className="absolute top-full left-0 mt-1 w-80 max-h-64 overflow-auto bg-gray-800 border border-gray-700 rounded-md shadow-lg z-50">
              {allFiles.map((file) => {
                const isCommon = fileAnalysis.commonFiles.includes(file);
                return (
                  <button
                    key={file}
                    onClick={() => {
                      setSelectedFile(file);
                      setIsDropdownOpen(false);
                    }}
                    className={cn(
                      'w-full px-3 py-2 text-left text-sm hover:bg-gray-700 transition-colors flex items-center gap-2',
                      selectedFile === file && 'bg-gray-700'
                    )}
                  >
                    <DocumentIcon className="w-4 h-4 text-gray-500 flex-shrink-0" />
                    <span className="font-mono text-gray-200 truncate flex-1">
                      {file}
                    </span>
                    {isCommon && (
                      <span className="px-1.5 py-0.5 text-xs bg-purple-500/20 text-purple-400 rounded">
                        common
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Diff Columns */}
      <div className="flex-1 overflow-auto">
        {selectedFile && (
          <div
            className="grid h-full"
            style={{
              gridTemplateColumns: `repeat(${runs.length}, minmax(300px, 1fr))`,
            }}
          >
            {runs.map((run, index) => (
              <DiffColumn
                key={run.id}
                run={run}
                filePath={selectedFile}
                isLast={index === runs.length - 1}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface DiffColumnProps {
  run: Run;
  filePath: string;
  isLast: boolean;
}

function DiffColumn({ run, filePath, isLast }: DiffColumnProps) {
  const displayName = getExecutorDisplayName(run.executor_type) || run.executor_type;
  const fileDiff = getFileDiff(run, filePath);

  if (!fileDiff) {
    return (
      <div className={cn('flex flex-col h-full', !isLast && 'border-r border-gray-800')}>
        {/* Header */}
        <div className="px-3 py-2 bg-gray-800/50 border-b border-gray-800 flex-shrink-0">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-200">{displayName}</span>
          </div>
        </div>
        {/* No changes */}
        <div className="flex-1 flex items-center justify-center text-gray-600 text-sm">
          No changes to this file
        </div>
      </div>
    );
  }

  const hunks = parseDiff(fileDiff.patch);

  return (
    <div className={cn('flex flex-col h-full', !isLast && 'border-r border-gray-800')}>
      {/* Header */}
      <div className="px-3 py-2 bg-gray-800/50 border-b border-gray-800 flex-shrink-0">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-200">{displayName}</span>
          <span className="text-xs">
            <span className="text-green-400">+{fileDiff.added_lines}</span>
            <span className="text-gray-600 mx-1">/</span>
            <span className="text-red-400">-{fileDiff.removed_lines}</span>
          </span>
        </div>
      </div>

      {/* Diff content */}
      <div className="flex-1 overflow-auto">
        <pre className="text-xs m-0 bg-gray-950">
          {hunks.map((hunk, hunkIndex) => (
            <div key={hunkIndex}>
              {/* Hunk header */}
              <div className="px-3 py-1 bg-blue-900/30 text-blue-400 border-y border-gray-800 font-mono">
                {hunk.header}
              </div>

              {/* Lines */}
              <table className="w-full border-collapse">
                <tbody>
                  {hunk.lines.map((line, lineIndex) => (
                    <tr
                      key={lineIndex}
                      className={cn(
                        line.type === 'add' && 'bg-green-900/20',
                        line.type === 'remove' && 'bg-red-900/20'
                      )}
                    >
                      <td className="w-10 px-2 py-0.5 text-right text-gray-600 select-none border-r border-gray-800/50 font-mono">
                        {line.lineNumber || ''}
                      </td>
                      <td
                        className={cn(
                          'px-3 py-0.5 font-mono whitespace-pre',
                          line.type === 'add' && 'text-green-300',
                          line.type === 'remove' && 'text-red-300',
                          line.type === 'context' && 'text-gray-400'
                        )}
                      >
                        <span className="select-none mr-1">
                          {line.type === 'add' ? '+' : line.type === 'remove' ? '-' : ' '}
                        </span>
                        {line.content}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </pre>
      </div>
    </div>
  );
}
