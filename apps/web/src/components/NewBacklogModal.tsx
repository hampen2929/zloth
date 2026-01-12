'use client';

import { useState, useEffect, useCallback } from 'react';
import useSWR from 'swr';
import { githubApi, reposApi, backlogApi, preferencesApi } from '@/lib/api';
import type {
  BrokenDownTaskType,
  EstimatedSize,
  BacklogItemCreate,
  SubTaskCreate,
} from '@/types';
import { Modal, ModalBody, ModalFooter } from './ui/Modal';
import { Button } from './ui/Button';
import { Input, Textarea } from './ui/Input';
import { useToast } from './ui/Toast';
import { cn } from '@/lib/utils';
import {
  PlusIcon,
  TrashIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';

const TASK_TYPES: { value: BrokenDownTaskType; label: string }[] = [
  { value: 'feature', label: 'Feature' },
  { value: 'bug_fix', label: 'Bug Fix' },
  { value: 'refactoring', label: 'Refactoring' },
  { value: 'docs', label: 'Documentation' },
  { value: 'test', label: 'Test' },
];

const SIZE_OPTIONS: { value: EstimatedSize; label: string }[] = [
  { value: 'small', label: 'Small' },
  { value: 'medium', label: 'Medium' },
  { value: 'large', label: 'Large' },
];

interface NewBacklogModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: () => void;
}

