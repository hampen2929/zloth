'use client';

import { cn } from '@/lib/utils';
import type { BrokenDownTask, BrokenDownTaskType, EstimatedSize } from '@/types';
import {
  SparklesIcon,
  BugAntIcon,
  ArrowPathIcon,
  DocumentTextIcon,
  BeakerIcon,
  CheckIcon,
} from '@heroicons/react/24/outline';

interface BreakdownTaskCardProps {
  task: BrokenDownTask;
  selected: boolean;
  onToggle: () => void;
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

export default function BreakdownTaskCard({
  task,
  selected,
  onToggle,
}: BreakdownTaskCardProps) {
  const typeInfo = typeConfig[task.type] || typeConfig.feature;
  const sizeInfo = sizeConfig[task.estimated_size] || sizeConfig.medium;

  return (
    <div
      onClick={onToggle}
      className={cn(
        'p-4 rounded-lg border cursor-pointer transition-all duration-200',
        selected
          ? 'bg-blue-900/20 border-blue-700 ring-1 ring-blue-500/50'
          : 'bg-gray-800/30 border-gray-700 hover:border-gray-600 hover:bg-gray-800/50'
      )}
    >
      <div className="flex items-start gap-3">
        {/* Checkbox */}
        <div
          className={cn(
            'w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 mt-0.5 transition-colors',
            selected
              ? 'bg-blue-600 border-blue-600'
              : 'border-gray-600 hover:border-gray-500'
          )}
        >
          {selected && <CheckIcon className="w-3.5 h-3.5 text-white" />}
        </div>

        <div className="flex-1 min-w-0">
          {/* Title */}
          <div className="flex items-center gap-2 mb-1">
            <span className={cn('flex-shrink-0', typeInfo.color)}>
              {typeInfo.icon}
            </span>
            <h4 className="font-medium text-gray-100 truncate">{task.title}</h4>
          </div>

          {/* Meta info */}
          <div className="flex items-center gap-2 mb-2 text-xs">
            <span
              className={cn(
                'px-2 py-0.5 rounded border',
                sizeInfo.color
              )}
            >
              {sizeInfo.label}
            </span>
            <span className="text-gray-500">{typeInfo.label}</span>
          </div>

          {/* Description */}
          <p className="text-sm text-gray-400 mb-2 line-clamp-2">
            {task.description}
          </p>

          {/* Target files */}
          {task.target_files.length > 0 && (
            <div className="mb-2">
              <span className="text-xs text-gray-500">Target: </span>
              <span className="text-xs text-gray-400 font-mono">
                {task.target_files.slice(0, 2).join(', ')}
                {task.target_files.length > 2 && ` +${task.target_files.length - 2} more`}
              </span>
            </div>
          )}

          {/* Tags */}
          {task.tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {task.tags.slice(0, 4).map((tag, i) => (
                <span
                  key={i}
                  className="text-xs px-1.5 py-0.5 bg-gray-700/50 text-gray-400 rounded"
                >
                  {tag}
                </span>
              ))}
              {task.tags.length > 4 && (
                <span className="text-xs text-gray-500">+{task.tags.length - 4}</span>
              )}
            </div>
          )}

          {/* Implementation hint (collapsed) */}
          {task.implementation_hint && (
            <details className="mt-2">
              <summary className="text-xs text-blue-400 cursor-pointer hover:text-blue-300">
                Implementation hint
              </summary>
              <p className="mt-1 text-xs text-gray-400 pl-2 border-l border-gray-700">
                {task.implementation_hint}
              </p>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}
