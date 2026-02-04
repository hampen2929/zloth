'use client';

import { useState, useEffect, useRef } from 'react';
import useSWR from 'swr';
import { prsApi, preferencesApi } from '@/lib/api';
import type { Run, PRUpdateMode } from '@/types';
import { DiffViewer } from '@/components/DiffViewer';
import { StreamingLogs } from '@/components/StreamingLogs';
import { ProgressDisplay } from '@/components/ProgressDisplay';
import { Button } from './ui/Button';
import { useToast } from './ui/Toast';
import { cn } from '@/lib/utils';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  DocumentTextIcon,
  CodeBracketIcon,
  CommandLineIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  ArrowPathIcon,
  ArrowTopRightOnSquareIcon,
  DocumentDuplicateIcon,
  ClipboardDocumentIcon,
  ClipboardDocumentCheckIcon,
  LightBulbIcon,
  Cog6ToothIcon,
  ChatBubbleLeftRightIcon,
  MagnifyingGlassIcon,
  DocumentMagnifyingGlassIcon,
  SparklesIcon,
  ChevronDownIcon,
} from '@heroicons/react/24/outline';

const UPDATE_PR_OPTIONS: { id: PRUpdateMode; label: string; description: string }[] = [
  { id: 'both', label: 'Both', description: 'Update title and description' },
  { id: 'description', label: 'Description', description: 'Update description only' },
  { id: 'title', label: 'Title', description: 'Update title only' },
];
import { deriveStructuredSummary, getSummaryTypeStyles } from '@/lib/summary-utils';
import type { SummaryType } from '@/types';
import { getErrorDisplay, type ErrorAction } from '@/lib/error-handling';
import { getExecutorDisplayName, isCLIExecutor } from '@/hooks';
import { useLanguage } from '@/lib/i18n';

interface RunDetailPanelProps {
  run: Run;
  taskId: string;
  onPRCreated: () => void;
  onRetry?: () => void;
  onSwitchModel?: () => void;
  onCancel?: () => void;
}

type Tab = 'summary' | 'diff' | 'logs';

const tabConfig: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'summary', label: 'Summary', icon: <DocumentTextIcon className="w-4 h-4" /> },
  { id: 'diff', label: 'Diff', icon: <CodeBracketIcon className="w-4 h-4" /> },
  { id: 'logs', label: 'Logs', icon: <CommandLineIcon className="w-4 h-4" /> },
];

// Determine the default tab based on run status
function getDefaultTab(status: Run['status']): Tab {
  // Show logs tab for running/queued runs to see real-time output
  if (status === 'running' || status === 'queued') {
    return 'logs';
  }
  // Show diff tab for completed runs
  return 'diff';
}

