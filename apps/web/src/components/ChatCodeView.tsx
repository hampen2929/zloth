'use client';

import { useState, useRef, useEffect } from 'react';
import { tasksApi, runsApi, prsApi } from '@/lib/api';
import type { Message, ModelProfile, ExecutorType, Run, RunStatus } from '@/types';
import { Button } from './ui/Button';
import { DiffViewer } from './DiffViewer';
import { useToast } from './ui/Toast';
import { getShortcutText, isModifierPressed } from '@/lib/platform';
import { cn } from '@/lib/utils';
import {
  UserIcon,
  CpuChipIcon,
  ChatBubbleLeftIcon,
  CheckIcon,
  CommandLineIcon,
  DocumentTextIcon,
  CodeBracketIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  ArrowPathIcon,
  ArrowTopRightOnSquareIcon,
  DocumentDuplicateIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ClipboardDocumentIcon,
  CodeBracketSquareIcon,
} from '@heroicons/react/24/outline';

interface ChatCodeViewProps {
  taskId: string;
  messages: Message[];
  runs: Run[];
  models: ModelProfile[];
  executorType?: ExecutorType;
  initialModelIds?: string[];
  onRunsCreated: () => void;
  onPRCreated: () => void;
}

type RunTab = 'summary' | 'diff' | 'logs';

const runTabConfig: { id: RunTab; label: string; icon: React.ReactNode }[] = [
  { id: 'summary', label: 'Summary', icon: <DocumentTextIcon className="w-4 h-4" /> },
  { id: 'diff', label: 'Diff', icon: <CodeBracketIcon className="w-4 h-4" /> },
  { id: 'logs', label: 'Logs', icon: <CommandLineIcon className="w-4 h-4" /> },
];

