'use client';

import { useState, useEffect, useMemo } from 'react';
import useSWR from 'swr';
import { githubApi } from '@/lib/api';
import type { GitHubRepository } from '@/types';

interface RepoSelectorProps {
  onSelect: (owner: string, repo: string, branch: string) => void;
  disabled?: boolean;
}

export default function RepoSelector({ onSelect, disabled }: RepoSelectorProps) {
  const { data: repos, error: reposError, isLoading: reposLoading } = useSWR(
    'github-repos',
    githubApi.listRepos
  );

  const [selectedRepo, setSelectedRepo] = useState<GitHubRepository | null>(null);
  const [selectedBranch, setSelectedBranch] = useState<string>('');
  const [repoSearch, setRepoSearch] = useState('');

  const { data: branches, isLoading: branchesLoading } = useSWR(
    selectedRepo ? `branches-${selectedRepo.owner}-${selectedRepo.name}` : null,
    () => selectedRepo ? githubApi.listBranches(selectedRepo.owner, selectedRepo.name) : null
  );

  // Filter repos based on search
  const filteredRepos = useMemo(() => {
    if (!repos) return [];
    if (!repoSearch.trim()) return repos;
    const search = repoSearch.toLowerCase();
    return repos.filter(
      (repo) =>
        repo.name.toLowerCase().includes(search) ||
        repo.full_name.toLowerCase().includes(search)
    );
  }, [repos, repoSearch]);

  // Compute the effective branch based on available branches
  // This is the actual branch that should be used for display and parent notification
  const effectiveBranch = useMemo(() => {
    if (!selectedRepo || !branches || branches.length === 0) {
      return selectedBranch;
    }
    // If user has manually selected a valid branch, use it
    if (selectedBranch && branches.includes(selectedBranch)) {
      return selectedBranch;
    }
    // Otherwise, prefer the default branch, or first branch
    if (branches.includes(selectedRepo.default_branch)) {
      return selectedRepo.default_branch;
    }
    return branches[0];
  }, [selectedRepo, branches, selectedBranch]);

  // Notify parent when selection is complete
  useEffect(() => {
    if (selectedRepo && effectiveBranch) {
      onSelect(selectedRepo.owner, selectedRepo.name, effectiveBranch);
    }
  }, [selectedRepo, effectiveBranch, onSelect]);

  if (reposError) {
    return (
      <div className="p-4 bg-yellow-900/20 border border-yellow-800 rounded-lg">
        <p className="text-yellow-400 text-sm font-medium">GitHub App not configured</p>
        <p className="text-yellow-500 text-xs mt-1">
          Configure your GitHub App in Settings to select repositories.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Repository Selection */}
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          Repository
        </label>
        <div className="relative">
          <input
            type="text"
            value={selectedRepo ? selectedRepo.full_name : repoSearch}
            onChange={(e) => {
              setRepoSearch(e.target.value);
              if (selectedRepo) {
                setSelectedRepo(null);
                setSelectedBranch('');
              }
            }}
            placeholder={reposLoading ? 'Loading repositories...' : 'Search repositories...'}
            className="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-white placeholder-gray-500"
            disabled={disabled || reposLoading}
          />
          {reposLoading && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              <svg className="w-5 h-5 animate-spin text-gray-400" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            </div>
          )}
        </div>

        {/* Repo dropdown */}
        {!selectedRepo && repoSearch && filteredRepos.length > 0 && (
          <div className="mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-lg max-h-60 overflow-y-auto">
            {filteredRepos.slice(0, 20).map((repo) => (
              <button
                key={repo.id}
                type="button"
                onClick={() => {
                  setSelectedRepo(repo);
                  setRepoSearch('');
                }}
                className="w-full px-4 py-3 text-left hover:bg-gray-700 transition-colors flex items-center justify-between"
              >
                <div>
                  <div className="text-white font-medium">{repo.full_name}</div>
                  <div className="text-gray-500 text-xs mt-0.5">
                    Default branch: {repo.default_branch}
                  </div>
                </div>
                {repo.private && (
                  <span className="text-xs bg-gray-700 px-2 py-0.5 rounded text-gray-400">
                    Private
                  </span>
                )}
              </button>
            ))}
          </div>
        )}

        {/* Show all repos if no search */}
        {!selectedRepo && !repoSearch && repos && repos.length > 0 && (
          <div className="mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-lg max-h-60 overflow-y-auto">
            {repos.slice(0, 10).map((repo) => (
              <button
                key={repo.id}
                type="button"
                onClick={() => setSelectedRepo(repo)}
                className="w-full px-4 py-3 text-left hover:bg-gray-700 transition-colors flex items-center justify-between"
              >
                <div>
                  <div className="text-white font-medium">{repo.full_name}</div>
                  <div className="text-gray-500 text-xs mt-0.5">
                    Default branch: {repo.default_branch}
                  </div>
                </div>
                {repo.private && (
                  <span className="text-xs bg-gray-700 px-2 py-0.5 rounded text-gray-400">
                    Private
                  </span>
                )}
              </button>
            ))}
            {repos.length > 10 && (
              <div className="px-4 py-2 text-gray-500 text-xs text-center border-t border-gray-700">
                Type to search {repos.length - 10} more repositories...
              </div>
            )}
          </div>
        )}

        {selectedRepo && (
          <button
            type="button"
            onClick={() => {
              setSelectedRepo(null);
              setSelectedBranch('');
            }}
            className="mt-1 text-xs text-blue-400 hover:text-blue-300"
          >
            Change repository
          </button>
        )}
      </div>

      {/* Branch Selection */}
      {selectedRepo && (
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Branch
          </label>
          <select
            value={effectiveBranch}
            onChange={(e) => setSelectedBranch(e.target.value)}
            disabled={disabled || branchesLoading}
            className="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-white"
          >
            {branchesLoading ? (
              <option>Loading branches...</option>
            ) : (
              branches?.map((branch) => (
                <option key={branch} value={branch}>
                  {branch}
                  {branch === selectedRepo.default_branch ? ' (default)' : ''}
                </option>
              ))
            )}
          </select>
        </div>
      )}
    </div>
  );
}
