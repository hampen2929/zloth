'use client';

import { useState, useRef, useEffect } from 'react';
import { tasksApi, runsApi, prsApi } from '@/lib/api';
import type { Message, ModelProfile, ExecutorType, Run } from '@/types';
import { Button } from './ui/Button';
import { Input, Textarea } from './ui/Input';
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
  const [currentExecutor, setCurrentExecutor] = useState<ExecutorType>(executorType);
  const [loading, setLoading] = useState(false);
  const [expandedRuns, setExpandedRuns] = useState<Set<string>>(new Set());
  const [runTabs, setRunTabs] = useState<Record<string, RunTab>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { success, error } = useToast();

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, runs]);

  // Select all models by default if none specified
  useEffect(() => {
    if (models.length > 0 && selectedModels.length === 0 && !initialModelIds) {
      setSelectedModels(models.map((m) => m.id));
    }
  }, [models, selectedModels.length, initialModelIds]);

  // Update executor type from props
  useEffect(() => {
    setCurrentExecutor(executorType);
  }, [executorType]);

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    if (currentExecutor === 'patch_agent' && selectedModels.length === 0) return;

    setLoading(true);

    try {
      // Add user message
      await tasksApi.addMessage(taskId, {
        role: 'user',
        content: input.trim(),
      });

      // Create runs based on executor type
      if (currentExecutor === 'claude_code') {
        await runsApi.create(taskId, {
          instruction: input.trim(),
          executor_type: 'claude_code',
        });
        success('Started Claude Code run');
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

  const getRunTab = (runId: string): RunTab => runTabs[runId] || 'diff';
  const setRunTab = (runId: string, tab: RunTab) => {
    setRunTabs((prev) => ({ ...prev, [runId]: tab }));
  };

  // Calculate runs per user message for distribution
  const userMessageIndices = messages
    .map((msg, idx) => (msg.role === 'user' ? idx : -1))
    .filter((idx) => idx !== -1);

  // Reverse runs to match chronological order of messages
  // (API returns runs newest-first, but messages are oldest-first)
  const sortedRuns = [...runs].reverse();

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
                    taskId={taskId}
                    expanded={expandedRuns.has(run.id)}
                    onToggleExpand={() => toggleRunExpanded(run.id)}
                    activeTab={getRunTab(run.id)}
                    onTabChange={(tab) => setRunTab(run.id, tab)}
                    onPRCreated={onPRCreated}
                  />
                ))}
              </div>
            ))}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Executor Type & Model Selection */}
      <div className="border-t border-gray-800 p-3 space-y-3">
        {/* Executor Type Toggle */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Executor:</span>
          <div className="flex items-center bg-gray-800 rounded-lg p-0.5">
            <button
              type="button"
              onClick={() => setCurrentExecutor('patch_agent')}
              className={cn(
                'flex items-center gap-1.5 px-2.5 py-1 rounded text-xs transition-colors',
                currentExecutor === 'patch_agent'
                  ? 'bg-gray-700 text-white'
                  : 'text-gray-400 hover:text-white'
              )}
            >
              <CpuChipIcon className="w-3.5 h-3.5" />
              <span>Models</span>
            </button>
            <button
              type="button"
              onClick={() => setCurrentExecutor('claude_code')}
              className={cn(
                'flex items-center gap-1.5 px-2.5 py-1 rounded text-xs transition-colors',
                currentExecutor === 'claude_code'
                  ? 'bg-gray-700 text-white'
                  : 'text-gray-400 hover:text-white'
              )}
            >
              <CommandLineIcon className="w-3.5 h-3.5" />
              <span>Claude Code</span>
            </button>
          </div>
        </div>

        {/* Model Selection (only for patch_agent) */}
        {currentExecutor === 'patch_agent' && (
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
        )}

        {/* Claude Code info */}
        {currentExecutor === 'claude_code' && (
          <div className="flex items-center gap-2 p-2 bg-purple-900/20 rounded-lg border border-purple-800/30">
            <CommandLineIcon className="w-4 h-4 text-purple-400" />
            <span className="text-xs text-purple-300">
              Claude Code will execute in an isolated worktree
            </span>
          </div>
        )}
      </div>

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
            disabled={loading || !input.trim() || (currentExecutor === 'patch_agent' && selectedModels.length === 0)}
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
          {currentExecutor === 'patch_agent' && selectedModels.length > 0 && (
            <span className="text-xs text-gray-500">
              {selectedModels.length} model{selectedModels.length > 1 ? 's' : ''} selected
            </span>
          )}
          {currentExecutor === 'claude_code' && (
            <span className="text-xs text-purple-400">
              Claude Code CLI
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
  taskId: string;
  expanded: boolean;
  onToggleExpand: () => void;
  activeTab: RunTab;
  onTabChange: (tab: RunTab) => void;
  onPRCreated: () => void;
}

function RunResultCard({
  run,
  taskId,
  expanded,
  onToggleExpand,
  activeTab,
  onTabChange,
  onPRCreated,
}: RunResultCardProps) {
  const [showPRForm, setShowPRForm] = useState(false);
  const [prTitle, setPRTitle] = useState('');
  const [prBody, setPRBody] = useState('');
  const [creating, setCreating] = useState(false);
  const [prResult, setPRResult] = useState<{ url: string } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const { success, error } = useToast();

  const handleCreatePR = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prTitle.trim()) return;

    setCreating(true);
    setFormError(null);

    try {
      const result = await prsApi.create(taskId, {
        selected_run_id: run.id,
        title: prTitle.trim(),
        body: prBody.trim() || undefined,
      });
      setPRResult(result);
      onPRCreated();
      success('Pull request created successfully!');
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
    if (run.executor_type === 'claude_code') {
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
        run.executor_type === 'claude_code' ? 'bg-purple-900/10' : 'bg-gray-800/50'
      )}
    >
      {/* Header - Always visible */}
      <button
        onClick={onToggleExpand}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-800/30 transition-colors rounded-t-lg"
      >
        <div className="flex items-center gap-3">
          {run.executor_type === 'claude_code' ? (
            <CommandLineIcon className="w-5 h-5 text-purple-400" />
          ) : (
            <CpuChipIcon className="w-5 h-5 text-blue-400" />
          )}
          <div className="text-left">
            <div className="font-medium text-gray-200 text-sm">
              {run.executor_type === 'claude_code' ? 'Claude Code' : run.model_name}
            </div>
            {run.executor_type === 'claude_code' && run.working_branch && (
              <div className="text-xs font-mono text-purple-400">{run.working_branch}</div>
            )}
            {run.executor_type !== 'claude_code' && run.provider && (
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
              {/* PR Actions */}
              {run.patch && !prResult && (
                <div className="px-4 pt-3 flex justify-end">
                  <Button
                    variant="success"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowPRForm(!showPRForm);
                    }}
                  >
                    {showPRForm ? 'Cancel' : 'Create PR'}
                  </Button>
                </div>
              )}

              {/* PR Form */}
              {showPRForm && (
                <div className="mx-4 mt-3 p-3 bg-gray-800/50 rounded-lg border border-gray-700">
                  {prResult ? (
                    <div className="flex flex-col items-center text-center py-2">
                      <CheckCircleIcon className="w-8 h-8 text-green-400 mb-2" />
                      <p className="text-green-400 font-medium text-sm mb-2">PR created!</p>
                      <a
                        href={prResult.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 text-blue-400 hover:text-blue-300 transition-colors text-sm"
                      >
                        View on GitHub
                        <ArrowTopRightOnSquareIcon className="w-4 h-4" />
                      </a>
                    </div>
                  ) : (
                    <form onSubmit={handleCreatePR} className="space-y-2">
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
                          Create PR
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
                      <h3 className="font-medium text-gray-200 text-sm mb-2">Summary</h3>
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
