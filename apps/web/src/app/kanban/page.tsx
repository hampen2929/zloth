'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { kanbanApi, githubApi } from '@/lib/api';
import { KanbanBoard } from './components/KanbanBoard';
import { KanbanFilters } from './components/KanbanFilters';
import type { GitHubRepository } from '@/types';

export default function KanbanPage() {
  const [selectedRepo, setSelectedRepo] = useState<GitHubRepository | null>(null);

  const { data: repos } = useSWR('github-repos', githubApi.listRepos);

  const {
    data: board,
    isLoading,
    mutate,
  } = useSWR(
    ['kanban', selectedRepo?.id],
    () => kanbanApi.getBoard(selectedRepo?.id?.toString()),
    { refreshInterval: 5000 }
  );

  return (
    <div className="h-screen flex flex-col bg-gray-950">
      <header className="p-4 border-b border-gray-800">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-white">Kanban Board</h1>
          <KanbanFilters
            selectedRepo={selectedRepo}
            repos={repos ?? []}
            onRepoChange={setSelectedRepo}
          />
        </div>
      </header>

      <main className="flex-1 overflow-x-auto p-4">
        {isLoading ? (
          <KanbanSkeleton />
        ) : board ? (
          <KanbanBoard board={board} onUpdate={mutate} />
        ) : (
          <EmptyState />
        )}
      </main>
    </div>
  );
}

function KanbanSkeleton() {
  return (
    <div className="flex gap-4 h-full">
      {[...Array(6)].map((_, i) => (
        <div
          key={i}
          className="flex-shrink-0 w-80 bg-gray-900 rounded-lg animate-pulse"
        >
          <div className="p-3 border-b border-gray-800">
            <div className="h-5 bg-gray-800 rounded w-24" />
          </div>
          <div className="p-2 space-y-2">
            {[...Array(3)].map((_, j) => (
              <div key={j} className="h-24 bg-gray-800 rounded-lg" />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center">
        <p className="text-gray-500 text-lg">No tasks found</p>
        <p className="text-gray-600 text-sm mt-1">
          Create a task from the home page to get started
        </p>
      </div>
    </div>
  );
}
