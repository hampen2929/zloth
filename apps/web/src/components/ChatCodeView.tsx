'use client';

import { useState, useRef, useEffect, useMemo } from 'react';
import useSWR from 'swr';
import { tasksApi, runsApi, prsApi, preferencesApi, reviewsApi, ciChecksApi } from '@/lib/api';
import type { Message, ModelProfile, ExecutorType, Run, RunStatus, Review, CICheck } from '@/types';
import { Button } from './ui/Button';
import { useToast } from './ui/Toast';
import { getShortcutText, isModifierPressed } from '@/lib/platform';
import { cn } from '@/lib/utils';
import { useClipboard, getExecutorDisplayName } from '@/hooks';
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
  ChevronDownIcon,
} from '@heroicons/react/24/outline';
import { ReviewButton } from './ReviewButton';
import { ReviewResultCard } from './ReviewResultCard';
import { CIResultCard } from './CIResultCard';

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
  // executorType prop kept for backwards compatibility but not used
  initialModelIds,
  onRunsCreated,
  onPRCreated,
}: ChatCodeViewProps) {
  const [input, setInput] = useState('');
  const [selectedModels, setSelectedModels] = useState<string[]>(initialModelIds || []);
  const [loading, setLoading] = useState(false);
  const [selectedExecutorType, setSelectedExecutorType] = useState<ExecutorType | null>(null);
  const [runTabs, setRunTabs] = useState<Record<string, RunTab>>({});
  const [creatingPR, setCreatingPR] = useState(false);
  const [prResult, setPRResult] = useState<{ url: string; number: number; pr_id?: string } | null>(null);
  const [prLinkResult, setPRLinkResult] = useState<{ url: string } | null>(null);
  const [updatingDesc, setUpdatingDesc] = useState(false);
  const [reviewExpanded, setReviewExpanded] = useState<Record<string, boolean>>({});
  const [ciCheckExpanded, setCICheckExpanded] = useState<Record<string, boolean>>({});
  const [checkingCI, setCheckingCI] = useState(false);
  const [hasPendingCIChecks, setHasPendingCIChecks] = useState(false);
  const [recentPRCreation, setRecentPRCreation] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { success, error } = useToast();
  const { copy } = useClipboard();

  const { data: preferences } = useSWR('preferences', preferencesApi.get);
  const { data: prs, mutate: mutatePrs } = useSWR(`prs-${taskId}`, () => prsApi.list(taskId), {
    refreshInterval: prLinkResult ? 2000 : 0,
  });

  // Fetch reviews for the task
  const { data: reviewSummaries, mutate: mutateReviews } = useSWR(
    `reviews-${taskId}`,
    () => reviewsApi.list(taskId),
    { refreshInterval: 3000 }
  );

  // Fetch full review data for each review summary
  const { data: reviews } = useSWR<Review[]>(
    reviewSummaries ? `reviews-full-${taskId}` : null,
    async () => {
      if (!reviewSummaries) return [];
      const fullReviews = await Promise.all(
        reviewSummaries.map((s) => reviewsApi.get(s.id))
      );
      return fullReviews;
    },
    { refreshInterval: 3000 }
  );

  // Fetch CI checks for the task
  // Auto-poll when:
  // 1. User clicked "Check CI" button (checkingCI=true), OR
  // 2. There are pending CI checks (from automatic gating), OR
  // 3. PR was recently created (aggressive polling for 10 seconds)
  const { data: ciChecks, mutate: mutateCIChecks } = useSWR<CICheck[]>(
    `ci-checks-${taskId}`,
    () => ciChecksApi.list(taskId),
    { refreshInterval: checkingCI || hasPendingCIChecks || recentPRCreation ? (recentPRCreation ? 1000 : 5000) : 0 }
  );

  // Track pending CI checks state for auto-polling
  useEffect(() => {
    setHasPendingCIChecks(ciChecks?.some((check) => check.status === 'pending') ?? false);
  }, [ciChecks]);

  // Determine executor types used in this task
  const sortedRuns = useMemo(() => [...runs].reverse(), [runs]);

  // Check if patch_agent is used
  const hasPatchAgent = sortedRuns.some((r) => r.executor_type === 'patch_agent');


  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, runs, reviews]);

  // Select all models by default if none specified (patch_agent only)
  useEffect(() => {
    if (hasPatchAgent && models.length > 0 && selectedModels.length === 0 && !initialModelIds) {
      setSelectedModels(models.map((m) => m.id));
    }
  }, [models, selectedModels.length, initialModelIds, hasPatchAgent]);

  // Get unique executor types from runs (for executor selector cards)
  const uniqueExecutorTypes = useMemo(
    () => [...new Set(sortedRuns.map((r) => r.executor_type))] as ExecutorType[],
    [sortedRuns]
  );

  // Auto-select the first executor type when runs change
  useEffect(() => {
    if (uniqueExecutorTypes.length > 0 && (!selectedExecutorType || !uniqueExecutorTypes.includes(selectedExecutorType))) {
      setSelectedExecutorType(uniqueExecutorTypes[0]);
    }
  }, [uniqueExecutorTypes, selectedExecutorType]);

  // Get runs for selected executor type, grouped by message_id
  const runsForSelectedExecutor = sortedRuns.filter(
    (r) => r.executor_type === selectedExecutorType
  );

  // Get branch name from selected run (each executor has its own branch)
  // This ensures PR creation uses the selected executor's run, not any executor
  const latestSuccessfulRun = runsForSelectedExecutor.find(
    (r) => r.status === 'succeeded' && r.working_branch
  );

  // Get successful run IDs for review (only for the selected executor type)
  const successfulRunIds = runsForSelectedExecutor
    .filter((r) => r.status === 'succeeded')
    .map((r) => r.id);

  // Get the latest run for the selected executor (for branch info, PR creation)
  const latestRunForSelectedExecutor = runsForSelectedExecutor[0];

  // Get the PR for the selected executor's branch (each executor has its own PR)
  const selectedExecutorBranch = latestRunForSelectedExecutor?.working_branch;
  const latestPR = useMemo(() => {
    if (!prs || !selectedExecutorBranch) return null;
    return prs.find((pr) => pr.branch === selectedExecutorBranch) || null;
  }, [prs, selectedExecutorBranch]);

  // Sync PR result from backend for the selected executor
  useEffect(() => {
    if (latestPR && !prResult) {
      setPRResult({ url: latestPR.url, number: latestPR.number, pr_id: latestPR.id });
      setPRLinkResult(null);
      // Immediately refresh CI checks when PR is detected
      mutateCIChecks();
    }
  }, [latestPR, prResult, mutateCIChecks]);

  // Reset PR state when switching to a different executor
  // This allows creating a new PR for each executor
  const prevSelectedExecutorBranch = useRef<string | null | undefined>(undefined);
  useEffect(() => {
    if (prevSelectedExecutorBranch.current !== undefined &&
        prevSelectedExecutorBranch.current !== selectedExecutorBranch) {
      // Executor changed, reset PR state to allow creating PR for new executor
      setPRResult(null);
      setPRLinkResult(null);
    }
    prevSelectedExecutorBranch.current = selectedExecutorBranch;
  }, [selectedExecutorBranch]);

  // Build a map of message_id -> run for the selected executor
  const runByMessageId = new Map<string, Run>();
  runsForSelectedExecutor.forEach((run) => {
    if (run.message_id) {
      runByMessageId.set(run.message_id, run);
    }
  });

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

  // Auto-switch tabs only when run status actually changes (not on every runTabs update)
  // This prevents overriding user's manual tab selection
  const prevStatusesForTab = useRef<Map<string, RunStatus>>(new Map());
  useEffect(() => {
    const prevStatuses = prevStatusesForTab.current;

    runs.forEach((run) => {
      const prevStatus = prevStatuses.get(run.id);
      const currentStatus = run.status;

      // Only auto-switch when status actually changes
      if (prevStatus !== currentStatus) {
        if (currentStatus === 'running' || currentStatus === 'queued') {
          // Auto-switch to logs tab when run starts
          setRunTab(run.id, 'logs');
        } else if (currentStatus === 'succeeded' && (prevStatus === 'running' || prevStatus === 'queued')) {
          // Auto-switch to summary tab when run completes (only from running/queued state)
          setRunTab(run.id, 'summary');
        }
      }

      prevStatuses.set(run.id, currentStatus);
    });
  }, [runs]);

  // Derive PR title from run summary
  const derivePRTitle = (run: Run): string => {
    if (run.summary) {
      const firstLine = run.summary.split('\n')[0].trim();
      return firstLine.length > 72 ? firstLine.slice(0, 69) + '...' : firstLine;
    }
    return 'Update code changes';
  };

  const handleCreatePR = async () => {
    if (!latestSuccessfulRun) return;

    setCreatingPR(true);
    try {
      const title = derivePRTitle(latestSuccessfulRun);
      const autoGenerate = preferences?.auto_generate_pr_description ?? false;

      if (preferences?.default_pr_creation_mode === 'link') {
        // Link mode: open GitHub PR creation page
        let result;
        if (autoGenerate) {
          // Use polling-based API to generate title and description with AI
          result = await prsApi.createLinkAutoWithPolling(
            taskId,
            { selected_run_id: latestSuccessfulRun.id },
            { pollInterval: 1000, maxWaitTime: 120000 }
          );
        } else {
          // Use regular API with derived title (no AI generation)
          result = await prsApi.createLink(taskId, {
            selected_run_id: latestSuccessfulRun.id,
            title,
          });
        }
        setPRLinkResult({ url: result.url });
        success('PR link generated. Create the PR on GitHub.');
      } else {
        // Direct mode: create PR immediately
        let result;
        if (autoGenerate) {
          // Use auto API to generate title and description with AI
          result = await prsApi.createAuto(taskId, {
            selected_run_id: latestSuccessfulRun.id,
          });
        } else {
          // Use regular API with derived title (no AI generation)
          result = await prsApi.create(taskId, {
            selected_run_id: latestSuccessfulRun.id,
            title,
          });
        }
        setPRResult({ url: result.url, number: result.number, pr_id: result.pr_id });
        onPRCreated();
        // Refresh PRs cache so latestPR is updated when switching executors
        mutatePrs();
        // Immediately refresh CI checks to show pending CI status
        mutateCIChecks();
        // Enable aggressive polling for 10 seconds after PR creation
        setRecentPRCreation(true);
        setTimeout(() => setRecentPRCreation(false), 10000);
        success('Pull request created successfully!');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create PR';
      error(message);
    } finally {
      setCreatingPR(false);
    }
  };

  const handleUpdatePRDesc = async (mode: 'both' | 'description' | 'title' = 'both') => {
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

  const handleCheckCI = async () => {
    if (!prResult?.pr_id) return;

    setCheckingCI(true);
    try {
      // Start polling for CI status
      const ciCheck = await ciChecksApi.checkWithPolling(taskId, prResult.pr_id, {
        pollInterval: 10000, // 10 seconds
        maxWaitTime: 1800000, // 30 minutes
        onProgress: () => {
          mutateCIChecks();
        },
      });

      // Final refresh
      mutateCIChecks();

      if (ciCheck.status === 'success') {
        success('CI checks passed!');
      } else if (ciCheck.status === 'failure') {
        error('CI checks failed. Check the results for details.');
      }
    } catch (err) {
      console.error('CI check error:', err);
      const message = err instanceof Error ? err.message : 'Failed to check CI status';
      error(message);
    } finally {
      setCheckingCI(false);
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
          setPRResult({ url: synced.pr.url, number: synced.pr.number, pr_id: synced.pr.pr_id });
          setPRLinkResult(null);
          onPRCreated();
          // Refresh PRs cache so latestPR is updated when switching executors
          mutatePrs();
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
  }, [prLinkResult, latestSuccessfulRun, prResult, taskId, onPRCreated, success, mutatePrs]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    // Need a selected executor type or models selected (for patch_agent)
    if (!selectedExecutorType && selectedModels.length === 0) return;

    setLoading(true);

    try {
      // Create message and get its ID for linking to runs
      const message = await tasksApi.addMessage(taskId, { role: 'user', content: input.trim() });

      // Only send to the currently selected executor type (not all executors)
      const executorTypesToRun: ExecutorType[] = [];

      // Check if selected executor is a CLI type
      const isCLISelected = selectedExecutorType &&
        (selectedExecutorType === 'claude_code' ||
         selectedExecutorType === 'codex_cli' ||
         selectedExecutorType === 'gemini_cli');

      if (isCLISelected) {
        executorTypesToRun.push(selectedExecutorType);
      }

      // If patch_agent is selected, add it with models
      if (selectedExecutorType === 'patch_agent' && selectedModels.length > 0) {
        executorTypesToRun.push('patch_agent');
      }

      // Create run for the selected executor only, linked to the message
      await runsApi.create(taskId, {
        instruction: input.trim(),
        executor_types: executorTypesToRun,
        model_ids: selectedExecutorType === 'patch_agent' && selectedModels.length > 0 ? selectedModels : undefined,
        message_id: message.id,
      });

      // Show success message
      const executorName = getExecutorDisplayName(selectedExecutorType!) || selectedExecutorType;
      success(`Started ${executorName} run`);

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

  const getRunTab = (runId: string): RunTab => runTabs[runId] || 'summary';
  const setRunTab = (runId: string, tab: RunTab) => {
    setRunTabs((prev) => ({ ...prev, [runId]: tab }));
  };

  // Review expansion helpers
  const isReviewExpanded = (reviewId: string): boolean => reviewExpanded[reviewId] ?? true;
  const toggleReviewExpanded = (reviewId: string) => {
    setReviewExpanded((prev) => ({ ...prev, [reviewId]: !isReviewExpanded(reviewId) }));
  };

  // Filter reviews based on target runs' executor type (not the reviewer's executor type)
  // A review should appear in the executor panel where the reviewed runs belong
  const reviewsForSelectedExecutor = useMemo(() => {
    if (!reviews || !selectedExecutorType) return [];
    // Build a set of run IDs for the selected executor
    const selectedExecutorRunIds = new Set(
      runsForSelectedExecutor.map((r) => r.id)
    );
    // Include reviews where any of the target runs belong to the selected executor
    return reviews.filter((r) =>
      r.target_run_ids.some((runId) => selectedExecutorRunIds.has(runId))
    );
  }, [reviews, selectedExecutorType, runsForSelectedExecutor]);

  // CI check expansion helpers
  const isCICheckExpanded = (ciCheckId: string): boolean => ciCheckExpanded[ciCheckId] ?? true;
  const toggleCICheckExpanded = (ciCheckId: string) => {
    setCICheckExpanded((prev) => ({ ...prev, [ciCheckId]: !isCICheckExpanded(ciCheckId) }));
  };

  // Filter CI checks for selected executor's PR, deduplicated by SHA
  // Only show one CI check per SHA (the latest one) to avoid duplicate entries
  const ciChecksForSelectedExecutor = useMemo(() => {
    if (!ciChecks || !latestPR) return [];
    const checksForPR = ciChecks.filter((check) => check.pr_id === latestPR.id);

    // Deduplicate by SHA - keep only the latest check for each SHA
    const bysha = new Map<string, CICheck>();
    for (const check of checksForPR) {
      const sha = check.sha || check.id; // Use id as fallback if no SHA
      const existing = bysha.get(sha);
      if (!existing || new Date(check.updated_at) > new Date(existing.updated_at)) {
        bysha.set(sha, check);
      }
    }
    return Array.from(bysha.values());
  }, [ciChecks, latestPR]);

  // Auto-trigger CI check for pending CI checks (gating auto-polling)
  // This ensures that when automatic gating creates a pending CI check,
  // we actually poll GitHub for the latest status
  // Use a ref to track the last triggered SHA to prevent duplicate triggers
  const lastTriggeredCICheckRef = useRef<string | null>(null);
  const ciCheckTriggerTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!prResult?.pr_id || !ciChecks) return;

    // Don't trigger if currently checking CI (user clicked button)
    if (checkingCI) return;

    const pendingCheck = ciChecks.find(
      (c) => c.status === 'pending' && c.pr_id === prResult.pr_id
    );

    if (pendingCheck) {
      // Use SHA or ID as unique identifier to prevent duplicate triggers
      const checkKey = pendingCheck.sha || pendingCheck.id;

      // Skip if we already triggered for this check recently
      if (lastTriggeredCICheckRef.current === checkKey) {
        return;
      }

      // Clear any pending timeout
      if (ciCheckTriggerTimeoutRef.current) {
        clearTimeout(ciCheckTriggerTimeoutRef.current);
      }

      // Debounce: wait 2 seconds before triggering to avoid rapid-fire requests
      ciCheckTriggerTimeoutRef.current = setTimeout(() => {
        lastTriggeredCICheckRef.current = checkKey;

        // Trigger CI check to update status from GitHub
        // This is fire-and-forget; SWR polling will pick up the updated data
        ciChecksApi.check(taskId, prResult.pr_id!).catch(() => {
          // Ignore errors - we'll retry on next poll
          // Reset the ref so we can retry
          lastTriggeredCICheckRef.current = null;
        });
      }, 2000);
    } else {
      // No pending check - reset the ref
      lastTriggeredCICheckRef.current = null;
    }

    // Cleanup timeout on unmount or dependency change
    return () => {
      if (ciCheckTriggerTimeoutRef.current) {
        clearTimeout(ciCheckTriggerTimeoutRef.current);
      }
    };
  }, [ciChecks, prResult?.pr_id, taskId, checkingCI]);

  // Create a unified timeline of messages+runs and reviews, sorted chronologically
  type TimelineItem =
    | { type: 'message-run'; message: Message; run: Run; createdAt: string }
    | { type: 'review'; review: Review; createdAt: string }
    | { type: 'ci-check'; ciCheck: CICheck; createdAt: string };

  const timeline = useMemo<TimelineItem[]>(() => {
    const items: TimelineItem[] = [];

    // Add message+run pairs
    messages
      .filter((msg) => runByMessageId.has(msg.id))
      .forEach((msg) => {
        const run = runByMessageId.get(msg.id)!;
        items.push({
          type: 'message-run',
          message: msg,
          run,
          createdAt: msg.created_at,
        });
      });

    // Add reviews
    reviewsForSelectedExecutor.forEach((review) => {
      items.push({
        type: 'review',
        review,
        createdAt: review.created_at,
      });
    });

    // Add CI checks
    ciChecksForSelectedExecutor.forEach((ciCheck) => {
      items.push({
        type: 'ci-check',
        ciCheck,
        createdAt: ciCheck.created_at,
      });
    });

    // Sort by created_at ascending (chronological order)
    items.sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime());

    return items;
  }, [messages, runByMessageId, reviewsForSelectedExecutor, ciChecksForSelectedExecutor]);

  // Get aggregate stats for an executor type
  const getExecutorStats = (executorType: ExecutorType) => {
    const executorRuns = sortedRuns.filter((r) => r.executor_type === executorType);
    const latestRun = executorRuns[0];
    const totalFiles = executorRuns.reduce((acc, r) => acc + (r.files_changed?.length || 0), 0);
    const totalAdded = executorRuns.reduce(
      (acc, r) => acc + (r.files_changed?.reduce((a, f) => a + f.added_lines, 0) || 0),
      0
    );
    const totalRemoved = executorRuns.reduce(
      (acc, r) => acc + (r.files_changed?.reduce((a, f) => a + f.removed_lines, 0) || 0),
      0
    );
    return { latestRun, totalFiles, totalAdded, totalRemoved, runCount: executorRuns.length };
  };

  return (
    <div className="flex flex-col h-full bg-gray-900 rounded-lg border border-gray-800">
      {/* Session Header - shows selected executor's branch */}
      {latestRunForSelectedExecutor?.working_branch && (
        <SessionHeader
          sessionBranch={latestRunForSelectedExecutor.working_branch}
          prResult={prResult}
          prLinkResult={prLinkResult}
          latestSuccessfulRun={latestSuccessfulRun}
          successfulRunIds={successfulRunIds}
          taskId={taskId}
          creatingPR={creatingPR}
          updatingDesc={updatingDesc}
          checkingCI={checkingCI}
          onCopyBranch={() => copy(latestRunForSelectedExecutor.working_branch!, 'Branch name')}
          onCreatePR={handleCreatePR}
          onUpdatePRDesc={handleUpdatePRDesc}
          onCheckCI={handleCheckCI}
          onReviewCreated={() => {
            mutateReviews();
            success('Review started');
          }}
          onReviewError={(message) => error(message)}
        />
      )}

      {/* Executor Selector Cards - one per executor type */}
      {uniqueExecutorTypes.length > 0 && (
        <div className="px-4 py-3 border-b border-gray-800">
          <div className="flex gap-2 overflow-x-auto pb-1">
            {uniqueExecutorTypes.map((executorType) => {
              const stats = getExecutorStats(executorType);
              return (
                <ExecutorSelectorCard
                  key={executorType}
                  executorType={executorType}
                  stats={stats}
                  isSelected={selectedExecutorType === executorType}
                  onClick={() => setSelectedExecutorType(executorType)}
                />
              );
            })}
          </div>
        </div>
      )}

      {/* Interleaved Conversation Area: User message -> AI output -> Review (chronologically sorted) */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && runs.length === 0 ? (
          <EmptyState />
        ) : (
          <>
            {/* Render timeline items in chronological order */}
            {timeline.map((item) => {
              if (item.type === 'message-run') {
                return (
                  <div key={item.message.id} className="space-y-3">
                    {/* User message */}
                    <MessageBubble message={item.message} />
                    {/* AI output for this message */}
                    <div className="ml-4 border-l-2 border-purple-500/30 pl-4">
                      <RunResultCard
                        run={item.run}
                        expanded={true}
                        onToggleExpand={() => {}}
                        activeTab={getRunTab(item.run.id)}
                        onTabChange={(tab) => setRunTab(item.run.id, tab)}
                      />
                    </div>
                  </div>
                );
              } else if (item.type === 'review') {
                return (
                  <div key={item.review.id} className="ml-4 border-l-2 border-blue-500/30 pl-4">
                    <ReviewResultCard
                      review={item.review}
                      expanded={isReviewExpanded(item.review.id)}
                      onToggleExpand={() => toggleReviewExpanded(item.review.id)}
                      onApplyFix={(instruction) => {
                        setInput(instruction);
                        success('Fix instruction added to input');
                      }}
                    />
                  </div>
                );
              } else {
                return (
                  <div key={item.ciCheck.id} className="ml-4 border-l-2 border-green-500/30 pl-4">
                    <CIResultCard
                      ciCheck={item.ciCheck}
                      expanded={isCICheckExpanded(item.ciCheck.id)}
                      onToggleExpand={() => toggleCICheckExpanded(item.ciCheck.id)}
                    />
                  </div>
                );
              }
            })}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Model Selection (only when patch_agent is selected) */}
      {selectedExecutorType === 'patch_agent' && (
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
        disabled={!selectedExecutorType || (selectedExecutorType === 'patch_agent' && selectedModels.length === 0)}
        selectedModelCount={selectedExecutorType === 'patch_agent' ? selectedModels.length : undefined}
      />

    </div>
  );
}

// --- Sub-components ---

interface SessionHeaderProps {
  sessionBranch: string;
  prResult: { url: string; number: number; pr_id?: string } | null;
  prLinkResult: { url: string } | null;
  latestSuccessfulRun: Run | undefined;
  successfulRunIds: string[];
  taskId: string;
  creatingPR: boolean;
  updatingDesc: boolean;
  checkingCI: boolean;
  onCopyBranch: () => void;
  onCreatePR: () => void;
  onUpdatePRDesc: (mode: 'both' | 'description' | 'title') => void;
  onCheckCI: () => void;
  onReviewCreated: () => void;
  onReviewError: (message: string) => void;
}

const UPDATE_PR_OPTIONS: { id: 'both' | 'description' | 'title'; label: string; description: string }[] = [
  { id: 'both', label: 'Both', description: 'Update title and description' },
  { id: 'description', label: 'Description', description: 'Update description only' },
  { id: 'title', label: 'Title', description: 'Update title only' },
];

function SessionHeader({
  sessionBranch,
  prResult,
  prLinkResult,
  latestSuccessfulRun,
  successfulRunIds,
  taskId,
  creatingPR,
  updatingDesc,
  checkingCI,
  onCopyBranch,
  onCreatePR,
  onUpdatePRDesc,
  onCheckCI,
  onReviewCreated,
  onReviewError,
}: SessionHeaderProps) {
  const [isUpdateDropdownOpen, setIsUpdateDropdownOpen] = useState(false);
  const updateDropdownRef = useRef<HTMLDivElement>(null);

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

  const handleUpdatePR = (mode: 'both' | 'description' | 'title') => {
    setIsUpdateDropdownOpen(false);
    onUpdatePRDesc(mode);
  };

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

      {/* Review Button */}
      {successfulRunIds.length > 0 && (
        <ReviewButton
          taskId={taskId}
          runIds={successfulRunIds}
          onReviewCreated={onReviewCreated}
          onError={onReviewError}
        />
      )}

      {prResult ? (
        <>
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
          {prResult.pr_id && (
            <>
              <div className="relative" ref={updateDropdownRef}>
                <div className="flex">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handleUpdatePR('both')}
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
                        onClick={() => handleUpdatePR(option.id)}
                        className="w-full flex flex-col items-start px-3 py-2 text-sm transition-colors text-gray-300 hover:bg-gray-700"
                      >
                        <span className="font-medium">{option.label}</span>
                        <span className="text-xs text-gray-500">{option.description}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={onCheckCI}
                disabled={checkingCI}
                isLoading={checkingCI}
              >
                {checkingCI ? 'Checking CI...' : 'Check CI'}
              </Button>
            </>
          )}
        </>
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

interface ExecutorStats {
  latestRun: Run | undefined;
  totalFiles: number;
  totalAdded: number;
  totalRemoved: number;
  runCount: number;
}

interface ExecutorSelectorCardProps {
  executorType: ExecutorType;
  stats: ExecutorStats;
  isSelected: boolean;
  onClick: () => void;
}

function ExecutorSelectorCard({ executorType, stats, isSelected, onClick }: ExecutorSelectorCardProps) {
  const displayName = getExecutorDisplayName(executorType) || executorType;
  const { latestRun, totalAdded, totalRemoved } = stats;

  const getStatusInfo = () => {
    if (!latestRun) {
      return { text: 'No runs', color: 'text-gray-500' };
    }
    switch (latestRun.status) {
      case 'running':
        return { text: 'Running...', color: 'text-blue-400' };
      case 'queued':
        return { text: 'Queued', color: 'text-gray-400' };
      case 'succeeded':
        if (totalAdded === 0 && totalRemoved === 0) {
          return { text: 'No changes', color: 'text-gray-400' };
        }
        return { text: '', color: 'text-gray-300' };
      case 'failed':
        return { text: 'Failed', color: 'text-red-400' };
      case 'canceled':
        return { text: 'Canceled', color: 'text-gray-500' };
      default:
        return { text: '', color: 'text-gray-400' };
    }
  };

  const statusInfo = getStatusInfo();

  return (
    <button
      onClick={onClick}
      className={cn(
        'flex-shrink-0 px-4 py-2.5 rounded-lg border transition-all text-left min-w-[140px]',
        isSelected
          ? 'bg-gray-800 border-purple-500 shadow-lg shadow-purple-500/10'
          : 'bg-gray-800/50 border-gray-700 hover:border-gray-600 hover:bg-gray-800'
      )}
    >
      <div className="flex items-center gap-2 mb-1">
        {latestRun?.status === 'running' && (
          <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
        )}
        {latestRun?.status === 'succeeded' && (
          <CheckCircleIcon className="w-4 h-4 text-green-500" />
        )}
        <span className="text-sm font-medium text-white truncate">{displayName}</span>
      </div>
      <div className={cn('text-xs', statusInfo.color)}>
        {latestRun?.status === 'succeeded' && (totalAdded > 0 || totalRemoved > 0) ? (
          <span>
            {totalAdded > 0 && <span className="text-green-400">+{totalAdded}</span>}
            {totalRemoved > 0 && <span className="text-red-400 ml-1">-{totalRemoved}</span>}
          </span>
        ) : (
          statusInfo.text
        )}
      </div>
    </button>
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
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea based on content
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      const newHeight = Math.min(textarea.scrollHeight, 200); // Max height of 200px
      textarea.style.height = `${newHeight}px`;
    }
  }, [value]);

  return (
    <form onSubmit={onSubmit} className="border-t border-gray-800 p-3">
      <div className="flex gap-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Enter your instructions..."
          rows={1}
          className={cn(
            'flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded resize-none',
            'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'text-sm text-gray-100 placeholder:text-gray-500',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'transition-colors min-h-[42px] max-h-[200px] overflow-y-auto'
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
