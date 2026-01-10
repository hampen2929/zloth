'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import useSWR from 'swr';
import {
  XMarkIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon,
  ClipboardDocumentIcon,
  WrenchScrewdriverIcon,
  CommandLineIcon,
  DocumentTextIcon,
} from '@heroicons/react/24/outline';
import { reviewsApi } from '@/lib/api';
import type { Review, ReviewSeverity, OutputLine } from '@/types';
import { Button } from './ui/Button';
import { ReviewFeedbackCard } from './ReviewFeedbackCard';
import { cn } from '@/lib/utils';
import { useClipboard } from '@/hooks';

type ReviewTab = 'results' | 'logs';

interface ReviewPanelProps {
  reviewId: string;
  onClose: () => void;
  onApplyFix: (instruction: string) => void;
}

export function ReviewPanel({ reviewId, onClose, onApplyFix }: ReviewPanelProps) {
  const [selectedFeedbacks, setSelectedFeedbacks] = useState<Set<string>>(new Set());
  const [generatingFix, setGeneratingFix] = useState(false);
  const [activeTab, setActiveTab] = useState<ReviewTab>('results');
  const [logs, setLogs] = useState<string[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const [streamActive, setStreamActive] = useState(false);
  const logsContainerRef = useRef<HTMLDivElement>(null);
  const logsLengthRef = useRef(0);
  const { copy } = useClipboard();

  const { data: review, mutate } = useSWR<Review>(`review-${reviewId}`, () =>
    reviewsApi.get(reviewId)
  );

  // Poll for updates while review is running
  useEffect(() => {
    if (!review || review.status === 'succeeded' || review.status === 'failed') {
      return;
    }

    const interval = setInterval(() => {
      mutate();
    }, 2000);

    return () => clearInterval(interval);
  }, [review, mutate]);

  // Auto-switch to logs tab when review is running
  useEffect(() => {
    if (review?.status === 'running' || review?.status === 'queued') {
      setActiveTab('logs');
    } else if (review?.status === 'succeeded') {
      setActiveTab('results');
    }
  }, [review?.status]);

  // Keep logsLengthRef in sync with logs.length
  useEffect(() => {
    logsLengthRef.current = logs.length;
  }, [logs.length]);

  // Stream logs while running
  const reviewStatus = review?.status;
  useEffect(() => {
    if (!reviewStatus || (reviewStatus !== 'queued' && reviewStatus !== 'running')) {
      setStreamActive(false);
      return;
    }

    // Start streaming from the current line count
    // Using ref to avoid reconnection loops when logs change
    const fromLine = logsLengthRef.current;

    setStreamActive(true);
    const cleanup = reviewsApi.streamLogs(reviewId, {
      fromLine,
      onLine: (line: OutputLine) => {
        setLogs((prev) => {
          // Avoid duplicates
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
        mutate();
      },
      onError: () => {
        setStreamActive(false);
      },
    });

    return cleanup;
  }, [reviewId, reviewStatus, mutate]);

  // Auto-scroll logs
  useEffect(() => {
    if (autoScroll && logsContainerRef.current) {
      logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  // Handle scroll to detect user manual scroll
  const handleLogsScroll = useCallback(() => {
    if (!logsContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = logsContainerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
    setAutoScroll(isAtBottom);
  }, []);

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
    if (!review) return;
    if (selectedFeedbacks.size === review.feedbacks.length) {
      setSelectedFeedbacks(new Set());
    } else {
      setSelectedFeedbacks(new Set(review.feedbacks.map((f) => f.id)));
    }
  };

  const handleSelectBySeverity = (severity: ReviewSeverity) => {
    if (!review) return;
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
    if (!review || selectedFeedbacks.size === 0) return;

    setGeneratingFix(true);
    try {
      const response = await reviewsApi.generateFix(reviewId, {
        feedback_ids: Array.from(selectedFeedbacks),
      });
      onApplyFix(response.instruction);
    } catch (err) {
      console.error('Failed to generate fix:', err);
    } finally {
      setGeneratingFix(false);
    }
  };

  const isLoading = !review || review.status === 'queued' || review.status === 'running';

  // Count feedbacks by severity
  const severityCounts = review
    ? {
        critical: review.feedbacks.filter((f) => f.severity === 'critical').length,
        high: review.feedbacks.filter((f) => f.severity === 'high').length,
        medium: review.feedbacks.filter((f) => f.severity === 'medium').length,
        low: review.feedbacks.filter((f) => f.severity === 'low').length,
      }
    : { critical: 0, high: 0, medium: 0, low: 0 };

  // Get executor display name
  const getExecutorName = () => {
    if (!review) return '';
    switch (review.executor_type) {
      case 'claude_code':
        return 'Claude Code';
      case 'codex_cli':
        return 'Codex';
      case 'gemini_cli':
        return 'Gemini CLI';
      default:
        return review.executor_type;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-gray-900 rounded-lg border border-gray-700 w-full max-w-3xl max-h-[80vh] flex flex-col shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-white">Code Review</h2>
            {review && (
              <>
                <span className="text-sm text-gray-400">
                  ({getExecutorName()})
                </span>
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
              </>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-gray-700 transition-colors"
          >
            <XMarkIcon className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-700" role="tablist">
          <button
            onClick={() => setActiveTab('results')}
            role="tab"
            aria-selected={activeTab === 'results'}
            className={cn(
              'flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset',
              activeTab === 'results'
                ? 'text-blue-400 border-b-2 border-blue-500 -mb-[1px]'
                : 'text-gray-400 hover:text-gray-300'
            )}
          >
            <DocumentTextIcon className="w-4 h-4" />
            Review Results
            {review && review.feedbacks.length > 0 && (
              <span className="px-1.5 py-0.5 text-xs rounded bg-gray-700">
                {review.feedbacks.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('logs')}
            role="tab"
            aria-selected={activeTab === 'logs'}
            className={cn(
              'flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset',
              activeTab === 'logs'
                ? 'text-blue-400 border-b-2 border-blue-500 -mb-[1px]'
                : 'text-gray-400 hover:text-gray-300'
            )}
          >
            <CommandLineIcon className="w-4 h-4" />
            Logs
            {streamActive && (
              <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            )}
          </button>
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-hidden" role="tabpanel">
          {activeTab === 'results' ? (
            <div className="h-full overflow-y-auto p-4">
              {isLoading ? (
                <div className="flex flex-col items-center justify-center py-12">
                  <ArrowPathIcon className="w-8 h-8 text-blue-400 animate-spin" />
                  <p className="mt-3 text-gray-400">Running code review...</p>
                  <button
                    onClick={() => setActiveTab('logs')}
                    className="mt-2 text-sm text-blue-400 hover:text-blue-300"
                  >
                    View logs
                  </button>
                </div>
              ) : review?.status === 'failed' ? (
                <div className="flex flex-col items-center justify-center py-12">
                  <ExclamationTriangleIcon className="w-12 h-12 text-red-400" />
                  <p className="mt-3 text-red-400 font-medium">Review failed</p>
                  {review.error && (
                    <p className="mt-2 text-gray-400 text-sm">{review.error}</p>
                  )}
                  <button
                    onClick={() => setActiveTab('logs')}
                    className="mt-2 text-sm text-blue-400 hover:text-blue-300"
                  >
                    View logs for details
                  </button>
                </div>
              ) : review ? (
                <div className="space-y-4">
                  {/* Summary */}
                  {review.overall_summary && (
                    <div className="p-4 bg-gray-800 rounded-lg">
                      <div className="flex items-start gap-3">
                        <CheckCircleIcon className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
                        <div className="flex-1">
                          <p className="text-gray-200">{review.overall_summary}</p>
                          {review.overall_score !== null && (
                            <div className="mt-2 flex items-center gap-2">
                              <span className="text-sm text-gray-400">Score:</span>
                              <span
                                className={cn(
                                  'font-medium',
                                  review.overall_score >= 0.8
                                    ? 'text-green-400'
                                    : review.overall_score >= 0.6
                                      ? 'text-yellow-400'
                                      : 'text-red-400'
                                )}
                              >
                                {Math.round(review.overall_score * 100)}%
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Severity Summary */}
                  <div className="flex items-center gap-4 px-2">
                    <button
                      onClick={() => handleSelectBySeverity('critical')}
                      className="flex items-center gap-1.5 text-sm text-red-400 hover:text-red-300"
                    >
                      <span className="font-medium">{severityCounts.critical}</span>
                      <span>Critical</span>
                    </button>
                    <button
                      onClick={() => handleSelectBySeverity('high')}
                      className="flex items-center gap-1.5 text-sm text-orange-400 hover:text-orange-300"
                    >
                      <span className="font-medium">{severityCounts.high}</span>
                      <span>High</span>
                    </button>
                    <button
                      onClick={() => handleSelectBySeverity('medium')}
                      className="flex items-center gap-1.5 text-sm text-yellow-400 hover:text-yellow-300"
                    >
                      <span className="font-medium">{severityCounts.medium}</span>
                      <span>Medium</span>
                    </button>
                    <button
                      onClick={() => handleSelectBySeverity('low')}
                      className="flex items-center gap-1.5 text-sm text-blue-400 hover:text-blue-300"
                    >
                      <span className="font-medium">{severityCounts.low}</span>
                      <span>Low</span>
                    </button>
                    <span className="text-gray-500 mx-2">|</span>
                    <button
                      onClick={handleSelectAll}
                      className="text-sm text-gray-400 hover:text-white"
                    >
                      {selectedFeedbacks.size === review.feedbacks.length
                        ? 'Deselect All'
                        : 'Select All'}
                    </button>
                  </div>

                  {/* Feedbacks */}
                  {review.feedbacks.length === 0 ? (
                    <div className="py-8 text-center">
                      <CheckCircleIcon className="w-12 h-12 text-green-400 mx-auto" />
                      <p className="mt-3 text-green-400 font-medium">No issues found</p>
                      <p className="text-gray-400 text-sm mt-1">
                        The code looks good!
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {review.feedbacks.map((feedback) => (
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
              ) : null}
            </div>
          ) : (
            /* Logs Tab */
            <div className="h-full flex flex-col">
              {/* Streaming status indicator */}
              {streamActive && (
                <div className="flex items-center gap-2 px-4 py-2 bg-gray-800/50 border-b border-gray-700">
                  <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                  <span className="text-xs text-green-400">Streaming logs...</span>
                </div>
              )}

              {/* Logs container */}
              <div
                ref={logsContainerRef}
                onScroll={handleLogsScroll}
                className="flex-1 overflow-y-auto p-4 font-mono text-xs bg-gray-900"
              >
                {logs.length === 0 ? (
                  <div className="text-gray-500 text-center py-8">
                    {isLoading ? 'Waiting for output...' : 'No logs available.'}
                  </div>
                ) : (
                  <div className="space-y-1">
                    {logs.map((line, i) => (
                      <div
                        key={i}
                        className="text-gray-400 leading-relaxed whitespace-pre-wrap hover:bg-gray-800/50 -mx-2 px-2"
                      >
                        <span className="text-gray-600 mr-3 select-none inline-block w-8 text-right">
                          {i + 1}
                        </span>
                        <span>{line}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Streaming indicator at bottom */}
                {streamActive && logs.length > 0 && (
                  <div className="flex items-center gap-2 text-blue-400 mt-4 pt-2 border-t border-gray-800">
                    <span className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
                    <span className="text-xs">Receiving output...</span>
                  </div>
                )}
              </div>

              {/* Scroll to bottom button */}
              {!autoScroll && logs.length > 10 && (
                <button
                  onClick={() => {
                    if (logsContainerRef.current) {
                      logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
                      setAutoScroll(true);
                    }
                  }}
                  className="absolute bottom-20 right-8 bg-blue-600 hover:bg-blue-500 text-white text-xs px-3 py-1.5 rounded-full shadow-lg transition-colors flex items-center gap-1.5"
                >
                  <svg
                    className="w-3 h-3"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 14l-7 7m0 0l-7-7m7 7V3"
                    />
                  </svg>
                  Scroll to bottom
                </button>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        {review?.status === 'succeeded' && review.feedbacks.length > 0 && activeTab === 'results' && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-700">
            <span className="text-sm text-gray-400">
              {selectedFeedbacks.size} of {review.feedbacks.length} selected
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
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
                <ClipboardDocumentIcon className="w-4 h-4 mr-1.5" />
                Copy
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleGenerateFix}
                disabled={selectedFeedbacks.size === 0 || generatingFix}
                isLoading={generatingFix}
              >
                <WrenchScrewdriverIcon className="w-4 h-4 mr-1.5" />
                Generate Fix
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
