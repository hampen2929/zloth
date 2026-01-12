'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import useSWR from 'swr';
import type { TaskWithKanbanStatus, ExecutorType, CodingMode } from '@/types';
import { cn } from '@/lib/utils';
import { useClickOutside, getExecutorDisplayName } from '@/hooks';
import { reposApi, tasksApi, runsApi, githubApi, preferencesApi } from '@/lib/api';
import { useToast } from '@/components/ui/Toast';
import {
  XMarkIcon,
  CommandLineIcon,
  CheckIcon,
  BoltIcon,
  ChevronDownIcon,
  PlayIcon,
} from '@heroicons/react/24/outline';

interface StartTaskModalProps {
  task: TaskWithKanbanStatus;
  onClose: () => void;
  onSuccess: () => void;
}

const CLI_OPTIONS: { type: ExecutorType; description: string }[] = [
  { type: 'claude_code', description: 'Claude Code CLI' },
  { type: 'codex_cli', description: 'OpenAI Codex CLI' },
  { type: 'gemini_cli', description: 'Google Gemini CLI' },
];

const MODE_CONFIG: { value: CodingMode; label: string; description: string }[] = [
  { value: 'interactive', label: 'Interactive', description: 'Manual control' },
  { value: 'semi_auto', label: 'Semi Auto', description: 'Auto with approval' },
  { value: 'full_auto', label: 'Full Auto', description: 'Fully autonomous' },
];

