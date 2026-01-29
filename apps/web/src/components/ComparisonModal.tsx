'use client';

import { useState, useMemo } from 'react';
import type { Run, ExecutorType } from '@/types';
import { Modal } from './ui/Modal';
import { cn } from '@/lib/utils';
import { getComparableRuns } from '@/lib/comparison-utils';
import { getExecutorDisplayName } from '@/hooks';
import { SummaryComparisonView } from './comparison/SummaryComparisonView';
import { StatsComparisonView } from './comparison/StatsComparisonView';
import { FileDiffComparisonView } from './comparison/FileDiffComparisonView';
import {
  DocumentTextIcon,
  ChartBarIcon,
  DocumentDuplicateIcon,
  CheckIcon,
} from '@heroicons/react/24/outline';

export interface ComparisonModalProps {
  isOpen: boolean;
  onClose: () => void;
  runs: Run[];
}

type ViewMode = 'summary' | 'stats' | 'diff';

const VIEW_MODES: { id: ViewMode; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: 'summary', label: 'Summary', icon: DocumentTextIcon },
  { id: 'stats', label: 'Stats', icon: ChartBarIcon },
  { id: 'diff', label: 'File Diff', icon: DocumentDuplicateIcon },
];

export function ComparisonModal({ isOpen, onClose, runs }: ComparisonModalProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('summary');

  // Get comparable runs (latest succeeded run per executor)
  const comparableRuns = useMemo(() => getComparableRuns(runs), [runs]);

  // Get list of executor types
  const executorTypes = useMemo(() => [...comparableRuns.keys()], [comparableRuns]);

  // Track which executors are deselected (start with all selected by default)
  const [deselectedExecutors, setDeselectedExecutors] = useState<Set<ExecutorType>>(new Set());

  // Derive selected executors: all executorTypes minus deselected ones
  const selectedExecutors = useMemo(() => {
    return new Set(executorTypes.filter((e) => !deselectedExecutors.has(e)));
  }, [executorTypes, deselectedExecutors]);

  // Get runs for selected executors
  const selectedRuns = useMemo(() => {
    const result: Run[] = [];
    for (const executor of selectedExecutors) {
      const run = comparableRuns.get(executor);
      if (run) {
        result.push(run);
      }
    }
    return result;
  }, [selectedExecutors, comparableRuns]);

  const toggleExecutor = (executor: ExecutorType) => {
    setDeselectedExecutors((prev) => {
      const next = new Set(prev);
      const isCurrentlySelected = !prev.has(executor);
      if (isCurrentlySelected) {
        // Don't allow deselecting if only 2 are selected
        if (selectedExecutors.size <= 2) return prev;
        next.add(executor);
      } else {
        next.delete(executor);
      }
      return next;
    });
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Compare Executor Outputs"
      size="full"
    >
      <div className="flex flex-col h-[80vh]">
        {/* Header with executor selection and view mode */}
        <div className="flex flex-wrap items-center justify-between gap-4 px-6 py-3 border-b border-gray-800 bg-gray-900/50">
          {/* Executor selection chips */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-gray-500 mr-2">Comparing:</span>
            {executorTypes.map((executor) => {
              const isSelected = selectedExecutors.has(executor);
              const displayName = getExecutorDisplayName(executor) || executor;
              return (
                <button
                  key={executor}
                  onClick={() => toggleExecutor(executor)}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all',
                    isSelected
                      ? 'bg-purple-600 text-white'
                      : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                  )}
                >
                  {isSelected && <CheckIcon className="w-3 h-3" />}
                  {displayName}
                </button>
              );
            })}
          </div>

          {/* View mode toggle */}
          <div className="flex bg-gray-800 rounded-lg p-1">
            {VIEW_MODES.map((mode) => {
              const Icon = mode.icon;
              return (
                <button
                  key={mode.id}
                  onClick={() => setViewMode(mode.id)}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                    viewMode === mode.id
                      ? 'bg-gray-700 text-white'
                      : 'text-gray-400 hover:text-white'
                  )}
                >
                  <Icon className="w-4 h-4" />
                  {mode.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* View content */}
        <div className="flex-1 overflow-hidden">
          {selectedRuns.length < 2 ? (
            <div className="flex items-center justify-center h-full text-gray-500">
              Select at least 2 executors to compare
            </div>
          ) : (
            <>
              {viewMode === 'summary' && <SummaryComparisonView runs={selectedRuns} />}
              {viewMode === 'stats' && <StatsComparisonView runs={selectedRuns} />}
              {viewMode === 'diff' && <FileDiffComparisonView runs={selectedRuns} />}
            </>
          )}
        </div>
      </div>
    </Modal>
  );
}