export function RunDetailPanel({
  run,
  taskId,
  onPRCreated,
  onRetry,
  onSwitchModel,
  onCancel,
}: RunDetailPanelProps) {
  const [activeTab, setActiveTab] = useState<Tab>(() => getDefaultTab(run.status));
  const [creating, setCreating] = useState(false);
  const [prResult, setPRResult] = useState<{ url: string; pr_id?: string } | null>(null);
  const [prResultMode, setPRResultMode] = useState<'created' | 'link' | null>(null);
  const [updatingDesc, setUpdatingDesc] = useState(false);
  const [isUpdateDropdownOpen, setIsUpdateDropdownOpen] = useState(false);
  const [pendingSyncRunId, setPendingSyncRunId] = useState<string | null>(null);
  const updateDropdownRef = useRef<HTMLDivElement>(null);

  // Update tab when run changes or status changes
  useEffect(() => {
    setActiveTab(getDefaultTab(run.status));
  }, [run.id, run.status]);
  const { success, error } = useToast();

  const { data: preferences } = useSWR('preferences', preferencesApi.get);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (updateDropdownRef.current && !updateDropdownRef.current.contains(event.target as Node)) {
        setIsUpdateDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // If a PR was created manually (link mode), poll sync until found, then switch to the PR URL.
  useEffect(() => {
    if (!pendingSyncRunId) return;
    if (prResultMode === 'created') return;

    let cancelled = false;
    const interval = setInterval(async () => {
      if (cancelled) return;
      try {
        const synced = await prsApi.sync(taskId, pendingSyncRunId);
        if (synced.found && synced.pr) {
          setPRResult({ url: synced.pr.url, pr_id: synced.pr.pr_id });
          setPRResultMode('created');
          setPendingSyncRunId(null);
          onPRCreated();
          success('PR detected. Opening PR.');
        }
      } catch {
        // Ignore transient errors while user is still creating the PR.
      }
    }, 2000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [pendingSyncRunId, prResultMode, taskId, onPRCreated, success]);

  // Derive PR title from run summary or use a default
  const derivePRTitle = (): string => {
    if (run.summary) {
      // Use first line of summary, truncated to 72 chars
      const firstLine = run.summary.split('\n')[0].trim();
      return firstLine.length > 72 ? firstLine.slice(0, 69) + '...' : firstLine;
    }
    return 'Update code changes';
  };

  const handleCreatePR = async () => {
    setCreating(true);

    try {
      const title = derivePRTitle();
      const autoGenerate = preferences?.auto_generate_pr_description ?? false;

      if (preferences?.default_pr_creation_mode === 'link') {
        // Link mode: open GitHub PR creation page
        let result;
        if (autoGenerate) {
          // Use auto API to generate title and description with AI
          result = await prsApi.createLinkAuto(taskId, {
            selected_run_id: run.id,
          });
        } else {
          // Use regular API with derived title
          result = await prsApi.createLink(taskId, {
            selected_run_id: run.id,
            title,
          });
        }
        setPRResult({ url: result.url });
        setPRResultMode('link');
        setPendingSyncRunId(run.id);
        // Open GitHub PR creation page immediately
        window.open(result.url, '_blank');
      } else {
        // Direct mode: create PR immediately
        let result;
        if (autoGenerate) {
          // Use auto API to generate title and description with AI
          result = await prsApi.createAuto(taskId, {
            selected_run_id: run.id,
          });
        } else {
          // Use regular API with derived title
          result = await prsApi.create(taskId, {
            selected_run_id: run.id,
            title,
          });
        }
        setPRResult({ url: result.url, pr_id: result.pr_id });
        setPRResultMode('created');
        onPRCreated();
        // Open created PR immediately
        window.open(result.url, '_blank');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create PR';
      error(message);
    } finally {
      setCreating(false);
    }
  };

  const handleUpdatePRDesc = async (mode: PRUpdateMode = 'both') => {
    if (!prResult?.pr_id) return;

    setUpdatingDesc(true);
    try {
      await prsApi.regenerateDescription(taskId, prResult.pr_id, mode);
      const modeLabel = mode === 'both' ? 'title and description' : mode;
      success(`PR ${modeLabel} updated successfully!`);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update PR';
      error(message);
    } finally {
      setUpdatingDesc(false);
    }
  };

  const getStatusBadge = () => {
    switch (run.status) {
      case 'succeeded':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium bg-green-500/20 text-green-400">
            <CheckCircleIcon className="w-3.5 h-3.5" />
            Completed
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium bg-red-500/20 text-red-400">
            <ExclamationTriangleIcon className="w-3.5 h-3.5" />
            Failed
          </span>
        );
      case 'running':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium bg-yellow-500/20 text-yellow-400">
            <ArrowPathIcon className="w-3.5 h-3.5 animate-spin" />
            Running
          </span>
        );
      case 'queued':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium bg-gray-500/20 text-gray-400">
            <ClockIcon className="w-3.5 h-3.5" />
            Queued
          </span>
        );
      default:
        return null;
    }
  };

  const isCLI = isCLIExecutor(run.executor_type);
  const modelLabel = isCLI ? getExecutorDisplayName(run.executor_type) : (run.model_name || 'Model');
  const headerLabel = `Implementation(${modelLabel})`;

  return (
    <div className="flex flex-col h-full bg-gray-900 rounded-lg border border-gray-800">
      {/* Header */}
      <div className="p-4 border-b border-gray-800">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="font-semibold text-gray-100 flex items-center gap-2">
              {isCLI && <CommandLineIcon className="w-5 h-5 text-purple-400" />}
              <span>{headerLabel}</span>
            </h2>
            <div className="flex items-center gap-2 mt-1">
              {isCLI ? (
                run.working_branch && (
                  <button
                    onClick={async () => {
                      try {
                        if (navigator.clipboard) {
                          await navigator.clipboard.writeText(run.working_branch!);
                        } else {
                          // Fallback for non-secure contexts
                          const textarea = document.createElement('textarea');
                          textarea.value = run.working_branch!;
                          document.body.appendChild(textarea);
                          textarea.select();
                          document.execCommand('copy');
                          document.body.removeChild(textarea);
                        }
                        success('Branch name copied!');
                      } catch {
                        error('Failed to copy to clipboard');
                      }
                    }}
                    className="flex items-center gap-1 text-xs font-mono text-purple-400 hover:text-purple-300 transition-colors"
                    title="Click to copy branch name"
                  >
                    <span>{run.working_branch}</span>
                    <ClipboardDocumentIcon className="w-3 h-3" />
                  </button>
                )
              ) : (
                <span className="text-xs text-gray-500">{run.provider}</span>
              )}
              {getStatusBadge()}
            </div>
          </div>
          {run.status === 'succeeded' && run.patch && (
            <div className="flex items-center gap-2">
              {!prResult && (
                <Button
                  variant="success"
                  size="sm"
                  onClick={handleCreatePR}
                  isLoading={creating}
                >
                  Create PR
                </Button>
              )}
              {prResult && prResultMode === 'link' && (
                <a
                  href={prResult.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg bg-green-700 text-green-100 hover:bg-green-600 transition-colors"
                >
                  Open PR on GitHub
                  <ArrowTopRightOnSquareIcon className="w-4 h-4" />
                </a>
              )}
              {prResult && prResultMode === 'created' && prResult.pr_id && (
                <>
                  <a
                    href={prResult.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg bg-gray-700 text-blue-400 hover:text-blue-300 hover:bg-gray-600 transition-colors"
                  >
                    View PR
                    <ArrowTopRightOnSquareIcon className="w-4 h-4" />
                  </a>
                  <div className="relative" ref={updateDropdownRef}>
                    <div className="flex">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                          setIsUpdateDropdownOpen(false);
                          handleUpdatePRDesc('both');
                        }}
                        disabled={updatingDesc}
                        isLoading={updatingDesc}
                        className="rounded-r-none border-r-0"
                      >
                        Update PR
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setIsUpdateDropdownOpen(!isUpdateDropdownOpen)}
                        disabled={updatingDesc}
                        className="px-2 rounded-l-none"
                      >
                        <ChevronDownIcon className={cn('w-4 h-4 transition-transform', isUpdateDropdownOpen && 'rotate-180')} />
                      </Button>
                    </div>

                    {/* Dropdown menu */}
                    {isUpdateDropdownOpen && (
                      <div className="absolute right-0 top-full mt-1 z-50 w-56 bg-gray-800 border border-gray-700 rounded-lg shadow-lg py-1">
                        <div className="px-3 py-2 border-b border-gray-700">
                          <p className="text-xs text-gray-400 font-medium">Update PR</p>
                        </div>
                        {UPDATE_PR_OPTIONS.map((option) => (
                          <button
                            key={option.id}
                            onClick={() => {
                              setIsUpdateDropdownOpen(false);
                              handleUpdatePRDesc(option.id);
                            }}
                            className="w-full flex flex-col items-start px-3 py-2 text-sm transition-colors text-gray-300 hover:bg-gray-700"
                          >
                            <span className="font-medium">{option.label}</span>
                            <span className="text-xs text-gray-500">{option.description}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>


      {/* Tabs */}
      <div className="flex border-b border-gray-800" role="tablist">
        {tabConfig.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            role="tab"
            aria-selected={activeTab === tab.id}
            className={cn(
              'flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset',
              activeTab === tab.id
                ? 'text-blue-400 border-b-2 border-blue-500 -mb-[1px]'
                : 'text-gray-400 hover:text-gray-300'
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto p-4" role="tabpanel">
        {/* Running status - show progress display or logs */}
        {run.status === 'running' && (
          <>
            {activeTab === 'logs' ? (
              <StreamingLogs
                runId={run.id}
                isRunning={true}
                initialLogs={run.logs}
              />
            ) : (
              <ProgressDisplay
                status="running"
                startedAt={run.started_at}
                logs={run.logs}
                onCancel={onCancel}
                onViewLogs={() => setActiveTab('logs')}
              />
            )}
          </>
        )}

        {/* Queued status - show progress display or logs */}
        {run.status === 'queued' && (
          <>
            {activeTab === 'logs' ? (
              <StreamingLogs
                runId={run.id}
                isRunning={true}
                initialLogs={run.logs}
              />
            ) : (
              <ProgressDisplay
                status="queued"
                startedAt={null}
                logs={run.logs}
                onViewLogs={() => setActiveTab('logs')}
              />
            )}
          </>
        )}

        {/* Failed status */}
        {run.status === 'failed' && (
          <FailedStatusDisplay
            error={run.error}
            logs={run.logs}
            activeTab={activeTab}
            onTabChange={setActiveTab}
            onRetry={onRetry}
            onSwitchModel={onSwitchModel}
          />
        )}

        {run.status === 'succeeded' && (
          <>
            {activeTab === 'summary' && (
              <StructuredSummaryDisplay run={run} />
            )}

            {activeTab === 'diff' && (
              <DiffViewer patch={run.patch || ''} />
            )}

            {activeTab === 'logs' && (
              <div className="font-mono text-xs space-y-1 bg-gray-800/50 rounded-lg p-3">
                {!run.logs || run.logs.length === 0 ? (
                  <p className="text-gray-500 text-center py-4">No logs available.</p>
                ) : (
                  run.logs.map((log, i) => (
                    <div key={i} className="text-gray-400 leading-relaxed">
                      <span className="text-gray-600 mr-2 select-none">{i + 1}</span>
                      {log}
                    </div>
                  ))
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// --- Sub-components ---

interface FailedStatusDisplayProps {
  error: string | null | undefined;
  logs: string[] | null | undefined;
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
  onRetry?: () => void;
  onSwitchModel?: () => void;
}

function FailedStatusDisplay({
  error,
  logs,
  activeTab,
  onTabChange,
  onRetry,
  onSwitchModel,
}: FailedStatusDisplayProps) {
  const { t } = useLanguage();
  const [retryCountdown, setRetryCountdown] = useState<number | null>(null);
  const errorDisplay = getErrorDisplay(error, t.errors);

  // Handle delayed retry countdown
  useEffect(() => {
    if (retryCountdown === null) return;
    if (retryCountdown <= 0) {
      setRetryCountdown(null);
      onRetry?.();
      return;
    }

    const timer = setTimeout(() => {
      setRetryCountdown(retryCountdown - 1);
    }, 1000);

    return () => clearTimeout(timer);
  }, [retryCountdown, onRetry]);

  const handleAction = (action: ErrorAction) => {
    switch (action.type) {
      case 'retry':
        onRetry?.();
        break;
      case 'retry_delayed':
        if (action.delayMs) {
          setRetryCountdown(Math.ceil(action.delayMs / 1000));
        }
        break;
      case 'switch_model':
        onSwitchModel?.();
        break;
      case 'view_logs':
        onTabChange('logs');
        break;
      case 'settings':
        if (action.href) {
          // Navigate to settings via hash - this is intentional external system interaction
          // eslint-disable-next-line react-hooks/immutability
          window.location.hash = action.href.replace('#', '');
        }
        break;
    }
  };

  const ErrorSummary = () => (
    <div className="p-4 bg-red-900/20 border border-red-800/50 rounded-lg">
      <div className="flex items-center gap-2 mb-2">
        <ExclamationTriangleIcon className="w-5 h-5 text-red-400" />
        <h3 className="font-medium text-red-400">{errorDisplay.title}</h3>
      </div>
      <p className="text-sm text-red-300 mb-4">{errorDisplay.message}</p>

      {/* Recommended actions */}
      {errorDisplay.actions.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-amber-400 text-sm">
            <LightBulbIcon className="w-4 h-4" />
            <span className="font-medium">{t.runDetail.recommendedActions}</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {errorDisplay.actions.map((action, idx) => (
              <ActionButton
                key={idx}
                action={action}
                onClick={() => handleAction(action)}
                disabled={retryCountdown !== null && action.type === 'retry_delayed'}
                countdown={action.type === 'retry_delayed' ? retryCountdown : null}
                hasHandler={
                  (action.type === 'retry' && !!onRetry) ||
                  (action.type === 'switch_model' && !!onSwitchModel) ||
                  action.type === 'view_logs' ||
                  action.type === 'settings'
                }
              />
            ))}
          </div>
        </div>
      )}

      {/* View logs link (if not in logs tab and has actions) */}
      {logs && logs.length > 0 && activeTab !== 'logs' && !errorDisplay.actions.some(a => a.type === 'view_logs') && (
        <button
          onClick={() => onTabChange('logs')}
          className="mt-3 text-blue-400 hover:text-blue-300 text-sm underline"
        >
          {t.runDetail.viewLogs} ({logs.length} lines)
        </button>
      )}
    </div>
  );

  if (activeTab === 'logs') {
    return (
      <div className="space-y-4">
        <ErrorSummary />
        <div className="font-mono text-xs space-y-1 bg-gray-800/50 rounded-lg p-3">
          {!logs || logs.length === 0 ? (
            <p className="text-gray-500 text-center py-4">No logs available.</p>
          ) : (
            logs.map((log, i) => (
              <div key={i} className="text-gray-400 leading-relaxed">
                <span className="text-gray-600 mr-2 select-none">{i + 1}</span>
                {log}
              </div>
            ))
          )}
        </div>
      </div>
    );
  }

  return <ErrorSummary />;
}

interface ActionButtonProps {
  action: ErrorAction;
  onClick: () => void;
  disabled?: boolean;
  countdown: number | null;
  hasHandler: boolean;
}

function ActionButton({ action, onClick, disabled, countdown, hasHandler }: ActionButtonProps) {
  const { t } = useLanguage();

  // Don't render if no handler available for retry/switch_model
  if (!hasHandler && (action.type === 'retry' || action.type === 'switch_model')) {
    return null;
  }

  const getIcon = () => {
    switch (action.type) {
      case 'retry':
      case 'retry_delayed':
        return <ArrowPathIcon className="w-4 h-4" />;
      case 'settings':
        return <Cog6ToothIcon className="w-4 h-4" />;
      default:
        return null;
    }
  };

  const buttonLabel = countdown !== null ? t.runDetail.retryInSeconds.replace('{seconds}', String(countdown)) : action.label;

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors',
        'border focus:outline-none focus:ring-2 focus:ring-blue-500',
        disabled
          ? 'bg-gray-700 border-gray-600 text-gray-400 cursor-not-allowed'
          : 'bg-gray-800 border-gray-700 text-gray-200 hover:bg-gray-700 hover:border-gray-600'
      )}
    >
      {getIcon()}
      {buttonLabel}
    </button>
  );
}

/**
 * Get icon for summary type
 */
function getSummaryTypeIcon(type: SummaryType) {
  switch (type) {
    case 'code_change':
      return <CodeBracketIcon className="w-5 h-5" />;
    case 'qa_response':
      return <ChatBubbleLeftRightIcon className="w-5 h-5" />;
    case 'analysis':
      return <MagnifyingGlassIcon className="w-5 h-5" />;
    case 'no_action':
      return <CheckCircleIcon className="w-5 h-5" />;
  }
}

/**
 * Structured Summary Display Component
 * Displays rich, structured information about the run results.
 */
function StructuredSummaryDisplay({ run }: { run: Run }) {
  const [copied, setCopied] = useState(false);
  const structuredSummary = deriveStructuredSummary(run);
  const typeStyles = getSummaryTypeStyles(structuredSummary.type);
  const typeIcon = getSummaryTypeIcon(structuredSummary.type);
  const { success, error } = useToast();

  const handleCopyMarkdown = async () => {
    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(structuredSummary.response);
      } else {
        // Fallback for non-secure contexts
        const textarea = document.createElement('textarea');
        textarea.value = structuredSummary.response;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      setCopied(true);
      success('Summary copied as Markdown!');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      error('Failed to copy to clipboard');
    }
  };

  return (
    <div className="space-y-6">
      {/* Summary Type Badge */}
      <div className={cn(
        'inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium',
        typeStyles.bgColor,
        typeStyles.color
      )}>
        {typeIcon}
        {typeStyles.label}
      </div>

      {/* Response (Agent's Answer) - Rendered as Markdown */}
      <div className={cn(
        'p-4 rounded-lg border',
        typeStyles.bgColor,
        typeStyles.borderColor
      )}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <SparklesIcon className={cn('w-5 h-5', typeStyles.color)} />
            <h4 className={cn('text-sm font-medium', typeStyles.color)}>Response</h4>
          </div>
          <button
            onClick={handleCopyMarkdown}
            className="flex items-center gap-1.5 px-2 py-1 text-xs font-medium text-gray-400 hover:text-gray-200 bg-gray-800/50 hover:bg-gray-700/50 rounded transition-colors"
            title="Copy as Markdown"
          >
            {copied ? (
              <>
                <ClipboardDocumentCheckIcon className="w-4 h-4 text-green-400" />
                <span className="text-green-400">Copied!</span>
              </>
            ) : (
              <>
                <ClipboardDocumentIcon className="w-4 h-4" />
                <span>Copy Markdown</span>
              </>
            )}
          </button>
        </div>
        <div className="prose prose-sm prose-invert max-w-none text-gray-300 prose-headings:text-gray-200 prose-p:text-gray-300 prose-strong:text-gray-200 prose-code:text-blue-300 prose-code:bg-gray-800 prose-code:px-1 prose-code:rounded prose-pre:bg-gray-800 prose-ul:text-gray-300 prose-ol:text-gray-300 prose-li:text-gray-300 prose-table:text-gray-300 prose-th:text-gray-200 prose-th:bg-gray-800 prose-td:border-gray-700 prose-th:border-gray-700 prose-thead:border-gray-700 prose-tr:border-gray-700">
          <Markdown remarkPlugins={[remarkGfm]}>{structuredSummary.response}</Markdown>
        </div>
      </div>

      {/* Key Points (if available) */}
      {structuredSummary.key_points.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <LightBulbIcon className="w-5 h-5 text-yellow-400" />
            <h4 className="text-sm font-medium text-gray-200">Key Points</h4>
          </div>
          <ul className="space-y-2">
            {structuredSummary.key_points.map((point, i) => (
              <li
                key={i}
                className="flex items-start gap-3 p-3 bg-gray-800/30 rounded-lg text-sm text-gray-300"
              >
                <span className="text-yellow-400 mt-0.5 font-bold">{i + 1}.</span>
                <span>{point}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Analyzed Files (for Q&A/Analysis types) */}
      {structuredSummary.analyzed_files.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <DocumentMagnifyingGlassIcon className="w-5 h-5 text-gray-400" />
            <h4 className="text-sm font-medium text-gray-200">
              Files Analyzed ({structuredSummary.analyzed_files.length})
            </h4>
          </div>
          <div className="flex flex-wrap gap-2">
            {structuredSummary.analyzed_files.map((file, i) => (
              <span
                key={i}
                className="px-3 py-1.5 bg-gray-800/50 rounded-lg text-sm font-mono text-gray-300"
              >
                {file}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Warnings */}
      {run.warnings && run.warnings.length > 0 && (
        <div className="p-4 bg-yellow-900/20 border border-yellow-800/50 rounded-lg">
          <div className="flex items-center gap-2 mb-3">
            <ExclamationTriangleIcon className="w-5 h-5 text-yellow-400" />
            <h4 className="text-sm font-medium text-yellow-400">
              Warnings ({run.warnings.length})
            </h4>
          </div>
          <ul className="list-disc list-inside text-sm text-yellow-300 space-y-1.5">
            {run.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Files Changed (for code changes) */}
      {run.files_changed && run.files_changed.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <DocumentDuplicateIcon className="w-5 h-5 text-gray-400" />
            <h4 className="text-sm font-medium text-gray-200">
              Files Changed ({run.files_changed.length})
            </h4>
          </div>
          <ul className="space-y-2">
            {run.files_changed.map((f, i) => (
              <li
                key={i}
                className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg text-sm"
              >
                <span className="font-mono text-gray-300 truncate mr-3">
                  {f.path}
                </span>
                <span className="flex-shrink-0 text-sm font-medium">
                  <span className="text-green-400">+{f.added_lines}</span>
                  <span className="text-gray-600 mx-2">/</span>
                  <span className="text-red-400">-{f.removed_lines}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
