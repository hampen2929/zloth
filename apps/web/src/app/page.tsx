'use client';

import { useState, useCallback, useRef, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import useSWR from 'swr';
import { reposApi, tasksApi, modelsApi, githubApi, preferencesApi, runsApi } from '@/lib/api';
import type { GitHubRepository, ExecutorType, CodingMode } from '@/types';
import { useToast } from '@/components/ui/Toast';
import { cn } from '@/lib/utils';
import { useShortcutText, isModifierPressed } from '@/lib/platform';
import { useClickOutside } from '@/hooks';
import { ExecutorSelector } from '@/components/ExecutorSelector';
import { BranchSelector } from '@/components/BranchSelector';
import {
  FolderIcon,
  ChevronDownIcon,
  PhotoIcon,
  ArrowUpIcon,
  LockClosedIcon,
  ExclamationTriangleIcon,
  Cog6ToothIcon,
  BoltIcon,
} from '@heroicons/react/24/outline';

export default function HomePage() {
  return (
    <Suspense fallback={<HomePageSkeleton />}>
      <HomePageContent />
    </Suspense>
  );
}

function HomePageSkeleton() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-100px)]">
      <div className="w-full max-w-3xl px-4">
        <div className="bg-gray-900 border border-gray-700 rounded-xl shadow-lg p-4 animate-pulse">
          <div className="h-20 bg-gray-800 rounded mb-4" />
          <div className="h-8 bg-gray-800 rounded w-1/3" />
        </div>
      </div>
    </div>
  );
}

function HomePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { error: toastError } = useToast();
  const submitShortcut = useShortcutText('Enter');

  // Get initial instruction from query params (from backlog Start Work)
  const initialInstruction = searchParams.get('instruction') || '';

  const [instruction, setInstruction] = useState(initialInstruction);
  const [selectedRepo, setSelectedRepo] = useState<GitHubRepository | null>(null);
  const [selectedBranch, setSelectedBranch] = useState<string>('');
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [selectedCLIs, setSelectedCLIs] = useState<ExecutorType[]>(['claude_code']);
  const [selectedMode, setSelectedMode] = useState<CodingMode>('interactive');
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
  const { data: repos, isLoading: reposLoading } = useSWR('github-repos', githubApi.listRepos);
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

  // Auto-resize textarea when instruction is pre-filled from backlog
  useEffect(() => {
    if (initialInstruction && textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 300)}px`;
    }
  }, [initialInstruction]);

  // Apply default coding mode from preferences
  useEffect(() => {
    if (preferences?.default_coding_mode) {
      setSelectedMode(preferences.default_coding_mode);
    }
  }, [preferences]);

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

  // Toggle CLI selection
  const toggleCLI = (cli: ExecutorType) => {
    setSelectedCLIs((prev) =>
      prev.includes(cli) ? prev.filter((c) => c !== cli) : [...prev, cli]
    );
  };

  const handleSubmit = async () => {
    // Validate: need instruction, repo, branch, and at least one CLI
    if (!instruction.trim() || !selectedRepo || !selectedBranch) {
      return;
    }
    if (selectedCLIs.length === 0) {
      return;
    }

    setLoading(true);
    setError(null);

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
        coding_mode: selectedMode,
      });

      // Add the instruction as the first message and get its ID
      const message = await tasksApi.addMessage(task.id, {
        role: 'user',
        content: instruction,
      });

      // Build executor_types array for the API (CLI only)
      const executorTypesToRun: ExecutorType[] = [...selectedCLIs];

      // Create runs with executor_types for parallel execution, linked to the message
      await runsApi.create(task.id, {
        instruction: instruction,
        executor_types: executorTypesToRun,
        message_id: message.id,
      });

      // Navigate to the task page with executor info
      const params = new URLSearchParams();
      if (selectedCLIs.length > 0) {
        params.set('executors', selectedCLIs.join(','));
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

  const hasExecutor = selectedCLIs.length > 0;
  const canSubmit =
    instruction.trim() &&
    selectedRepo &&
    selectedBranch &&
    !loading &&
    hasExecutor;

  // Compute validation errors for display
  // Don't show errors while data is still loading
  const getValidationErrors = () => {
    const errors: { message: string; action?: { label: string; href: string } }[] = [];

    // Only show GitHub App error after loading completes
    if (!reposLoading && !repos) {
      errors.push({
        message: 'GitHub Appが未設定です',
        action: { label: '設定する', href: '#settings-github' },
      });
    } else if (!reposLoading && repos && !selectedRepo) {
      errors.push({ message: 'リポジトリを選択してください' });
    }
    if (selectedRepo && !selectedBranch) {
      errors.push({ message: 'ブランチを選択してください' });
    }
    // Show executor selection error if no CLI is selected
    if (selectedCLIs.length === 0) {
      errors.push({ message: 'CLIを選択してください' });
    }
    return errors;
  };

  const validationErrors = getValidationErrors();

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-100px)]">
      <div className="w-full max-w-3xl px-4">
        {/* Main Input Area */}
        <div className="bg-gray-900 border border-gray-700 rounded-xl shadow-lg">
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
                selectedCLIs={selectedCLIs}
                selectedModels={selectedModels}
                models={models || []}
                onCLIToggle={toggleCLI}
                onCLIsChange={setSelectedCLIs}
                onModelToggle={toggleModel}
                onModelsChange={setSelectedModels}
                hideModels={true}
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

          {/* Mode Selector */}
          <ModeSelector
            selectedMode={selectedMode}
            onModeChange={setSelectedMode}
          />
        </div>

        {/* Keyboard hint */}
        <div className="mt-3 text-xs text-gray-600 text-center">{submitShortcut} to submit</div>

        {/* Validation hints - show when there are issues preventing submission */}
        {!canSubmit && !loading && validationErrors.length > 0 && (
          <div className="mt-4 space-y-2">
            {validationErrors.map((err, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between gap-2 p-2 bg-amber-900/20 border border-amber-800/50 rounded-lg text-sm"
              >
                <div className="flex items-center gap-2 text-amber-400">
                  <ExclamationTriangleIcon className="w-4 h-4 flex-shrink-0" />
                  <span>{err.message}</span>
                </div>
                {err.action && (
                  <button
                    onClick={() => {
                      // Trigger settings open via hash - will be handled by ClientLayout
                      window.location.hash = err.action!.href.replace('#', '');
                    }}
                    className="flex items-center gap-1 text-blue-400 hover:text-blue-300 transition-colors text-sm whitespace-nowrap"
                  >
                    <Cog6ToothIcon className="w-4 h-4" />
                    {err.action.label}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

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

// Mode labels for display
const MODE_CONFIG: { value: CodingMode; label: string; description: string }[] = [
  { value: 'interactive', label: 'Interactive', description: 'Manual control' },
  { value: 'semi_auto', label: 'Semi Auto', description: 'Auto with approval' },
  { value: 'full_auto', label: 'Full Auto', description: 'Fully autonomous' },
];

interface ModeSelectorProps {
  selectedMode: CodingMode;
  onModeChange: (mode: CodingMode) => void;
}

function ModeSelector({ selectedMode, onModeChange }: ModeSelectorProps) {
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useClickOutside(dropdownRef, () => setShowDropdown(false), showDropdown);

  const currentConfig = MODE_CONFIG.find((m) => m.value === selectedMode) || MODE_CONFIG[0];

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setShowDropdown(!showDropdown)}
        className={cn(
          'flex items-center gap-2 transition-colors',
          'text-gray-400 hover:text-white',
          'focus:outline-none focus:ring-2 focus:ring-blue-500 rounded px-2 py-1'
        )}
      >
        <BoltIcon className="w-4 h-4" />
        <span>{currentConfig.label}</span>
        <ChevronDownIcon
          className={cn('w-4 h-4 transition-transform', showDropdown && 'rotate-180')}
        />
      </button>

      {showDropdown && (
        <div className="absolute top-full left-0 mt-2 w-56 bg-gray-800 border border-gray-700 rounded-lg shadow-xl overflow-hidden z-10 animate-in fade-in slide-in-from-bottom-2 duration-200">
          {MODE_CONFIG.map((mode) => (
            <button
              key={mode.value}
              onClick={() => {
                onModeChange(mode.value);
                setShowDropdown(false);
              }}
              className={cn(
                'w-full px-3 py-2.5 text-left flex items-center justify-between',
                'hover:bg-gray-700 transition-colors',
                'focus:outline-none focus:bg-gray-700',
                selectedMode === mode.value && 'bg-gray-700/50'
              )}
            >
              <div>
                <div className="text-gray-100">{mode.label}</div>
                <div className="text-xs text-gray-500">{mode.description}</div>
              </div>
              {selectedMode === mode.value && (
                <span className="text-blue-400 text-sm">&#10003;</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
