# API Reference

Base URL: `http://localhost:8000/v1`

## Authentication

v0.1 has no authentication (local/self-host assumption).

## Models API

Manage model profiles (LLM provider + model + API key).

### List Models

```http
GET /models
```

**Response** `200 OK`
```json
[
  {
    "id": "uuid",
    "provider": "openai",
    "model_name": "gpt-4o",
    "display_name": "GPT-4o (fast)",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

### Create Model

```http
POST /models
Content-Type: application/json

{
  "provider": "openai",
  "model_name": "gpt-4o",
  "display_name": "GPT-4o (fast)",
  "api_key": "sk-..."
}
```

**Parameters**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| provider | string | Yes | `openai`, `anthropic`, `google` |
| model_name | string | Yes | Model identifier |
| display_name | string | No | Display name |
| api_key | string | Yes | API key (stored encrypted) |

**Response** `201 Created`
```json
{
  "id": "uuid",
  "provider": "openai",
  "model_name": "gpt-4o",
  "display_name": "GPT-4o (fast)",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Delete Model

```http
DELETE /models/{model_id}
```

**Response** `204 No Content`

---

## Repos API

Manage Git repositories.

### Clone Repository

```http
POST /repos/clone
Content-Type: application/json

{
  "repo_url": "https://github.com/owner/repo",
  "ref": "main"
}
```

**Parameters**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| repo_url | string | Yes | Git URL |
| ref | string | No | Branch/commit to checkout |

**Response** `201 Created`
```json
{
  "id": "uuid",
  "repo_url": "https://github.com/owner/repo",
  "default_branch": "main",
  "latest_commit": "abc123...",
  "workspace_path": "/app/workspaces/uuid",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Get Repository

```http
GET /repos/{repo_id}
```

**Response** `200 OK`
```json
{
  "id": "uuid",
  "repo_url": "https://github.com/owner/repo",
  "default_branch": "main",
  "latest_commit": "abc123...",
  "workspace_path": "/app/workspaces/uuid",
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

## Tasks API

Manage tasks (conversation units).

### Create Task

```http
POST /tasks
Content-Type: application/json

{
  "repo_id": "uuid",
  "title": "Add input validation"
}
```

**Response** `201 Created`
```json
{
  "id": "uuid",
  "repo_id": "uuid",
  "title": "Add input validation",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### List Tasks

```http
GET /tasks?repo_id={repo_id}
```

**Query Parameters**

| Field | Type | Description |
|-------|------|-------------|
| repo_id | string | Filter by repository |

**Response** `200 OK`
```json
[
  {
    "id": "uuid",
    "repo_id": "uuid",
    "title": "Add input validation",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

### Get Task Detail

```http
GET /tasks/{task_id}
```

**Response** `200 OK`
```json
{
  "id": "uuid",
  "repo_id": "uuid",
  "title": "Add input validation",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "messages": [
    {
      "id": "uuid",
      "task_id": "uuid",
      "role": "user",
      "content": "Add validation to the form",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "runs": [
    {
      "id": "uuid",
      "model_id": "uuid",
      "model_name": "gpt-4o",
      "provider": "openai",
      "status": "succeeded",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "prs": [
    {
      "id": "uuid",
      "number": 123,
      "url": "https://github.com/owner/repo/pull/123",
      "branch": "dursor/abc123",
      "status": "open"
    }
  ]
}
```

### Add Message

```http
POST /tasks/{task_id}/messages
Content-Type: application/json

{
  "role": "user",
  "content": "Add email validation"
}
```

**Parameters**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| role | string | Yes | `user`, `assistant`, `system` |
| content | string | Yes | Message content |

**Response** `201 Created`
```json
{
  "id": "uuid",
  "task_id": "uuid",
  "role": "user",
  "content": "Add email validation",
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

## Runs API

Manage runs (model execution units).

### Create Runs (Parallel Execution)

```http
POST /tasks/{task_id}/runs
Content-Type: application/json

{
  "instruction": "Add input validation to the user form",
  "model_ids": ["uuid1", "uuid2", "uuid3"],
  "base_ref": "main"
}
```

**Parameters**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| instruction | string | Yes | Natural language instruction |
| model_ids | array | Yes | List of model IDs to execute |
| base_ref | string | No | Base branch/commit |

**Response** `201 Created`
```json
{
  "run_ids": ["uuid1", "uuid2", "uuid3"]
}
```

### List Runs

```http
GET /tasks/{task_id}/runs
```

**Response** `200 OK`
```json
[
  {
    "id": "uuid",
    "task_id": "uuid",
    "model_id": "uuid",
    "model_name": "gpt-4o",
    "provider": "openai",
    "instruction": "Add input validation",
    "base_ref": "main",
    "status": "succeeded",
    "summary": "Added validation to 3 files",
    "patch": "--- a/src/form.ts\n+++ b/src/form.ts\n...",
    "files_changed": [
      {
        "path": "src/form.ts",
        "added_lines": 15,
        "removed_lines": 2,
        "patch": "..."
      }
    ],
    "logs": ["Reading files...", "Generating patch..."],
    "warnings": [],
    "error": null,
    "created_at": "2024-01-01T00:00:00Z",
    "started_at": "2024-01-01T00:00:01Z",
    "completed_at": "2024-01-01T00:00:10Z"
  }
]
```

### Get Run

```http
GET /runs/{run_id}
```

**Response** `200 OK`
(Same format as List Runs)

### Cancel Run

```http
POST /runs/{run_id}/cancel
```

**Response** `204 No Content`

---

## PRs API

Manage Pull Requests.

### Create PR

```http
POST /tasks/{task_id}/prs
Content-Type: application/json

{
  "selected_run_id": "uuid",
  "title": "Add input validation",
  "body": "This PR adds validation to the user form."
}
```

**Parameters**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| selected_run_id | string | Yes | ID of the run to adopt |
| title | string | Yes | PR title |
| body | string | No | PR description |

**Response** `201 Created`
```json
{
  "pr_id": "uuid",
  "url": "https://github.com/owner/repo/pull/123",
  "branch": "dursor/abc123",
  "number": 123
}
```

### Update PR

```http
POST /tasks/{task_id}/prs/{pr_id}/update
Content-Type: application/json

{
  "selected_run_id": "uuid",
  "message": "Add email validation"
}
```

**Parameters**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| selected_run_id | string | Yes | ID of the run to apply |
| message | string | No | Commit message |

**Response** `200 OK`
```json
{
  "url": "https://github.com/owner/repo/pull/123",
  "latest_commit": "def456..."
}
```

### Get PR

```http
GET /tasks/{task_id}/prs/{pr_id}
```

**Response** `200 OK`
```json
{
  "id": "uuid",
  "task_id": "uuid",
  "number": 123,
  "url": "https://github.com/owner/repo/pull/123",
  "branch": "dursor/abc123",
  "title": "Add input validation",
  "body": "This PR adds validation...",
  "latest_commit": "def456...",
  "status": "open",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### List PRs

```http
GET /tasks/{task_id}/prs
```

**Response** `200 OK`
```json
[
  {
    "id": "uuid",
    "task_id": "uuid",
    "number": 123,
    "url": "https://github.com/owner/repo/pull/123",
    "branch": "dursor/abc123",
    "title": "Add input validation",
    "body": "...",
    "latest_commit": "def456...",
    "status": "open",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

---

## Error Responses

### 400 Bad Request

```json
{
  "detail": "Invalid request: model_ids cannot be empty"
}
```

### 404 Not Found

```json
{
  "detail": "Task not found"
}
```

### 500 Internal Server Error

```json
{
  "detail": "Internal server error"
}
```

---

## Enums

### Run Status

| Status | Description |
|--------|-------------|
| `queued` | Waiting in queue |
| `running` | Currently executing |
| `succeeded` | Completed successfully |
| `failed` | Execution failed |
| `canceled` | Canceled by user |

### Provider

| Value | Description |
|-------|-------------|
| `openai` | OpenAI API |
| `anthropic` | Anthropic API |
| `google` | Google Generative AI API |
