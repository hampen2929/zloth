'use client';

import { useRef, useState } from 'react';
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
  const dropdownRef = useRef<HTMLDivElement>(null);

  useClickOutside(dropdownRef, () => setShowDropdown(false), showDropdown);

  const handleSelect = (branch: string) => {
    onBranchSelect(branch);
    setShowDropdown(false);
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

      {showDropdown && branches && (
        <div className="absolute top-full left-0 mt-2 w-56 bg-gray-800 border border-gray-700 rounded-lg shadow-xl overflow-hidden z-10 animate-in fade-in slide-in-from-bottom-2 duration-200">
          <div className="max-h-60 overflow-y-auto">
            {branches.map((branch) => (
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
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
