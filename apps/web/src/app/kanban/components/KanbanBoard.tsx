'use client';

import { KanbanColumn } from './KanbanColumn';
import { kanbanApi } from '@/lib/api';
import type { KanbanBoard as KanbanBoardType, TaskKanbanStatus } from '@/types';
import { useToast } from '@/components/ui/Toast';

interface KanbanBoardProps {
  board: KanbanBoardType;
  onUpdate: () => void;
}

// Order of columns to display
const COLUMN_ORDER: TaskKanbanStatus[] = [
  'backlog',
  'todo',
  'in_progress',
  'in_review',
  'done',
  'archived',
];

export function KanbanBoard({ board, onUpdate }: KanbanBoardProps) {
  const { success, error: toastError } = useToast();

  // Get columns in the correct order
  const orderedColumns = COLUMN_ORDER.map((status) => {
    const column = board.columns.find((c) => c.status === status);
    return column ?? { status, tasks: [], count: 0 };
  });

  const handleMoveToTodo = async (taskId: string) => {
    try {
      await kanbanApi.moveToTodo(taskId);
      success('Task moved to ToDo');
      onUpdate();
    } catch (err) {
      toastError(err instanceof Error ? err.message : 'Failed to move task');
    }
  };

  const handleMoveToBacklog = async (taskId: string) => {
    try {
      await kanbanApi.moveToBacklog(taskId);
      success('Task moved to Backlog');
      onUpdate();
    } catch (err) {
      toastError(err instanceof Error ? err.message : 'Failed to move task');
    }
  };

  const handleArchive = async (taskId: string) => {
    try {
      await kanbanApi.archiveTask(taskId);
      success('Task archived');
      onUpdate();
    } catch (err) {
      toastError(err instanceof Error ? err.message : 'Failed to archive task');
    }
  };

  const handleUnarchive = async (taskId: string) => {
    try {
      await kanbanApi.unarchiveTask(taskId);
      success('Task restored');
      onUpdate();
    } catch (err) {
      toastError(err instanceof Error ? err.message : 'Failed to restore task');
    }
  };

  return (
    <div className="flex gap-4 h-full">
      {orderedColumns.map((column) => (
        <KanbanColumn
          key={column.status}
          column={column}
          onMoveToTodo={handleMoveToTodo}
          onMoveToBacklog={handleMoveToBacklog}
          onArchive={handleArchive}
          onUnarchive={handleUnarchive}
        />
      ))}
    </div>
  );
}
