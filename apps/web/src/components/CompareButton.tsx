'use client';

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import type { ExecutorType, ModelProfile, Run } from '@/types';
import { compareApi } from '@/lib/api';

interface CompareButtonProps {
  taskId: string;
  runs: Run[];
  models: ModelProfile[];
}

const EXECUTOR_NAMES: Record<ExecutorType, string> = {
  claude_code: 'Claude Code',
  codex_cli: 'Codex',
  gemini_cli: 'Gemini CLI',
  patch_agent: 'Patch Agent',
};

export function CompareButton({ taskId, runs, models }: CompareButtonProps) {
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Get succeeded runs
  const succeededRuns = useMemo(() => {
    return runs.filter((run) => run.status === 'succeeded');
  }, [runs]);

  // Can compare if we have at least 2 succeeded runs
  const canCompare = succeededRuns.length >= 2;

  // Get all run IDs for comparison
  const runIdsForComparison = useMemo(() => {
    return succeededRuns.map((run) => run.id);
  }, [succeededRuns]);

  // Available executors for analysis (CLI-based)
  const availableExecutors = useMemo(() => {
    const cliExecutors: ExecutorType[] = ['claude_code', 'codex_cli', 'gemini_cli'];
    return cliExecutors;
  }, []);

  const handleCompare = async (executorType?: ExecutorType, modelId?: string) => {
    if (!canCompare) return;

    setIsLoading(true);
    setError(null);

    try {
      const result = await compareApi.create(taskId, {
        run_ids: runIdsForComparison,
        executor_type: executorType,
        model_id: modelId,
      });

      // Navigate to comparison page
      router.push(`/tasks/${taskId}/compare/${result.comparison_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create comparison');
      setIsLoading(false);
    }
  };

  if (!canCompare) {
    return null;
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={isLoading}
        className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isLoading ? (
          <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24">
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
              fill="none"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        ) : (
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
            />
          </svg>
        )}
        <span>Compare</span>
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d={isOpen ? 'M5 15l7-7 7 7' : 'M19 9l-7 7-7-7'}
          />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-64 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-50">
          <div className="p-3 border-b border-gray-200 dark:border-gray-700">
            <p className="text-sm font-medium text-gray-900 dark:text-white">
              Compare with:
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              {succeededRuns.length} runs will be compared
            </p>
          </div>

          <div className="py-1">
            <p className="px-3 py-1 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              CLI Executors
            </p>
            {availableExecutors.map((executor) => (
              <button
                key={executor}
                onClick={() => {
                  setIsOpen(false);
                  handleCompare(executor);
                }}
                className="w-full text-left px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
              >
                {EXECUTOR_NAMES[executor]}
              </button>
            ))}

            {models.length > 0 && (
              <>
                <div className="border-t border-gray-200 dark:border-gray-700 my-1" />
                <p className="px-3 py-1 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  LLM Models
                </p>
                {models.map((model) => (
                  <button
                    key={model.id}
                    onClick={() => {
                      setIsOpen(false);
                      handleCompare(undefined, model.id);
                    }}
                    className="w-full text-left px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                  >
                    {model.display_name || model.model_name}
                    <span className="text-xs text-gray-400 ml-2">({model.provider})</span>
                  </button>
                ))}
              </>
            )}
          </div>

          {error && (
            <div className="p-3 border-t border-gray-200 dark:border-gray-700">
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            </div>
          )}
        </div>
      )}

      {/* Backdrop to close dropdown */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  );
}
