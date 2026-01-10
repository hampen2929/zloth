/**
 * API client for dursor backend
 */

import type {
  ModelProfile,
  ModelProfileCreate,
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
  BacklogItem,
  BacklogItemCreate,
  BacklogItemUpdate,
  BacklogStatus,
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

// Models
export const modelsApi = {
  list: () => fetchApi<ModelProfile[]>('/models'),

  create: (data: ModelProfileCreate) =>
    fetchApi<ModelProfile>('/models', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  get: (id: string) => fetchApi<ModelProfile>(`/models/${id}`),

  delete: (id: string) =>
    fetchApi<void>(`/models/${id}`, { method: 'DELETE' }),
};

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
   * Start async PR link generation job (returns immediately with job ID).
   * Use this for long-running PR link generation to avoid proxy timeout.
   */
  startLinkAutoJob: (taskId: string, data: PRCreateAuto) =>
    fetchApi<PRLinkJob>(`/tasks/${taskId}/prs/auto/link/job`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  /**
   * Get status of PR link generation job.
   * Poll this endpoint until status is 'completed' or 'failed'.
   */
  getLinkAutoJob: (jobId: string) =>
    fetchApi<PRLinkJobResult>(`/prs/jobs/${jobId}`),

  /**
   * Poll for PR link generation job completion.
   *
   * @param taskId - Task ID
   * @param data - PR creation data
   * @param options - Polling options
   * @returns Cleanup function to cancel polling
   */
  pollLinkAuto: (
    taskId: string,
    data: PRCreateAuto,
    options: {
      onComplete: (result: PRCreateLink) => void;
      onError: (error: Error) => void;
      onStatusChange?: (status: string) => void;
    }
  ): (() => void) => {
    let cancelled = false;
    const pollInterval = 1000;

    const poll = async () => {
      if (cancelled) return;

      try {
        // Start the job
        const job = await prsApi.startLinkAutoJob(taskId, data);
        options.onStatusChange?.(job.status);

        // Poll for completion
        const checkStatus = async () => {
          if (cancelled) return;

          try {
            const result = await prsApi.getLinkAutoJob(job.job_id);
            options.onStatusChange?.(result.status);

            if (result.status === 'completed' && result.result) {
              options.onComplete(result.result);
              return;
            }

            if (result.status === 'failed') {
              options.onError(new Error(result.error || 'Job failed'));
              return;
            }

            // Continue polling
            if (!cancelled) {
              setTimeout(checkStatus, pollInterval);
            }
          } catch (error) {
            if (!cancelled) {
              options.onError(
                error instanceof Error ? error : new Error('Failed to check job status')
              );
            }
          }
        };

        checkStatus();
      } catch (error) {
        if (!cancelled) {
          options.onError(
            error instanceof Error ? error : new Error('Failed to start job')
          );
        }
      }
    };

    poll();

    return () => {
      cancelled = true;
    };
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

  regenerateDescription: (taskId: string, prId: string) =>
    fetchApi<PR>(`/tasks/${taskId}/prs/${prId}/regenerate-description`, {
      method: 'POST',
    }),
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
  list: (repoId?: string, status?: BacklogStatus) => {
    const params = new URLSearchParams();
    if (repoId) params.set('repo_id', repoId);
    if (status) params.set('status', status);
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

export { ApiError };
