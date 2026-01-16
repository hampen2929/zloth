'use client';

import { useState } from 'react';
import { KanbanCard } from './KanbanCard';
import type { KanbanColumn as KanbanColumnType, TaskWithKanbanStatus } from '@/types';
import { InboxIcon, ArchiveBoxIcon } from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';

interface BacklogArchivedColumnProps {
  backlogColumn: KanbanColumnType;
  archivedColumn: KanbanColumnType;
  onMoveToTodo: (taskId: string) => void;
  onMoveToBacklog: (taskId: string) => void;
  onArchive: (taskId: string) => void;
  onUnarchive: (taskId: string) => void;
  onStartTask?: (task: TaskWithKanbanStatus) => void;
}

type TabType = 'backlog' | 'archived';

export function BacklogArchivedColumn({
  backlogColumn,
  archivedColumn,
  onMoveToTodo,
  onMoveToBacklog,
  onArchive,
  onUnarchive,
  onStartTask,
}: BacklogArchivedColumnProps) {
  const [activeTab, setActiveTab] = useState<TabType>('backlog');

  const currentColumn = activeTab === 'backlog' ? backlogColumn : archivedColumn;
  const totalCount = backlogColumn.count + archivedColumn.count;

  return (
    <div className="flex-shrink-0 w-80 bg-gray-900 rounded-lg flex flex-col">
      {/* Header */}
      <div className="p-3 border-b border-gray-800 rounded-t-lg bg-gray-800">
        <div className="flex items-center gap-2">
          <InboxIcon className="w-5 h-5 text-gray-400" />
          <span className="font-medium text-gray-400">Backlog & Archived</span>
          <span className="ml-auto text-sm text-gray-500 bg-gray-700 px-2 py-0.5 rounded">
            {totalCount}
          </span>
        </div>
        <p className="text-xs text-gray-500 mt-1">Ideas, unorganized, and archived tasks</p>
      </div>

      {/* Tab buttons */}
      <div className="flex border-b border-gray-800">
        <button
          onClick={() => setActiveTab('backlog')}
          className={cn(
            'flex-1 flex items-center justify-center gap-2 py-2 text-sm transition-colors',
            activeTab === 'backlog'
              ? 'text-gray-200 bg-gray-800/50 border-b-2 border-gray-400'
              : 'text-gray-500 hover:text-gray-400 hover:bg-gray-800/30'
          )}
        >
          <InboxIcon className="w-4 h-4" />
          <span>Backlog</span>
          <span className="text-xs bg-gray-700 px-1.5 py-0.5 rounded">{backlogColumn.count}</span>
        </button>
        <button
          onClick={() => setActiveTab('archived')}
          className={cn(
            'flex-1 flex items-center justify-center gap-2 py-2 text-sm transition-colors',
            activeTab === 'archived'
              ? 'text-gray-200 bg-gray-800/50 border-b-2 border-gray-400'
              : 'text-gray-500 hover:text-gray-400 hover:bg-gray-800/30'
          )}
        >
          <ArchiveBoxIcon className="w-4 h-4" />
          <span>Archived</span>
          <span className="text-xs bg-gray-700 px-1.5 py-0.5 rounded">{archivedColumn.count}</span>
        </button>
      </div>

      {/* Task list */}
      <div className="p-2 space-y-2 flex-1 overflow-y-auto max-h-[calc(100vh-250px)]">
        {currentColumn.tasks.map((task) => (
          <KanbanCard
            key={task.id}
            task={task}
            columnStatus={currentColumn.status}
            onMoveToTodo={onMoveToTodo}
            onMoveToBacklog={onMoveToBacklog}
            onArchive={onArchive}
            onUnarchive={onUnarchive}
            onStartTask={onStartTask}
          />
        ))}
        {currentColumn.tasks.length === 0 && (
          <div className="text-center py-8 text-gray-600 text-sm">
            {activeTab === 'backlog' ? 'No backlog tasks' : 'No archived tasks'}
          </div>
        )}
      </div>
    </div>
  );
}
