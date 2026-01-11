'use client';

import { useEffect, useMemo, useState } from 'react';
import useSWR from 'swr';
import { Modal, ModalBody, ModalFooter } from './ui/Modal';
import { Button } from './ui/Button';
import { Input, Textarea, Select } from './ui/Input';
import { useToast } from './ui/Toast';
import { cn } from '@/lib/utils';
import { backlogApi, githubApi, reposApi } from '@/lib/api';
import type { BacklogItem, BrokenDownTaskType, EstimatedSize } from '@/types';
import { ExclamationTriangleIcon, PlusIcon } from '@heroicons/react/24/outline';

interface NewBacklogModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated?: (item: BacklogItem) => void;
}

const TYPE_OPTIONS: { value: BrokenDownTaskType; label: string }[] = [
  { value: 'feature', label: 'Feature' },
  { value: 'bug_fix', label: 'Bug Fix' },
  { value: 'refactoring', label: 'Refactoring' },
  { value: 'docs', label: 'Docs' },
  { value: 'test', label: 'Test' },
];

const SIZE_OPTIONS: { value: EstimatedSize; label: string }[] = [
  { value: 'small', label: 'Small' },
  { value: 'medium', label: 'Medium' },
  { value: 'large', label: 'Large' },
];

export default function NewBacklogModal({ isOpen, onClose, onCreated }: NewBacklogModalProps) {
  const { data: githubConfig } = useSWR('github-config', githubApi.getConfig);
  const { data: repos, isLoading: reposLoading } = useSWR(
    githubConfig?.is_configured ? 'github-repos' : null,
    githubApi.listRepos
  );

  const [selectedRepo, setSelectedRepo] = useState<string>('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [type, setType] = useState<BrokenDownTaskType>('feature');
  const [size, setSize] = useState<EstimatedSize>('medium');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { success, error: toastError } = useToast();

  // Reset on close
  useEffect(() => {
    if (!isOpen) {
      setSelectedRepo('');
      setTitle('');
      setDescription('');
      setType('feature');
      setSize('medium');
      setSubmitting(false);
      setError(null);
    }
  }, [isOpen]);

  const repoOptions = useMemo(() => {
    const opts = [{ value: '', label: 'Select a repository' }];
    if (!repos) return opts;
    return opts.concat(repos.map((r) => ({ value: r.full_name, label: r.full_name })));
  }, [repos]);

  const isGitHubConfigured = githubConfig?.is_configured;
  const canSubmit = Boolean(title.trim() && selectedRepo && isGitHubConfigured && !submitting);

  const handleCreate = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      // Ensure the repo exists in backend and get repo_id
      const [owner, repo] = selectedRepo.split('/');
      const repoResult = await reposApi.select({ owner, repo });

      const created = await backlogApi.create({
        repo_id: repoResult.id,
        title: title.trim(),
        description: description.trim() || undefined,
        type,
        estimated_size: size,
      });

      success('Backlog item created');
      if (onCreated) onCreated(created);
      onClose();
    } catch (e: any) {
      const message = e?.message || 'Failed to create backlog item';
      setError(message);
      toastError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="New Backlog Item" size="lg">
      <ModalBody className="space-y-4">
        {!isGitHubConfigured && (
          <div className="flex items-center gap-2 p-3 bg-yellow-900/20 border border-yellow-800/50 rounded-lg text-yellow-400 text-sm">
            <ExclamationTriangleIcon className="w-5 h-5 flex-shrink-0" />
            <span>
              Configure GitHub App first to create backlog items.{' '}
              <a href="#settings-github" className="underline hover:text-yellow-300">Go to Settings</a>
            </span>
          </div>
        )}

        <Select
          label="Repository"
          value={selectedRepo}
          onChange={(e) => setSelectedRepo(e.target.value)}
          options={repoOptions}
          disabled={reposLoading || !isGitHubConfigured}
        />

        <Input
          label="Title"
          placeholder="Short summary of the work"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />

        <Textarea
          label="Description (optional)"
          placeholder="Details, acceptance criteria, references, etc."
          rows={5}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Select
            label="Type"
            value={type}
            onChange={(e) => setType(e.target.value as BrokenDownTaskType)}
            options={TYPE_OPTIONS}
          />
          <Select
            label="Estimated Size"
            value={size}
            onChange={(e) => setSize(e.target.value as EstimatedSize)}
            options={SIZE_OPTIONS}
          />
        </div>

        {error && (
          <div className="text-sm text-red-400">{error}</div>
        )}
      </ModalBody>
      <ModalFooter>
        <Button variant="secondary" onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button
          onClick={handleCreate}
          disabled={!canSubmit}
          isLoading={submitting}
          leftIcon={<PlusIcon className="w-4 h-4" />}
          className={cn('bg-blue-600 hover:bg-blue-700')}
        >
          Create
        </Button>
      </ModalFooter>
    </Modal>
  );
}

