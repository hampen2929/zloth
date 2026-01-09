/**
 * Type definitions for dursor frontend
 */

// Enums
export type Provider = 'openai' | 'anthropic' | 'google';
export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled';
export type MessageRole = 'user' | 'assistant' | 'system';
export type ExecutorType = 'patch_agent' | 'claude_code' | 'codex_cli' | 'gemini_cli';
export type PRCreationMode = 'create' | 'link';

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
  kanban_status: string;
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
  message_id: string | null;
  model_id: string | null;
  model_name: string | null;
  provider: Provider | null;
  executor_type: ExecutorType;
  working_branch: string | null;
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
  message_id: string | null;
  model_id: string | null;
  model_name: string | null;
  provider: Provider | null;
  executor_type: ExecutorType;
  working_branch: string | null;
  worktree_path: string | null;
  instruction: string;
  base_ref: string | null;
  commit_sha: string | null;
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
  model_ids?: string[];
  base_ref?: string;
  executor_type?: ExecutorType;
  message_id?: string;
}

export interface RunsCreated {
  run_ids: string[];
}

// Streaming Output
export interface OutputLine {
  line_number: number;
  content: string;
  timestamp: number;
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

export interface PRCreateAuto {
  selected_run_id: string;
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

export interface PRCreateLink {
  url: string;
  branch: string;
  base: string;
}

export interface PRSyncRequest {
  selected_run_id: string;
}

export interface PRSyncResult {
  found: boolean;
  pr: PRCreated | null;
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

// User Preferences
export interface UserPreferences {
  default_repo_owner: string | null;
  default_repo_name: string | null;
  default_branch: string | null;
  default_branch_prefix: string | null;
  default_pr_creation_mode: PRCreationMode;
}

export interface UserPreferencesSave {
  default_repo_owner?: string | null;
  default_repo_name?: string | null;
  default_branch?: string | null;
  default_branch_prefix?: string | null;
  default_pr_creation_mode?: PRCreationMode | null;
}

// Task Breakdown
export type BreakdownStatus = 'pending' | 'running' | 'succeeded' | 'failed';
export type BrokenDownTaskType = 'feature' | 'bug_fix' | 'refactoring' | 'docs' | 'test';
export type EstimatedSize = 'small' | 'medium' | 'large';

export interface TaskBreakdownRequest {
  content: string;
  executor_type: ExecutorType;
  repo_id: string;
  context?: Record<string, unknown>;
}

export interface BrokenDownSubTask {
  title: string;
}

export interface BrokenDownTask {
  title: string;
  description: string;
  type: BrokenDownTaskType;
  estimated_size: EstimatedSize;
  target_files: string[];
  implementation_hint: string | null;
  tags: string[];
  subtasks: BrokenDownSubTask[];
}

export interface CodebaseAnalysis {
  files_analyzed: number;
  relevant_modules: string[];
  tech_stack: string[];
}

export interface TaskBreakdownResponse {
  breakdown_id: string;
  status: BreakdownStatus;
  tasks: BrokenDownTask[];
  backlog_items: BacklogItem[];
  summary: string | null;
  original_content: string;
  codebase_analysis: CodebaseAnalysis | null;
  error: string | null;
}

export interface BreakdownLogsResponse {
  logs: OutputLine[];
  is_complete: boolean;
  total_lines: number;
}

export interface TaskBulkCreate {
  repo_id: string;
  tasks: TaskCreate[];
}

export interface TaskBulkCreated {
  created_tasks: Task[];
  count: number;
}

// Kanban
export type TaskKanbanStatus =
  | 'backlog'
  | 'todo'
  | 'in_progress'
  | 'in_review'
  | 'done'
  | 'archived';

export interface TaskWithKanbanStatus extends Task {
  computed_status: TaskKanbanStatus;
  run_count: number;
  running_count: number;
  completed_count: number;
  pr_count: number;
  latest_pr_status: string | null;
}

export interface KanbanColumn {
  status: TaskKanbanStatus;
  tasks: TaskWithKanbanStatus[];
  count: number;
}

export interface KanbanBoard {
  columns: KanbanColumn[];
  total_tasks: number;
}

// Backlog
export type BacklogStatus = 'draft' | 'ready' | 'in_progress' | 'done';

export interface SubTask {
  id: string;
  title: string;
  completed: boolean;
}

export interface SubTaskCreate {
  title: string;
}

export interface BacklogItem {
  id: string;
  repo_id: string;
  title: string;
  description: string;
  type: BrokenDownTaskType;
  estimated_size: EstimatedSize;
  target_files: string[];
  implementation_hint: string | null;
  tags: string[];
  subtasks: SubTask[];
  status: BacklogStatus;
  task_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface BacklogItemCreate {
  repo_id: string;
  title: string;
  description?: string;
  type?: BrokenDownTaskType;
  estimated_size?: EstimatedSize;
  target_files?: string[];
  implementation_hint?: string;
  tags?: string[];
  subtasks?: SubTaskCreate[];
}

export interface BacklogItemUpdate {
  title?: string;
  description?: string;
  type?: BrokenDownTaskType;
  estimated_size?: EstimatedSize;
  target_files?: string[];
  implementation_hint?: string;
  tags?: string[];
  subtasks?: SubTask[];
  status?: BacklogStatus;
}
