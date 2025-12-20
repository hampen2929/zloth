/**
 * Type definitions for dursor frontend
 */

// Enums
export type Provider = 'openai' | 'anthropic' | 'google';
export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled';
export type MessageRole = 'user' | 'assistant' | 'system';

// Model Profile
export interface ModelProfile {
  id: string;
  provider: Provider;
  model_name: string;
  display_name: string | null;
  created_at: string;
}

export interface ModelProfileCreate {
  provider: Provider;
  model_name: string;
  display_name?: string;
  api_key: string;
}

// Repository
export interface Repo {
  id: string;
  repo_url: string;
  default_branch: string;
  latest_commit: string;
  workspace_path: string;
  created_at: string;
}

export interface RepoCloneRequest {
  repo_url: string;
  ref?: string;
}

// Task
export interface Task {
  id: string;
  repo_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskCreate {
  repo_id: string;
  title?: string;
}

export interface TaskDetail extends Task {
  messages: Message[];
  runs: RunSummary[];
  prs: PRSummary[];
}

// Message
export interface Message {
  id: string;
  task_id: string;
  role: MessageRole;
  content: string;
  created_at: string;
}

export interface MessageCreate {
  role: MessageRole;
  content: string;
}

// Run
export interface RunSummary {
  id: string;
  model_id: string;
  model_name: string;
  provider: Provider;
  status: RunStatus;
  created_at: string;
}

export interface FileDiff {
  path: string;
  old_path?: string;
  added_lines: number;
  removed_lines: number;
  patch: string;
}

export interface Run {
  id: string;
  task_id: string;
  model_id: string;
  model_name: string;
  provider: Provider;
  instruction: string;
  base_ref: string | null;
  status: RunStatus;
  summary: string | null;
  patch: string | null;
  files_changed: FileDiff[];
  logs: string[];
  warnings: string[];
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface RunCreate {
  instruction: string;
  model_ids: string[];
  base_ref?: string;
}

export interface RunsCreated {
  run_ids: string[];
}

// Pull Request
export interface PRSummary {
  id: string;
  number: number;
  url: string;
  branch: string;
  status: string;
}

export interface PR {
  id: string;
  task_id: string;
  number: number;
  url: string;
  branch: string;
  title: string;
  body: string | null;
  latest_commit: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface PRCreate {
  selected_run_id: string;
  title: string;
  body?: string;
}

export interface PRUpdate {
  selected_run_id: string;
  message?: string;
}

export interface PRCreated {
  pr_id: string;
  url: string;
  branch: string;
  number: number;
}

export interface PRUpdated {
  url: string;
  latest_commit: string;
}

// GitHub App Configuration
export interface GitHubAppConfig {
  app_id: string | null;
  app_id_masked: string | null;
  installation_id: string | null;
  installation_id_masked: string | null;
  has_private_key: boolean;
  is_configured: boolean;
  source: 'env' | 'db' | null;
}

export interface GitHubAppConfigSave {
  app_id: string;
  private_key?: string;
  installation_id: string;
}

// GitHub Repository (for selection by name)
export interface GitHubRepository {
  id: number;
  name: string;
  full_name: string;
  owner: string;
  default_branch: string;
  private: boolean;
}

export interface RepoSelectRequest {
  owner: string;
  repo: string;
  branch?: string;
}
