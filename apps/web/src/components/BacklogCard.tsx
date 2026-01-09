'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import type { BacklogItem, BacklogStatus, BrokenDownTaskType, EstimatedSize, SubTask } from '@/types';
import { backlogApi } from '@/lib/api';
import {
  SparklesIcon,
  BugAntIcon,
  ArrowPathIcon,
  DocumentTextIcon,
  BeakerIcon,
  PlayIcon,
  CheckIcon,
  ChevronDownIcon,
  ChevronRightIcon,
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

const statusConfig: Record<BacklogStatus, { label: string; color: string }> = {
  draft: { label: 'Draft', color: 'bg-gray-700 text-gray-300' },
  ready: { label: 'Ready', color: 'bg-blue-900/50 text-blue-300' },
  in_progress: { label: 'In Progress', color: 'bg-purple-900/50 text-purple-300' },
  done: { label: 'Done', color: 'bg-green-900/50 text-green-300' },
};

export default function BacklogCard({
  item,
  onUpdate,
  onStartWork,
}: BacklogCardProps) {
  const router = useRouter();
  const [isExpanded, setIsExpanded] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const typeInfo = typeConfig[item.type] || typeConfig.feature;
  const sizeInfo = sizeConfig[item.estimated_size] || sizeConfig.medium;
  const statusInfo = statusConfig[item.status] || statusConfig.draft;

  const completedSubtasks = item.subtasks.filter((st) => st.completed).length;
  const totalSubtasks = item.subtasks.length;

  const handleStartWork = async (e: React.MouseEvent) => {
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
      console.error('Failed to start work:', error);
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
            <h4 className="font-medium text-gray-100 truncate flex-1">
              {item.title}
            </h4>
            <span
              className={cn(
                'px-2 py-0.5 rounded border text-xs flex-shrink-0',
                sizeInfo.color
              )}
            >
              {sizeInfo.label}
            </span>
          </div>

          {/* Status and meta info */}
          <div className="flex items-center gap-2 mb-2 text-xs">
            <span className={cn('px-2 py-0.5 rounded', statusInfo.color)}>
              {statusInfo.label}
            </span>
            <span className="text-gray-500">{typeInfo.label}</span>
            {totalSubtasks > 0 && (
              <span className="text-gray-500">
                Subtasks: {completedSubtasks}/{totalSubtasks}
              </span>
            )}
          </div>

          {/* Description */}
          <p className="text-sm text-gray-400 mb-2 line-clamp-2">
            {item.description}
          </p>

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
            {item.task_id ? (
              <button
                onClick={handleViewTask}
                className="px-3 py-1 text-sm bg-gray-700 hover:bg-gray-600 text-gray-200 rounded transition-colors"
              >
                View Task
              </button>
            ) : (
              <button
                onClick={handleStartWork}
                disabled={isStarting}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1 text-sm rounded transition-colors',
                  isStarting
                    ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
                    : 'bg-purple-600 hover:bg-purple-700 text-white'
                )}
              >
                <PlayIcon className="w-3.5 h-3.5" />
                {isStarting ? 'Starting...' : 'Start Work'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
