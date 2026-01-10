/**
 * Common types for AI Role services
 *
 * All AI Roles (Implementation/Run, Review, Breakdown) share these
 * common interfaces for consistent UI rendering and status handling.
 */

import type { ExecutorType, FileDiff, ReviewFeedbackItem, BrokenDownTask, CodebaseAnalysis } from '../types';

// ============================================================
// Common Status
// ============================================================

/**
 * Common execution status for all AI Roles.
 * All roles follow the same lifecycle: queued → running → succeeded/failed
 */
export type RoleExecutionStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled';

// ============================================================
// Base Interfaces
// ============================================================

/**
 * Base interface for all role execution records.
 * All roles (Run, Review, etc.) share these common fields.
 */
export interface RoleExecutionBase {
  id: string;
  task_id: string;
  executor_type: ExecutorType;
  status: RoleExecutionStatus;
  logs: string[];
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

/**
 * Base interface for role execution results.
 * Used for API responses and internal result handling.
 */
export interface RoleResultBase {
  success: boolean;
  summary: string | null;
  logs: string[];
  warnings: string[];
  error: string | null;
}

// ============================================================
// Role-Specific Interfaces
// ============================================================

/**
 * Implementation role result (extends base with patch data).
 */
export interface ImplementationResult extends RoleResultBase {
  patch: string | null;
  files_changed: FileDiff[];
  session_id: string | null;
}

/**
 * Review role result (extends base with feedbacks).
 */
export interface ReviewResult extends RoleResultBase {
  overall_score: number | null;
  feedbacks: ReviewFeedbackItem[];
}

/**
 * Breakdown role result (extends base with tasks).
 */
export interface BreakdownResult extends RoleResultBase {
  tasks: BrokenDownTask[];
  codebase_analysis: CodebaseAnalysis | null;
}

// ============================================================
// UI Component Types
// ============================================================

/**
 * Tab configuration for role result cards.
 */
export interface RoleTab {
  id: string;
  label: string;
  icon?: React.ComponentType<{ className?: string }>;
}

/**
 * Status badge configuration.
 */
export interface StatusConfig {
  color: 'gray' | 'yellow' | 'green' | 'red';
  label: string;
  animate?: boolean;
}

/**
 * Status to configuration mapping.
 */
export const STATUS_CONFIGS: Record<RoleExecutionStatus, StatusConfig> = {
  queued: { color: 'gray', label: 'Queued' },
  running: { color: 'yellow', label: 'Running', animate: true },
  succeeded: { color: 'green', label: 'Succeeded' },
  failed: { color: 'red', label: 'Failed' },
  canceled: { color: 'gray', label: 'Canceled' },
};

// ============================================================
// Utility Types
// ============================================================

/**
 * Check if a status indicates the role is still processing.
 */
export function isProcessing(status: RoleExecutionStatus): boolean {
  return status === 'queued' || status === 'running';
}

/**
 * Check if a status indicates the role has completed (success or failure).
 */
export function isCompleted(status: RoleExecutionStatus): boolean {
  return status === 'succeeded' || status === 'failed' || status === 'canceled';
}

/**
 * Check if a status indicates success.
 */
export function isSucceeded(status: RoleExecutionStatus): boolean {
  return status === 'succeeded';
}
