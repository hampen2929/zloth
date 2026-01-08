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
  Message,
  MessageCreate,
  Run,
  RunCreate,
  RunsCreated,
  PR,
  PRCreate,
  PRCreateAuto,
  PRCreated,
  PRUpdate,
  PRUpdated,
  GitHubAppConfig,
  GitHubAppConfigSave,
  GitHubRepository,
  UserPreferences,
  UserPreferencesSave,
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

export { ApiError };
