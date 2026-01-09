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
  PRSyncResult,
  PRUpdate,
  PRUpdated,
  GitHubAppConfig,
  GitHubAppConfigSave,
  GitHubRepository,
  UserPreferences,
  UserPreferencesSave,
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
