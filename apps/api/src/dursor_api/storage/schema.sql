-- dursor v0.1 SQLite Schema

-- Model profiles (provider + model + encrypted API key)
CREATE TABLE IF NOT EXISTS model_profiles (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,          -- openai, anthropic, google
    model_name TEXT NOT NULL,        -- gpt-4o, claude-3-opus, etc.
    display_name TEXT,
    api_key_encrypted TEXT NOT NULL, -- encrypted API key
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_model_profiles_provider ON model_profiles(provider);

-- Repositories (cloned repos)
CREATE TABLE IF NOT EXISTS repos (
    id TEXT PRIMARY KEY,
    repo_url TEXT NOT NULL,
    default_branch TEXT NOT NULL,
    selected_branch TEXT,            -- user-selected branch for worktree base
    latest_commit TEXT NOT NULL,
    workspace_path TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_repos_url ON repos(repo_url);

-- Tasks (conversation units)
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL REFERENCES repos(id),
    title TEXT,
    coding_mode TEXT NOT NULL DEFAULT 'interactive',  -- interactive, semi_auto, full_auto
    kanban_status TEXT NOT NULL DEFAULT 'backlog',  -- backlog, todo, archived (dynamic: in_progress, in_review, done)
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tasks_repo ON tasks(repo_id);

-- Messages (chat history)
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    role TEXT NOT NULL,              -- user, assistant, system
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_task ON messages(task_id);

-- Runs (parallel execution units per model)
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    message_id TEXT REFERENCES messages(id),  -- links run to triggering message
    model_id TEXT,                   -- can be NULL for claude_code executor
    model_name TEXT,                 -- denormalized for env model support
    provider TEXT,                   -- denormalized for env model support
    executor_type TEXT NOT NULL DEFAULT 'patch_agent',  -- patch_agent, claude_code
    working_branch TEXT,             -- git branch for worktree (claude_code)
    worktree_path TEXT,              -- filesystem path to worktree (claude_code)
    session_id TEXT,                 -- CLI session ID for conversation persistence
    instruction TEXT NOT NULL,
    base_ref TEXT,
    commit_sha TEXT,                 -- latest commit SHA for the run
    status TEXT NOT NULL DEFAULT 'queued',  -- queued, running, succeeded, failed, canceled
    summary TEXT,
    patch TEXT,
    files_changed TEXT,              -- JSON array of FileDiff
    logs TEXT,                       -- JSON array of log strings
    warnings TEXT,                   -- JSON array of warning strings
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task_id);
CREATE INDEX IF NOT EXISTS idx_runs_message ON runs(message_id);
CREATE INDEX IF NOT EXISTS idx_runs_model ON runs(model_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);

-- Pull Requests
CREATE TABLE IF NOT EXISTS prs (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    number INTEGER NOT NULL,
    url TEXT NOT NULL,
    branch TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    latest_commit TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_prs_task ON prs(task_id);

-- GitHub App configuration (singleton table)
CREATE TABLE IF NOT EXISTS github_app_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- Singleton constraint
    app_id TEXT NOT NULL,
    private_key TEXT NOT NULL,              -- Base64 encoded private key
    installation_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- User preferences (singleton table for default settings)
CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- Singleton constraint
    default_repo_owner TEXT,                -- Default repository owner (e.g., "anthropics")
    default_repo_name TEXT,                 -- Default repository name (e.g., "claude-code")
    default_branch TEXT,                    -- Default branch (e.g., "main")
    default_branch_prefix TEXT,             -- Default branch prefix for work branches (e.g., "dursor")
    default_pr_creation_mode TEXT,          -- Default PR creation behavior: create|link
    default_coding_mode TEXT,               -- Default coding mode: interactive|semi_auto|full_auto
    auto_generate_pr_description INTEGER DEFAULT 0,  -- Auto-generate PR description: 0=no, 1=yes
    update_pr_title_on_regenerate INTEGER DEFAULT 1, -- Update PR title when regenerating: 0=no, 1=yes
    worktrees_dir TEXT,                     -- Custom worktrees directory (e.g., "~/.dursor/worktrees")
    enable_gating_status INTEGER DEFAULT 0, -- Enable Gating status in kanban: 0=no, 1=yes
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Backlog items (feature-level tasks from breakdown)
CREATE TABLE IF NOT EXISTS backlog_items (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    type TEXT NOT NULL DEFAULT 'feature',          -- feature, bug_fix, refactoring, docs, test
    estimated_size TEXT NOT NULL DEFAULT 'medium', -- small, medium, large
    target_files TEXT NOT NULL DEFAULT '[]',       -- JSON array
    implementation_hint TEXT,
    tags TEXT NOT NULL DEFAULT '[]',               -- JSON array
    subtasks TEXT NOT NULL DEFAULT '[]',           -- JSON array of SubTask
    task_id TEXT,                                  -- Reference to task if promoted
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (repo_id) REFERENCES repos(id),
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE INDEX IF NOT EXISTS idx_backlog_items_repo_id ON backlog_items(repo_id);

-- Reviews table
CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    target_run_ids TEXT NOT NULL,  -- JSON array
    executor_type TEXT NOT NULL,
    model_id TEXT,
    model_name TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    overall_summary TEXT,
    overall_score REAL,
    logs TEXT,  -- JSON array
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    completed_at TEXT,

    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

-- Review feedbacks table
CREATE TABLE IF NOT EXISTS review_feedbacks (
    id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    severity TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    suggestion TEXT,
    code_snippet TEXT,

    FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_reviews_task ON reviews(task_id);
CREATE INDEX IF NOT EXISTS idx_reviews_status ON reviews(status);
CREATE INDEX IF NOT EXISTS idx_feedbacks_review ON review_feedbacks(review_id);
CREATE INDEX IF NOT EXISTS idx_feedbacks_severity ON review_feedbacks(severity);

-- Agentic execution runs
CREATE TABLE IF NOT EXISTS agentic_runs (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    mode TEXT NOT NULL,                    -- interactive, semi_auto, full_auto
    phase TEXT NOT NULL,                   -- coding, waiting_ci, reviewing, etc.
    iteration INTEGER NOT NULL DEFAULT 0,
    ci_iterations INTEGER NOT NULL DEFAULT 0,
    review_iterations INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_activity TEXT NOT NULL DEFAULT (datetime('now')),
    pr_number INTEGER,
    current_sha TEXT,
    last_ci_result TEXT,                   -- JSON
    last_review_score REAL,
    error TEXT,
    human_approved INTEGER NOT NULL DEFAULT 0,  -- 0 = false, 1 = true

    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agentic_runs_task ON agentic_runs(task_id);
CREATE INDEX IF NOT EXISTS idx_agentic_runs_phase ON agentic_runs(phase);

-- Agentic audit log (for compliance and debugging)
CREATE TABLE IF NOT EXISTS agentic_audit_log (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    agentic_run_id TEXT NOT NULL,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    phase TEXT NOT NULL,
    action TEXT NOT NULL,
    agent TEXT,                            -- claude_code, codex, system
    input_summary TEXT,
    output_summary TEXT,
    duration_ms INTEGER,
    success INTEGER,                       -- 0 = false, 1 = true
    error TEXT,

    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (agentic_run_id) REFERENCES agentic_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agentic_audit_task ON agentic_audit_log(task_id);
CREATE INDEX IF NOT EXISTS idx_agentic_audit_run ON agentic_audit_log(agentic_run_id);
CREATE INDEX IF NOT EXISTS idx_agentic_audit_timestamp ON agentic_audit_log(timestamp);

-- CI Checks (CI status check records for PRs)
CREATE TABLE IF NOT EXISTS ci_checks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    pr_id TEXT NOT NULL,
    status TEXT NOT NULL,              -- pending, success, failure, error
    workflow_run_id INTEGER,
    sha TEXT,
    jobs TEXT,                         -- JSON: job_name -> result
    failed_jobs TEXT,                  -- JSON: list of CIJobResult
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (pr_id) REFERENCES prs(id)
);

CREATE INDEX IF NOT EXISTS idx_ci_checks_task_id ON ci_checks(task_id);
CREATE INDEX IF NOT EXISTS idx_ci_checks_pr_id ON ci_checks(pr_id);
