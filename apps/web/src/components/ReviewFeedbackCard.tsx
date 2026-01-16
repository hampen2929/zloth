'use client';

import { useState } from 'react';
import {
  ExclamationTriangleIcon,
  ExclamationCircleIcon,
  InformationCircleIcon,
  LightBulbIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  DocumentTextIcon,
} from '@heroicons/react/24/outline';
import type { ReviewFeedbackItem, ReviewSeverity, ReviewCategory } from '@/types';
import { cn } from '@/lib/utils';

interface ReviewFeedbackCardProps {
  feedback: ReviewFeedbackItem;
  selected?: boolean;
  onSelect?: (id: string, selected: boolean) => void;
}

const severityConfig: Record<
  ReviewSeverity,
  { icon: typeof ExclamationTriangleIcon; color: string; bgColor: string }
> = {
  critical: {
    icon: ExclamationTriangleIcon,
    color: 'text-red-400',
    bgColor: 'bg-red-500/10 border-red-500/30',
  },
  high: {
    icon: ExclamationCircleIcon,
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/10 border-orange-500/30',
  },
  medium: {
    icon: InformationCircleIcon,
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-500/10 border-yellow-500/30',
  },
  low: {
    icon: LightBulbIcon,
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10 border-blue-500/30',
  },
};

const categoryLabels: Record<ReviewCategory, string> = {
  security: 'Security',
  bug: 'Bug',
  performance: 'Performance',
  maintainability: 'Maintainability',
  best_practice: 'Best Practice',
  style: 'Style',
  documentation: 'Documentation',
  test: 'Test',
};

export function ReviewFeedbackCard({
  feedback,
  selected = false,
  onSelect,
}: ReviewFeedbackCardProps) {
  const [expanded, setExpanded] = useState(false);

  const config = severityConfig[feedback.severity];
  const SeverityIcon = config.icon;

  const lineInfo = feedback.line_start
    ? feedback.line_end && feedback.line_end !== feedback.line_start
      ? `L${feedback.line_start}-${feedback.line_end}`
      : `L${feedback.line_start}`
    : null;

  return (
    <div
      className={cn(
        'rounded-lg border transition-all',
        config.bgColor,
        selected && 'ring-2 ring-blue-500'
      )}
    >
      {/* Header */}
      <div
        className="flex items-start gap-3 p-3 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        {onSelect && (
          <input
            type="checkbox"
            checked={selected}
            onChange={(e) => {
              e.stopPropagation();
              onSelect(feedback.id, e.target.checked);
            }}
            className="mt-1 h-4 w-4 rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-900"
          />
        )}

        <SeverityIcon className={cn('w-5 h-5 flex-shrink-0 mt-0.5', config.color)} />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={cn(
                'px-1.5 py-0.5 text-xs font-medium rounded uppercase',
                config.color,
                'bg-gray-800/50'
              )}
            >
              {feedback.severity}
            </span>
            <span className="px-1.5 py-0.5 text-xs font-medium rounded text-gray-400 bg-gray-800/50">
              {categoryLabels[feedback.category]}
            </span>
          </div>

          <h4 className="font-medium text-gray-200 mt-1">{feedback.title}</h4>

          <div className="flex items-center gap-2 mt-1 text-xs text-gray-400">
            <DocumentTextIcon className="w-3.5 h-3.5" />
            <span className="font-mono truncate">{feedback.file_path}</span>
            {lineInfo && <span className="text-gray-500">{lineInfo}</span>}
          </div>
        </div>

        <button
          className="p-1 rounded hover:bg-gray-700/50 transition-colors"
          onClick={(e) => {
            e.stopPropagation();
            setExpanded(!expanded);
          }}
        >
          {expanded ? (
            <ChevronUpIcon className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronDownIcon className="w-4 h-4 text-gray-400" />
          )}
        </button>
      </div>

      {/* Expanded Content */}
      {expanded && (
        <div className="px-3 pb-3 space-y-3 border-t border-gray-700/50 pt-3">
          <div>
            <h5 className="text-xs font-medium text-gray-400 mb-1">Description</h5>
            <p className="text-sm text-gray-300">{feedback.description}</p>
          </div>

          {feedback.code_snippet && (
            <div>
              <h5 className="text-xs font-medium text-gray-400 mb-1">Code</h5>
              <pre className="p-2 bg-gray-900 rounded text-xs text-gray-300 overflow-x-auto font-mono">
                {feedback.code_snippet}
              </pre>
            </div>
          )}

          {feedback.suggestion && (
            <div>
              <h5 className="text-xs font-medium text-gray-400 mb-1">Suggested Fix</h5>
              <p className="text-sm text-green-300">{feedback.suggestion}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
