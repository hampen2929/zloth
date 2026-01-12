'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import type { BacklogItem, BrokenDownTaskType, EstimatedSize, SubTask } from '@/types';
import { backlogApi } from '@/lib/api';
import {
  SparklesIcon,
  BugAntIcon,
  ArrowPathIcon,
  DocumentTextIcon,
  BeakerIcon,
  ArrowRightIcon,
  CheckIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  PencilIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';

interface BacklogCardProps {
  item: BacklogItem;
  onUpdate?: (item: BacklogItem) => void;
  onStartWork?: (item: BacklogItem, taskId: string) => void;
}

const typeConfig: Record<
  BrokenDownTaskType,
  { label: string; icon: React.ReactNode; color: string }
> = {
  feature: {
    label: 'Feature',
    icon: <SparklesIcon className="w-4 h-4" />,
    color: 'text-blue-400',
  },
  bug_fix: {
    label: 'Bug Fix',
    icon: <BugAntIcon className="w-4 h-4" />,
    color: 'text-red-400',
  },
  refactoring: {
    label: 'Refactoring',
    icon: <ArrowPathIcon className="w-4 h-4" />,
    color: 'text-yellow-400',
  },
  docs: {
    label: 'Docs',
    icon: <DocumentTextIcon className="w-4 h-4" />,
    color: 'text-green-400',
  },
  test: {
    label: 'Test',
    icon: <BeakerIcon className="w-4 h-4" />,
    color: 'text-purple-400',
  },
};

const sizeConfig: Record<EstimatedSize, { label: string; color: string }> = {
  small: { label: 'Small', color: 'bg-green-900/30 text-green-400 border-green-800/50' },
  medium: { label: 'Medium', color: 'bg-yellow-900/30 text-yellow-400 border-yellow-800/50' },
  large: { label: 'Large', color: 'bg-red-900/30 text-red-400 border-red-800/50' },
};

export default function BacklogCard({
  item,
  onUpdate,
  onStartWork,
}: BacklogCardProps) {
  const router = useRouter();
  const [isExpanded, setIsExpanded] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(item.title);
  const [editDescription, setEditDescription] = useState(item.description);
  const [isSaving, setIsSaving] = useState(false);
  const typeInfo = typeConfig[item.type] || typeConfig.feature;
  const sizeInfo = sizeConfig[item.estimated_size] || sizeConfig.medium;

  const completedSubtasks = item.subtasks.filter((st) => st.completed).length;
  const totalSubtasks = item.subtasks.length;

  const handleMoveToTodo = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isStarting || item.task_id) return;

    setIsStarting(true);
    try {
      const task = await backlogApi.startWork(item.id);
      if (onStartWork) {
        onStartWork(item, task.id);
      }
      router.push(`/tasks/${task.id}`);
    } catch (error) {
      console.error('Failed to move to ToDo:', error);
    } finally {
      setIsStarting(false);
    }
  };

  const handleViewTask = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (item.task_id) {
      router.push(`/tasks/${item.task_id}`);
    }
  };

  const handleEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditTitle(item.title);
    setEditDescription(item.description);
    setIsEditing(true);
    setIsExpanded(true);
  };

  const handleCancelEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsEditing(false);
    setEditTitle(item.title);
    setEditDescription(item.description);
  };

  const handleSaveEdit = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isSaving) return;

    setIsSaving(true);
    try {
      const updated = await backlogApi.update(item.id, {
        title: editTitle,
        description: editDescription,
      });
      if (onUpdate) {
        onUpdate(updated);
      }
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to update backlog item:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleSubtaskToggle = async (subtask: SubTask) => {
    const updatedSubtasks = item.subtasks.map((st) =>
      st.id === subtask.id ? { ...st, completed: !st.completed } : st
    );

    try {
      const updated = await backlogApi.update(item.id, {
        subtasks: updatedSubtasks,
      });
      if (onUpdate) {
        onUpdate(updated);
      }
    } catch (error) {
      console.error('Failed to update subtask:', error);
    }
  };

  return (
    <div
      className={cn(
        'p-4 rounded-lg border transition-all duration-200',
        'bg-gray-800/30 border-gray-700 hover:border-gray-600 hover:bg-gray-800/50'
      )}
    >
      <div className="flex items-start gap-3">
        {/* Expand toggle */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="p-0.5 text-gray-500 hover:text-gray-300 flex-shrink-0 mt-0.5"
        >
          {isExpanded ? (
            <ChevronDownIcon className="w-4 h-4" />
          ) : (
            <ChevronRightIcon className="w-4 h-4" />
          )}
        </button>

        <div className="flex-1 min-w-0">
          {/* Title row */}
          <div className="flex items-center gap-2 mb-1">
            <span className={cn('flex-shrink-0', typeInfo.color)}>
              {typeInfo.icon}
            </span>
            {isEditing ? (
              <input
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                onClick={(e) => e.stopPropagation()}
                className="flex-1 bg-gray-700 text-gray-100 px-2 py-1 rounded border border-gray-600 focus:border-purple-500 focus:outline-none text-sm font-medium"
                placeholder="Title"
              />
            ) : (
              <h4 className="font-medium text-gray-100 truncate flex-1">
                {item.title}
              </h4>
            )}
            <span
              className={cn(
                'px-2 py-0.5 rounded border text-xs flex-shrink-0',
                sizeInfo.color
              )}
            >
              {sizeInfo.label}
            </span>
            {!isEditing && !item.task_id && (
              <button
                onClick={handleEdit}
                className="p-1 text-gray-500 hover:text-gray-300 transition-colors"
                title="Edit"
              >
                <PencilIcon className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Meta info */}
          <div className="flex items-center gap-2 mb-2 text-xs">
            <span className="text-gray-500">{typeInfo.label}</span>
            {totalSubtasks > 0 && (
              <span className="text-gray-500">
                Subtasks: {completedSubtasks}/{totalSubtasks}
              </span>
            )}
            {item.task_id && (
              <span className="px-2 py-0.5 rounded bg-green-900/50 text-green-300">
                Linked to Task
              </span>
            )}
          </div>

          {/* Description */}
          {isEditing ? (
            <textarea
              value={editDescription}
              onChange={(e) => setEditDescription(e.target.value)}
              onClick={(e) => e.stopPropagation()}
              className="w-full bg-gray-700 text-gray-300 px-2 py-1 rounded border border-gray-600 focus:border-purple-500 focus:outline-none text-sm mb-2 min-h-[60px] resize-y"
              placeholder="Description"
            />
          ) : (
            <p className="text-sm text-gray-400 mb-2 line-clamp-2">
              {item.description}
            </p>
          )}

          {/* Subtasks (expanded) */}
          {isExpanded && item.subtasks.length > 0 && (
            <div className="mb-3 space-y-1">
              {item.subtasks.map((subtask) => (
                <div
                  key={subtask.id}
                  className="flex items-center gap-2 text-sm"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    onClick={() => handleSubtaskToggle(subtask)}
                    className={cn(
                      'w-4 h-4 rounded border flex items-center justify-center flex-shrink-0',
                      subtask.completed
                        ? 'bg-green-600 border-green-600'
                        : 'border-gray-600 hover:border-gray-500'
                    )}
                  >
                    {subtask.completed && (
                      <CheckIcon className="w-3 h-3 text-white" />
                    )}
                  </button>
                  <span
                    className={cn(
                      subtask.completed
                        ? 'text-gray-500 line-through'
                        : 'text-gray-300'
                    )}
                  >
                    {subtask.title}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Target files (expanded) */}
          {isExpanded && item.target_files.length > 0 && (
            <div className="mb-2">
              <span className="text-xs text-gray-500">Target: </span>
              <span className="text-xs text-gray-400 font-mono">
                {item.target_files.join(', ')}
              </span>
            </div>
          )}

          {/* Tags */}
          {item.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-2">
              {item.tags.slice(0, isExpanded ? undefined : 4).map((tag, i) => (
                <span
                  key={i}
                  className="text-xs px-1.5 py-0.5 bg-gray-700/50 text-gray-400 rounded"
                >
                  {tag}
                </span>
              ))}
              {!isExpanded && item.tags.length > 4 && (
                <span className="text-xs text-gray-500">
                  +{item.tags.length - 4}
                </span>
              )}
            </div>
          )}

          {/* Implementation hint (expanded) */}
          {isExpanded && item.implementation_hint && (
            <div className="mb-3 text-xs text-gray-400 pl-2 border-l border-gray-700">
              <span className="text-blue-400 font-medium">Hint: </span>
              {item.implementation_hint}
            </div>
          )}

          {/* Action buttons */}
          <div className="flex items-center gap-2 mt-2">
            {isEditing ? (
              <>
                <button
                  onClick={handleSaveEdit}
                  disabled={isSaving}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1 text-sm rounded transition-colors',
                    isSaving
                      ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
                      : 'bg-green-600 hover:bg-green-700 text-white'
                  )}
                >
                  <CheckIcon className="w-3.5 h-3.5" />
                  {isSaving ? 'Saving...' : 'Save'}
                </button>
                <button
                  onClick={handleCancelEdit}
                  disabled={isSaving}
                  className="flex items-center gap-1.5 px-3 py-1 text-sm bg-gray-700 hover:bg-gray-600 text-gray-200 rounded transition-colors"
                >
                  <XMarkIcon className="w-3.5 h-3.5" />
                  Cancel
                </button>
              </>
            ) : item.task_id ? (
              <button
                onClick={handleViewTask}
                className="px-3 py-1 text-sm bg-gray-700 hover:bg-gray-600 text-gray-200 rounded transition-colors"
              >
                View Task
              </button>
            ) : (
              <button
                onClick={handleMoveToTodo}
                disabled={isStarting}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1 text-sm rounded transition-colors',
                  isStarting
                    ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
                    : 'bg-purple-600 hover:bg-purple-700 text-white'
                )}
              >
                <ArrowRightIcon className="w-3.5 h-3.5" />
                {isStarting ? 'Moving...' : 'Move to ToDo'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
