# dursor - Repository Summary

## What is dursor?

**dursor** is a self-hostable, multi-model parallel coding agent platform. It enables developers to:

1. **Run multiple AI models in parallel** on the same coding task
2. **Compare outputs side-by-side** and choose the best implementation
3. **Iterate through conversation** to refine code changes
4. **Create GitHub Pull Requests** directly from the UI

### Key Value Proposition

- **BYO API Keys**: Use your own OpenAI, Anthropic, or Google API keys
- **Multi-Model Comparison**: Execute the same instruction on GPT-4, Claude, and Gemini simultaneously
- **Conversation-Driven Development**: Chat with AI to iteratively improve code
- **Self-Hosted**: Deploy on your own infrastructure for security and control

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Web UI (Next.js 15)                      │
│   Task Creation → Run Monitoring → Diff Viewing → PR Flow   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    API Server (FastAPI)                      │
│  Routes → Services → Agents/Executors → Storage             │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │  SQLite  │   │   Git    │   │ LLM APIs │
        │ Database │   │Workspaces│   │ + CLIs   │
        └──────────┘   └──────────┘   └──────────┘
```

### Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.11+, Pydantic |
| Database | SQLite with aiosqlite |
| LLM Integration | OpenAI, Anthropic, Google SDKs + Claude/Codex/Gemini CLIs |
| DevOps | Docker, Docker Compose |

---

## Core Concepts

### Entities

| Entity | Description |
|--------|-------------|
| **ModelProfile** | Stored LLM configuration (provider + model + encrypted API key) |
| **Repo** | Cloned Git repository managed by dursor |
| **Task** | A conversation unit representing one development goal |
| **Message** | Chat message within a task (user/assistant/system) |
| **Run** | Single execution of an AI model on a task's instruction |
| **PR** | GitHub Pull Request created from a run's changes |

### Execution Flow

```
1. User selects repository and branch
2. User enters natural language instruction
3. User selects which AI models to run
4. dursor creates parallel "Runs" for each model
5. Each Run generates a unified diff patch
6. User compares results and views diffs
7. User creates PR from the best result
```

---

## Directory Structure

```
dursor/
├── apps/
│   ├── api/                    # FastAPI backend
│   │   └── src/dursor_api/
│   │       ├── main.py         # Entry point
│   │       ├── agents/         # LLM-based patch generators
│   │       ├── executors/      # CLI-based agents (Claude, Codex, Gemini)
│   │       ├── routes/         # API endpoints
│   │       ├── services/       # Business logic
│   │       └── storage/        # Database layer
│   │
│   └── web/                    # Next.js frontend
│       └── src/
│           ├── app/            # Pages (App Router)
│           ├── components/     # React components
│           └── lib/            # API client & utilities
│
├── docs/                       # Documentation
├── workspaces/                 # Git clones (runtime, gitignored)
├── data/                       # SQLite DB (runtime, gitignored)
└── docker-compose.yml
```

---

## API Endpoints

| Resource | Endpoint | Description |
|----------|----------|-------------|
| Models | `GET/POST/DELETE /v1/models` | Manage LLM profiles |
| Repos | `POST /v1/repos/clone` | Clone repositories |
| Repos | `POST /v1/repos/select` | Select existing repo |
| Tasks | `GET/POST /v1/tasks` | Create/list tasks |
| Tasks | `POST /v1/tasks/{id}/messages` | Add chat messages |
| Runs | `POST /v1/tasks/{id}/runs` | Execute AI agents |
| Runs | `GET /v1/runs/{id}` | Get run details & patch |
| Runs | `GET /v1/runs/{id}/logs` | Stream execution logs (SSE) |
| PRs | `POST /v1/tasks/{id}/prs` | Create GitHub PR |
| GitHub | `GET /v1/github/repos` | List accessible repos |

---

## Execution Modes

### 1. Patch Agent (LLM-based)

Uses LLM APIs directly to generate unified diff patches:
- Reads workspace files
- Sends to LLM with system prompt for diff generation
- Parses and validates unified diff output
- Supports: OpenAI, Anthropic, Google

### 2. CLI Executors

Runs external coding agent CLIs:
- **Claude Code** (`claude`): Anthropic's coding CLI
- **Codex CLI** (`codex`): OpenAI's coding CLI
- **Gemini CLI** (`gemini`): Google's coding CLI

CLI executors support:
- Session-based conversation persistence
- Streaming stdout/stderr logs
- Automatic patch extraction from git diff

---

## Security Features

| Feature | Description |
|---------|-------------|
| **API Key Encryption** | Fernet (AES-128) encryption at rest |
| **Forbidden Paths** | Blocks access to `.git`, `.env`, `*.key`, `*.pem` |
| **Workspace Isolation** | Each run executes in separate git worktree |
| **GitHub App Auth** | Uses GitHub App for repository access and PR creation |

---

## Getting Started

### Quick Start (Docker)

```bash
git clone https://github.com/your-org/dursor.git
cd dursor
cp .env.example .env
# Edit .env with your encryption key and GitHub App settings
docker compose up -d
```

Access the UI at `http://localhost:3000`

### Development Setup

```bash
# Backend
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m dursor_api.main

# Frontend (in another terminal)
cd apps/web
npm install
npm run dev
```

---

## Configuration

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `DURSOR_ENCRYPTION_KEY` | Encryption key for API keys |

### Optional (GitHub Integration)

| Variable | Description |
|----------|-------------|
| `DURSOR_GITHUB_APP_ID` | GitHub App ID |
| `DURSOR_GITHUB_APP_PRIVATE_KEY` | GitHub App private key (base64) |
| `DURSOR_GITHUB_APP_INSTALLATION_ID` | GitHub App installation ID |

GitHub App configuration can also be set through the Settings UI.

---

## Current Limitations (v0.1)

- **No shell command execution**: Agents generate patches only (security measure)
- **Single-user**: No multi-tenant isolation
- **In-memory job queue**: Jobs lost on server restart
- **GitHub App required**: PR features require GitHub App setup

---

## Roadmap

| Version | Features |
|---------|----------|
| v0.1 | MVP: Patch generation, PR creation, multi-model parallel runs |
| v0.2 | Docker sandbox for commands, Review agent, PR comment triggers |
| v0.3 | Multi-user support, Cost/budget management, Policy injection |

---

## Documentation Index

- [Architecture](./architecture.md) - Detailed system design
- [API Reference](./api.md) - Complete endpoint documentation
- [Development Guide](./development.md) - Setup and contribution guide
- [Agent System](./agents.md) - LLM integration details
- [UI/UX Improvement Plan](./ui-ux-improvement.md) - Frontend roadmap

---

## Key Design Decisions

1. **Orchestrator Pattern**: dursor manages git operations; agents only edit files
2. **Patch-Only Output**: All changes expressed as unified diffs for reviewability
3. **Async-First**: Backend uses asyncio throughout for concurrent execution
4. **Type-Safe**: Pydantic on backend, strict TypeScript on frontend
5. **Self-Contained**: SQLite + file-based workspaces for easy deployment
