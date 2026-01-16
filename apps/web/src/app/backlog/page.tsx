'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { backlogApi, kanbanApi } from '@/lib/api';
import type { BacklogItem, TaskWithKanbanStatus } from '@/types';
import BacklogCard from '@/components/BacklogCard';
import NewBacklogModal from '@/components/NewBacklogModal';
import { cn } from '@/lib/utils';
import {
  ClipboardDocumentListIcon,
  SparklesIcon,
  PlusIcon,
  ArchiveBoxIcon,
  InboxIcon,
} from '@heroicons/react/24/outline';

type TabType = 'backlog' | 'archived';

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();

  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString();
}

export default function BacklogPage() {
  const [activeTab, setActiveTab] = useState<TabType>('backlog');
  const [items, setItems] = useState<BacklogItem[]>([]);
  const [archivedTasks, setArchivedTasks] = useState<TaskWithKanbanStatus[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isNewModalOpen, setIsNewModalOpen] = useState(false);

  const fetchItems = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [backlogData, kanbanData] = await Promise.all([
        backlogApi.list(),
        kanbanApi.getBoard(),
      ]);
      setItems(backlogData);
      // Extract archived tasks from kanban board
      const archivedColumn = kanbanData.columns.find(c => c.status === 'archived');
      setArchivedTasks(archivedColumn?.tasks ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load items');
    } finally {
      setIsLoading(false);
    }
  }, []);

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

  const handleUnarchive = async (taskId: string) => {
    try {
      await kanbanApi.unarchiveTask(taskId);
      fetchItems();
    } catch (err) {
      console.error('Failed to unarchive task:', err);
    }
  };

  const currentCount = useMemo(() => {
    return activeTab === 'backlog' ? items.length : archivedTasks.length;
  }, [activeTab, items.length, archivedTasks.length]);

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-gray-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ClipboardDocumentListIcon className="w-6 h-6 text-purple-400" />
            <h1 className="text-xl font-semibold text-white">Backlog & Archived</h1>
            <span className="text-sm text-gray-500">
              {currentCount} item{currentCount !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {activeTab === 'backlog' && (
              <>
                <button
                  onClick={() => setIsNewModalOpen(true)}
                  className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
                >
                  <PlusIcon className="w-4 h-4" />
                  New Backlog
                </button>
                <button
                  onClick={handleOpenBreakdown}
                  className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
                >
                  <SparklesIcon className="w-4 h-4" />
                  Breakdown
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Tab buttons */}
      <div className="flex-shrink-0 px-6 border-b border-gray-800">
        <div className="flex gap-4">
          <button
            onClick={() => setActiveTab('backlog')}
            className={cn(
              'flex items-center gap-2 py-3 text-sm font-medium transition-colors border-b-2 -mb-px',
              activeTab === 'backlog'
                ? 'text-purple-400 border-purple-400'
                : 'text-gray-500 border-transparent hover:text-gray-300'
            )}
          >
            <InboxIcon className="w-4 h-4" />
            <span>Backlog</span>
            <span className="text-xs bg-gray-700 px-1.5 py-0.5 rounded">{items.length}</span>
          </button>
          <button
            onClick={() => setActiveTab('archived')}
            className={cn(
              'flex items-center gap-2 py-3 text-sm font-medium transition-colors border-b-2 -mb-px',
              activeTab === 'archived'
                ? 'text-gray-300 border-gray-400'
                : 'text-gray-500 border-transparent hover:text-gray-300'
            )}
          >
            <ArchiveBoxIcon className="w-4 h-4" />
            <span>Archived</span>
            <span className="text-xs bg-gray-700 px-1.5 py-0.5 rounded">{archivedTasks.length}</span>
          </button>
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
        ) : activeTab === 'backlog' ? (
          // Backlog tab content
          items.length === 0 ? (
            <div className="text-center py-16">
              <ClipboardDocumentListIcon className="w-16 h-16 text-gray-700 mx-auto mb-4" />
              <h2 className="text-lg font-medium text-gray-300 mb-2">
                No backlog items yet
              </h2>
              <p className="text-gray-500 mb-6">
                Create a new backlog item or use Breakdown to analyze requirements.
              </p>
              <div className="flex items-center justify-center gap-3">
                <button
                  onClick={() => setIsNewModalOpen(true)}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
                >
                  <PlusIcon className="w-4 h-4" />
                  New Backlog
                </button>
                <button
                  onClick={handleOpenBreakdown}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
                >
                  <SparklesIcon className="w-4 h-4" />
                  Breakdown
                </button>
              </div>
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
          )
        ) : (
          // Archived tab content
          archivedTasks.length === 0 ? (
            <div className="text-center py-16">
              <ArchiveBoxIcon className="w-16 h-16 text-gray-700 mx-auto mb-4" />
              <h2 className="text-lg font-medium text-gray-300 mb-2">
                No archived tasks
              </h2>
              <p className="text-gray-500">
                Archived tasks will appear here.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {archivedTasks.map((task) => (
                <div
                  key={task.id}
                  className="flex items-center justify-between p-4 bg-gray-800 rounded-lg border border-gray-700"
                >
                  <div className="flex-1 min-w-0">
                    <Link
                      href={`/tasks/${task.id}`}
                      className="font-medium text-white hover:text-blue-400 transition-colors"
                    >
                      {task.title || 'Untitled Task'}
                    </Link>
                    <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                      <span>{formatRelativeTime(task.updated_at)}</span>
                      {task.run_count > 0 && (
                        <span>{task.run_count} run{task.run_count !== 1 ? 's' : ''}</span>
                      )}
                      {task.pr_count > 0 && (
                        <span>{task.pr_count} PR{task.pr_count !== 1 ? 's' : ''}</span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => handleUnarchive(task.id)}
                    className="ml-4 px-3 py-1.5 text-sm text-blue-400 hover:text-blue-300 hover:bg-gray-700 rounded transition-colors"
                  >
                    Restore
                  </button>
                </div>
              ))}
            </div>
          )
        )}
      </div>

      {/* New Backlog Modal */}
      <NewBacklogModal
        isOpen={isNewModalOpen}
        onClose={() => setIsNewModalOpen(false)}
        onCreated={fetchItems}
      />
    </div>
  );
}
