'use client';

import { useState, useEffect, useRef } from 'react';
import type { Review, ReviewSeverity, OutputLine } from '@/types';
import { cn } from '@/lib/utils';
import { reviewsApi } from '@/lib/api';
import { Button } from './ui/Button';
import { ReviewFeedbackCard } from './ReviewFeedbackCard';
import {
  MagnifyingGlassIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon,
  WrenchScrewdriverIcon,
  ClipboardDocumentIcon,
  DocumentTextIcon,
  CommandLineIcon,
} from '@heroicons/react/24/outline';
import { useClipboard } from '@/hooks';

type ReviewTab = 'results' | 'logs';

interface ReviewResultCardProps {
  review: Review;
  expanded: boolean;
  onToggleExpand: () => void;
  onApplyFix?: (instruction: string) => void;
}

export function ReviewResultCard({
  review,
  expanded,
  onToggleExpand,
  onApplyFix,
}: ReviewResultCardProps) {
  const [selectedFeedbacks, setSelectedFeedbacks] = useState<Set<string>>(new Set());
  const [generatingFix, setGeneratingFix] = useState(false);
  const [activeTab, setActiveTab] = useState<ReviewTab>('results');
  const [logs, setLogs] = useState<string[]>([]);
  const [streamActive, setStreamActive] = useState(false);
  const logsContainerRef = useRef<HTMLDivElement>(null);
  const logsLengthRef = useRef(0);
  const { copy } = useClipboard();

  // Keep logsLengthRef in sync
  useEffect(() => {
    logsLengthRef.current = logs.length;
  }, [logs.length]);

  // Stream logs while running
  useEffect(() => {
    if (review.status !== 'queued' && review.status !== 'running') {
      setStreamActive(false);
      return;
    }

    setStreamActive(true);
    const fromLine = logsLengthRef.current;

    const cleanup = reviewsApi.streamLogs(review.id, {
      fromLine,
      onLine: (line: OutputLine) => {
        setLogs((prev) => {
          if (line.line_number < prev.length) {
            return prev;
          }
          const newLines = [...prev];
          while (newLines.length < line.line_number) {
            newLines.push('');
          }
          newLines.push(line.content);
          return newLines;
        });
      },
      onComplete: () => {
        setStreamActive(false);
      },
      onError: () => {
        setStreamActive(false);
      },
    });

    return cleanup;
  }, [review.id, review.status]);

  // Auto-scroll logs when streaming
  useEffect(() => {
    if (streamActive && logsContainerRef.current) {
      logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
    }
  }, [logs, streamActive]);

  // Auto-switch to logs tab when running
  useEffect(() => {
    if (review.status === 'running' || review.status === 'queued') {
      setActiveTab('logs');
    } else if (review.status === 'succeeded') {
      setActiveTab('results');
    }
  }, [review.status]);

  const handleSelectFeedback = (id: string, selected: boolean) => {
    setSelectedFeedbacks((prev) => {
      const next = new Set(prev);
      if (selected) {
        next.add(id);
      } else {
        next.delete(id);
      }
      return next;
    });
  };

  const handleSelectAll = () => {
    if (selectedFeedbacks.size === review.feedbacks.length) {
      setSelectedFeedbacks(new Set());
    } else {
      setSelectedFeedbacks(new Set(review.feedbacks.map((f) => f.id)));
    }
  };

  const handleSelectBySeverity = (severity: ReviewSeverity) => {
    const feedbackIds = review.feedbacks
      .filter((f) => f.severity === severity)
      .map((f) => f.id);
    setSelectedFeedbacks((prev) => {
      const next = new Set(prev);
      feedbackIds.forEach((id) => next.add(id));
      return next;
    });
  };

  const handleGenerateFix = async () => {
    if (selectedFeedbacks.size === 0 || !onApplyFix) return;

    setGeneratingFix(true);
    try {
      const response = await reviewsApi.generateFix(review.id, {
        feedback_ids: Array.from(selectedFeedbacks),
      });
      onApplyFix(response.instruction);
    } catch (err) {
      console.error('Failed to generate fix:', err);
    } finally {
      setGeneratingFix(false);
    }
  };

  // Count feedbacks by severity
  const severityCounts = {
    critical: review.feedbacks.filter((f) => f.severity === 'critical').length,
    high: review.feedbacks.filter((f) => f.severity === 'high').length,
    medium: review.feedbacks.filter((f) => f.severity === 'medium').length,
    low: review.feedbacks.filter((f) => f.severity === 'low').length,
  };

  const getStatusColor = () => {
    switch (review.status) {
      case 'succeeded':
        return 'border-green-500/30 bg-green-900/10';
      case 'failed':
        return 'border-red-500/30 bg-red-900/10';
      case 'running':
      case 'queued':
        return 'border-yellow-500/30 bg-yellow-900/10';
      default:
        return 'border-gray-700 bg-gray-800/50';
    }
  };

  return (
    <div
      className={cn(
        'rounded-lg border animate-in fade-in slide-in-from-top-2 duration-300',
        getStatusColor()
      )}
    >
      {/* Header */}
      <button
        onClick={onToggleExpand}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-800/30 transition-colors rounded-t-lg"
      >
        <div className="flex items-center gap-3">
          <MagnifyingGlassIcon className="w-5 h-5 text-blue-400" />
          <div className="text-left">
            <div className="font-medium text-gray-200 text-sm">
              Code Review({review.executor_type === 'claude_code' ? 'Claude Code' : review.executor_type === 'codex_cli' ? 'Codex' : review.executor_type === 'gemini_cli' ? 'Gemini CLI' : review.executor_type})
            </div>
            {review.overall_score !== null && (
              <div className={cn(
                'text-xs font-medium',
                review.overall_score >= 0.8
                  ? 'text-green-400'
                  : review.overall_score >= 0.6
                    ? 'text-yellow-400'
                    : 'text-red-400'
              )}>
                Score: {Math.round(review.overall_score * 100)}%
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={cn(
              'px-2 py-0.5 text-xs font-medium rounded',
              review.status === 'succeeded'
                ? 'bg-green-500/20 text-green-400'
                : review.status === 'failed'
                  ? 'bg-red-500/20 text-red-400'
                  : 'bg-yellow-500/20 text-yellow-400'
            )}
          >
            {review.status}
          </span>
          {expanded ? (
            <ChevronUpIcon className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronDownIcon className="w-4 h-4 text-gray-400" />
          )}
        </div>
      </button>

      {/* Expanded Content */}
      {expanded && (
        <div className="border-t border-gray-700/50">
          {/* Tabs */}
          <div className="flex border-b border-gray-700/50 px-2" role="tablist">
            <button
              onClick={(e) => { e.stopPropagation(); setActiveTab('results'); }}
              role="tab"
              aria-selected={activeTab === 'results'}
              className={cn(
                'flex items-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors',
                activeTab === 'results'
                  ? 'text-blue-400 border-b-2 border-blue-500 -mb-[1px]'
                  : 'text-gray-400 hover:text-gray-300'
              )}
            >
              <DocumentTextIcon className="w-3.5 h-3.5" />
              Review Results
              {review.feedbacks.length > 0 && (
                <span className="px-1 py-0.5 text-[10px] rounded bg-gray-700">
                  {review.feedbacks.length}
                </span>
              )}
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); setActiveTab('logs'); }}
              role="tab"
              aria-selected={activeTab === 'logs'}
              className={cn(
                'flex items-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors',
                activeTab === 'logs'
                  ? 'text-blue-400 border-b-2 border-blue-500 -mb-[1px]'
                  : 'text-gray-400 hover:text-gray-300'
              )}
            >
              <CommandLineIcon className="w-3.5 h-3.5" />
              Logs
              {streamActive && (
                <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
              )}
            </button>
          </div>

          {/* Tab Content */}
          <div className="p-4">
            {activeTab === 'results' ? (
              <>
                {/* Running/Queued State */}
                {(review.status === 'running' || review.status === 'queued') && (
                  <div className="flex flex-col items-center justify-center py-8">
                    <ArrowPathIcon className="w-8 h-8 text-blue-400 animate-spin" />
                    <p className="mt-3 text-gray-400">Running code review...</p>
                    <button
                      onClick={(e) => { e.stopPropagation(); setActiveTab('logs'); }}
                      className="mt-2 text-xs text-blue-400 hover:text-blue-300"
                    >
                      View logs
                    </button>
                  </div>
                )}

                {/* Failed State */}
                {review.status === 'failed' && (
                  <div className="p-3 bg-red-900/20 border border-red-800/50 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <ExclamationTriangleIcon className="w-4 h-4 text-red-400" />
                      <h3 className="font-medium text-red-400 text-sm">Review Failed</h3>
                    </div>
                    {review.error && (
                      <p className="text-sm text-red-300">{review.error}</p>
                    )}
                    <button
                      onClick={(e) => { e.stopPropagation(); setActiveTab('logs'); }}
                      className="mt-2 text-xs text-blue-400 hover:text-blue-300"
                    >
                      View logs for details
                    </button>
                  </div>
                )}

                {/* Succeeded State */}
                {review.status === 'succeeded' && (
                  <div className="space-y-4">
                    {/* Summary */}
                    {review.overall_summary && (
                      <div className="p-3 bg-gray-800 rounded-lg">
                        <div className="flex items-start gap-3">
                          <CheckCircleIcon className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
                          <div>
                            <p className="text-gray-200 text-sm">{review.overall_summary}</p>
                            {review.overall_score !== null && (
                              <p className={cn(
                                'text-xs mt-1 font-medium',
                                review.overall_score >= 0.8
                                  ? 'text-green-400'
                                  : review.overall_score >= 0.6
                                    ? 'text-yellow-400'
                                    : 'text-red-400'
                              )}>
                                Score: {Math.round(review.overall_score * 100)}%
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Severity Summary - Always show counts */}
                    <div className="p-3 bg-gray-800/50 rounded-lg">
                      <h4 className="text-xs font-medium text-gray-400 mb-2">Issues by Severity</h4>
                      <div className="grid grid-cols-4 gap-2">
                        <button
                          onClick={(e) => { e.stopPropagation(); handleSelectBySeverity('critical'); }}
                          className="flex flex-col items-center p-2 rounded bg-gray-800 hover:bg-gray-700 transition-colors"
                        >
                          <span className="text-lg font-bold text-red-400">{severityCounts.critical}</span>
                          <span className="text-[10px] text-red-400/80">Critical</span>
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleSelectBySeverity('high'); }}
                          className="flex flex-col items-center p-2 rounded bg-gray-800 hover:bg-gray-700 transition-colors"
                        >
                          <span className="text-lg font-bold text-orange-400">{severityCounts.high}</span>
                          <span className="text-[10px] text-orange-400/80">High</span>
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleSelectBySeverity('medium'); }}
                          className="flex flex-col items-center p-2 rounded bg-gray-800 hover:bg-gray-700 transition-colors"
                        >
                          <span className="text-lg font-bold text-yellow-400">{severityCounts.medium}</span>
                          <span className="text-[10px] text-yellow-400/80">Medium</span>
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleSelectBySeverity('low'); }}
                          className="flex flex-col items-center p-2 rounded bg-gray-800 hover:bg-gray-700 transition-colors"
                        >
                          <span className="text-lg font-bold text-blue-400">{severityCounts.low}</span>
                          <span className="text-[10px] text-blue-400/80">Low</span>
                        </button>
                      </div>
                      <p className="text-[10px] text-gray-500 mt-2 text-center">
                        Total: {review.feedbacks.length} issue{review.feedbacks.length !== 1 ? 's' : ''}
                        {review.feedbacks.length > 0 && ' (click severity to select)'}
                      </p>
                    </div>

                    {/* Feedbacks grouped by severity */}
                    {review.feedbacks.length === 0 ? (
                      <div className="py-4 text-center border border-green-500/20 rounded-lg bg-green-900/10">
                        <CheckCircleIcon className="w-8 h-8 text-green-400 mx-auto" />
                        <p className="mt-2 text-green-400 font-medium text-sm">No issues found</p>
                        <p className="text-gray-400 text-xs mt-1">The code looks good!</p>
                      </div>
                    ) : (
                      <div className="space-y-3 max-h-80 overflow-y-auto">
                        {/* Selection controls */}
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-gray-400">Detailed Findings</span>
                          <button
                            onClick={(e) => { e.stopPropagation(); handleSelectAll(); }}
                            className="text-xs text-blue-400 hover:text-blue-300"
                          >
                            {selectedFeedbacks.size === review.feedbacks.length
                              ? 'Deselect All'
                              : 'Select All'}
                          </button>
                        </div>

                        {/* Critical issues */}
                        {severityCounts.critical > 0 && (
                          <div className="space-y-2">
                            <h5 className="text-xs font-medium text-red-400 flex items-center gap-1">
                              <span className="w-2 h-2 rounded-full bg-red-400" />
                              Critical ({severityCounts.critical})
                            </h5>
                            {review.feedbacks.filter(f => f.severity === 'critical').map((feedback) => (
                              <ReviewFeedbackCard
                                key={feedback.id}
                                feedback={feedback}
                                selected={selectedFeedbacks.has(feedback.id)}
                                onSelect={handleSelectFeedback}
                              />
                            ))}
                          </div>
                        )}

                        {/* High issues */}
                        {severityCounts.high > 0 && (
                          <div className="space-y-2">
                            <h5 className="text-xs font-medium text-orange-400 flex items-center gap-1">
                              <span className="w-2 h-2 rounded-full bg-orange-400" />
                              High ({severityCounts.high})
                            </h5>
                            {review.feedbacks.filter(f => f.severity === 'high').map((feedback) => (
                              <ReviewFeedbackCard
                                key={feedback.id}
                                feedback={feedback}
                                selected={selectedFeedbacks.has(feedback.id)}
                                onSelect={handleSelectFeedback}
                              />
                            ))}
                          </div>
                        )}

                        {/* Medium issues */}
                        {severityCounts.medium > 0 && (
                          <div className="space-y-2">
                            <h5 className="text-xs font-medium text-yellow-400 flex items-center gap-1">
                              <span className="w-2 h-2 rounded-full bg-yellow-400" />
                              Medium ({severityCounts.medium})
                            </h5>
                            {review.feedbacks.filter(f => f.severity === 'medium').map((feedback) => (
                              <ReviewFeedbackCard
                                key={feedback.id}
                                feedback={feedback}
                                selected={selectedFeedbacks.has(feedback.id)}
                                onSelect={handleSelectFeedback}
                              />
                            ))}
                          </div>
                        )}

                        {/* Low issues */}
                        {severityCounts.low > 0 && (
                          <div className="space-y-2">
                            <h5 className="text-xs font-medium text-blue-400 flex items-center gap-1">
                              <span className="w-2 h-2 rounded-full bg-blue-400" />
                              Low ({severityCounts.low})
                            </h5>
                            {review.feedbacks.filter(f => f.severity === 'low').map((feedback) => (
                              <ReviewFeedbackCard
                                key={feedback.id}
                                feedback={feedback}
                                selected={selectedFeedbacks.has(feedback.id)}
                                onSelect={handleSelectFeedback}
                              />
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Actions */}
                    {review.feedbacks.length > 0 && onApplyFix && (
                      <div className="flex items-center justify-between pt-2 border-t border-gray-700/50">
                        <span className="text-xs text-gray-400">
                          {selectedFeedbacks.size} of {review.feedbacks.length} selected
                        </span>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              const text = review.feedbacks
                                .filter((f) => selectedFeedbacks.has(f.id))
                                .map(
                                  (f) =>
                                    `[${f.severity.toUpperCase()}] ${f.title}\nFile: ${f.file_path}${f.line_start ? `:${f.line_start}` : ''}\n${f.description}`
                                )
                                .join('\n\n');
                              copy(text, 'Selected feedbacks');
                            }}
                            disabled={selectedFeedbacks.size === 0}
                          >
                            <ClipboardDocumentIcon className="w-4 h-4 mr-1" />
                            Copy
                          </Button>
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleGenerateFix();
                            }}
                            disabled={selectedFeedbacks.size === 0 || generatingFix}
                            isLoading={generatingFix}
                          >
                            <WrenchScrewdriverIcon className="w-4 h-4 mr-1" />
                            Generate Fix
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </>
            ) : (
              /* Logs Tab */
              <div className="space-y-2">
                {/* Streaming indicator */}
                {streamActive && (
                  <div className="flex items-center gap-2 text-xs text-green-400 pb-2 border-b border-gray-700/50">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                    <span>Streaming logs...</span>
                  </div>
                )}

                {/* Logs container */}
                <div
                  ref={logsContainerRef}
                  className="max-h-60 overflow-y-auto font-mono text-xs bg-gray-900/50 rounded p-2"
                >
                  {logs.length === 0 ? (
                    <div className="text-gray-500 text-center py-4">
                      {review.status === 'running' || review.status === 'queued'
                        ? 'Waiting for output...'
                        : 'No logs available.'}
                    </div>
                  ) : (
                    <div className="space-y-0.5">
                      {logs.map((line, i) => (
                        <div
                          key={i}
                          className="text-gray-400 leading-relaxed whitespace-pre-wrap hover:bg-gray-800/50 px-1 -mx-1"
                        >
                          <span className="text-gray-600 mr-2 select-none inline-block w-6 text-right">
                            {i + 1}
                          </span>
                          <span>{line}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Streaming indicator at bottom */}
                  {streamActive && logs.length > 0 && (
                    <div className="flex items-center gap-2 text-blue-400 mt-2 pt-2 border-t border-gray-800">
                      <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse" />
                      <span className="text-xs">Receiving output...</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
