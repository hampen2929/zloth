'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { reposApi, tasksApi } from '@/lib/api';
import RepoSelector from '@/components/RepoSelector';

export default function HomePage() {
  const router = useRouter();
  const [selectedRepo, setSelectedRepo] = useState<{
    owner: string;
    repo: string;
    branch: string;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRepoSelect = useCallback((owner: string, repo: string, branch: string) => {
    setSelectedRepo({ owner, repo, branch });
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRepo) return;

    setLoading(true);
    setError(null);

    try {
      // Clone/select the repository
      const repo = await reposApi.select({
        owner: selectedRepo.owner,
        repo: selectedRepo.repo,
        branch: selectedRepo.branch,
      });

      // Create a new task
      const task = await tasksApi.create({
        repo_id: repo.id,
        title: `Task for ${selectedRepo.owner}/${selectedRepo.repo}`,
      });

      // Navigate to the task page
      router.push(`/tasks/${task.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to select repository');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto py-8">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold mb-4">dursor</h1>
        <p className="text-gray-400 text-lg">
          Multi-model parallel coding agent
        </p>
        <p className="text-gray-500 mt-2">
          Compare outputs from different models. Choose the best. Create PRs.
        </p>
      </div>

      {/* Repository Selection */}
      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <h2 className="text-lg font-medium text-white mb-4">Select Repository</h2>
          <RepoSelector onSelect={handleRepoSelect} disabled={loading} />
        </div>

        {error && (
          <div className="p-3 bg-red-900/30 border border-red-800 rounded-lg text-red-400 text-sm">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading || !selectedRepo}
          className="w-full py-3 px-4 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
        >
          {loading ? 'Setting up workspace...' : 'Start New Task'}
        </button>
      </form>
    </div>
  );
}
