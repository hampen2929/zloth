'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import useSWR, { mutate } from 'swr';
import { githubApi, breakdownApi, tasksApi, reposApi } from '@/lib/api';
import type {
  ExecutorType,
  TaskBreakdownResponse,
  OutputLine,
} from '@/types';
import { Modal, ModalBody, ModalFooter } from './ui/Modal';
import { Button } from './ui/Button';
import { Textarea } from './ui/Input';
import { useToast } from './ui/Toast';
import BreakdownTaskCard from './BreakdownTaskCard';
import { cn } from '@/lib/utils';
import {
  SparklesIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';

type BreakdownPhase = 'input' | 'analyzing' | 'result';

const CLI_EXECUTORS: { value: ExecutorType; label: string; description: string }[] = [
  {
    value: 'claude_code',
    label: 'Claude Code',
    description: 'Anthropic Claude CLI',
  },
  {
    value: 'codex_cli',
    label: 'Codex CLI',
    description: 'OpenAI Codex CLI',
  },
  {
    value: 'gemini_cli',
    label: 'Gemini CLI',
    description: 'Google Gemini CLI',
  },
];

interface BreakdownModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function BreakdownModal({ isOpen, onClose }: BreakdownModalProps) {
  const { data: githubConfig } = useSWR('github-config', githubApi.getConfig);
  const { data: repos, isLoading: reposLoading } = useSWR(
    githubConfig?.is_configured ? 'github-repos' : null,
    githubApi.listRepos
  );

  const [phase, setPhase] = useState<BreakdownPhase>('input');
  const [content, setContent] = useState('');
  const [selectedRepo, setSelectedRepo] = useState<string>('');
  const [selectedBranch, setSelectedBranch] = useState<string>('');
  const [branches, setBranches] = useState<string[]>([]);
  const [branchesLoading, setBranchesLoading] = useState(false);
  const [executorType, setExecutorType] = useState<ExecutorType>('claude_code');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [breakdownResult, setBreakdownResult] = useState<TaskBreakdownResponse | null>(null);
  const [selectedTasks, setSelectedTasks] = useState<Set<number>>(new Set());
  const [logs, setLogs] = useState<OutputLine[]>([]);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const cleanupRef = useRef<(() => void) | null>(null);
  const { success, error: toastError } = useToast();

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setPhase('input');
      setContent('');
      setBreakdownResult(null);
      setSelectedTasks(new Set());
      setLogs([]);
      setError(null);
      if (cleanupRef.current) {
        cleanupRef.current();
        cleanupRef.current = null;
      }
    }
  }, [isOpen]);

  // Auto-scroll logs
  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  // Get the default branch for the selected repository
  const selectedRepoDefaultBranch = (() => {
    if (!repos || !selectedRepo) return null;
    return repos.find((r) => r.full_name === selectedRepo)?.default_branch ?? null;
  })();

  // Build branch options with default branch on top
  const branchOptions: { value: string; label: string }[] = (() => {
    const list = branches || [];
    const seen = new Set<string>();
    const opts: { value: string; label: string }[] = [];

    if (selectedRepoDefaultBranch) {
      seen.add(selectedRepoDefaultBranch);
      opts.push({
        value: selectedRepoDefaultBranch,
        label: `Default (${selectedRepoDefaultBranch})`,
      });
    }

    for (const b of list) {
      if (seen.has(b)) continue;
      seen.add(b);
      opts.push({ value: b, label: b });
    }

    return opts;
  })();

  // Load branches when repo changes
  const loadBranches = useCallback(async (owner: string, repo: string, defaultBranch?: string | null) => {
    setBranchesLoading(true);
    try {
      const branchList = await githubApi.listBranches(owner, repo);
      setBranches(branchList);
      if (branchList.length > 0) {
        // Prefer the repository's default branch
        if (defaultBranch && branchList.includes(defaultBranch)) {
          setSelectedBranch(defaultBranch);
        } else {
          const mainBranch =
            branchList.find((b) => b === 'main') ||
            branchList.find((b) => b === 'master') ||
            branchList[0];
          setSelectedBranch(mainBranch);
        }
      }
    } catch (err) {
      console.error('Failed to load branches:', err);
      setBranches([]);
    } finally {
      setBranchesLoading(false);
    }
  }, []);

  const handleRepoChange = async (fullName: string) => {
    setSelectedRepo(fullName);
    setSelectedBranch('');
    setBranches([]);

    if (fullName) {
      const [owner, repo] = fullName.split('/');
      // Get the default branch for this repository
      const repoData = repos?.find((r) => r.full_name === fullName);
      await loadBranches(owner, repo, repoData?.default_branch);
    }
  };

  const handleAnalyze = async () => {
    if (!content.trim() || !selectedRepo || !selectedBranch) return;

    setIsAnalyzing(true);
    setPhase('analyzing');
    setError(null);
    setLogs([]);

    try {
      // First, select/clone the repository
      const [owner, repo] = selectedRepo.split('/');
      const repoResult = await reposApi.select({
        owner,
        repo,
        branch: selectedBranch,
      });

      // Start breakdown analysis (returns immediately with 'running' status)
      const initialResult = await breakdownApi.analyze({
        content: content.trim(),
        executor_type: executorType,
        repo_id: repoResult.id,
      });

      console.log('Breakdown started:', initialResult);

      // Start streaming logs
      cleanupRef.current = breakdownApi.streamLogs(initialResult.breakdown_id, {
        onLine: (line) => {
          setLogs((prev) => [...prev, line]);
        },
        onComplete: () => {
          // Logs completed - result should be ready
        },
        onError: (err) => {
          console.error('Log streaming error:', err);
        },
      });

      // Poll for the final result
      const pollInterval = 2000; // 2 seconds
      const maxAttempts = 180; // 6 minutes max
      let attempts = 0;
      let finalResult = initialResult;

      while (
        (finalResult.status === 'running' || finalResult.status === 'pending') &&
        attempts < maxAttempts
      ) {
        await new Promise((resolve) => setTimeout(resolve, pollInterval));
        attempts++;

        try {
          finalResult = await breakdownApi.getResult(initialResult.breakdown_id);
          console.log(`Poll attempt ${attempts}:`, finalResult.status);
        } catch (pollErr) {
          console.error('Poll error:', pollErr);
          // Continue polling on error
        }
      }

      setBreakdownResult(finalResult);

      if (finalResult.status === 'succeeded') {
        setPhase('result');
        // Select all tasks by default
        setSelectedTasks(new Set(finalResult.tasks.map((_, i) => i)));
      } else if (finalResult.status === 'failed') {
        setError(finalResult.error || 'Breakdown failed');
        setPhase('input');
      } else {
        // Timeout or unknown status
        setError('Breakdown timed out. Please try again.');
        setPhase('input');
      }
    } catch (err) {
      console.error('Breakdown error:', err);
      setError(err instanceof Error ? err.message : 'Failed to analyze');
      setPhase('input');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleToggleTask = (index: number) => {
    setSelectedTasks((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  const handleSelectAll = () => {
    if (!breakdownResult) return;
    if (selectedTasks.size === breakdownResult.tasks.length) {
      setSelectedTasks(new Set());
    } else {
      setSelectedTasks(new Set(breakdownResult.tasks.map((_, i) => i)));
    }
  };

  const handleCreateTasks = async () => {
    if (!breakdownResult || selectedTasks.size === 0) return;

    setIsCreating(true);
    try {
      // Get repo from the breakdown result context
      const [owner, repo] = selectedRepo.split('/');
      const repoResult = await reposApi.select({
        owner,
        repo,
        branch: selectedBranch,
      });

      // Get selected tasks
      const tasksToCreate = breakdownResult.tasks
        .filter((_, i) => selectedTasks.has(i))
        .map((task) => ({
          title: task.title,
          description: task.description,
        }));

      // Bulk create tasks
      const result = await tasksApi.bulkCreate({
        repo_id: repoResult.id,
        tasks: tasksToCreate.map((t) => ({ repo_id: repoResult.id, title: t.title })),
      });

      success(`Created ${result.count} task(s) successfully`);
      mutate('tasks');
      onClose();
    } catch (err) {
      console.error('Failed to create tasks:', err);
      toastError(err instanceof Error ? err.message : 'Failed to create tasks');
    } finally {
      setIsCreating(false);
    }
  };

  const handleBack = () => {
    setPhase('input');
    setBreakdownResult(null);
    setSelectedTasks(new Set());
    if (cleanupRef.current) {
      cleanupRef.current();
      cleanupRef.current = null;
    }
  };

  const isGitHubConfigured = githubConfig?.is_configured;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Task Breakdown"
      size="xl"
    >
      <ModalBody className="max-h-[calc(85vh-180px)] overflow-y-auto">
        {!isGitHubConfigured && (
          <div className="flex items-center gap-2 p-3 bg-yellow-900/20 border border-yellow-800/50 rounded-lg text-yellow-400 text-sm mb-4">
            <ExclamationTriangleIcon className="w-5 h-5 flex-shrink-0" />
            <span>
              Configure GitHub App first to use task breakdown.{' '}
              <a href="#settings-github" className="underline hover:text-yellow-300">
                Go to Settings
              </a>
            </span>
          </div>
        )}

        {/* Input Phase */}
        {phase === 'input' && (
          <div className="space-y-4">
            {/* Repository Selection */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="block text-sm font-medium text-gray-300">
                  Repository
                </label>
                <select
                  value={selectedRepo}
                  onChange={(e) => handleRepoChange(e.target.value)}
                  disabled={reposLoading || !isGitHubConfigured}
                  className={cn(
                    'w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md',
                    'focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent',
                    'text-gray-100 transition-colors disabled:opacity-50'
                  )}
                >
                  <option value="">Select a repository</option>
                  {repos?.map((repo) => (
                    <option key={repo.id} value={repo.full_name}>
                      {repo.full_name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1">
                <label className="block text-sm font-medium text-gray-300">
                  Branch
                </label>
                <select
                  value={selectedBranch}
                  onChange={(e) => setSelectedBranch(e.target.value)}
                  disabled={!selectedRepo || branchesLoading}
                  className={cn(
                    'w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md',
                    'focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent',
                    'text-gray-100 transition-colors disabled:opacity-50'
                  )}
                >
                  <option value="">
                    {branchesLoading ? 'Loading...' : 'Select a branch'}
                  </option>
                  {branchOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Content Input */}
            <Textarea
              label="Content"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder={`Enter the content to analyze...

Example:
- Login screen doesn't show error message when password is wrong
- Need search functionality on user list
- Create admin-only pages with access control`}
              rows={8}
              hint="Describe the requirements or issues you want to break down into tasks"
            />

            {/* Agent Selection */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-300">
                Agent Tool
              </label>
              <p className="text-xs text-gray-500 mb-2">
                Select the AI agent to analyze your codebase and create tasks
              </p>
              <div className="flex flex-wrap gap-2">
                {CLI_EXECUTORS.map((executor) => (
                  <label
                    key={executor.value}
                    className={cn(
                      'flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-colors',
                      executorType === executor.value
                        ? 'bg-purple-900/30 border-purple-700 text-purple-300'
                        : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:border-gray-600'
                    )}
                  >
                    <input
                      type="radio"
                      name="executor"
                      value={executor.value}
                      checked={executorType === executor.value}
                      onChange={() => setExecutorType(executor.value)}
                      className="sr-only"
                    />
                    <div
                      className={cn(
                        'w-3 h-3 rounded-full border-2',
                        executorType === executor.value
                          ? 'border-purple-500 bg-purple-500'
                          : 'border-gray-500'
                      )}
                    />
                    <span className="text-sm font-medium">{executor.label}</span>
                  </label>
                ))}
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 p-3 bg-red-900/20 border border-red-800/50 rounded-lg text-red-400 text-sm">
                <ExclamationTriangleIcon className="w-5 h-5 flex-shrink-0" />
                {error}
              </div>
            )}
          </div>
        )}

        {/* Analyzing Phase */}
        {phase === 'analyzing' && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-purple-400">
              <ArrowPathIcon className="w-5 h-5 animate-spin" />
              <span className="font-medium">Analyzing codebase...</span>
            </div>

            {/* Logs display */}
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 h-64 overflow-y-auto font-mono text-xs">
              {logs.length === 0 ? (
                <div className="text-gray-500">Waiting for output...</div>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className="text-gray-400">
                    <span className="text-gray-600 mr-2">{log.line_number + 1}</span>
                    {log.content}
                  </div>
                ))
              )}
              <div ref={logsEndRef} />
            </div>
          </div>
        )}

        {/* Result Phase */}
        {phase === 'result' && breakdownResult && (
          <div className="space-y-4">
            {/* Summary */}
            <div className="flex items-center gap-2 p-3 bg-green-900/20 border border-green-800/50 rounded-lg text-green-400">
              <CheckCircleIcon className="w-5 h-5 flex-shrink-0" />
              <span className="text-sm">
                {breakdownResult.summary || `Found ${breakdownResult.tasks.length} task(s)`}
              </span>
            </div>

            {/* Codebase Analysis */}
            {breakdownResult.codebase_analysis && (
              <div className="text-xs text-gray-500 flex flex-wrap gap-4">
                <span>
                  Files analyzed: {breakdownResult.codebase_analysis.files_analyzed}
                </span>
                {breakdownResult.codebase_analysis.tech_stack.length > 0 && (
                  <span>
                    Tech: {breakdownResult.codebase_analysis.tech_stack.join(', ')}
                  </span>
                )}
              </div>
            )}

            {/* Task Selection Header */}
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-gray-300">
                Breakdown Result ({breakdownResult.tasks.length} tasks)
              </h3>
              <button
                onClick={handleSelectAll}
                className="text-xs text-blue-400 hover:text-blue-300"
              >
                {selectedTasks.size === breakdownResult.tasks.length
                  ? 'Deselect All'
                  : 'Select All'}
              </button>
            </div>

            {/* Task List */}
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {breakdownResult.tasks.map((task, index) => (
                <BreakdownTaskCard
                  key={index}
                  task={task}
                  selected={selectedTasks.has(index)}
                  onToggle={() => handleToggleTask(index)}
                />
              ))}
            </div>
          </div>
        )}
      </ModalBody>

      <ModalFooter>
        {phase === 'input' && (
          <>
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button
              onClick={handleAnalyze}
              disabled={
                !content.trim() ||
                !selectedRepo ||
                !selectedBranch ||
                !isGitHubConfigured
              }
              isLoading={isAnalyzing}
              leftIcon={<SparklesIcon className="w-4 h-4" />}
              className="bg-purple-600 hover:bg-purple-700"
            >
              Analyze
            </Button>
          </>
        )}

        {phase === 'analyzing' && (
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
        )}

        {phase === 'result' && (
          <>
            <Button variant="secondary" onClick={handleBack}>
              Back
            </Button>
            <Button
              onClick={handleCreateTasks}
              disabled={selectedTasks.size === 0}
              isLoading={isCreating}
            >
              Create {selectedTasks.size} Task{selectedTasks.size !== 1 ? 's' : ''}
            </Button>
          </>
        )}
      </ModalFooter>
    </Modal>
  );
}
