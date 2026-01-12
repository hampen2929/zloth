'use client';

import { useMemo, useRef, useState } from 'react';
import type { GitHubRepository } from '@/types';
import { cn } from '@/lib/utils';
import { useClickOutside } from '@/hooks';
import { BoltIcon, ChevronDownIcon } from '@heroicons/react/24/outline';

interface BranchSelectorProps {
  selectedBranch: string;
  branches: string[] | undefined;
  selectedRepo: GitHubRepository | null;
  onBranchSelect: (branch: string) => void;
  disabled?: boolean;
}

export function BranchSelector({
  selectedBranch,
  branches,
  selectedRepo,
  onBranchSelect,
  disabled = false,
}: BranchSelectorProps) {
  const [showDropdown, setShowDropdown] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);

  useClickOutside(dropdownRef, () => {
    setShowDropdown(false);
    setSearchQuery('');
  }, showDropdown);

  const filteredBranches = useMemo(() => {
    if (!branches) return undefined;
    if (!searchQuery) return branches;
    const query = searchQuery.toLowerCase();
    return branches.filter((branch) => branch.toLowerCase().includes(query));
  }, [branches, searchQuery]);

  const handleSelect = (branch: string) => {
    onBranchSelect(branch);
    setShowDropdown(false);
    setSearchQuery('');
  };

  const isDisabled = disabled || !selectedRepo;

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => !isDisabled && setShowDropdown(!showDropdown)}
        disabled={isDisabled}
        className={cn(
          'flex items-center gap-2 transition-colors',
          'focus:outline-none focus:ring-2 focus:ring-blue-500 rounded px-2 py-1',
          isDisabled ? 'text-gray-600 cursor-not-allowed' : 'text-gray-400 hover:text-white'
        )}
      >
        <BoltIcon className="w-4 h-4" />
        <span>{selectedBranch || 'Select branch'}</span>
        <ChevronDownIcon
          className={cn('w-4 h-4 transition-transform', showDropdown && 'rotate-180')}
        />
      </button>

      {showDropdown && (
        <div className="absolute top-full left-0 mt-2 w-64 bg-gray-800 border border-gray-700 rounded-lg shadow-xl overflow-hidden z-10 animate-in fade-in slide-in-from-bottom-2 duration-200">
          <div className="p-2 border-b border-gray-700">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search branches..."
              className={cn(
                'w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded',
                'text-white text-sm placeholder:text-gray-500',
                'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
              )}
              autoFocus
            />
          </div>
          <div className="max-h-60 overflow-y-auto">
            {!branches ? (
              <div className="p-4 text-center">
                <div className="w-5 h-5 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin mx-auto" />
                <p className="text-gray-500 text-sm mt-2">Loading branches...</p>
              </div>
            ) : filteredBranches && filteredBranches.length === 0 ? (
              <div className="p-4 text-center">
                <BoltIcon className="w-8 h-8 text-gray-600 mx-auto mb-2" />
                <p className="text-gray-500 text-sm">No branches found</p>
              </div>
            ) : (
              filteredBranches?.map((branch) => (
                <button
                  key={branch}
                  onClick={() => handleSelect(branch)}
                  className={cn(
                    'w-full px-3 py-2.5 text-left flex items-center justify-between',
                    'hover:bg-gray-700 transition-colors',
                    'focus:outline-none focus:bg-gray-700',
                    branch === selectedBranch ? 'text-blue-400' : 'text-gray-100'
                  )}
                >
                  <span className="truncate">{branch}</span>
                  {selectedRepo && branch === selectedRepo.default_branch && (
                    <span className="text-xs text-gray-500 ml-2 flex-shrink-0">(default)</span>
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
