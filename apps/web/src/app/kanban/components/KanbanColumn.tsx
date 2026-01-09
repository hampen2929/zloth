'use client';

import { KanbanCard } from './KanbanCard';
import type { KanbanColumn as KanbanColumnType, TaskKanbanStatus } from '@/types';
import {
  InboxIcon,
  ClipboardDocumentListIcon,
  CogIcon,
  EyeIcon,
  CheckCircleIcon,
  ArchiveBoxIcon,
} from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';

interface KanbanColumnProps {
  column: KanbanColumnType;
  onMoveToTodo: (taskId: string) => void;
  onMoveToBacklog: (taskId: string) => void;
  onArchive: (taskId: string) => void;
  onUnarchive: (taskId: string) => void;
}

const COLUMN_CONFIG: Record<
  TaskKanbanStatus,
  {
    label: string;
    color: string;
    bgColor: string;
    icon: React.ComponentType<{ className?: string }>;
    description: string;
  }
> = {
  backlog: {
    label: 'Backlog',
    color: 'text-gray-400',
    bgColor: 'bg-gray-800',
    icon: InboxIcon,
    description: 'Ideas and unorganized tasks',
  },
  todo: {
    label: 'ToDo',
    color: 'text-blue-400',
    bgColor: 'bg-blue-900/20',
    icon: ClipboardDocumentListIcon,
    description: 'Ready for AI implementation',
  },
  in_progress: {
    label: 'In Progress',
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-900/20',
    icon: CogIcon,
    description: 'AI is working on it',
  },
  in_review: {
    label: 'In Review',
    color: 'text-purple-400',
    bgColor: 'bg-purple-900/20',
    icon: EyeIcon,
    description: 'Waiting for human review',
  },
  done: {
    label: 'Done',
    color: 'text-green-400',
    bgColor: 'bg-green-900/20',
    icon: CheckCircleIcon,
    description: 'PR merged',
  },
  archived: {
    label: 'Archived',
    color: 'text-gray-500',
    bgColor: 'bg-gray-800/50',
    icon: ArchiveBoxIcon,
    description: 'Archived tasks',
  },
};

export function KanbanColumn({
  column,
  onMoveToTodo,
  onMoveToBacklog,
  onArchive,
  onUnarchive,
}: KanbanColumnProps) {
  const config = COLUMN_CONFIG[column.status];
  const Icon = config.icon;

  return (
    <div className="flex-shrink-0 w-80 bg-gray-900 rounded-lg flex flex-col">
      <div className={cn('p-3 border-b border-gray-800 rounded-t-lg', config.bgColor)}>
        <div className="flex items-center gap-2">
          <Icon className={cn('w-5 h-5', config.color)} />
          <span className={cn('font-medium', config.color)}>{config.label}</span>
          <span className="ml-auto text-sm text-gray-500 bg-gray-800 px-2 py-0.5 rounded">
            {column.count}
          </span>
        </div>
        <p className="text-xs text-gray-500 mt-1">{config.description}</p>
      </div>

      <div className="p-2 space-y-2 flex-1 overflow-y-auto max-h-[calc(100vh-200px)]">
        {column.tasks.map((task) => (
          <KanbanCard
            key={task.id}
            task={task}
            columnStatus={column.status}
            onMoveToTodo={onMoveToTodo}
            onMoveToBacklog={onMoveToBacklog}
            onArchive={onArchive}
            onUnarchive={onUnarchive}
          />
        ))}
        {column.tasks.length === 0 && (
          <div className="text-center py-8 text-gray-600 text-sm">No tasks</div>
        )}
      </div>
    </div>
  );
}
