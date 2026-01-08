'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import useSWR from 'swr';
import { reposApi, tasksApi, modelsApi, githubApi, preferencesApi, runsApi } from '@/lib/api';
import type { GitHubRepository, ExecutorType } from '@/types';
import { useToast } from '@/components/ui/Toast';
import { cn } from '@/lib/utils';
import { useShortcutText, isModifierPressed } from '@/lib/platform';
import { useClickOutside, isCLIExecutor } from '@/hooks';
import { ExecutorSelector } from '@/components/ExecutorSelector';
import { BranchSelector } from '@/components/BranchSelector';
import {
  FolderIcon,
  ChevronDownIcon,
  PhotoIcon,
  ArrowUpIcon,
  LockClosedIcon,
} from '@heroicons/react/24/outline';

export default function HomePage() {
  const router = useRouter();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { error: toastError } = useToast();
  const submitShortcut = useShortcutText('Enter');

  const [instruction, setInstruction] = useState('');
  const [selectedRepo, setSelectedRepo] = useState<GitHubRepository | null>(null);
  const [selectedBranch, setSelectedBranch] = useState<string>('');
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [executorType, setExecutorType] = useState<ExecutorType>('claude_code');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Dropdown states
  const [showRepoDropdown, setShowRepoDropdown] = useState(false);
  const [repoSearch, setRepoSearch] = useState('');

  // Refs for dropdown containers
  const repoDropdownRef = useRef<HTMLDivElement>(null);

  // Close repo dropdown when clicking outside
  useClickOutside(repoDropdownRef, () => setShowRepoDropdown(false), showRepoDropdown);

  // Data fetching
  const { data: models } = useSWR('models', modelsApi.list);
  const { data: repos } = useSWR('github-repos', githubApi.listRepos);
  const { data: preferences } = useSWR('preferences', preferencesApi.get);
  const { data: branches } = useSWR(
    selectedRepo ? `branches-${selectedRepo.owner}-${selectedRepo.name}` : null,
    () => (selectedRepo ? githubApi.listBranches(selectedRepo.owner, selectedRepo.name) : null)
  );

  // Apply default preferences when repos are loaded
  useEffect(() => {
    if (repos && preferences && !selectedRepo) {
      if (preferences.default_repo_owner && preferences.default_repo_name) {
        const defaultRepo = repos.find(
          (r) => r.owner === preferences.default_repo_owner && r.name === preferences.default_repo_name
        );
        if (defaultRepo) {
          setSelectedRepo(defaultRepo);
          setSelectedBranch(preferences.default_branch || defaultRepo.default_branch);
        }
      }
    }
  }, [repos, preferences, selectedRepo]);

  // Set default branch when repo changes
  const handleRepoSelect = useCallback((repo: GitHubRepository) => {
    setSelectedRepo(repo);
    setSelectedBranch(repo.default_branch);
    setShowRepoDropdown(false);
    setRepoSearch('');
  }, []);

  // Filter repos by search
  const filteredRepos = repos?.filter(
    (repo) => !repoSearch || repo.full_name.toLowerCase().includes(repoSearch.toLowerCase())
  );

  // Toggle model selection
  const toggleModel = (modelId: string) => {
    setSelectedModels((prev) =>
      prev.includes(modelId) ? prev.filter((id) => id !== modelId) : [...prev, modelId]
    );
  };

  const handleSubmit = async () => {
    // Validate based on executor type
    if (!instruction.trim() || !selectedRepo || !selectedBranch) {
      return;
    }
    if (executorType === 'patch_agent' && selectedModels.length === 0) {
      return;
    }

    setLoading(true);
    setError(null);

    const isCLI = isCLIExecutor(executorType);

    try {
      // Clone/select the repository
      const repo = await reposApi.select({
        owner: selectedRepo.owner,
        repo: selectedRepo.name,
        branch: selectedBranch,
      });

      // Create a new task
      const task = await tasksApi.create({
        repo_id: repo.id,
        title: instruction.slice(0, 50) + (instruction.length > 50 ? '...' : ''),
      });

      // Add the instruction as the first message
      await tasksApi.addMessage(task.id, {
        role: 'user',
        content: instruction,
      });

      // Create runs based on executor type
      if (isCLI) {
        await runsApi.create(task.id, {
          instruction: instruction,
          executor_type: executorType,
        });
      } else if (selectedModels.length > 0) {
        await runsApi.create(task.id, {
          instruction: instruction,
          model_ids: selectedModels,
          executor_type: 'patch_agent',
        });
      }

      // Navigate to the task page with executor type
      const params = new URLSearchParams();
      params.set('executor', executorType);
      if (executorType === 'patch_agent') {
        params.set('models', selectedModels.join(','));
      }
      router.push(`/tasks/${task.id}?${params.toString()}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to start task';
      setError(message);
      toastError(message);
    } finally {
      setLoading(false);
    }
  };

  // Handle keyboard shortcuts
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && isModifierPressed(e)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Auto-resize textarea
  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInstruction(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 300)}px`;
    }
  };

  const isCLI = isCLIExecutor(executorType);
  const canSubmit =
    instruction.trim() &&
    selectedRepo &&
    selectedBranch &&
    !loading &&
    (isCLI || selectedModels.length > 0);

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-100px)]">
      <div className="w-full max-w-3xl px-4">
        {/* Main Input Area */}
        <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden shadow-lg">
          {/* Textarea */}
          <div className="p-4">
            <textarea
              ref={textareaRef}
              value={instruction}
              onChange={handleTextareaChange}
              onKeyDown={handleKeyDown}
              placeholder="Ask dursor to build, fix bugs, explore..."
              className={cn(
                'w-full bg-transparent text-white placeholder-gray-500',
                'text-lg resize-none focus:outline-none min-h-[80px]',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
              rows={3}
              disabled={loading}
              aria-label="Task instruction"
            />
          </div>

          {/* Bottom Bar */}
          <div className="px-4 pb-4 flex items-center justify-between">
            <div className="flex items-center gap-4">
              {/* Executor Selector */}
              <ExecutorSelector
                executorType={executorType}
                selectedModels={selectedModels}
                models={models || []}
                onExecutorChange={setExecutorType}
                onModelToggle={toggleModel}
                onModelsChange={setSelectedModels}
              />
            </div>

            {/* Right side buttons */}
            <div className="flex items-center gap-2">
              {/* Image attach button (placeholder) */}
              <button
                className="p-2 text-gray-500 hover:text-gray-300 transition-colors rounded-lg hover:bg-gray-800"
                title="Attach image (coming soon)"
                disabled
              >
                <PhotoIcon className="w-5 h-5" />
              </button>

              {/* Submit button */}
              <button
                onClick={handleSubmit}
                disabled={!canSubmit}
                className={cn(
                  'p-2 rounded-lg transition-all',
                  'focus:outline-none focus:ring-2 focus:ring-blue-500',
                  canSubmit
                    ? 'bg-white text-gray-900 hover:bg-gray-100'
                    : 'bg-gray-700 text-gray-500 cursor-not-allowed'
                )}
                title={`Submit (${submitShortcut})`}
                aria-label="Submit task"
              >
                {loading ? (
                  <div className="w-5 h-5 border-2 border-gray-500 border-t-transparent rounded-full animate-spin" />
                ) : (
                  <ArrowUpIcon className="w-5 h-5" />
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Repository and Branch Selection */}
        <div className="mt-4 flex flex-wrap items-center gap-4 text-sm">
          {/* Repository Selector */}
          <RepoSelector
            selectedRepo={selectedRepo}
            repos={repos}
            filteredRepos={filteredRepos}
            showDropdown={showRepoDropdown}
            repoSearch={repoSearch}
            dropdownRef={repoDropdownRef}
            onToggleDropdown={() => setShowRepoDropdown(!showRepoDropdown)}
            onSearchChange={setRepoSearch}
            onSelect={handleRepoSelect}
          />

          {/* Branch Selector */}
          <BranchSelector
            selectedBranch={selectedBranch}
            branches={branches ?? undefined}
            selectedRepo={selectedRepo}
            onBranchSelect={setSelectedBranch}
          />
        </div>

        {/* Keyboard hint */}
        <div className="mt-3 text-xs text-gray-600 text-center">{submitShortcut} to submit</div>

        {/* Error message */}
        {error && (
          <div className="mt-4 p-3 bg-red-900/20 border border-red-800/50 rounded-lg text-red-400 text-sm flex items-center gap-2">
            <span>{error}</span>
          </div>
        )}

        {/* Loading indicator */}
        {loading && (
          <div className="mt-4 flex items-center justify-center gap-2 text-gray-400">
            <div className="w-4 h-4 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin" />
            <span>Setting up workspace...</span>
          </div>
        )}
      </div>
    </div>
  );
}

// --- Sub-components ---

interface RepoSelectorProps {
  selectedRepo: GitHubRepository | null;
  repos: GitHubRepository[] | undefined;
  filteredRepos: GitHubRepository[] | undefined;
  showDropdown: boolean;
  repoSearch: string;
  dropdownRef: React.RefObject<HTMLDivElement | null>;
  onToggleDropdown: () => void;
  onSearchChange: (value: string) => void;
  onSelect: (repo: GitHubRepository) => void;
}

function RepoSelector({
  selectedRepo,
  repos,
  filteredRepos,
  showDropdown,
  repoSearch,
  dropdownRef,
  onToggleDropdown,
  onSearchChange,
  onSelect,
}: RepoSelectorProps) {
  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={onToggleDropdown}
        className={cn(
          'flex items-center gap-2 transition-colors',
          'text-gray-400 hover:text-white',
          'focus:outline-none focus:ring-2 focus:ring-blue-500 rounded px-2 py-1'
        )}
      >
        <FolderIcon className="w-4 h-4" />
        <span>{selectedRepo ? selectedRepo.full_name : 'Select repository'}</span>
        <ChevronDownIcon
          className={cn('w-4 h-4 transition-transform', showDropdown && 'rotate-180')}
        />
      </button>

      {showDropdown && (
        <div className="absolute top-full left-0 mt-2 w-80 bg-gray-800 border border-gray-700 rounded-lg shadow-xl overflow-hidden z-10 animate-in fade-in slide-in-from-bottom-2 duration-200">
          <div className="p-2 border-b border-gray-700">
            <input
              type="text"
              value={repoSearch}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Search repositories..."
              className={cn(
                'w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded',
                'text-white text-sm placeholder:text-gray-500',
                'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
              )}
              autoFocus
            />
          </div>
          <div className="max-h-60 overflow-y-auto">
            {!repos ? (
              <div className="p-4 text-center">
                <div className="w-5 h-5 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin mx-auto" />
                <p className="text-gray-500 text-sm mt-2">Loading repositories...</p>
              </div>
            ) : filteredRepos && filteredRepos.length === 0 ? (
              <div className="p-4 text-center">
                <FolderIcon className="w-8 h-8 text-gray-600 mx-auto mb-2" />
                <p className="text-gray-500 text-sm">No repositories found</p>
              </div>
            ) : (
              filteredRepos?.slice(0, 20).map((repo) => (
                <button
                  key={repo.id}
                  onClick={() => onSelect(repo)}
                  className={cn(
                    'w-full px-3 py-2.5 text-left flex items-center justify-between',
                    'hover:bg-gray-700 transition-colors',
                    'focus:outline-none focus:bg-gray-700'
                  )}
                >
                  <span className="text-gray-100 truncate">{repo.full_name}</span>
                  {repo.private && (
                    <span className="flex items-center gap-1 text-xs bg-gray-700 px-2 py-0.5 rounded text-gray-400 ml-2 flex-shrink-0">
                      <LockClosedIcon className="w-3 h-3" />
                      Private
                    </span>
                  )}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