export default function NewBacklogModal({ isOpen, onClose, onCreated }: NewBacklogModalProps) {
  const { data: githubConfig } = useSWR('github-config', githubApi.getConfig);
  const { data: repos, isLoading: reposLoading } = useSWR(
    githubConfig?.is_configured ? 'github-repos' : null,
    githubApi.listRepos
  );
  const { data: preferences } = useSWR('preferences', preferencesApi.get);

  const [selectedRepo, setSelectedRepo] = useState<string>('');
  const [selectedBranch, setSelectedBranch] = useState<string>('');
  const [branches, setBranches] = useState<string[]>([]);
  const [branchesLoading, setBranchesLoading] = useState(false);

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [taskType, setTaskType] = useState<BrokenDownTaskType>('feature');
  const [estimatedSize, setEstimatedSize] = useState<EstimatedSize>('medium');
  const [targetFiles, setTargetFiles] = useState('');
  const [implementationHint, setImplementationHint] = useState('');
  const [tags, setTags] = useState('');
  const [subtasks, setSubtasks] = useState<SubTaskCreate[]>([]);
  const [newSubtask, setNewSubtask] = useState('');

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { success } = useToast();

  // Reset form when modal closes
  useEffect(() => {
    if (!isOpen) {
      setTitle('');
      setDescription('');
      setTaskType('feature');
      setEstimatedSize('medium');
      setTargetFiles('');
      setImplementationHint('');
      setTags('');
      setSubtasks([]);
      setNewSubtask('');
      setError(null);
    }
  }, [isOpen]);

  // Apply defaults from Settings → Defaults when modal opens and data is ready
  useEffect(() => {
    if (!isOpen) return;
    if (!repos || !preferences) return;
    if (selectedRepo) return; // don't override if user already interacted

    const owner = preferences.default_repo_owner;
    const name = preferences.default_repo_name;
    if (owner && name) {
      const fullName = `${owner}/${name}`;
      const repoInfo = repos.find((r) => r.full_name === fullName);
      if (repoInfo) {
        setSelectedRepo(fullName);
        const preferredBranch = preferences.default_branch || repoInfo.default_branch;
        // Load branches and select the preferred one if available
        loadBranches(owner, name, preferredBranch);
      }
    }
  }, [isOpen, repos, preferences, selectedRepo, loadBranches]);

  // Get default branch for selected repo
  const selectedRepoDefaultBranch = (() => {
    if (!repos || !selectedRepo) return null;
    return repos.find((r) => r.full_name === selectedRepo)?.default_branch ?? null;
  })();

  // Build branch options with default branch at top
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
      if (defaultBranch && branchList.includes(defaultBranch)) {
        setSelectedBranch(defaultBranch);
      } else if (branchList.length > 0) {
        const mainBranch =
          branchList.find((b) => b === 'main') ||
          branchList.find((b) => b === 'master') ||
          branchList[0];
        setSelectedBranch(mainBranch);
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
      const repoInfo = repos?.find((r) => r.full_name === fullName);
      await loadBranches(owner, repo, repoInfo?.default_branch);
    }
  };

  const handleAddSubtask = () => {
    if (!newSubtask.trim()) return;
    setSubtasks((prev) => [...prev, { title: newSubtask.trim() }]);
    setNewSubtask('');
  };

  const handleRemoveSubtask = (index: number) => {
    setSubtasks((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !selectedRepo || !selectedBranch) return;

    setIsSubmitting(true);
    setError(null);

    try {
      // First, select/clone the repository to get repo_id
      const [owner, repo] = selectedRepo.split('/');
      const repoResult = await reposApi.select({
        owner,
        repo,
        branch: selectedBranch,
      });

      // Prepare backlog item data
      const data: BacklogItemCreate = {
        repo_id: repoResult.id,
        title: title.trim(),
        description: description.trim() || undefined,
        type: taskType,
        estimated_size: estimatedSize,
        target_files: targetFiles.trim()
          ? targetFiles.split(',').map((f) => f.trim()).filter(Boolean)
          : undefined,
        implementation_hint: implementationHint.trim() || undefined,
        tags: tags.trim()
          ? tags.split(',').map((t) => t.trim()).filter(Boolean)
          : undefined,
        subtasks: subtasks.length > 0 ? subtasks : undefined,
      };

      await backlogApi.create(data);
      success('Backlog item created successfully');
      onCreated();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create backlog item');
    } finally {
      setIsSubmitting(false);
    }
  };

  const isGitHubConfigured = githubConfig?.is_configured;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="New Backlog Item"
      size="lg"
    >
      <form onSubmit={handleSubmit}>
        <ModalBody className="max-h-[calc(85vh-180px)] overflow-y-auto space-y-4">
          {!isGitHubConfigured && (
            <div className="flex items-center gap-2 p-3 bg-yellow-900/20 border border-yellow-800/50 rounded-lg text-yellow-400 text-sm">
              <ExclamationTriangleIcon className="w-5 h-5 flex-shrink-0" />
              <span>
                Configure GitHub App first to create backlog items.
              </span>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-900/20 border border-red-800/50 rounded-lg text-red-400 text-sm">
              <ExclamationTriangleIcon className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}

          {/* Repository and Branch Selection */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="block text-sm font-medium text-gray-300">
                Repository
              </label>
              <select
                value={selectedRepo}
                onChange={(e) => handleRepoChange(e.target.value)}
                disabled={!isGitHubConfigured || reposLoading}
                className={cn(
                  'w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md',
                  'focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent',
                  'text-gray-100 transition-colors disabled:opacity-50'
                )}
              >
                <option value="">
                  {reposLoading ? 'Loading...' : 'Select repository'}
                </option>
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
                  {branchesLoading ? 'Loading...' : 'Select branch'}
                </option>
                {branchOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Title */}
          <Input
            label="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Enter backlog item title"
            required
            disabled={!isGitHubConfigured}
          />

          {/* Description */}
          <Textarea
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe what needs to be done"
            rows={3}
            disabled={!isGitHubConfigured}
          />

          {/* Type and Size */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="block text-sm font-medium text-gray-300">
                Type
              </label>
              <select
                value={taskType}
                onChange={(e) => setTaskType(e.target.value as BrokenDownTaskType)}
                disabled={!isGitHubConfigured}
                className={cn(
                  'w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md',
                  'focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent',
                  'text-gray-100 transition-colors disabled:opacity-50'
                )}
              >
                {TASK_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <label className="block text-sm font-medium text-gray-300">
                Estimated Size
              </label>
              <select
                value={estimatedSize}
                onChange={(e) => setEstimatedSize(e.target.value as EstimatedSize)}
                disabled={!isGitHubConfigured}
                className={cn(
                  'w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md',
                  'focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent',
                  'text-gray-100 transition-colors disabled:opacity-50'
                )}
              >
                {SIZE_OPTIONS.map((size) => (
                  <option key={size.value} value={size.value}>
                    {size.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Target Files */}
          <Input
            label="Target Files"
            value={targetFiles}
            onChange={(e) => setTargetFiles(e.target.value)}
            placeholder="src/components/Button.tsx, src/utils/helpers.ts"
            hint="Comma-separated list of files to modify"
            disabled={!isGitHubConfigured}
          />

          {/* Implementation Hint */}
          <Textarea
            label="Implementation Hint"
            value={implementationHint}
            onChange={(e) => setImplementationHint(e.target.value)}
            placeholder="Any hints or notes for implementation"
            rows={2}
            disabled={!isGitHubConfigured}
          />

          {/* Tags */}
          <Input
            label="Tags"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="frontend, ui, urgent"
            hint="Comma-separated list of tags"
            disabled={!isGitHubConfigured}
          />

          {/* Subtasks */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-300">
              Subtasks
            </label>
            <div className="flex gap-2">
              <Input
                value={newSubtask}
                onChange={(e) => setNewSubtask(e.target.value)}
                placeholder="Add a subtask"
                disabled={!isGitHubConfigured}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAddSubtask();
                  }
                }}
              />
              <Button
                type="button"
                variant="secondary"
                onClick={handleAddSubtask}
                disabled={!newSubtask.trim() || !isGitHubConfigured}
              >
                <PlusIcon className="w-4 h-4" />
              </Button>
            </div>
            {subtasks.length > 0 && (
              <div className="space-y-1 mt-2">
                {subtasks.map((subtask, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between px-3 py-2 bg-gray-800 rounded-md"
                  >
                    <span className="text-sm text-gray-200">{subtask.title}</span>
                    <button
                      type="button"
                      onClick={() => handleRemoveSubtask(index)}
                      className="text-gray-500 hover:text-red-400 transition-colors"
                    >
                      <TrashIcon className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </ModalBody>

        <ModalFooter>
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={!title.trim() || !selectedRepo || !selectedBranch || isSubmitting || !isGitHubConfigured}
            isLoading={isSubmitting}
          >
            Create
          </Button>
        </ModalFooter>
      </form>
    </Modal>
  );
}
