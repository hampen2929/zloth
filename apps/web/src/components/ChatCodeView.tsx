'use client';

import { useState, useRef, useEffect } from 'react';
import useSWR from 'swr';
import { tasksApi, runsApi, prsApi, preferencesApi } from '@/lib/api';
import type { Message, ModelProfile, ExecutorType, Run, RunStatus } from '@/types';
import { Button } from './ui/Button';
import { useToast } from './ui/Toast';
import { getShortcutText, isModifierPressed } from '@/lib/platform';
import { cn } from '@/lib/utils';
import { useExecutorType, useClipboard, getExecutorDisplayName } from '@/hooks';
import { RunResultCard, type RunTab } from './RunResultCard';
import {
  UserIcon,
  CpuChipIcon,
  ChatBubbleLeftIcon,
  CheckIcon,
  CheckCircleIcon,
  ArrowTopRightOnSquareIcon,
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
  const [prLinkResult, setPRLinkResult] = useState<{ url: string } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { success, error } = useToast();
  const { copy } = useClipboard();

  const { data: preferences } = useSWR('preferences', preferencesApi.get);
  const { data: prs } = useSWR(`prs-${taskId}`, () => prsApi.list(taskId), {
    refreshInterval: prLinkResult ? 2000 : 0,
  });

  // Determine the locked executor and its properties
  const sortedRuns = [...runs].reverse();
  const lockedExecutor: ExecutorType = (sortedRuns[0]?.executor_type || executorType) as ExecutorType;
  const { isCLI: isCLIExecutor, displayName: cliDisplayName } = useExecutorType(lockedExecutor);

  // Get session-level branch name
  const sessionBranch = sortedRuns.find((r) => r.working_branch)?.working_branch || null;
  const latestSuccessfulRun = sortedRuns.find((r) => r.status === 'succeeded' && r.working_branch);
  const latestPR = prs && prs.length > 0 ? prs[0] : null;

  // Sync PR result from backend
  useEffect(() => {
    if (latestPR && !prResult) {
      setPRResult({ url: latestPR.url, number: latestPR.number });
      setPRLinkResult(null);
    }
  }, [latestPR, prResult]);

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

      if (prevStatus && (prevStatus === 'running' || prevStatus === 'queued')) {
        const displayName = getExecutorDisplayName(run.executor_type);
        const executorName = displayName || run.model_name || 'Run';

        if (currentStatus === 'failed') {
          const errorMsg = run.error
            ? `${executorName}: ${run.error.slice(0, 100)}${run.error.length > 100 ? '...' : ''}`
            : `${executorName} execution failed`;
          error(errorMsg, 'Run Failed');
        } else if (currentStatus === 'succeeded') {
          success(`${executorName} completed successfully`);
        }
      }

      prevStatuses.set(run.id, currentStatus);
    });
  }, [runs, error, success]);

  const handleCreatePR = async () => {
    if (!latestSuccessfulRun) return;

    setCreatingPR(true);
    try {
      if (preferences?.default_pr_creation_mode === 'link') {
        const result = await prsApi.createLinkAuto(taskId, {
          selected_run_id: latestSuccessfulRun.id,
        });
        setPRLinkResult({ url: result.url });
        success('PR link generated. Create the PR on GitHub.');
      } else {
        const result = await prsApi.createAuto(taskId, {
          selected_run_id: latestSuccessfulRun.id,
        });
        setPRResult({ url: result.url, number: result.number });
        onPRCreated();
        success('Pull request created successfully!');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create PR';
      error(message);
    } finally {
      setCreatingPR(false);
    }
  };

  // Poll for PR sync when using link mode
  useEffect(() => {
    if (!prLinkResult || !latestSuccessfulRun || prResult) return;

    let cancelled = false;
    const interval = setInterval(async () => {
      if (cancelled) return;
      try {
        const synced = await prsApi.sync(taskId, latestSuccessfulRun.id);
        if (synced.found && synced.pr) {
          setPRResult({ url: synced.pr.url, number: synced.pr.number });
          setPRLinkResult(null);
          onPRCreated();
          success('PR detected. Opening PR link.');
        }
      } catch {
        // Ignore transient errors
      }
    }, 2000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [prLinkResult, latestSuccessfulRun, prResult, taskId, onPRCreated, success]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    if (!isCLIExecutor && selectedModels.length === 0) return;

    setLoading(true);

    try {
      await tasksApi.addMessage(taskId, { role: 'user', content: input.trim() });

      if (isCLIExecutor) {
        await runsApi.create(taskId, {
          instruction: input.trim(),
          executor_type: lockedExecutor,
        });
        success(`Started ${cliDisplayName} run`);
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
      prev.includes(modelId) ? prev.filter((id) => id !== modelId) : [...prev, modelId]
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

  const getRunsForUserMessage = (msgIndex: number): Run[] => {
    const userMsgOrder = userMessageIndices.indexOf(msgIndex);
    if (userMsgOrder === -1) return [];

    const totalUserMessages = userMessageIndices.length;
    if (totalUserMessages === 0 || sortedRuns.length === 0) return [];

    const runsPerMessage = Math.ceil(sortedRuns.length / totalUserMessages);
    const startIdx = userMsgOrder * runsPerMessage;
    const endIdx = Math.min(startIdx + runsPerMessage, sortedRuns.length);

    return sortedRuns.slice(startIdx, endIdx);
  };

  return (
    <div className="flex flex-col h-full bg-gray-900 rounded-lg border border-gray-800">
      {/* Session Header */}
      {sessionBranch && (
        <SessionHeader
          sessionBranch={sessionBranch}
          prResult={prResult}
          prLinkResult={prLinkResult}
          latestSuccessfulRun={latestSuccessfulRun}
          creatingPR={creatingPR}
          onCopyBranch={() => copy(sessionBranch, 'Branch name')}
          onCreatePR={handleCreatePR}
        />
      )}

      {/* Conversation Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && runs.length === 0 ? (
          <EmptyState />
        ) : (
          <>
            {messages.map((msg, msgIndex) => (
              <div key={msg.id} className="space-y-3">
                <MessageBubble message={msg} />
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

      {/* Model Selection (patch_agent only) */}
      {!isCLIExecutor && (
        <ModelSelector
          models={models}
          selectedModels={selectedModels}
          onToggleModel={toggleModel}
          onSelectAll={selectAllModels}
        />
      )}

      {/* Input */}
      <ChatInput
        value={input}
        onChange={setInput}
        onSubmit={handleSubmit}
        loading={loading}
        disabled={!isCLIExecutor && selectedModels.length === 0}
        selectedModelCount={isCLIExecutor ? undefined : selectedModels.length}
      />
    </div>
  );
}

// --- Sub-components ---

interface SessionHeaderProps {
  sessionBranch: string;
  prResult: { url: string; number: number } | null;
  prLinkResult: { url: string } | null;
  latestSuccessfulRun: Run | undefined;
  creatingPR: boolean;
  onCopyBranch: () => void;
  onCreatePR: () => void;
}

function SessionHeader({
  sessionBranch,
  prResult,
  prLinkResult,
  latestSuccessfulRun,
  creatingPR,
  onCopyBranch,
  onCreatePR,
}: SessionHeaderProps) {
  return (
    <div className="flex items-center justify-end gap-3 px-4 py-2 border-b border-gray-800 bg-gray-900/50">
      <button
        onClick={onCopyBranch}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-gray-800 hover:bg-gray-700 transition-colors group"
        title="Click to copy branch name"
      >
        <CodeBracketSquareIcon className="w-4 h-4 text-purple-400" />
        <span className="font-mono text-sm text-gray-300 group-hover:text-white truncate max-w-[200px]">
          {sessionBranch}
        </span>
        <ClipboardDocumentIcon className="w-3.5 h-3.5 text-gray-500 group-hover:text-gray-300" />
      </button>

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
      ) : prLinkResult ? (
        <a
          href={prLinkResult.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors"
        >
          Open PR link
          <ArrowTopRightOnSquareIcon className="w-3.5 h-3.5" />
        </a>
      ) : latestSuccessfulRun ? (
        <Button
          variant="success"
          size="sm"
          onClick={onCreatePR}
          disabled={creatingPR}
          isLoading={creatingPR}
          className="flex items-center gap-1.5"
        >
          {creatingPR ? 'Creating PR...' : 'Create PR'}
        </Button>
      ) : null}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center py-8">
      <ChatBubbleLeftIcon className="w-12 h-12 text-gray-700 mb-3" />
      <p className="text-gray-500 text-sm">Start by entering your instructions below.</p>
      <p className="text-gray-600 text-xs mt-1">
        Your messages and code changes will appear here.
      </p>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  return (
    <div
      className={cn(
        'p-3 rounded-lg animate-in fade-in duration-200',
        message.role === 'user'
          ? 'bg-blue-900/30 border border-blue-800'
          : 'bg-gray-800'
      )}
    >
      <div className="flex items-center gap-2 text-xs text-gray-500 mb-2">
        {message.role === 'user' ? (
          <UserIcon className="w-4 h-4" />
        ) : (
          <CpuChipIcon className="w-4 h-4" />
        )}
        <span className="capitalize font-medium">{message.role}</span>
      </div>
      <div className="text-sm whitespace-pre-wrap text-gray-200">{message.content}</div>
    </div>
  );
}

interface ModelSelectorProps {
  models: ModelProfile[];
  selectedModels: string[];
  onToggleModel: (modelId: string) => void;
  onSelectAll: () => void;
}

function ModelSelector({ models, selectedModels, onToggleModel, onSelectAll }: ModelSelectorProps) {
  return (
    <div className="border-t border-gray-800 p-3 space-y-3">
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-gray-500">Select models to run:</span>
          {models.length > 1 && (
            <button
              type="button"
              onClick={onSelectAll}
              className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
            >
              {selectedModels.length === models.length ? 'Deselect all' : 'Select all'}
            </button>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {models.length === 0 ? (
            <p className="text-gray-600 text-xs">No models configured. Add models in Settings.</p>
          ) : (
            models.map((model) => {
              const isSelected = selectedModels.includes(model.id);
              return (
                <button
                  key={model.id}
                  type="button"
                  onClick={() => onToggleModel(model.id)}
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
  );
}

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  loading: boolean;
  disabled: boolean;
  selectedModelCount?: number;
}

function ChatInput({
  value,
  onChange,
  onSubmit,
  loading,
  disabled,
  selectedModelCount,
}: ChatInputProps) {
  return (
    <form onSubmit={onSubmit} className="border-t border-gray-800 p-3">
      <div className="flex gap-2">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
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
              onSubmit(e);
            }
          }}
          aria-label="Instructions input"
        />
        <Button
          type="submit"
          disabled={loading || !value.trim() || disabled}
          isLoading={loading}
          className="self-end"
        >
          Run
        </Button>
      </div>
      <div className="flex items-center justify-between mt-2">
        <span className="text-xs text-gray-500">{getShortcutText('Enter')} to submit</span>
        {selectedModelCount !== undefined && selectedModelCount > 0 && (
          <span className="text-xs text-gray-500">
            {selectedModelCount} model{selectedModelCount > 1 ? 's' : ''} selected
          </span>
        )}
      </div>
    </form>
  );
}
