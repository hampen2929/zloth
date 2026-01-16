'use client';

import { useState, useRef } from 'react';
import type { GitHubRepository } from '@/types';
import { FolderIcon, ChevronDownIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';
import { useClickOutside } from '@/hooks';

interface KanbanFiltersProps {
  selectedRepo: GitHubRepository | null;
  repos: GitHubRepository[];
  onRepoChange: (repo: GitHubRepository | null) => void;
}

export function KanbanFilters({
  selectedRepo,
  repos,
  onRepoChange,
}: KanbanFiltersProps) {
  const [showDropdown, setShowDropdown] = useState(false);
  const [search, setSearch] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);

  useClickOutside(dropdownRef, () => setShowDropdown(false), showDropdown);

  const filteredRepos = repos.filter(
    (repo) => !search || repo.full_name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex items-center gap-2">
      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => setShowDropdown(!showDropdown)}
          className={cn(
            'flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors',
            'bg-gray-800 hover:bg-gray-700 text-gray-300',
            'border border-gray-700'
          )}
        >
          <FolderIcon className="w-4 h-4" />
          <span className="text-sm">
            {selectedRepo ? selectedRepo.full_name : 'All repositories'}
          </span>
          <ChevronDownIcon
            className={cn('w-4 h-4 transition-transform', showDropdown && 'rotate-180')}
          />
        </button>

        {showDropdown && (
          <div className="absolute top-full right-0 mt-2 w-72 bg-gray-800 border border-gray-700 rounded-lg shadow-xl overflow-hidden z-20">
            <div className="p-2 border-b border-gray-700">
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search repositories..."
                className={cn(
                  'w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded',
                  'text-white text-sm placeholder:text-gray-500',
                  'focus:outline-none focus:ring-2 focus:ring-blue-500'
                )}
                autoFocus
              />
            </div>

            <div className="max-h-60 overflow-y-auto">
              <button
                onClick={() => {
                  onRepoChange(null);
                  setShowDropdown(false);
                  setSearch('');
                }}
                className={cn(
                  'w-full px-3 py-2.5 text-left flex items-center gap-2',
                  'hover:bg-gray-700 transition-colors text-sm',
                  !selectedRepo && 'bg-gray-700'
                )}
              >
                <span className="text-gray-300">All repositories</span>
              </button>

              {filteredRepos.map((repo) => (
                <button
                  key={repo.id}
                  onClick={() => {
                    onRepoChange(repo);
                    setShowDropdown(false);
                    setSearch('');
                  }}
                  className={cn(
                    'w-full px-3 py-2.5 text-left',
                    'hover:bg-gray-700 transition-colors text-sm',
                    selectedRepo?.id === repo.id && 'bg-gray-700'
                  )}
                >
                  <span className="text-gray-300">{repo.full_name}</span>
                </button>
              ))}

              {filteredRepos.length === 0 && (
                <div className="p-4 text-center text-gray-500 text-sm">
                  No repositories found
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {selectedRepo && (
        <button
          onClick={() => onRepoChange(null)}
          className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
          title="Clear filter"
        >
          <XMarkIcon className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
