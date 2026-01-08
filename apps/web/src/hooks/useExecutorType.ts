import { useMemo } from 'react';
import type { ExecutorType } from '@/types';

/**
 * Executor type utilities and display information
 */

export interface ExecutorTypeInfo {
  /** Whether this executor type is a CLI-based executor */
  isCLI: boolean;
  /** Human-readable display name for the executor */
  displayName: string;
  /** Whether this executor uses user-provided models */
  usesModels: boolean;
}

const CLI_EXECUTORS: ExecutorType[] = ['claude_code', 'codex_cli', 'gemini_cli'];

const EXECUTOR_DISPLAY_NAMES: Record<ExecutorType, string> = {
  patch_agent: 'Patch Agent',
  claude_code: 'Claude Code',
  codex_cli: 'Codex',
  gemini_cli: 'Gemini CLI',
};

/**
 * Check if an executor type is a CLI-based executor
 */
export function isCLIExecutor(executorType: ExecutorType): boolean {
  return CLI_EXECUTORS.includes(executorType);
}

/**
 * Get the display name for an executor type
 */
export function getExecutorDisplayName(executorType: ExecutorType): string {
  return EXECUTOR_DISPLAY_NAMES[executorType] ?? executorType;
}

/**
 * Get executor info for a given executor type
 */
export function getExecutorInfo(executorType: ExecutorType): ExecutorTypeInfo {
  const isCLI = isCLIExecutor(executorType);
  return {
    isCLI,
    displayName: getExecutorDisplayName(executorType),
    usesModels: !isCLI,
  };
}

/**
 * Hook to get executor type utilities
 * Provides memoized information about the current executor type
 */
export function useExecutorType(executorType: ExecutorType): ExecutorTypeInfo {
  return useMemo(() => getExecutorInfo(executorType), [executorType]);
}
