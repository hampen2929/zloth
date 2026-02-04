'use client';

import React from 'react';
import { useParams, useRouter } from 'next/navigation';
import useSWR from 'swr';
import { decisionsApi, tasksApi } from '@/lib/api';
import type { Decision, DecisionType } from '@/types';
import { DecisionCard } from '@/components/DecisionCard';
import { Button } from '@/components/ui/Button';
import {
  ArrowLeftIcon,
  FunnelIcon,
  ClipboardDocumentListIcon,
} from '@heroicons/react/24/outline';

export default function DecisionsPage() {
  const params = useParams();
  const router = useRouter();
  const taskId = params.taskId as string;

  const [typeFilter, setTypeFilter] = React.useState<DecisionType | 'all'>('all');

  const { data: task } = useSWR(
    taskId ? ['task', taskId] : null,
    () => tasksApi.get(taskId)
  );

  const {
    data: decisions,
    error,
    isLoading,
    mutate,
  } = useSWR<Decision[]>(
    taskId ? ['decisions', taskId, typeFilter] : null,
    () =>
      decisionsApi.list(taskId, typeFilter === 'all' ? undefined : typeFilter)
  );

  const handleBack = () => {
    router.push(`/tasks/${taskId}`);
  };

  const typeFilterOptions: Array<{ value: DecisionType | 'all'; label: string }> = [
    { value: 'all', label: 'All' },
    { value: 'selection', label: 'Selection' },
    { value: 'promotion', label: 'Promotion' },
    { value: 'merge', label: 'Merge' },
  ];

  const groupedDecisions = React.useMemo(() => {
    if (!decisions) return {};

    const groups: Record<string, Decision[]> = {};

    for (const decision of decisions) {
      const date = new Date(decision.created_at).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      });

      if (!groups[date]) {
        groups[date] = [];
      }
      groups[date].push(decision);
    }

    return groups;
  }, [decisions]);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="sm" onClick={handleBack}>
                <ArrowLeftIcon className="h-4 w-4 mr-2" />
                Back to Task
              </Button>
              <div className="h-6 w-px bg-gray-700" />
              <div className="flex items-center gap-2">
                <ClipboardDocumentListIcon className="h-5 w-5 text-gray-400" />
                <h1 className="text-lg font-semibold">Decision History</h1>
              </div>
            </div>

            {task && (
              <div className="text-sm text-gray-400">
                {task.title || 'Untitled Task'}
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Filters */}
      <div className="max-w-5xl mx-auto px-4 py-4">
        <div className="flex items-center gap-3">
          <FunnelIcon className="h-4 w-4 text-gray-500" />
          <span className="text-sm text-gray-400">Filter by type:</span>
          <div className="flex gap-2">
            {typeFilterOptions.map((option) => (
              <button
                key={option.value}
                onClick={() => setTypeFilter(option.value)}
                className={`px-3 py-1 text-sm rounded-full transition-colors ${
                  typeFilter === option.value
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <main className="max-w-5xl mx-auto px-4 py-6">
        {isLoading && (
          <div className="text-center py-12 text-gray-500">
            Loading decisions...
          </div>
        )}

        {error && (
          <div className="text-center py-12 text-red-400">
            Failed to load decisions: {error.message}
          </div>
        )}

        {decisions && decisions.length === 0 && (
          <div className="text-center py-12">
            <ClipboardDocumentListIcon className="h-12 w-12 text-gray-600 mx-auto mb-4" />
            <p className="text-gray-400">No decisions recorded yet</p>
            <p className="text-sm text-gray-500 mt-2">
              Decisions will appear here when you select runs, create PRs, or merge changes.
            </p>
          </div>
        )}

        {decisions && decisions.length > 0 && (
          <div className="space-y-8">
            {Object.entries(groupedDecisions).map(([date, dateDecisions]) => (
              <div key={date}>
                <h3 className="text-sm font-medium text-gray-400 mb-4 sticky top-16 bg-gray-950 py-2">
                  {date}
                </h3>
                <div className="space-y-4">
                  {dateDecisions.map((decision) => (
                    <DecisionCard
                      key={decision.id}
                      decision={decision}
                      onOutcomeUpdate={() => mutate()}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Summary Stats */}
        {decisions && decisions.length > 0 && (
          <div className="mt-12 pt-8 border-t border-gray-800">
            <h3 className="text-sm font-medium text-gray-400 mb-4">Summary</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-gray-800/50 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-gray-200">
                  {decisions.length}
                </div>
                <div className="text-sm text-gray-500">Total Decisions</div>
              </div>
              <div className="bg-gray-800/50 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-blue-400">
                  {decisions.filter((d) => d.decision_type === 'selection').length}
                </div>
                <div className="text-sm text-gray-500">Selections</div>
              </div>
              <div className="bg-gray-800/50 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-green-400">
                  {decisions.filter((d) => d.decision_type === 'promotion').length}
                </div>
                <div className="text-sm text-gray-500">Promotions</div>
              </div>
              <div className="bg-gray-800/50 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-purple-400">
                  {decisions.filter((d) => d.decision_type === 'merge').length}
                </div>
                <div className="text-sm text-gray-500">Merges</div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
