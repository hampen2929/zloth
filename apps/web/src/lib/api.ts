/**
 * API client for zloth backend
 */

import type {
  Repo,
  RepoCloneRequest,
  RepoSelectRequest,
  Task,
  TaskCreate,
  TaskDetail,
  TaskBulkCreate,
  TaskBulkCreated,
  TaskBreakdownRequest,
  TaskBreakdownResponse,
  BreakdownLogsResponse,
  Message,
  MessageCreate,
  Run,
  RunCreate,
  RunsCreated,
  OutputLine,
  PR,
  PRCreate,
  PRCreateAuto,
  PRCreated,
  PRCreateLink,
  PRLinkJob,
  PRLinkJobResult,
  PRSyncResult,
  PRUpdate,
  PRUpdated,
  GitHubAppConfig,
  GitHubAppConfigSave,
  GitHubRepository,
  UserPreferences,
  UserPreferencesSave,
  KanbanBoard,
  RepoSummary,
  BacklogItem,
  BacklogItemCreate,
  BacklogItemUpdate,
  Review,
  ReviewCreate,
  ReviewCreated,
  ReviewSummary,
  FixInstructionRequest,
  FixInstructionResponse,
  CICheck,
  CICheckResponse,
  MetricsDetail,
  MetricsSummary,
  MetricsTrend,
  RealtimeMetrics,
  AnalysisDetail,
  AnalysisSummary,
  AnalysisRecommendation,
  PromptQualityAnalysis,
  ExecutorsStatus,
  Decision,
  DecisionCreate,
  DecisionType,
  OutcomeUpdate,
} from '@/types';

const API_BASE = '/api';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(response.status, error.detail || 'Request failed');
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

