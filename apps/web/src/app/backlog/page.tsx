'use client';

import { useState, useEffect, useCallback } from 'react';
import { backlogApi } from '@/lib/api';
import type { BacklogItem, BacklogStatus } from '@/types';
import BacklogCard from '@/components/BacklogCard';
import {
  ClipboardDocumentListIcon,
  SparklesIcon,
  FunnelIcon,
} from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';

const statusFilters: { value: BacklogStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'ready', label: 'Ready' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'done', label: 'Done' },
];

export default function BacklogPage() {
  const [items, setItems] = useState<BacklogItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<BacklogStatus | 'all'>('all');

  const fetchItems = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const status = statusFilter === 'all' ? undefined : statusFilter;
      const data = await backlogApi.list(undefined, status);
      setItems(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load backlog items');
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  const handleItemUpdate = (updatedItem: BacklogItem) => {
    setItems((prev) =>
      prev.map((item) => (item.id === updatedItem.id ? updatedItem : item))
    );
  };

  const handleStartWork = () => {
    // Refresh the list after starting work
    fetchItems();
  };

  const handleOpenBreakdown = () => {
    // Dispatch custom event to open breakdown modal
    window.dispatchEvent(new CustomEvent('openBreakdownModal'));
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-gray-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ClipboardDocumentListIcon className="w-6 h-6 text-purple-400" />
            <h1 className="text-xl font-semibold text-white">Backlog</h1>
            <span className="text-sm text-gray-500">
              {items.length} item{items.length !== 1 ? 's' : ''}
            </span>
          </div>
          <button
            onClick={handleOpenBreakdown}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
          >
            <SparklesIcon className="w-4 h-4" />
            Breakdown
          </button>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2 mt-4">
          <FunnelIcon className="w-4 h-4 text-gray-500" />
          <div className="flex gap-1">
            {statusFilters.map((filter) => (
              <button
                key={filter.value}
                onClick={() => setStatusFilter(filter.value)}
                className={cn(
                  'px-3 py-1 text-sm rounded transition-colors',
                  statusFilter === filter.value
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200'
                )}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500" />
          </div>
        ) : error ? (
          <div className="text-center py-8">
            <p className="text-red-400">{error}</p>
            <button
              onClick={fetchItems}
              className="mt-4 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-200 rounded-lg transition-colors"
            >
              Retry
            </button>
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-16">
            <ClipboardDocumentListIcon className="w-16 h-16 text-gray-700 mx-auto mb-4" />
            <h2 className="text-lg font-medium text-gray-300 mb-2">
              No backlog items yet
            </h2>
            <p className="text-gray-500 mb-6">
              Use Breakdown to analyze requirements and create backlog items.
            </p>
            <button
              onClick={handleOpenBreakdown}
              className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
            >
              <SparklesIcon className="w-4 h-4" />
              Start Breakdown
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {items.map((item) => (
              <BacklogCard
                key={item.id}
                item={item}
                onUpdate={handleItemUpdate}
                onStartWork={handleStartWork}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
