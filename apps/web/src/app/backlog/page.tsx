'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { backlogApi, kanbanApi } from '@/lib/api';
import type { BacklogItem, TaskWithKanbanStatus } from '@/types';
import BacklogCard from '@/components/BacklogCard';
import NewBacklogModal from '@/components/NewBacklogModal';
import { useToast } from '@/components/ui/Toast';
import {
  ClipboardDocumentListIcon,
  SparklesIcon,
  PlusIcon,
  ArchiveBoxIcon,
  ArrowPathIcon,
  InboxIcon,
} from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';
import { formatRelativeTime } from '@/lib/utils';

type TabType = 'backlog' | 'archived';

export default function BacklogPage() {
  const [items, setItems] = useState<BacklogItem[]>([]);
  const [backlogTasks, setBacklogTasks] = useState<TaskWithKanbanStatus[]>([]);
  const [archivedTasks, setArchivedTasks] = useState<TaskWithKanbanStatus[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isNewModalOpen, setIsNewModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>('backlog');
  const { success, error: toastError } = useToast();

  const fetchItems = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [backlogItems, board] = await Promise.all([
        backlogApi.list(),
        kanbanApi.getBoard(),
      ]);
      setItems(backlogItems);

      // Extract backlog and archived tasks from kanban board
      const backlogColumn = board.columns.find(c => c.status === 'backlog');
      const archivedColumn = board.columns.find(c => c.status === 'archived');
      setBacklogTasks(backlogColumn?.tasks ?? []);
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
      success('Task restored to backlog');
      fetchItems();
    } catch (err) {
      toastError(err instanceof Error ? err.message : 'Failed to restore task');
    }
  };

  const handleMoveToTodo = async (taskId: string) => {
    try {
      await kanbanApi.moveToTodo(taskId);
      success('Task moved to ToDo');
      fetchItems();
    } catch (err) {
      toastError(err instanceof Error ? err.message : 'Failed to move task');
    }
  };

  const handleArchive = async (taskId: string) => {
    try {
      await kanbanApi.archiveTask(taskId);
      success('Task archived');
      fetchItems();
    } catch (err) {
      toastError(err instanceof Error ? err.message : 'Failed to archive task');
    }
  };

  const backlogCount = items.length + backlogTasks.length;
  const archivedCount = archivedTasks.length;
  const totalCount = backlogCount + archivedCount;

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-gray-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ClipboardDocumentListIcon className="w-6 h-6 text-purple-400" />
            <h1 className="text-xl font-semibold text-white">Backlog & Archived</h1>
            <span className="text-sm text-gray-500">
              {totalCount} item{totalCount !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="flex items-center gap-2">
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
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-4 mt-4">
          <button
            onClick={() => setActiveTab('backlog')}
            className={cn(
              'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
              activeTab === 'backlog'
                ? 'bg-gray-800 text-white'
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
            )}
          >
            <InboxIcon className="w-4 h-4" />
            Backlog
            <span className="ml-1 px-2 py-0.5 text-xs rounded bg-gray-700 text-gray-300">
              {backlogCount}
            </span>
          </button>
          <button
            onClick={() => setActiveTab('archived')}
            className={cn(
              'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
              activeTab === 'archived'
                ? 'bg-gray-800 text-white'
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
            )}
          >
            <ArchiveBoxIcon className="w-4 h-4" />
            Archived
            <span className="ml-1 px-2 py-0.5 text-xs rounded bg-gray-700 text-gray-300">
              {archivedCount}
            </span>
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
          // Backlog Tab Content
          backlogCount === 0 ? (
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
            <div className="space-y-6">
              {/* Backlog Items (from backlog API) */}
              {items.length > 0 && (
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

              {/* Backlog Tasks (from kanban) */}
              {backlogTasks.length > 0 && (
                <div className="space-y-2">
                  {items.length > 0 && (
                    <h3 className="text-sm font-medium text-gray-400 mb-3">Tasks in Backlog</h3>
                  )}
                  {backlogTasks.map((task) => (
                    <TaskCard
                      key={task.id}
                      task={task}
                      onMoveToTodo={handleMoveToTodo}
                      onArchive={handleArchive}
                      showMoveToTodo
                    />
                  ))}
                </div>
              )}
            </div>
          )
        ) : (
          // Archived Tab Content
          archivedCount === 0 ? (
            <div className="text-center py-16">
              <ArchiveBoxIcon className="w-16 h-16 text-gray-700 mx-auto mb-4" />
              <h2 className="text-lg font-medium text-gray-300 mb-2">
                No archived tasks
              </h2>
              <p className="text-gray-500">
                Archived tasks will appear here. You can restore them to the backlog.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {archivedTasks.map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  onUnarchive={handleUnarchive}
                  showRestore
                />
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

// Simple task card for backlog and archived tasks
function TaskCard({
  task,
  onMoveToTodo,
  onArchive,
  onUnarchive,
  showMoveToTodo,
  showRestore,
}: {
  task: TaskWithKanbanStatus;
  onMoveToTodo?: (taskId: string) => void;
  onArchive?: (taskId: string) => void;
  onUnarchive?: (taskId: string) => void;
  showMoveToTodo?: boolean;
  showRestore?: boolean;
}) {
  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 hover:border-gray-600 transition-colors">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <Link
            href={`/tasks/${task.id}`}
            className="text-white font-medium hover:text-blue-400 transition-colors block truncate"
          >
            {task.title || 'Untitled Task'}
          </Link>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-gray-500">
              {formatRelativeTime(task.updated_at)}
            </span>
            {task.run_count > 0 && (
              <span className="text-xs text-gray-500">
                {task.run_count} run{task.run_count !== 1 ? 's' : ''}
              </span>
            )}
            {task.pr_count > 0 && (
              <span className="text-xs text-gray-500">
                {task.pr_count} PR{task.pr_count !== 1 ? 's' : ''}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {showMoveToTodo && onMoveToTodo && (
            <button
              onClick={() => onMoveToTodo(task.id)}
              className="px-3 py-1.5 text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors"
            >
              Move to ToDo
            </button>
          )}
          {showMoveToTodo && onArchive && (
            <button
              onClick={() => onArchive(task.id)}
              className="p-1.5 text-gray-400 hover:text-gray-200 hover:bg-gray-700 rounded transition-colors"
              title="Archive"
            >
              <ArchiveBoxIcon className="w-4 h-4" />
            </button>
          )}
          {showRestore && onUnarchive && (
            <button
              onClick={() => onUnarchive(task.id)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
            >
              <ArrowPathIcon className="w-3.5 h-3.5" />
              Restore
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
