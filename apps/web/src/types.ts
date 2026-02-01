/**
 * Type definitions for zloth frontend
 */

// Enums
export type Provider = 'openai' | 'anthropic' | 'google';
export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled';
export type MessageRole = 'user' | 'assistant' | 'system';
export type ExecutorType = 'patch_agent' | 'claude_code' | 'codex_cli' | 'gemini_cli';
export type PRCreationMode = 'create' | 'link';
export type CodingMode = 'interactive' | 'semi_auto' | 'full_auto';
export type PRUpdateMode = 'both' | 'description' | 'title';

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

export interface CICheckSummary {
  id: string;
  pr_id: string;
  status: string; // "pending" | "success" | "failure" | "error"
  created_at: string;
  updated_at: string;
}

export interface TaskDetail extends Task {
  messages: Message[];
  runs: RunSummary[];
  prs: PRSummary[];
  ci_checks: CICheckSummary[];
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

// PR Link Job (async PR link generation)
export type PRLinkJobStatus = 'pending' | 'completed' | 'failed';

export interface PRLinkJob {
  job_id: string;
  status: PRLinkJobStatus;
}

export interface PRLinkJobResult {
  job_id: string;
  status: PRLinkJobStatus;
  result: PRCreateLink | null;
  error: string | null;
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
  installation_id?: string;  // Optional: if not set, all installations are available
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
  auto_generate_pr_description: boolean;
  enable_gating_status: boolean;
  notify_on_ready: boolean;
  notify_on_complete: boolean;
  notify_on_failure: boolean;
  notify_on_warning: boolean;
  merge_method: string;
  review_min_score: number;
}

export interface UserPreferencesSave {
  default_repo_owner?: string | null;
  default_repo_name?: string | null;
  default_branch?: string | null;
  default_branch_prefix?: string | null;
  default_pr_creation_mode?: PRCreationMode | null;
  default_coding_mode?: CodingMode | null;
  auto_generate_pr_description?: boolean | null;
  enable_gating_status?: boolean | null;
  notify_on_ready?: boolean | null;
  notify_on_complete?: boolean | null;
  notify_on_failure?: boolean | null;
  notify_on_warning?: boolean | null;
  merge_method?: string | null;
  review_min_score?: number | null;
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
  | 'gating'
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
  repo_name: string | null; // Repository name (e.g., "owner/repo")
  run_count: number;
  running_count: number;
  completed_count: number;
  pr_count: number;
  latest_pr_status: string | null;
  latest_ci_status: string | null; // "pending" | "success" | "failure" | "error" | null
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

// Repository Summary
export interface RepoTaskCounts {
  backlog: number;
  todo: number;
  in_progress: number;
  gating: number;
  in_review: number;
  done: number;
  archived: number;
}

export interface RepoSummary {
  id: string;
  repo_url: string;
  repo_name: string | null;
  default_branch: string;
  task_counts: RepoTaskCounts;
  total_tasks: number;
  latest_activity: string | null;
  created_at: string;
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

// CI Check
export type CICheckStatus = 'pending' | 'success' | 'failure' | 'error';

export interface CIJobResult {
  job_name: string;
  result: string;  // "success" | "failure" | "skipped" | "cancelled"
  error_log: string | null;
}

export interface CICheck {
  id: string;
  task_id: string;
  pr_id: string;
  status: CICheckStatus;
  workflow_run_id: number | null;
  sha: string | null;
  jobs: Record<string, string>;
  failed_jobs: CIJobResult[];
  created_at: string;
  updated_at: string;
}

export interface CICheckResponse {
  ci_check: CICheck;
  is_complete: boolean;
}

// Development Metrics

export interface PRMetrics {
  total_prs: number;
  merged_prs: number;
  closed_prs: number;
  open_prs: number;
  merge_rate: number;
  avg_time_to_merge_hours: number | null;
}

export interface ConversationMetrics {
  total_messages: number;
  user_messages: number;
  assistant_messages: number;
  avg_messages_per_task: number;
  avg_user_messages_per_task: number;
}

export interface RunMetrics {
  total_runs: number;
  succeeded_runs: number;
  failed_runs: number;
  canceled_runs: number;
  run_success_rate: number;
  avg_run_duration_seconds: number | null;
  avg_queue_wait_seconds: number | null;
}

export interface ExecutorDistribution {
  executor_type: ExecutorType;
  count: number;
  percentage: number;
}

export interface CIMetrics {
  total_ci_checks: number;
  passed_ci_checks: number;
  failed_ci_checks: number;
  ci_success_rate: number;
  avg_ci_fix_iterations: number;
}

export interface ReviewMetrics {
  total_reviews: number;
  avg_review_score: number | null;
  critical_issues: number;
  high_issues: number;
  medium_issues: number;
  low_issues: number;
}

export interface AgenticMetrics {
  total_agentic_runs: number;
  completed_agentic_runs: number;
  failed_agentic_runs: number;
  agentic_completion_rate: number;
  avg_total_iterations: number;
  avg_ci_iterations: number;
  avg_review_iterations: number;
}

export interface ProductivityMetrics {
  avg_cycle_time_hours: number | null;
  throughput_per_week: number;
  first_time_success_rate: number;
}

export interface MetricsSummary {
  period: string;
  period_start: string;
  period_end: string;
  merge_rate: number;
  avg_cycle_time_hours: number | null;
  throughput: number;
  run_success_rate: number;
  total_tasks: number;
  total_prs: number;
  total_runs: number;
  total_messages: number;
  merge_rate_change: number | null;
  cycle_time_change: number | null;
  throughput_change: number | null;
}

export interface MetricsDataPoint {
  timestamp: string;
  value: number;
}

export interface MetricsTrend {
  metric_name: string;
  data_points: MetricsDataPoint[];
  trend: 'up' | 'down' | 'stable';
  change_percentage: number;
}

export interface RealtimeMetrics {
  active_tasks: number;
  running_runs: number;
  pending_ci_checks: number;
  open_prs: number;
  tasks_created_today: number;
  runs_completed_today: number;
  prs_merged_today: number;
}

export interface MetricsDetail {
  summary: MetricsSummary;
  pr_metrics: PRMetrics;
  conversation_metrics: ConversationMetrics;
  run_metrics: RunMetrics;
  executor_distribution: ExecutorDistribution[];
  ci_metrics: CIMetrics;
  review_metrics: ReviewMetrics;
  agentic_metrics: AgenticMetrics;
  productivity_metrics: ProductivityMetrics;
  realtime: RealtimeMetrics;
}

// Prompt Analysis

export interface PromptQualityAnalysis {
  avg_length: number;
  avg_word_count: number;
  specificity_score: number;
  context_score: number;
  prompts_with_file_refs: number;
  prompts_with_test_req: number;
  total_prompts_analyzed: number;
  common_missing_elements: string[];
}

export interface ExecutorSuccessRate {
  executor_type: ExecutorType;
  total_runs: number;
  succeeded_runs: number;
  success_rate: number;
  avg_duration_seconds: number | null;
}

export interface ErrorPattern {
  pattern: string;
  count: number;
  failure_rate: number;
  affected_files: string[];
}

export interface AnalysisRecommendation {
  id: string;
  priority: 'high' | 'medium' | 'low';
  category: string;
  title: string;
  description: string;
  impact: string;
  evidence: Record<string, unknown>;
}

export interface AnalysisSummary {
  period: string;
  period_start: string;
  period_end: string;
  prompt_quality_score: number;
  overall_success_rate: number;
  avg_iterations: number;
  total_tasks_analyzed: number;
}

export interface AnalysisDetail {
  summary: AnalysisSummary;
  prompt_analysis: PromptQualityAnalysis;
  executor_success_rates: ExecutorSuccessRate[];
  error_patterns: ErrorPattern[];
  recommendations: AnalysisRecommendation[];
}

// Executor Status (for Settings > Executors tab)
export interface ExecutorStatus {
  available: boolean;
  path: string;
  version: string | null;
  error: string | null;
}

export interface ExecutorsStatus {
  claude_code: ExecutorStatus;
  codex_cli: ExecutorStatus;
  gemini_cli: ExecutorStatus;
}