export function StartTaskModal({ task, onClose, onSuccess }: StartTaskModalProps) {
  const router = useRouter();
  const modalRef = useRef<HTMLDivElement>(null);
  const { success, error: toastError } = useToast();

  const [selectedCLIs, setSelectedCLIs] = useState<ExecutorType[]>(['claude_code']);
  const [selectedBranch, setSelectedBranch] = useState<string>('');
  const [selectedMode, setSelectedMode] = useState<CodingMode>(task.coding_mode);
  const [loading, setLoading] = useState(false);
  const [showBranchDropdown, setShowBranchDropdown] = useState(false);
  const [showModeDropdown, setShowModeDropdown] = useState(false);

  const branchDropdownRef = useRef<HTMLDivElement>(null);
  const modeDropdownRef = useRef<HTMLDivElement>(null);

  // Fetch repo info
  const { data: repo } = useSWR(task.repo_id ? `repo-${task.repo_id}` : null, () =>
    reposApi.get(task.repo_id)
  );

  // Fetch branches when we have repo info
  const repoUrl = repo?.repo_url;
  const repoOwner = repoUrl?.match(/github\.com\/([^/]+)/)?.[1];
  const repoName = repoUrl?.match(/github\.com\/[^/]+\/([^/.]+)/)?.[1];

  const { data: branches } = useSWR(
    repoOwner && repoName ? `branches-${repoOwner}-${repoName}` : null,
    () => (repoOwner && repoName ? githubApi.listBranches(repoOwner, repoName) : null)
  );

  // Fetch preferences for defaults
  const { data: preferences } = useSWR('preferences', preferencesApi.get);

  // Set default branch when repo is loaded
  useEffect(() => {
    if (repo && !selectedBranch) {
      setSelectedBranch(preferences?.default_branch || repo.default_branch);
    }
  }, [repo, preferences, selectedBranch]);

  useClickOutside(modalRef, onClose, true);
  useClickOutside(branchDropdownRef, () => setShowBranchDropdown(false), showBranchDropdown);
  useClickOutside(modeDropdownRef, () => setShowModeDropdown(false), showModeDropdown);

  const toggleCLI = (cli: ExecutorType) => {
    setSelectedCLIs((prev) =>
      prev.includes(cli) ? prev.filter((c) => c !== cli) : [...prev, cli]
    );
  };

  const handleStart = async () => {
    if (selectedCLIs.length === 0 || !selectedBranch || !repo) {
      return;
    }

    setLoading(true);

    try {
      // Ensure repo is cloned/selected with the chosen branch
      await reposApi.select({
        owner: repoOwner!,
        repo: repoName!,
        branch: selectedBranch,
      });

      // Get the first message content as the instruction
      const taskDetail = await tasksApi.get(task.id);
      const firstUserMessage = taskDetail.messages.find((m) => m.role === 'user');
      const instruction = firstUserMessage?.content || task.title || 'Start working on task';

      // Create runs with the selected executors
      await runsApi.create(task.id, {
        instruction: instruction,
        executor_types: selectedCLIs,
        message_id: firstUserMessage?.id,
      });

      success('Task started successfully');
      onSuccess();

      // Navigate to task page
      const params = new URLSearchParams();
      if (selectedCLIs.length > 0) {
        params.set('executors', selectedCLIs.join(','));
      }
      router.push(`/tasks/${task.id}?${params.toString()}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to start task';
      toastError(message);
    } finally {
      setLoading(false);
    }
  };

  const canStart = selectedCLIs.length > 0 && selectedBranch && !loading;
  const currentMode = MODE_CONFIG.find((m) => m.value === selectedMode) || MODE_CONFIG[0];

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div
        ref={modalRef}
        className="bg-gray-900 border border-gray-700 rounded-xl shadow-2xl w-full max-w-md animate-in fade-in zoom-in-95 duration-200"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold text-white">Start Task</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors p-1 rounded hover:bg-gray-800"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          {/* Task Title */}
          <div>
            <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1">
              Task
            </label>
            <p className="text-white font-medium truncate">{task.title || 'Untitled Task'}</p>
          </div>

          {/* Repository Info */}
          {repo && (
            <div>
              <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1">
                Repository
              </label>
              <p className="text-gray-300 text-sm">
                {repoOwner}/{repoName}
              </p>
            </div>
          )}

          {/* Branch Selector */}
          <div>
            <label className="block text-xs text-gray-500 uppercase tracking-wider mb-2">
              Branch
            </label>
            <div className="relative" ref={branchDropdownRef}>
              <button
                onClick={() => setShowBranchDropdown(!showBranchDropdown)}
                disabled={!branches}
                className={cn(
                  'w-full flex items-center justify-between px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg',
                  'text-left text-sm transition-colors',
                  !branches ? 'text-gray-600 cursor-not-allowed' : 'text-gray-100 hover:border-gray-600'
                )}
              >
                <span className="flex items-center gap-2">
                  <BoltIcon className="w-4 h-4 text-gray-400" />
                  {selectedBranch || 'Select branch'}
                </span>
                <ChevronDownIcon
                  className={cn('w-4 h-4 transition-transform text-gray-400', showBranchDropdown && 'rotate-180')}
                />
              </button>

              {showBranchDropdown && branches && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-xl overflow-hidden z-10 max-h-48 overflow-y-auto">
                  {branches.map((branch) => (
                    <button
                      key={branch}
                      onClick={() => {
                        setSelectedBranch(branch);
                        setShowBranchDropdown(false);
                      }}
                      className={cn(
                        'w-full px-3 py-2 text-left flex items-center justify-between',
                        'hover:bg-gray-700 transition-colors text-sm',
                        branch === selectedBranch ? 'text-blue-400' : 'text-gray-100'
                      )}
                    >
                      <span className="truncate">{branch}</span>
                      {repo && branch === repo.default_branch && (
                        <span className="text-xs text-gray-500 ml-2">(default)</span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Executor Selection */}
          <div>
            <label className="block text-xs text-gray-500 uppercase tracking-wider mb-2">
              Executor
            </label>
            <div className="space-y-2">
              {CLI_OPTIONS.map((option) => {
                const isSelected = selectedCLIs.includes(option.type);
                return (
                  <button
                    key={option.type}
                    onClick={() => toggleCLI(option.type)}
                    className={cn(
                      'w-full px-3 py-2.5 text-left flex items-center gap-3 rounded-lg border transition-colors',
                      isSelected
                        ? 'bg-blue-900/30 border-blue-700 text-blue-100'
                        : 'bg-gray-800 border-gray-700 text-gray-300 hover:border-gray-600'
                    )}
                  >
                    <div
                      className={cn(
                        'w-4 h-4 rounded border flex items-center justify-center flex-shrink-0',
                        isSelected ? 'bg-blue-600 border-blue-600' : 'border-gray-600'
                      )}
                    >
                      {isSelected && <CheckIcon className="w-3 h-3 text-white" />}
                    </div>
                    <CommandLineIcon className="w-4 h-4 text-gray-400" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium">
                        {getExecutorDisplayName(option.type)}
                      </div>
                      <div className="text-xs text-gray-500">{option.description}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Coding Mode Selector */}
          <div>
            <label className="block text-xs text-gray-500 uppercase tracking-wider mb-2">
              Coding Mode
            </label>
            <div className="relative" ref={modeDropdownRef}>
              <button
                onClick={() => setShowModeDropdown(!showModeDropdown)}
                className={cn(
                  'w-full flex items-center justify-between px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg',
                  'text-left text-sm text-gray-100 hover:border-gray-600 transition-colors'
                )}
              >
                <span className="flex items-center gap-2">
                  <BoltIcon className="w-4 h-4 text-gray-400" />
                  {currentMode.label}
                  <span className="text-xs text-gray-500">({currentMode.description})</span>
                </span>
                <ChevronDownIcon
                  className={cn('w-4 h-4 transition-transform text-gray-400', showModeDropdown && 'rotate-180')}
                />
              </button>

              {showModeDropdown && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-xl overflow-hidden z-10">
                  {MODE_CONFIG.map((mode) => (
                    <button
                      key={mode.value}
                      onClick={() => {
                        setSelectedMode(mode.value);
                        setShowModeDropdown(false);
                      }}
                      className={cn(
                        'w-full px-3 py-2.5 text-left',
                        'hover:bg-gray-700 transition-colors',
                        selectedMode === mode.value && 'bg-gray-700/50'
                      )}
                    >
                      <div className="text-sm text-gray-100">{mode.label}</div>
                      <div className="text-xs text-gray-500">{mode.description}</div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 p-4 border-t border-gray-700">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleStart}
            disabled={!canStart}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              canStart
                ? 'bg-green-600 text-white hover:bg-green-700'
                : 'bg-gray-700 text-gray-500 cursor-not-allowed'
            )}
          >
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Starting...
              </>
            ) : (
              <>
                <PlayIcon className="w-4 h-4" />
                Start Task
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
