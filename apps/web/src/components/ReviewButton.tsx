'use client';

import { useState, useRef, useEffect } from 'react';
import {
  MagnifyingGlassIcon,
  ChevronDownIcon,
  CommandLineIcon,
} from '@heroicons/react/24/outline';
import { Button } from './ui/Button';
import { reviewsApi } from '@/lib/api';
import { cn } from '@/lib/utils';

interface ReviewButtonProps {
  taskId: string;
  runIds: string[];
  disabled?: boolean;
  onReviewCreated: () => void;
  onError: (message: string) => void;
}

type ReviewExecutor = 'claude_code' | 'codex_cli' | 'gemini_cli';

const EXECUTOR_OPTIONS: { id: ReviewExecutor; label: string }[] = [
  { id: 'claude_code', label: 'Claude Code' },
  { id: 'codex_cli', label: 'Codex' },
  { id: 'gemini_cli', label: 'Gemini CLI' },
];

export function ReviewButton({
  taskId,
  runIds,
  disabled = false,
  onReviewCreated,
  onError,
}: ReviewButtonProps) {
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [selectedExecutor, setSelectedExecutor] = useState<ReviewExecutor>('claude_code');
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleStartReview = async () => {
    if (runIds.length === 0) {
      onError('No successful runs to review');
      return;
    }

    setIsOpen(false);
    setLoading(true);
    try {
      await reviewsApi.create(taskId, {
        target_run_ids: runIds,
        executor_type: selectedExecutor,
      });
      onReviewCreated();
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to start review');
    } finally {
      setLoading(false);
    }
  };

  const selectedLabel = EXECUTOR_OPTIONS.find((opt) => opt.id === selectedExecutor)?.label || 'Select';

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Split button: main action + dropdown */}
      <div className="flex">
        <Button
          variant="secondary"
          size="sm"
          onClick={handleStartReview}
          disabled={disabled || loading || runIds.length === 0}
          isLoading={loading}
          className="flex items-center gap-1.5 rounded-r-none border-r-0"
        >
          <MagnifyingGlassIcon className="w-4 h-4" />
          {loading ? 'Starting Review...' : 'Review Code'}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setIsOpen(!isOpen)}
          disabled={disabled || loading || runIds.length === 0}
          className="px-2 rounded-l-none"
        >
          <ChevronDownIcon className={cn('w-4 h-4 transition-transform', isOpen && 'rotate-180')} />
        </Button>
      </div>

      {/* Dropdown menu */}
      {isOpen && (
        <div className="absolute right-0 top-full mt-1 z-50 w-48 bg-gray-800 border border-gray-700 rounded-lg shadow-lg py-1">
          <div className="px-3 py-2 border-b border-gray-700">
            <p className="text-xs text-gray-400 font-medium">Review with</p>
          </div>
          {EXECUTOR_OPTIONS.map((option) => (
            <button
              key={option.id}
              onClick={() => {
                setSelectedExecutor(option.id);
              }}
              className={cn(
                'w-full flex items-center gap-2 px-3 py-2 text-sm transition-colors',
                selectedExecutor === option.id
                  ? 'bg-blue-600/20 text-blue-400'
                  : 'text-gray-300 hover:bg-gray-700'
              )}
            >
              <CommandLineIcon className="w-4 h-4" />
              <span>{option.label}</span>
              {selectedExecutor === option.id && (
                <span className="ml-auto text-blue-400">✓</span>
              )}
            </button>
          ))}
          <div className="border-t border-gray-700 mt-1 pt-1 px-3 py-2">
            <p className="text-xs text-gray-500">
              Currently: <span className="text-gray-400">{selectedLabel}</span>
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
