-- Migration: Add Claude Code support columns to runs table
-- Date: 2024-01-05
-- Description: Adds executor_type, working_branch, and worktree_path columns
--              for Claude Code workflow support

-- Add executor_type column with default value
ALTER TABLE runs ADD COLUMN executor_type TEXT NOT NULL DEFAULT 'patch_agent';

-- Add working_branch column for git worktree branch name
ALTER TABLE runs ADD COLUMN working_branch TEXT;

-- Add worktree_path column for filesystem path to worktree
ALTER TABLE runs ADD COLUMN worktree_path TEXT;

-- Make model_id nullable (it's NULL for claude_code executor)
-- Note: SQLite doesn't support ALTER COLUMN, so model_id, model_name, provider
-- were already nullable in the original schema after our update
