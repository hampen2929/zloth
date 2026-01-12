/**
 * Type definitions for dursor frontend
 */

// Enums
export type Provider = 'openai' | 'anthropic' | 'google';
export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled';
export type MessageRole = 'user' | 'assistant' | 'system';
export type ExecutorType = 'patch_agent' | 'claude_code' | 'codex_cli' | 'gemini_cli';
export type PRCreationMode = 'create' | 'link';
export type CodingMode = 'interactive' | 'semi_auto' | 'full_auto';

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
  coding_mode: CodingMode;
  kanban_status: string;
  created_at: string;
  updated_at: string;
}

export interface TaskCreate {
  repo_id: string;
  title?: string;
  coding_mode?: CodingMode;
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

// Structured Summary Types
export type SummaryType = 'code_change' | 'qa_response' | 'analysis' | 'no_action';

export interface CodeReference {
  file: string;
  line?: number;
  description: string;
}

export interface StructuredSummary {
  type: SummaryType;
  title: string;
  instruction: string;
  response: string;
  key_points: string[];
  analyzed_files: string[];
  references: CodeReference[];
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
  structured_summary: StructuredSummary | null;
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
  executor_types?: ExecutorType[];  // Multiple CLI executors for parallel execution
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
  default_coding_mode: CodingMode;
}

export interface UserPreferencesSave {
  default_repo_owner?: string | null;
  default_repo_name?: string | null;
  default_branch?: string | null;
  default_branch_prefix?: string | null;
  default_pr_creation_mode?: PRCreationMode | null;
  default_coding_mode?: CodingMode | null;
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

export interface ExecutorRunStatus {
  executor_type: ExecutorType;
  run_id: string | null;
  status: RunStatus | null;
  has_review: boolean;
}

export interface TaskWithKanbanStatus extends Task {
  computed_status: TaskKanbanStatus;
  run_count: number;
  running_count: number;
  completed_count: number;
  pr_count: number;
  latest_pr_status: string | null;
  executor_statuses: ExecutorRunStatus[];
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
}

// Code Review
export type ReviewSeverity = 'critical' | 'high' | 'medium' | 'low';
export type ReviewCategory =
  | 'security'
  | 'bug'
  | 'performance'
  | 'maintainability'
  | 'best_practice'
  | 'style'
  | 'documentation'
  | 'test';
export type ReviewStatus = 'queued' | 'running' | 'succeeded' | 'failed';

export interface ReviewFeedbackItem {
  id: string;
  file_path: string;
  line_start: number | null;
  line_end: number | null;
  severity: ReviewSeverity;
  category: ReviewCategory;
  title: string;
  description: string;
  suggestion: string | null;
  code_snippet: string | null;
}

export interface ReviewSummary {
  id: string;
  task_id: string;
  status: ReviewStatus;
  executor_type: ExecutorType;
  feedback_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  created_at: string;
}

export interface Review {
  id: string;
  task_id: string;
  target_run_ids: string[];
  executor_type: ExecutorType;
  model_id: string | null;
  model_name: string | null;
  status: ReviewStatus;
  overall_summary: string | null;
  overall_score: number | null;
  feedbacks: ReviewFeedbackItem[];
  logs: string[];
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface ReviewCreate {
  target_run_ids: string[];
  executor_type?: ExecutorType;
  model_id?: string;
  focus_areas?: ReviewCategory[];
}

export interface ReviewCreated {
  review_id: string;
}

export interface FixInstructionRequest {
  feedback_ids?: string[];
  severity_filter?: ReviewSeverity[];
  additional_instruction?: string;
}

export interface FixInstructionResponse {
  instruction: string;
  target_feedbacks: ReviewFeedbackItem[];
  estimated_changes: number;
}

// Agentic Execution
export type AgenticPhase =
  | 'coding'
  | 'waiting_ci'
  | 'reviewing'
  | 'fixing_ci'
  | 'fixing_review'
  | 'awaiting_human'
  | 'merge_check'
  | 'merging'
  | 'completed'
  | 'failed';

export interface AgenticStartRequest {
  instruction: string;
  mode?: CodingMode;
}

export interface AgenticStartResponse {
  agentic_run_id: string;
  status: string;
  mode: CodingMode;
}

export interface AgenticStatusResponse {
  agentic_run_id: string;
  task_id: string;
  mode: CodingMode;
  phase: AgenticPhase;
  iteration: number;
  ci_iterations: number;
  review_iterations: number;
  pr_number: number | null;
  last_review_score: number | null;
  human_approved: boolean;
  error: string | null;
  started_at: string;
  last_activity: string;
}
