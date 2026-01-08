'use client';

import { useState, useEffect } from 'react';
import useSWR from 'swr';
import { prsApi, preferencesApi } from '@/lib/api';
import type { Run } from '@/types';
import { DiffViewer } from '@/components/DiffViewer';
import { StreamingLogs } from '@/components/StreamingLogs';
import { ProgressDisplay } from '@/components/ProgressDisplay';
import { Button } from './ui/Button';
import { Input, Textarea } from './ui/Input';
import { useToast } from './ui/Toast';
import { cn } from '@/lib/utils';
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
  LightBulbIcon,
  Cog6ToothIcon,
} from '@heroicons/react/24/outline';
import { getErrorDisplay, type ErrorAction } from '@/lib/error-handling';

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
  const [showPRForm, setShowPRForm] = useState(false);
  const [prTitle, setPRTitle] = useState('');
  const [prBody, setPRBody] = useState('');
  const [creating, setCreating] = useState(false);
  const [prResult, setPRResult] = useState<{ url: string } | null>(null);
  const [prResultMode, setPRResultMode] = useState<'created' | 'link' | null>(null);
  const [pendingSyncRunId, setPendingSyncRunId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  // Update tab when run changes or status changes
  useEffect(() => {
    setActiveTab(getDefaultTab(run.status));
  }, [run.id, run.status]);
  const { success, error } = useToast();

  const { data: preferences } = useSWR('preferences', preferencesApi.get);

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
          setPRResult({ url: synced.pr.url });
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

  const handleCreatePR = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prTitle.trim()) return;

    setCreating(true);
    setFormError(null);

    try {
      if (preferences?.default_pr_creation_mode === 'link') {
        const result = await prsApi.createLink(taskId, {
          selected_run_id: run.id,
          title: prTitle.trim(),
          body: prBody.trim() || undefined,
        });
        setPRResult({ url: result.url });
        setPRResultMode('link');
        setPendingSyncRunId(run.id);
        success('PR link generated. Create the PR on GitHub.');
      } else {
        const result = await prsApi.create(taskId, {
          selected_run_id: run.id,
          title: prTitle.trim(),
          body: prBody.trim() || undefined,
        });
        setPRResult(result);
        setPRResultMode('created');
        onPRCreated();
        success('Pull request created successfully!');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create PR';
      setFormError(message);
      error(message);
    } finally {
      setCreating(false);
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

  const isCLI =
    run.executor_type === 'claude_code' ||
    run.executor_type === 'codex_cli' ||
    run.executor_type === 'gemini_cli';
  const cliName =
    run.executor_type === 'claude_code'
      ? 'Claude Code'
      : run.executor_type === 'codex_cli'
        ? 'Codex'
        : run.executor_type === 'gemini_cli'
          ? 'Gemini CLI'
          : 'CLI';

  return (
    <div className="flex flex-col h-full bg-gray-900 rounded-lg border border-gray-800">
      {/* Header */}
      <div className="p-4 border-b border-gray-800">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="font-semibold text-gray-100 flex items-center gap-2">
              {isCLI ? (
                <>
                  <CommandLineIcon className="w-5 h-5 text-purple-400" />
                  <span>{cliName}</span>
                </>
              ) : (
                run.model_name
              )}
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
          {run.status === 'succeeded' && run.patch && !prResult && (
            <Button
              variant="success"
              size="sm"
              onClick={() => setShowPRForm(!showPRForm)}
            >
              {showPRForm ? 'Cancel' : 'Create PR'}
            </Button>
          )}
        </div>
      </div>

      {/* PR Form */}
      {showPRForm && (
        <div className="p-4 border-b border-gray-800 bg-gray-800/30 animate-in fade-in duration-200">
          {prResult ? (
            <div className="flex flex-col items-center text-center py-4">
              <CheckCircleIcon className="w-10 h-10 text-green-400 mb-3" />
              <p className="text-green-400 font-medium mb-2">
                {prResultMode === 'link' ? 'PR link generated!' : 'PR created successfully!'}
              </p>
              <a
                href={prResult.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-blue-400 hover:text-blue-300 transition-colors"
              >
                {prResultMode === 'link' ? 'Open PR creation page on GitHub' : 'View PR on GitHub'}
                <ArrowTopRightOnSquareIcon className="w-4 h-4" />
              </a>
            </div>
          ) : (
            <form onSubmit={handleCreatePR} className="space-y-3">
              <Input
                value={prTitle}
                onChange={(e) => setPRTitle(e.target.value)}
                placeholder="PR title"
                error={formError || undefined}
              />
              <Textarea
                value={prBody}
                onChange={(e) => setPRBody(e.target.value)}
                placeholder="PR description (optional)"
                rows={2}
              />
              <div className="flex gap-2">
                <Button
                  type="submit"
                  variant="success"
                  size="sm"
                  disabled={!prTitle.trim()}
                  isLoading={creating}
                >
                  {preferences?.default_pr_creation_mode === 'link' ? 'Open PR link' : 'Create PR'}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setShowPRForm(false)}
                >
                  Cancel
                </Button>
              </div>
            </form>
          )}
        </div>
      )}

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
                isRunning={false}
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
              <div className="space-y-6">
                <div>
                  <h3 className="font-medium text-gray-200 mb-2 flex items-center gap-2">
                    <DocumentTextIcon className="w-5 h-5 text-gray-400" />
                    <span>Summary</span>
                  </h3>
                  <p className="text-gray-300 text-sm leading-relaxed">{run.summary}</p>
                </div>

                {run.warnings && run.warnings.length > 0 && (
                  <div className="p-3 bg-yellow-900/20 border border-yellow-800/50 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <ExclamationTriangleIcon className="w-4 h-4 text-yellow-400" />
                      <h4 className="text-sm font-medium text-yellow-400">
                        Warnings ({run.warnings.length})
                      </h4>
                    </div>
                    <ul className="list-disc list-inside text-sm text-yellow-300 space-y-1">
                      {run.warnings.map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {run.files_changed && run.files_changed.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-3">
                      <DocumentDuplicateIcon className="w-4 h-4 text-gray-400" />
                      <h4 className="text-sm font-medium text-gray-300">
                        Files Changed ({run.files_changed.length})
                      </h4>
                    </div>
                    <ul className="space-y-2">
                      {run.files_changed.map((f, i) => (
                        <li
                          key={i}
                          className="flex items-center justify-between p-2 bg-gray-800/50 rounded text-sm"
                        >
                          <span className="font-mono text-gray-300 truncate mr-2">
                            {f.path}
                          </span>
                          <span className="flex-shrink-0 text-xs font-medium">
                            <span className="text-green-400">+{f.added_lines}</span>
                            <span className="text-gray-600 mx-1">/</span>
                            <span className="text-red-400">-{f.removed_lines}</span>
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
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
  const [retryCountdown, setRetryCountdown] = useState<number | null>(null);
  const errorDisplay = getErrorDisplay(error);

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
            <span className="font-medium">推奨アクション</span>
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
          ログを確認 ({logs.length} lines)
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

  const buttonLabel = countdown !== null ? `${countdown}秒後に再試行` : action.label;

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