// Repos
export const reposApi = {
  clone: (data: RepoCloneRequest) =>
    fetchApi<Repo>('/repos/clone', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  select: (data: RepoSelectRequest) =>
    fetchApi<Repo>('/repos/select', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  get: (id: string) => fetchApi<Repo>(`/repos/${id}`),
};

// GitHub
export const githubApi = {
  getConfig: () => fetchApi<GitHubAppConfig>('/github/config'),

  saveConfig: (data: GitHubAppConfigSave) =>
    fetchApi<GitHubAppConfig>('/github/config', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  listRepos: () => fetchApi<GitHubRepository[]>('/github/repos'),

  listBranches: (owner: string, repo: string) =>
    fetchApi<string[]>(`/github/repos/${owner}/${repo}/branches`),
};

// Tasks
export const tasksApi = {
  list: (repoId?: string) => {
    const params = repoId ? `?repo_id=${repoId}` : '';
    return fetchApi<Task[]>(`/tasks${params}`);
  },

  create: (data: TaskCreate) =>
    fetchApi<Task>('/tasks', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  bulkCreate: (data: TaskBulkCreate) =>
    fetchApi<TaskBulkCreated>('/tasks/bulk', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  get: (id: string) => fetchApi<TaskDetail>(`/tasks/${id}`),

  addMessage: (taskId: string, data: MessageCreate) =>
    fetchApi<Message>(`/tasks/${taskId}/messages`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  listMessages: (taskId: string) =>
    fetchApi<Message[]>(`/tasks/${taskId}/messages`),
};

// Runs
export const runsApi = {
  create: (taskId: string, data: RunCreate) =>
    fetchApi<RunsCreated>(`/tasks/${taskId}/runs`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  list: (taskId: string) => fetchApi<Run[]>(`/tasks/${taskId}/runs`),

  get: (runId: string) => fetchApi<Run>(`/runs/${runId}`),

  cancel: (runId: string) =>
    fetchApi<void>(`/runs/${runId}/cancel`, { method: 'POST' }),

  /**
   * Get logs for a run (REST endpoint for polling).
   */
  getLogs: (runId: string, fromLine: number = 0) =>
    fetchApi<{
      logs: OutputLine[];
      is_complete: boolean;
      total_lines: number;
      run_status: string;
    }>(`/runs/${runId}/logs?from_line=${fromLine}`),

  /**
   * Stream run logs by polling the logs endpoint.
   *
   * This uses polling to fetch logs in real-time from OutputManager.
   *
   * @param runId - The run ID to stream logs for
   * @param options - Streaming options
   * @returns Cleanup function to stop polling
   */
  streamLogs: (
    runId: string,
    options: {
      fromLine?: number;
      onLine: (line: OutputLine) => void;
      onComplete: () => void;
      onError: (error: Error) => void;
    }
  ): (() => void) => {
    let cancelled = false;
    let nextLine = options.fromLine ?? 0;
    const pollInterval = 500; // Poll every 500ms for responsiveness

    const poll = async () => {
      if (cancelled) return;

      try {
        const result = await runsApi.getLogs(runId, nextLine);

        // Send new lines
        for (const log of result.logs) {
          if (cancelled) break;
          options.onLine(log);
        }

        // Update next line position
        if (result.logs.length > 0) {
          nextLine = result.total_lines;
        }

        // Check if complete
        if (result.is_complete) {
          options.onComplete();
          return;
        }

        // Continue polling if still running
        if (!cancelled) {
          setTimeout(poll, pollInterval);
        }
      } catch (error) {
        if (!cancelled) {
          options.onError(error instanceof Error ? error : new Error('Failed to fetch logs'));
        }
      }
    };

    // Start polling
    poll();

    // Return cleanup function
    return () => {
      cancelled = true;
    };
  },
};

// PRs
export const prsApi = {
  create: (taskId: string, data: PRCreate) =>
    fetchApi<PRCreated>(`/tasks/${taskId}/prs`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  createAuto: (taskId: string, data: PRCreateAuto) =>
    fetchApi<PRCreated>(`/tasks/${taskId}/prs/auto`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  createLink: (taskId: string, data: PRCreate) =>
    fetchApi<PRCreateLink>(`/tasks/${taskId}/prs/link`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  createLinkAuto: (taskId: string, data: PRCreateAuto) =>
    fetchApi<PRCreateLink>(`/tasks/${taskId}/prs/auto/link`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  /**
   * Start async PR link generation job.
   * Use this instead of createLinkAuto to avoid timeout.
   */
  startLinkAutoJob: (taskId: string, data: PRCreateAuto) =>
    fetchApi<PRLinkJob>(`/tasks/${taskId}/prs/auto/link/job`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  /**
   * Get status of PR link generation job.
   */
  getLinkAutoJob: (jobId: string) =>
    fetchApi<PRLinkJobResult>(`/prs/jobs/${jobId}`),

  /**
   * Create PR link with polling (async job approach).
   * This starts a job and polls until completion, avoiding timeout.
   *
   * @param taskId - The task ID
   * @param data - PR creation data
   * @param options - Polling options
   * @returns PRCreateLink result
   */
  createLinkAutoWithPolling: async (
    taskId: string,
    data: PRCreateAuto,
    options?: {
      pollInterval?: number;
      maxWaitTime?: number;
      onProgress?: () => void;
    }
  ): Promise<PRCreateLink> => {
    const pollInterval = options?.pollInterval ?? 1000;
    const maxWaitTime = options?.maxWaitTime ?? 120000; // 2 minutes default
    const startTime = Date.now();

    // Start the job
    const job = await prsApi.startLinkAutoJob(taskId, data);

    // Poll until complete or timeout
    while (Date.now() - startTime < maxWaitTime) {
      const result = await prsApi.getLinkAutoJob(job.job_id);

      if (result.status === 'completed' && result.result) {
        return result.result;
      }

      if (result.status === 'failed') {
        throw new ApiError(500, result.error || 'PR link generation failed');
      }

      options?.onProgress?.();
      await new Promise((resolve) => setTimeout(resolve, pollInterval));
    }

    throw new ApiError(504, 'PR link generation timed out');
  },

  sync: (taskId: string, selectedRunId: string) =>
    fetchApi<PRSyncResult>(`/tasks/${taskId}/prs/sync`, {
      method: 'POST',
      body: JSON.stringify({ selected_run_id: selectedRunId }),
    }),

  update: (taskId: string, prId: string, data: PRUpdate) =>
    fetchApi<PRUpdated>(`/tasks/${taskId}/prs/${prId}/update`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  get: (taskId: string, prId: string) =>
    fetchApi<PR>(`/tasks/${taskId}/prs/${prId}`),

  list: (taskId: string) => fetchApi<PR[]>(`/tasks/${taskId}/prs`),

  regenerateDescription: (taskId: string, prId: string, mode: 'both' | 'description' | 'title' = 'both') =>
    fetchApi<PR>(`/tasks/${taskId}/prs/${prId}/regenerate-description?mode=${mode}`, {
      method: 'POST',
    }),
};

// CI Checks
export const ciChecksApi = {
  /**
   * Check CI status for a PR.
   * If is_complete is false, poll again after a delay.
   */
  check: (taskId: string, prId: string) =>
    fetchApi<CICheckResponse>(`/tasks/${taskId}/prs/${prId}/check-ci`, {
      method: 'POST',
    }),

  /**
   * List all CI checks for a task.
   */
  list: (taskId: string) => fetchApi<CICheck[]>(`/tasks/${taskId}/ci-checks`),

  /**
   * Check CI status with polling until complete.
   *
   * @param taskId - The task ID
   * @param prId - The PR ID
   * @param options - Polling options
   * @returns CICheck result when complete
   */
  checkWithPolling: async (
    taskId: string,
    prId: string,
    options?: {
      pollInterval?: number;
      maxWaitTime?: number;
      onProgress?: (ciCheck: CICheck) => void;
    }
  ): Promise<CICheck> => {
    const pollInterval = options?.pollInterval ?? 10000; // 10 seconds
    const maxWaitTime = options?.maxWaitTime ?? 1800000; // 30 minutes
    const startTime = Date.now();

    while (Date.now() - startTime < maxWaitTime) {
      const response = await ciChecksApi.check(taskId, prId);

      options?.onProgress?.(response.ci_check);

      if (response.is_complete) {
        return response.ci_check;
      }

      // Wait before polling again
      await new Promise((resolve) => setTimeout(resolve, pollInterval));
    }

    throw new ApiError(504, 'CI check timed out');
  },
};

// Preferences
export const preferencesApi = {
  get: () => fetchApi<UserPreferences>('/preferences'),

  save: (data: UserPreferencesSave) =>
    fetchApi<UserPreferences>('/preferences', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// Breakdown
export const breakdownApi = {
  analyze: (data: TaskBreakdownRequest) =>
    fetchApi<TaskBreakdownResponse>('/breakdown', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getResult: (breakdownId: string) =>
    fetchApi<TaskBreakdownResponse>(`/breakdown/${breakdownId}`),

  getLogs: (breakdownId: string, fromLine: number = 0) =>
    fetchApi<BreakdownLogsResponse>(
      `/breakdown/${breakdownId}/logs?from_line=${fromLine}`
    ),

  /**
   * Stream breakdown logs by polling the logs endpoint.
   *
   * @param breakdownId - The breakdown ID to stream logs for
   * @param options - Streaming options
   * @returns Cleanup function to stop polling
   */
  streamLogs: (
    breakdownId: string,
    options: {
      fromLine?: number;
      onLine: (line: OutputLine) => void;
      onComplete: () => void;
      onError: (error: Error) => void;
    }
  ): (() => void) => {
    let cancelled = false;
    let nextLine = options.fromLine ?? 0;
    const pollInterval = 500;

    const poll = async () => {
      if (cancelled) return;

      try {
        const result = await breakdownApi.getLogs(breakdownId, nextLine);

        // Send new lines
        for (const log of result.logs) {
          if (cancelled) break;
          options.onLine(log);
        }

        // Update next line position
        if (result.logs.length > 0) {
          nextLine = result.total_lines;
        }

        // Check if complete
        if (result.is_complete) {
          options.onComplete();
          return;
        }

        // Continue polling if still running
        if (!cancelled) {
          setTimeout(poll, pollInterval);
        }
      } catch (error) {
        if (!cancelled) {
          options.onError(
            error instanceof Error ? error : new Error('Failed to fetch logs')
          );
        }
      }
    };

    // Start polling
    poll();

    // Return cleanup function
    return () => {
      cancelled = true;
    };
  },
};

// Kanban
export const kanbanApi = {
  getBoard: (repoId?: string) => {
    const params = repoId ? `?repo_id=${repoId}` : '';
    return fetchApi<KanbanBoard>(`/kanban${params}`);
  },

  getRepoSummaries: () => fetchApi<RepoSummary[]>('/kanban/repos'),

  moveToTodo: (taskId: string) =>
    fetchApi<Task>(`/kanban/tasks/${taskId}/move-to-todo`, { method: 'POST' }),

  moveToBacklog: (taskId: string) =>
    fetchApi<Task>(`/kanban/tasks/${taskId}/move-to-backlog`, {
      method: 'POST',
    }),

  archiveTask: (taskId: string) =>
    fetchApi<Task>(`/kanban/tasks/${taskId}/archive`, { method: 'POST' }),

  unarchiveTask: (taskId: string) =>
    fetchApi<Task>(`/kanban/tasks/${taskId}/unarchive`, { method: 'POST' }),

  syncPRStatus: (taskId: string, prId: string) =>
    fetchApi<PR>(`/kanban/tasks/${taskId}/prs/${prId}/sync-status`, {
      method: 'POST',
    }),
};

// Backlog
export const backlogApi = {
  list: (repoId?: string) => {
    const params = new URLSearchParams();
    if (repoId) params.set('repo_id', repoId);
    const query = params.toString();
    return fetchApi<BacklogItem[]>(`/backlog${query ? `?${query}` : ''}`);
  },

  create: (data: BacklogItemCreate) =>
    fetchApi<BacklogItem>('/backlog', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  get: (id: string) => fetchApi<BacklogItem>(`/backlog/${id}`),

  update: (id: string, data: BacklogItemUpdate) =>
    fetchApi<BacklogItem>(`/backlog/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  delete: (id: string) =>
    fetchApi<void>(`/backlog/${id}`, { method: 'DELETE' }),

  startWork: (id: string) =>
    fetchApi<Task>(`/backlog/${id}/start`, { method: 'POST' }),
};

// Reviews
export const reviewsApi = {
  create: (taskId: string, data: ReviewCreate) =>
    fetchApi<ReviewCreated>(`/tasks/${taskId}/reviews`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  list: (taskId: string) => fetchApi<ReviewSummary[]>(`/tasks/${taskId}/reviews`),

  get: (reviewId: string) => fetchApi<Review>(`/reviews/${reviewId}`),

  /**
   * Get logs for a review (REST endpoint for polling).
   * Returns OutputLine format for consistency with runs API.
   */
  getLogs: (reviewId: string, fromLine: number = 0) =>
    fetchApi<{
      logs: OutputLine[];
      is_complete: boolean;
      total_lines: number;
      review_status: string;
    }>(`/reviews/${reviewId}/logs?from_line=${fromLine}`),

  generateFix: (reviewId: string, data: FixInstructionRequest) =>
    fetchApi<FixInstructionResponse>(`/reviews/${reviewId}/generate-fix`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  toMessage: (reviewId: string) =>
    fetchApi<Message>(`/reviews/${reviewId}/to-message`, { method: 'POST' }),

  /**
   * Stream review logs by polling the logs endpoint.
   *
   * This uses polling to fetch logs in real-time from OutputManager.
   *
   * @param reviewId - The review ID to stream logs for
   * @param options - Streaming options
   * @returns Cleanup function to stop polling
   */
  streamLogs: (
    reviewId: string,
    options: {
      fromLine?: number;
      onLine: (line: OutputLine) => void;
      onComplete: () => void;
      onError: (error: Error) => void;
    }
  ): (() => void) => {
    let cancelled = false;
    let nextLine = options.fromLine ?? 0;
    const pollInterval = 500; // Poll every 500ms for responsiveness

    const poll = async () => {
      if (cancelled) return;

      try {
        const result = await reviewsApi.getLogs(reviewId, nextLine);

        // Send new lines
        for (const log of result.logs) {
          if (cancelled) break;
          options.onLine(log);
        }

        // Update next line position
        if (result.logs.length > 0) {
          nextLine = result.total_lines;
        }

        // Check if complete
        if (result.is_complete) {
          options.onComplete();
          return;
        }

        // Continue polling if still running
        if (!cancelled) {
          setTimeout(poll, pollInterval);
        }
      } catch (error) {
        if (!cancelled) {
          options.onError(error instanceof Error ? error : new Error('Failed to fetch logs'));
        }
      }
    };

    // Start polling
    poll();

    // Return cleanup function
    return () => {
      cancelled = true;
    };
  },

  /**
   * Poll review logs until complete (legacy - kept for backward compatibility).
   * @deprecated Use streamLogs instead for OutputLine format
   */
  pollLogs: (
    reviewId: string,
    options: {
      fromLine?: number;
      onLine: (line: string) => void;
      onComplete: () => void;
      onError: (error: Error) => void;
    }
  ): (() => void) => {
    return reviewsApi.streamLogs(reviewId, {
      fromLine: options.fromLine,
      onLine: (outputLine) => options.onLine(outputLine.content),
      onComplete: options.onComplete,
      onError: options.onError,
    });
  },
};

// Metrics
export const metricsApi = {
  /**
   * Get complete metrics detail for a period.
   */
  get: (period: string = '30d', repoId?: string) => {
    const params = new URLSearchParams();
    params.set('period', period);
    if (repoId) params.set('repo_id', repoId);
    return fetchApi<MetricsDetail>(`/metrics?${params.toString()}`);
  },

  /**
   * Get a summary of key metrics.
   */
  getSummary: (period: string = '7d', repoId?: string) => {
    const params = new URLSearchParams();
    params.set('period', period);
    if (repoId) params.set('repo_id', repoId);
    return fetchApi<MetricsSummary>(`/metrics/summary?${params.toString()}`);
  },

  /**
   * Get current real-time metrics.
   */
  getRealtime: (repoId?: string) => {
    const params = new URLSearchParams();
    if (repoId) params.set('repo_id', repoId);
    const query = params.toString();
    return fetchApi<RealtimeMetrics>(`/metrics/realtime${query ? `?${query}` : ''}`);
  },

  /**
   * Get trend data for specified metrics.
   */
  getTrends: (
    metrics: string[] = ['merge_rate', 'run_success_rate', 'throughput'],
    period: string = '30d',
    granularity: string = 'day',
    repoId?: string
  ) => {
    const params = new URLSearchParams();
    metrics.forEach((m) => params.append('metrics', m));
    params.set('period', period);
    params.set('granularity', granularity);
    if (repoId) params.set('repo_id', repoId);
    return fetchApi<MetricsTrend[]>(`/metrics/trends?${params.toString()}`);
  },
};

// Analysis
export const analysisApi = {
  /**
   * Get complete analysis detail for a period.
   */
  get: (period: string = '30d', repoId?: string) => {
    const params = new URLSearchParams();
    params.set('period', period);
    if (repoId) params.set('repo_id', repoId);
    return fetchApi<AnalysisDetail>(`/analysis?${params.toString()}`);
  },

  /**
   * Get analysis summary.
   */
  getSummary: (period: string = '30d', repoId?: string) => {
    const params = new URLSearchParams();
    params.set('period', period);
    if (repoId) params.set('repo_id', repoId);
    return fetchApi<AnalysisSummary>(`/analysis/summary?${params.toString()}`);
  },

  /**
   * Get prompt quality analysis.
   */
  getPromptAnalysis: (period: string = '30d', repoId?: string) => {
    const params = new URLSearchParams();
    params.set('period', period);
    if (repoId) params.set('repo_id', repoId);
    return fetchApi<PromptQualityAnalysis>(`/analysis/prompts?${params.toString()}`);
  },

  /**
   * Get prioritized recommendations.
   */
  getRecommendations: (period: string = '30d', repoId?: string) => {
    const params = new URLSearchParams();
    params.set('period', period);
    if (repoId) params.set('repo_id', repoId);
    return fetchApi<AnalysisRecommendation[]>(`/analysis/recommendations?${params.toString()}`);
  },
};

// Executors
export const executorsApi = {
  getStatus: () => fetchApi<ExecutorsStatus>('/executors/status'),
};

// Decisions (Decision Visibility P0)
export const decisionsApi = {
  /**
   * Create a decision record.
   */
  create: (taskId: string, data: DecisionCreate) =>
    fetchApi<Decision>(`/tasks/${taskId}/decisions`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  /**
   * List decisions for a task.
   */
  list: (taskId: string, decisionType?: DecisionType) => {
    const params = new URLSearchParams();
    if (decisionType) params.set('decision_type', decisionType);
    const query = params.toString();
    return fetchApi<Decision[]>(`/tasks/${taskId}/decisions${query ? `?${query}` : ''}`);
  },

  /**
   * Get a decision by ID.
   */
  get: (decisionId: string) =>
    fetchApi<Decision>(`/decisions/${decisionId}`),

  /**
   * Update decision outcome.
   */
  updateOutcome: (decisionId: string, data: OutcomeUpdate) =>
    fetchApi<Decision>(`/decisions/${decisionId}/outcome`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
};

export { ApiError };
