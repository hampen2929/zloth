-- Migration: Add branch_prefix column to user_preferences table
-- This allows users to customize the branch prefix (default: "dursor")

ALTER TABLE user_preferences ADD COLUMN branch_prefix TEXT DEFAULT 'dursor';
