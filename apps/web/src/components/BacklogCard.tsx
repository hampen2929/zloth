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
  PlusIcon,
  TrashIcon,
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

const typeOptions: { value: BrokenDownTaskType; label: string }[] = [
  { value: 'feature', label: 'Feature' },
  { value: 'bug_fix', label: 'Bug Fix' },
  { value: 'refactoring', label: 'Refactoring' },
  { value: 'docs', label: 'Docs' },
  { value: 'test', label: 'Test' },
];

const sizeOptions: { value: EstimatedSize; label: string }[] = [
  { value: 'small', label: 'Small' },
  { value: 'medium', label: 'Medium' },
  { value: 'large', label: 'Large' },
];

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
  const [isSaving, setIsSaving] = useState(false);

  // Edit state for all fields
  const [editTitle, setEditTitle] = useState(item.title);
  const [editDescription, setEditDescription] = useState(item.description);
  const [editType, setEditType] = useState<BrokenDownTaskType>(item.type);
  const [editSize, setEditSize] = useState<EstimatedSize>(item.estimated_size);
  const [editTargetFiles, setEditTargetFiles] = useState(item.target_files.join(', '));
  const [editImplementationHint, setEditImplementationHint] = useState(item.implementation_hint || '');
  const [editTags, setEditTags] = useState(item.tags.join(', '));
  const [editSubtasks, setEditSubtasks] = useState<SubTask[]>(item.subtasks);
  const [newSubtaskTitle, setNewSubtaskTitle] = useState('');

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
    // Reset all edit state to current item values
    setEditTitle(item.title);
    setEditDescription(item.description);
    setEditType(item.type);
    setEditSize(item.estimated_size);
    setEditTargetFiles(item.target_files.join(', '));
    setEditImplementationHint(item.implementation_hint || '');
    setEditTags(item.tags.join(', '));
    setEditSubtasks([...item.subtasks]);
    setNewSubtaskTitle('');
    setIsEditing(true);
    setIsExpanded(true);
  };

  const handleCancelEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsEditing(false);
  };

  const handleSaveEdit = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isSaving) return;

    setIsSaving(true);
    try {
      // Parse comma-separated values
      const targetFiles = editTargetFiles
        .split(',')
        .map((f) => f.trim())
        .filter((f) => f.length > 0);
      const tags = editTags
        .split(',')
        .map((t) => t.trim())
        .filter((t) => t.length > 0);

      const updated = await backlogApi.update(item.id, {
        title: editTitle,
        description: editDescription,
        type: editType,
        estimated_size: editSize,
        target_files: targetFiles,
        implementation_hint: editImplementationHint || undefined,
        tags: tags,
        subtasks: editSubtasks,
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
    if (isEditing) {
      // In edit mode, just update local state
      setEditSubtasks((prev) =>
        prev.map((st) =>
          st.id === subtask.id ? { ...st, completed: !st.completed } : st
        )
      );
    } else {
      // Not editing, update directly
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
    }
  };

  const handleAddSubtask = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!newSubtaskTitle.trim()) return;

    const newSubtask: SubTask = {
      id: `temp-${Date.now()}`,
      title: newSubtaskTitle.trim(),
      completed: false,
    };
    setEditSubtasks((prev) => [...prev, newSubtask]);
    setNewSubtaskTitle('');
  };

  const handleRemoveSubtask = (subtaskId: string) => {
    setEditSubtasks((prev) => prev.filter((st) => st.id !== subtaskId));
  };

  const currentSubtasks = isEditing ? editSubtasks : item.subtasks;

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
            <span className={cn('flex-shrink-0', isEditing ? typeConfig[editType]?.color : typeInfo.color)}>
              {isEditing ? typeConfig[editType]?.icon : typeInfo.icon}
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
            {isEditing ? (
              <select
                value={editSize}
                onChange={(e) => setEditSize(e.target.value as EstimatedSize)}
                onClick={(e) => e.stopPropagation()}
                className="bg-gray-700 text-gray-100 px-2 py-1 rounded border border-gray-600 focus:border-purple-500 focus:outline-none text-xs"
              >
                {sizeOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            ) : (
              <span
                className={cn(
                  'px-2 py-0.5 rounded border text-xs flex-shrink-0',
                  sizeInfo.color
                )}
              >
                {sizeInfo.label}
              </span>
            )}
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

          {/* Type selector (editing) */}
          {isEditing && (
            <div className="flex items-center gap-2 mb-2">
              <label className="text-xs text-gray-500">Type:</label>
              <select
                value={editType}
                onChange={(e) => setEditType(e.target.value as BrokenDownTaskType)}
                onClick={(e) => e.stopPropagation()}
                className="bg-gray-700 text-gray-100 px-2 py-1 rounded border border-gray-600 focus:border-purple-500 focus:outline-none text-xs"
              >
                {typeOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Meta info (not editing) */}
          {!isEditing && (
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
          )}

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

          {/* Target files (editing or expanded) */}
          {isEditing ? (
            <div className="mb-2">
              <label className="text-xs text-gray-500 block mb-1">Target Files (comma-separated):</label>
              <input
                type="text"
                value={editTargetFiles}
                onChange={(e) => setEditTargetFiles(e.target.value)}
                onClick={(e) => e.stopPropagation()}
                className="w-full bg-gray-700 text-gray-300 px-2 py-1 rounded border border-gray-600 focus:border-purple-500 focus:outline-none text-sm font-mono"
                placeholder="src/components/Button.tsx, src/utils/helpers.ts"
              />
            </div>
          ) : (
            isExpanded && item.target_files.length > 0 && (
              <div className="mb-2">
                <span className="text-xs text-gray-500">Target: </span>
                <span className="text-xs text-gray-400 font-mono">
                  {item.target_files.join(', ')}
                </span>
              </div>
            )
          )}

          {/* Implementation hint (editing or expanded) */}
          {isEditing ? (
            <div className="mb-2">
              <label className="text-xs text-gray-500 block mb-1">Implementation Hint:</label>
              <textarea
                value={editImplementationHint}
                onChange={(e) => setEditImplementationHint(e.target.value)}
                onClick={(e) => e.stopPropagation()}
                className="w-full bg-gray-700 text-gray-300 px-2 py-1 rounded border border-gray-600 focus:border-purple-500 focus:outline-none text-sm min-h-[40px] resize-y"
                placeholder="Any hints or notes for implementation"
              />
            </div>
          ) : (
            isExpanded && item.implementation_hint && (
              <div className="mb-3 text-xs text-gray-400 pl-2 border-l border-gray-700">
                <span className="text-blue-400 font-medium">Hint: </span>
                {item.implementation_hint}
              </div>
            )
          )}

          {/* Tags (editing or always shown if exist) */}
          {isEditing ? (
            <div className="mb-2">
              <label className="text-xs text-gray-500 block mb-1">Tags (comma-separated):</label>
              <input
                type="text"
                value={editTags}
                onChange={(e) => setEditTags(e.target.value)}
                onClick={(e) => e.stopPropagation()}
                className="w-full bg-gray-700 text-gray-300 px-2 py-1 rounded border border-gray-600 focus:border-purple-500 focus:outline-none text-sm"
                placeholder="frontend, ui, urgent"
              />
            </div>
          ) : (
            item.tags.length > 0 && (
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
            )
          )}

          {/* Subtasks (editing or expanded) */}
          {(isEditing || (isExpanded && currentSubtasks.length > 0)) && (
            <div className="mb-3">
              {isEditing && (
                <label className="text-xs text-gray-500 block mb-1">Subtasks:</label>
              )}
              <div className="space-y-1">
                {currentSubtasks.map((subtask) => (
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
                        'flex-1',
                        subtask.completed
                          ? 'text-gray-500 line-through'
                          : 'text-gray-300'
                      )}
                    >
                      {subtask.title}
                    </span>
                    {isEditing && (
                      <button
                        onClick={() => handleRemoveSubtask(subtask.id)}
                        className="p-0.5 text-gray-500 hover:text-red-400 transition-colors"
                        title="Remove subtask"
                      >
                        <TrashIcon className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
              {/* Add subtask input */}
              {isEditing && (
                <div className="flex items-center gap-2 mt-2">
                  <input
                    type="text"
                    value={newSubtaskTitle}
                    onChange={(e) => setNewSubtaskTitle(e.target.value)}
                    onClick={(e) => e.stopPropagation()}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleAddSubtask(e as unknown as React.MouseEvent);
                      }
                    }}
                    className="flex-1 bg-gray-700 text-gray-300 px-2 py-1 rounded border border-gray-600 focus:border-purple-500 focus:outline-none text-sm"
                    placeholder="Add subtask..."
                  />
                  <button
                    onClick={handleAddSubtask}
                    className="p-1 text-gray-500 hover:text-green-400 transition-colors"
                    title="Add subtask"
                  >
                    <PlusIcon className="w-4 h-4" />
                  </button>
                </div>
              )}
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