export function ChatCodeView({
  taskId,
  messages,
  runs,
  models,
  executorType = 'patch_agent',
  initialModelIds,
  onRunsCreated,
  onPRCreated,
}: ChatCodeViewProps) {
  const [input, setInput] = useState('');
  const [selectedModels, setSelectedModels] = useState<string[]>(initialModelIds || []);
  const [loading, setLoading] = useState(false);
  const [expandedRuns, setExpandedRuns] = useState<Set<string>>(new Set());
  const [runTabs, setRunTabs] = useState<Record<string, RunTab>>({});
  const [creatingPR, setCreatingPR] = useState(false);
  const [prResult, setPRResult] = useState<{ url: string; number: number } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { success, error } = useToast();

  // Determine the locked executor:
  // - If we already have runs, lock to the earliest run's executor_type.
  // - Otherwise, use the executorType provided via URL param (initial choice).
  const sortedRuns = [...runs].reverse(); // API returns newest-first
  const lockedExecutor: ExecutorType = (sortedRuns[0]?.executor_type || executorType) as ExecutorType;
  const isCLIExecutor =
    lockedExecutor === 'claude_code' || lockedExecutor === 'codex_cli' || lockedExecutor === 'gemini_cli';

  // Get session-level branch name (from the first run with a working_branch)
  const sessionBranch = sortedRuns.find((r) => r.working_branch)?.working_branch || null;

  // Get the latest successful run for PR creation
  const latestSuccessfulRun = sortedRuns.find((r) => r.status === 'succeeded' && r.working_branch);

  // Copy branch name to clipboard
  const copyBranchToClipboard = async () => {
    if (!sessionBranch) return;
    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(sessionBranch);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = sessionBranch;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      success('Branch name copied!');
    } catch {
      error('Failed to copy to clipboard');
    }
  };

  // Create PR with AI-generated title and description
  const handleCreatePR = async () => {
    if (!latestSuccessfulRun) return;

    setCreatingPR(true);
    try {
      const result = await prsApi.createAuto(taskId, {
        selected_run_id: latestSuccessfulRun.id,
      });
      setPRResult({ url: result.url, number: result.number });
      onPRCreated();
      success('Pull request created successfully!');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create PR';
      error(message);
    } finally {
      setCreatingPR(false);
    }
  };

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, runs]);

  // Select all models by default if none specified (patch_agent only)
  useEffect(() => {
    if (!isCLIExecutor && models.length > 0 && selectedModels.length === 0 && !initialModelIds) {
      setSelectedModels(models.map((m) => m.id));
    }
  }, [models, selectedModels.length, initialModelIds, isCLIExecutor]);

  // Auto-expand new runs
  useEffect(() => {
    if (runs.length > 0) {
      setExpandedRuns((prev) => {
        const newExpanded = new Set(prev);
        let hasNew = false;
        runs.forEach((run) => {
          if (!prev.has(run.id)) {
            newExpanded.add(run.id);
            hasNew = true;
          }
        });
        return hasNew ? newExpanded : prev;
      });
    }
  }, [runs]);

  // Track run status changes and show toast notifications
  const prevRunStatuses = useRef<Map<string, RunStatus>>(new Map());
  useEffect(() => {
    const prevStatuses = prevRunStatuses.current;

    runs.forEach((run) => {
      const prevStatus = prevStatuses.get(run.id);
      const currentStatus = run.status;

      // Only notify if status changed from running/queued
      if (prevStatus && (prevStatus === 'running' || prevStatus === 'queued')) {
        const executorName =
          run.executor_type === 'claude_code'
            ? 'Claude Code'
            : run.executor_type === 'codex_cli'
              ? 'Codex'
              : run.executor_type === 'gemini_cli'
                ? 'Gemini CLI'
                : run.model_name || 'Run';

        if (currentStatus === 'failed') {
          const errorMsg = run.error
            ? `${executorName}: ${run.error.slice(0, 100)}${run.error.length > 100 ? '...' : ''}`
            : `${executorName} execution failed`;
          error(errorMsg, 'Run Failed');
        } else if (currentStatus === 'succeeded') {
          success(`${executorName} completed successfully`);
        }
      }

      // Update tracked status
      prevStatuses.set(run.id, currentStatus);
    });
  }, [runs, error, success]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    if (!isCLIExecutor && selectedModels.length === 0) return;

    setLoading(true);

    try {
      // Add user message
      await tasksApi.addMessage(taskId, {
        role: 'user',
        content: input.trim(),
      });

      // Create runs based on executor type
      if (isCLIExecutor) {
        await runsApi.create(taskId, {
          instruction: input.trim(),
          executor_type: lockedExecutor,
        });
        const cliExecutorNames: Record<string, string> = {
          claude_code: 'Claude Code',
          codex_cli: 'Codex',
          gemini_cli: 'Gemini CLI',
        };
        success(`Started ${cliExecutorNames[lockedExecutor] ?? 'CLI'} run`);
      } else {
        await runsApi.create(taskId, {
          instruction: input.trim(),
          model_ids: selectedModels,
          executor_type: 'patch_agent',
        });
        success(`Started ${selectedModels.length} run${selectedModels.length > 1 ? 's' : ''}`);
      }

      setInput('');
      onRunsCreated();
    } catch (err) {
      console.error('Failed to create runs:', err);
      error('Failed to create runs. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const toggleModel = (modelId: string) => {
    setSelectedModels((prev) =>
      prev.includes(modelId)
        ? prev.filter((id) => id !== modelId)
        : [...prev, modelId]
    );
  };

  const selectAllModels = () => {
    if (selectedModels.length === models.length) {
      setSelectedModels([]);
    } else {
      setSelectedModels(models.map((m) => m.id));
    }
  };

  const toggleRunExpanded = (runId: string) => {
    setExpandedRuns((prev) => {
      const next = new Set(prev);
      if (next.has(runId)) {
        next.delete(runId);
      } else {
        next.add(runId);
      }
      return next;
    });
  };

  const getRunTab = (runId: string): RunTab => runTabs[runId] || 'summary';
  const setRunTab = (runId: string, tab: RunTab) => {
    setRunTabs((prev) => ({ ...prev, [runId]: tab }));
  };

  // Calculate runs per user message for distribution
  const userMessageIndices = messages
    .map((msg, idx) => (msg.role === 'user' ? idx : -1))
    .filter((idx) => idx !== -1);

  // Get runs for a specific user message (by user message order, 0-indexed)
  const getRunsForUserMessage = (msgIndex: number): Run[] => {
    // Find which user message this is (0-indexed among user messages)
    const userMsgOrder = userMessageIndices.indexOf(msgIndex);
    if (userMsgOrder === -1) return [];

    const totalUserMessages = userMessageIndices.length;
    if (totalUserMessages === 0 || sortedRuns.length === 0) return [];

    // Distribute runs evenly across user messages
    const runsPerMessage = Math.ceil(sortedRuns.length / totalUserMessages);
    const startIdx = userMsgOrder * runsPerMessage;
    const endIdx = Math.min(startIdx + runsPerMessage, sortedRuns.length);

    return sortedRuns.slice(startIdx, endIdx);
  };

  return (
    <div className="flex flex-col h-full bg-gray-900 rounded-lg border border-gray-800">
      {/* Session Header - Branch name and PR button */}
      {sessionBranch && (
        <div className="flex items-center justify-end gap-3 px-4 py-2 border-b border-gray-800 bg-gray-900/50">
          {/* Branch name with copy */}
          <button
            onClick={copyBranchToClipboard}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-gray-800 hover:bg-gray-700 transition-colors group"
            title="Click to copy branch name"
          >
            <CodeBracketSquareIcon className="w-4 h-4 text-purple-400" />
            <span className="font-mono text-sm text-gray-300 group-hover:text-white truncate max-w-[200px]">
              {sessionBranch}
            </span>
            <ClipboardDocumentIcon className="w-3.5 h-3.5 text-gray-500 group-hover:text-gray-300" />
          </button>

          {/* PR button or link */}
          {prResult ? (
            <a
              href={prResult.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-green-600 hover:bg-green-500 text-white text-sm font-medium transition-colors"
            >
              <CheckCircleIcon className="w-4 h-4" />
              PR #{prResult.number}
              <ArrowTopRightOnSquareIcon className="w-3.5 h-3.5" />
            </a>
          ) : latestSuccessfulRun ? (
            <Button
              variant="success"
              size="sm"
              onClick={handleCreatePR}
              disabled={creatingPR}
              isLoading={creatingPR}
              className="flex items-center gap-1.5"
            >
              {creatingPR ? 'Creating PR...' : 'Create PR'}
            </Button>
          ) : null}
        </div>
      )}

      {/* Conversation Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && runs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
            <ChatBubbleLeftIcon className="w-12 h-12 text-gray-700 mb-3" />
            <p className="text-gray-500 text-sm">
              Start by entering your instructions below.
            </p>
            <p className="text-gray-600 text-xs mt-1">
              Your messages and code changes will appear here.
            </p>
          </div>
        ) : (
          <>
            {messages.map((msg, msgIndex) => (
              <div key={msg.id} className="space-y-3">
                {/* Message */}
                <div
                  className={cn(
                    'p-3 rounded-lg animate-in fade-in duration-200',
                    msg.role === 'user'
                      ? 'bg-blue-900/30 border border-blue-800'
                      : 'bg-gray-800'
                  )}
                >
                  <div className="flex items-center gap-2 text-xs text-gray-500 mb-2">
                    {msg.role === 'user' ? (
                      <UserIcon className="w-4 h-4" />
                    ) : (
                      <CpuChipIcon className="w-4 h-4" />
                    )}
                    <span className="capitalize font-medium">{msg.role}</span>
                  </div>
                  <div className="text-sm whitespace-pre-wrap text-gray-200">
                    {msg.content}
                  </div>
                </div>

                {/* Runs after this user message */}
                {getRunsForUserMessage(msgIndex).map((run) => (
                  <RunResultCard
                    key={run.id}
                    run={run}
                    expanded={expandedRuns.has(run.id)}
                    onToggleExpand={() => toggleRunExpanded(run.id)}
                    activeTab={getRunTab(run.id)}
                    onTabChange={(tab) => setRunTab(run.id, tab)}
                  />
                ))}
              </div>
            ))}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Model Selection (patch_agent only; executor is locked and not shown) */}
      {!isCLIExecutor && (
        <div className="border-t border-gray-800 p-3 space-y-3">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-gray-500">Select models to run:</span>
              {models.length > 1 && (
                <button
                  type="button"
                  onClick={selectAllModels}
                  className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                >
                  {selectedModels.length === models.length ? 'Deselect all' : 'Select all'}
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {models.length === 0 ? (
                <p className="text-gray-600 text-xs">
                  No models configured. Add models in Settings.
                </p>
              ) : (
                models.map((model) => {
                  const isSelected = selectedModels.includes(model.id);
                  return (
                    <button
                      key={model.id}
                      type="button"
                      onClick={() => toggleModel(model.id)}
                      className={cn(
                        'flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium transition-all',
                        'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 focus:ring-offset-gray-900',
                        isSelected
                          ? 'bg-blue-600 text-white shadow-sm'
                          : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-300'
                      )}
                      aria-pressed={isSelected}
                    >
                      {isSelected && <CheckIcon className="w-3 h-3" />}
                      {model.display_name || model.model_name}
                    </button>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSubmit} className="border-t border-gray-800 p-3">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Enter your instructions..."
            rows={3}
            className={cn(
              'flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded resize-none',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
              'text-sm text-gray-100 placeholder:text-gray-500',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              'transition-colors'
            )}
            disabled={loading}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && isModifierPressed(e)) {
                handleSubmit(e);
              }
            }}
            aria-label="Instructions input"
          />
          <Button
            type="submit"
            disabled={loading || !input.trim() || (!isCLIExecutor && selectedModels.length === 0)}
            isLoading={loading}
            className="self-end"
          >
            Run
          </Button>
        </div>
        <div className="flex items-center justify-between mt-2">
          <span className="text-xs text-gray-500">
            {getShortcutText('Enter')} to submit
          </span>
          {!isCLIExecutor && selectedModels.length > 0 && (
            <span className="text-xs text-gray-500">
              {selectedModels.length} model{selectedModels.length > 1 ? 's' : ''} selected
            </span>
          )}
        </div>
      </form>
    </div>
  );
}

// Inline Run Result Card Component
interface RunResultCardProps {
  run: Run;
  expanded: boolean;
  onToggleExpand: () => void;
  activeTab: RunTab;
  onTabChange: (tab: RunTab) => void;
}

function RunResultCard({
  run,
  expanded,
  onToggleExpand,
  activeTab,
  onTabChange,
}: RunResultCardProps) {
  const getStatusBadge = () => {
    switch (run.status) {
      case 'succeeded':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-500/20 text-green-400">
            <CheckCircleIcon className="w-3 h-3" />
            Completed
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-500/20 text-red-400">
            <ExclamationTriangleIcon className="w-3 h-3" />
            Failed
          </span>
        );
      case 'running':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-500/20 text-yellow-400">
            <ArrowPathIcon className="w-3 h-3 animate-spin" />
            Running
          </span>
        );
      case 'queued':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-500/20 text-gray-400">
            <ClockIcon className="w-3 h-3" />
            Queued
          </span>
        );
      default:
        return null;
    }
  };

  const getBorderColor = () => {
    if (run.executor_type === 'claude_code' || run.executor_type === 'codex_cli' || run.executor_type === 'gemini_cli') {
      return 'border-purple-800/50';
    }
    switch (run.status) {
      case 'succeeded':
        return 'border-green-800/50';
      case 'failed':
        return 'border-red-800/50';
      case 'running':
        return 'border-yellow-800/50';
      default:
        return 'border-gray-700';
    }
  };

  return (
    <div
      className={cn(
        'rounded-lg border animate-in fade-in slide-in-from-top-2 duration-300',
        getBorderColor(),
        (run.executor_type === 'claude_code' || run.executor_type === 'codex_cli' || run.executor_type === 'gemini_cli')
          ? 'bg-purple-900/10'
          : 'bg-gray-800/50'
      )}
    >
      {/* Header - Always visible */}
      <button
        onClick={onToggleExpand}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-800/30 transition-colors rounded-t-lg"
      >
        <div className="flex items-center gap-3">
          {run.executor_type === 'claude_code' || run.executor_type === 'codex_cli' || run.executor_type === 'gemini_cli' ? (
            <CommandLineIcon className="w-5 h-5 text-purple-400" />
          ) : (
            <CpuChipIcon className="w-5 h-5 text-blue-400" />
          )}
          <div className="text-left">
            <div className="font-medium text-gray-200 text-sm">
              {run.executor_type === 'claude_code'
                ? 'Claude Code'
                : run.executor_type === 'codex_cli'
                  ? 'Codex'
                  : run.executor_type === 'gemini_cli'
                    ? 'Gemini CLI'
                    : run.model_name}
            </div>
            {(run.executor_type === 'claude_code' || run.executor_type === 'codex_cli' || run.executor_type === 'gemini_cli') && run.working_branch && (
              <div className="text-xs font-mono text-purple-400">{run.working_branch}</div>
            )}
            {(run.executor_type !== 'claude_code' && run.executor_type !== 'codex_cli' && run.executor_type !== 'gemini_cli') && run.provider && (
              <div className="text-xs text-gray-500">{run.provider}</div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {getStatusBadge()}
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
          {/* Running State */}
          {run.status === 'running' && (
            <div className="flex flex-col items-center justify-center py-8">
              <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mb-3" />
              <p className="text-gray-400 font-medium text-sm">Running...</p>
              <p className="text-gray-500 text-xs mt-1">This may take a few moments</p>
            </div>
          )}

          {/* Queued State */}
          {run.status === 'queued' && (
            <div className="flex flex-col items-center justify-center py-8">
              <ClockIcon className="w-8 h-8 text-gray-500 mb-3" />
              <p className="text-gray-400 font-medium text-sm">Waiting in queue...</p>
              <p className="text-gray-500 text-xs mt-1">Your run will start soon</p>
            </div>
          )}

          {/* Failed State */}
          {run.status === 'failed' && (
            <div className="p-4">
              <div className="p-3 bg-red-900/20 border border-red-800/50 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <ExclamationTriangleIcon className="w-4 h-4 text-red-400" />
                  <h3 className="font-medium text-red-400 text-sm">Execution Failed</h3>
                </div>
                <p className="text-sm text-red-300">{run.error}</p>
              </div>
            </div>
          )}

          {/* Succeeded State */}
          {run.status === 'succeeded' && (
            <>
              {/* Tabs */}
              <div className="flex border-b border-gray-700/50 mt-3 px-4" role="tablist">
                {runTabConfig.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => onTabChange(tab.id)}
                    role="tab"
                    aria-selected={activeTab === tab.id}
                    className={cn(
                      'flex items-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors',
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
              <div className="p-4 max-h-96 overflow-y-auto" role="tabpanel">
                {activeTab === 'summary' && (
                  <div className="space-y-4">
                    <div>
                      <h3 className="font-medium text-gray-200 text-sm mb-2 flex items-center gap-2">
                        <span>📋</span>
                        <span>Summary</span>
                      </h3>
                      <p className="text-gray-300 text-sm leading-relaxed">{run.summary}</p>
                    </div>

                    {run.warnings && run.warnings.length > 0 && (
                      <div className="p-3 bg-yellow-900/20 border border-yellow-800/50 rounded-lg">
                        <div className="flex items-center gap-2 mb-2">
                          <ExclamationTriangleIcon className="w-4 h-4 text-yellow-400" />
                          <h4 className="text-xs font-medium text-yellow-400">
                            Warnings ({run.warnings.length})
                          </h4>
                        </div>
                        <ul className="list-disc list-inside text-xs text-yellow-300 space-y-1">
                          {run.warnings.map((w, i) => (
                            <li key={i}>{w}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {run.files_changed && run.files_changed.length > 0 && (
                      <div>
                        <div className="flex items-center gap-2 mb-2">
                          <DocumentDuplicateIcon className="w-4 h-4 text-gray-400" />
                          <h4 className="text-xs font-medium text-gray-300">
                            Files Changed ({run.files_changed.length})
                          </h4>
                        </div>
                        <ul className="space-y-1.5">
                          {run.files_changed.map((f, i) => (
                            <li
                              key={i}
                              className="flex items-center justify-between p-2 bg-gray-800/50 rounded text-xs"
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
                  <div className="font-mono text-xs space-y-0.5 bg-gray-800/50 rounded-lg p-3">
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
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
