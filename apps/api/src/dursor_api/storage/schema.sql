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
    model_id TEXT NOT NULL,          -- can be env model ID (not in model_profiles)
    model_name TEXT NOT NULL,        -- denormalized for env model support
    provider TEXT NOT NULL,          -- denormalized for env model support
    instruction TEXT NOT NULL,
    base_ref TEXT,
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
