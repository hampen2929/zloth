-- Migration: Add pr_creation_mode column to user_preferences
-- This column allows users to choose between automatic PR creation (via API)
-- or manual PR creation (opening GitHub's PR creation page)

ALTER TABLE user_preferences ADD COLUMN pr_creation_mode TEXT DEFAULT 'auto';
