'use client';

import { useState, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import useSWR from 'swr';
import { reposApi, tasksApi, modelsApi, githubApi } from '@/lib/api';
import type { GitHubRepository, ModelProfile } from '@/types';

export default function HomePage() {
  const router = useRouter();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const [instruction, setInstruction] = useState('');
  const [selectedRepo, setSelectedRepo] = useState<GitHubRepository | null>(null);
  const [selectedBranch, setSelectedBranch] = useState<string>('');
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Dropdown states
  const [showModelDropdown, setShowModelDropdown] = useState(false);
  const [showRepoDropdown, setShowRepoDropdown] = useState(false);
  const [showBranchDropdown, setShowBranchDropdown] = useState(false);
  const [repoSearch, setRepoSearch] = useState('');

  // Data fetching
  const { data: models } = useSWR('models', modelsApi.list);
  const { data: repos } = useSWR('github-repos', githubApi.listRepos);
  const { data: branches } = useSWR(
    selectedRepo ? `branches-${selectedRepo.owner}-${selectedRepo.name}` : null,
    () => selectedRepo ? githubApi.listBranches(selectedRepo.owner, selectedRepo.name) : null
  );

  // Set default branch when repo changes
  const handleRepoSelect = useCallback((repo: GitHubRepository) => {
    setSelectedRepo(repo);
    setSelectedBranch(repo.default_branch);
    setShowRepoDropdown(false);
    setRepoSearch('');
  }, []);

  // Filter repos by search
  const filteredRepos = repos?.filter(
    (repo) =>
      !repoSearch ||
      repo.full_name.toLowerCase().includes(repoSearch.toLowerCase())
  );

  // Toggle model selection
  const toggleModel = (modelId: string) => {
    setSelectedModels((prev) =>
      prev.includes(modelId)
        ? prev.filter((id) => id !== modelId)
        : [...prev, modelId]
    );
  };

  // Get selected model names for display
  const getSelectedModelNames = () => {
    if (!models || selectedModels.length === 0) return 'Select models';
    const names = models
      .filter((m) => selectedModels.includes(m.id))
      .map((m) => m.display_name || m.model_name);
    if (names.length === 1) return names[0];
    return `${names.length} models selected`;
  };

  const handleSubmit = async () => {
    if (!instruction.trim() || !selectedRepo || !selectedBranch || selectedModels.length === 0) {
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
      });

      // Add the instruction as the first message
      await tasksApi.addMessage(task.id, {
        role: 'user',
        content: instruction,
      });

      // Navigate to the task page (runs will be created there)
      router.push(`/tasks/${task.id}?models=${selectedModels.join(',')}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start task');
    } finally {
      setLoading(false);
    }
  };

  // Handle keyboard shortcuts
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
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

  const canSubmit = instruction.trim() && selectedRepo && selectedBranch && selectedModels.length > 0 && !loading;

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-100px)]">
      <div className="w-full max-w-3xl px-4">
        {/* Main Input Area */}
        <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden">
          {/* Textarea */}
          <div className="p-4">
            <textarea
              ref={textareaRef}
              value={instruction}
              onChange={handleTextareaChange}
              onKeyDown={handleKeyDown}
              placeholder="Ask dursor to build, fix bugs, explore"
              className="w-full bg-transparent text-white placeholder-gray-500 text-lg resize-none focus:outline-none min-h-[80px]"
              rows={3}
              disabled={loading}
            />
          </div>

          {/* Bottom Bar */}
          <div className="px-4 pb-4 flex items-center justify-between">
            {/* Model Selector */}
            <div className="relative">
              <button
                onClick={() => setShowModelDropdown(!showModelDropdown)}
                className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors text-sm"
              >
                <span>{getSelectedModelNames()}</span>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {showModelDropdown && models && (
                <div className="absolute bottom-full left-0 mb-2 w-64 bg-gray-800 border border-gray-700 rounded-lg shadow-lg overflow-hidden z-10">
                  <div className="p-2 border-b border-gray-700">
                    <span className="text-xs text-gray-500 uppercase tracking-wider">Select Models</span>
                  </div>
                  <div className="max-h-60 overflow-y-auto">
                    {models.length === 0 ? (
                      <div className="p-3 text-gray-500 text-sm">
                        No models configured. Add in Settings.
                      </div>
                    ) : (
                      models.map((model) => (
                        <button
                          key={model.id}
                          onClick={() => toggleModel(model.id)}
                          className="w-full px-3 py-2 text-left hover:bg-gray-700 flex items-center gap-3"
                        >
                          <div className={`w-4 h-4 rounded border ${
                            selectedModels.includes(model.id)
                              ? 'bg-blue-600 border-blue-600'
                              : 'border-gray-600'
                          } flex items-center justify-center`}>
                            {selectedModels.includes(model.id) && (
                              <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                              </svg>
                            )}
                          </div>
                          <div>
                            <div className="text-white text-sm">{model.display_name || model.model_name}</div>
                            <div className="text-gray-500 text-xs">{model.provider}</div>
                          </div>
                        </button>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Right side buttons */}
            <div className="flex items-center gap-2">
              {/* Image attach button (placeholder) */}
              <button className="p-2 text-gray-500 hover:text-gray-300 transition-colors" title="Attach image">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </button>

              {/* Submit button */}
              <button
                onClick={handleSubmit}
                disabled={!canSubmit}
                className={`p-2 rounded-lg transition-colors ${
                  canSubmit
                    ? 'bg-white text-black hover:bg-gray-200'
                    : 'bg-gray-700 text-gray-500 cursor-not-allowed'
                }`}
                title="Submit (⌘+Enter)"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Repository and Branch Selection */}
        <div className="mt-3 flex items-center gap-4 text-sm">
          {/* Repository Selector */}
          <div className="relative">
            <button
              onClick={() => {
                setShowRepoDropdown(!showRepoDropdown);
                setShowBranchDropdown(false);
              }}
              className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
              </svg>
              <span>{selectedRepo ? selectedRepo.full_name : 'Select repository'}</span>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {showRepoDropdown && (
              <div className="absolute top-full left-0 mt-2 w-80 bg-gray-800 border border-gray-700 rounded-lg shadow-lg overflow-hidden z-10">
                <div className="p-2 border-b border-gray-700">
                  <input
                    type="text"
                    value={repoSearch}
                    onChange={(e) => setRepoSearch(e.target.value)}
                    placeholder="Search repositories..."
                    className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                    autoFocus
                  />
                </div>
                <div className="max-h-60 overflow-y-auto">
                  {!repos ? (
                    <div className="p-3 text-gray-500 text-sm">Loading...</div>
                  ) : filteredRepos && filteredRepos.length === 0 ? (
                    <div className="p-3 text-gray-500 text-sm">No repositories found</div>
                  ) : (
                    filteredRepos?.slice(0, 20).map((repo) => (
                      <button
                        key={repo.id}
                        onClick={() => handleRepoSelect(repo)}
                        className="w-full px-3 py-2 text-left hover:bg-gray-700 flex items-center justify-between"
                      >
                        <span className="text-white">{repo.full_name}</span>
                        {repo.private && (
                          <span className="text-xs bg-gray-700 px-2 py-0.5 rounded text-gray-400">Private</span>
                        )}
                      </button>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Branch Selector */}
          <div className="relative">
            <button
              onClick={() => {
                if (selectedRepo) {
                  setShowBranchDropdown(!showBranchDropdown);
                  setShowRepoDropdown(false);
                }
              }}
              disabled={!selectedRepo}
              className={`flex items-center gap-2 transition-colors ${
                selectedRepo ? 'text-gray-400 hover:text-white' : 'text-gray-600 cursor-not-allowed'
              }`}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              <span>{selectedBranch || 'Select branch'}</span>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {showBranchDropdown && branches && (
              <div className="absolute top-full left-0 mt-2 w-48 bg-gray-800 border border-gray-700 rounded-lg shadow-lg overflow-hidden z-10">
                <div className="max-h-60 overflow-y-auto">
                  {branches.map((branch) => (
                    <button
                      key={branch}
                      onClick={() => {
                        setSelectedBranch(branch);
                        setShowBranchDropdown(false);
                      }}
                      className={`w-full px-3 py-2 text-left hover:bg-gray-700 ${
                        branch === selectedBranch ? 'text-blue-400' : 'text-white'
                      }`}
                    >
                      {branch}
                      {selectedRepo && branch === selectedRepo.default_branch && (
                        <span className="ml-2 text-xs text-gray-500">(default)</span>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="mt-4 p-3 bg-red-900/30 border border-red-800 rounded-lg text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Loading indicator */}
        {loading && (
          <div className="mt-4 text-center text-gray-400">
            Setting up workspace...
          </div>
        )}
      </div>
    </div>
  );
}
