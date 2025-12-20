# CLAUDE.md - dursor Development Context

This file provides context for Claude Code to understand the project.

## Project Overview

**dursor** is a self-hostable multi-model parallel coding agent.

### Concept
- **BYO API Key**: Users bring their own API keys (OpenAI/Anthropic/Google)
- **Multi-model Parallel Execution**: Run the same task on multiple models simultaneously
- **Conversation-driven PR Development**: Grow PRs through chat interaction

### Tech Stack
- **Backend**: FastAPI (Python 3.11+)
- **Frontend**: Next.js 14 (React, TypeScript, Tailwind CSS)
- **Database**: SQLite (aiosqlite)
- **LLM**: OpenAI, Anthropic, Google Generative AI

## Directory Structure

```
dursor/
├── apps/
│   ├── api/                    # FastAPI backend
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   └── src/dursor_api/
│   │       ├── main.py         # FastAPI entrypoint
│   │       ├── config.py       # Configuration (env vars)
│   │       ├── dependencies.py # Dependency Injection
│   │       ├── agents/         # Agent implementations
│   │       │   ├── base.py     # BaseAgent abstract class
│   │       │   ├── llm_router.py # LLM client
│   │       │   └── patch_agent.py # Patch generation agent
│   │       ├── domain/         # Domain models
│   │       │   ├── enums.py    # Provider, RunStatus, etc.
│   │       │   └── models.py   # Pydantic models
│   │       ├── routes/         # API routes
│   │       │   ├── models.py   # /v1/models
│   │       │   ├── repos.py    # /v1/repos
│   │       │   ├── tasks.py    # /v1/tasks
│   │       │   ├── runs.py     # /v1/runs
│   │       │   └── prs.py      # /v1/prs
│   │       ├── services/       # Business logic
│   │       │   ├── crypto_service.py
│   │       │   ├── model_service.py
│   │       │   ├── repo_service.py
│   │       │   ├── run_service.py
│   │       │   └── pr_service.py
│   │       └── storage/        # Data persistence
│   │           ├── schema.sql  # SQLite schema
│   │           ├── db.py       # DB connection
│   │           └── dao.py      # Data Access Objects
│   │
│   └── web/                    # Next.js frontend
│       ├── package.json
│       ├── Dockerfile
│       ├── next.config.js
│       └── src/
│           ├── app/            # App Router
│           │   ├── layout.tsx
│           │   ├── page.tsx    # Home
│           │   ├── settings/   # Settings page
│           │   └── tasks/      # Task page
│           ├── components/     # React components
│           │   ├── ChatPanel.tsx
│           │   ├── RunsPanel.tsx
│           │   ├── RunDetailPanel.tsx
│           │   └── DiffViewer.tsx
│           ├── lib/
│           │   └── api.ts      # API client
│           └── types.ts        # TypeScript types
│
├── docs/                       # Documentation
├── workspaces/                 # Git clones (gitignored)
├── data/                       # SQLite DB (gitignored)
├── docker-compose.yml
├── .env.example
└── CLAUDE.md                   # This file
```

## Key Entities

| Entity | Description |
|--------|-------------|
| **ModelProfile** | LLM provider + model + encrypted API key |
| **Repo** | Cloned Git repository |
| **Task** | Conversation unit (1 task = 1 goal) |
| **Message** | Chat message within a Task |
| **Run** | Model execution unit (parallel within Task) |
| **PR** | Created Pull Request |

## API Design

### Endpoints Overview

```
# Models
GET    /v1/models              # List
POST   /v1/models              # Create
DELETE /v1/models/{id}         # Delete

# Repos
POST   /v1/repos/clone         # Clone

# Tasks
GET    /v1/tasks               # List
POST   /v1/tasks               # Create
GET    /v1/tasks/{id}          # Get details
POST   /v1/tasks/{id}/messages # Add message

# Runs
POST   /v1/tasks/{id}/runs     # Create parallel runs
GET    /v1/tasks/{id}/runs     # List
GET    /v1/runs/{id}           # Get details
POST   /v1/runs/{id}/cancel    # Cancel

# PRs
POST   /v1/tasks/{id}/prs      # Create PR
POST   /v1/tasks/{id}/prs/{prId}/update  # Update PR
GET    /v1/tasks/{id}/prs/{prId}         # Get details
```

## Agent Interface

### AgentRequest (Input)
```python
class AgentRequest:
    workspace_path: str      # Working directory
    base_ref: str           # Base branch/commit
    instruction: str        # Natural language instruction
    context: dict | None    # Additional context
    constraints: AgentConstraints  # Constraints (forbidden paths, etc.)
```

### AgentResult (Output)
```python
class AgentResult:
    summary: str            # Human-readable summary
    patch: str              # Unified diff
    files_changed: list     # List of changed files
    logs: list[str]         # Operation logs
    warnings: list[str]     # Warnings
```

## Development Commands

### Backend
```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Start dev server
python -m dursor_api.main

# Test
pytest

# Lint
ruff check src/
mypy src/
```

### Frontend
```bash
cd apps/web
npm install

# Start dev server
npm run dev

# Build
npm run build

# Lint
npm run lint
```

### Docker
```bash
# Start
docker compose up -d --build

# View logs
docker compose logs -f

# Stop
docker compose down
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DURSOR_ENCRYPTION_KEY` | API key encryption key | Yes |
| `DURSOR_GITHUB_PAT` | GitHub PAT (for PR operations) | Yes |
| `DURSOR_DEBUG` | Debug mode | No |
| `DURSOR_LOG_LEVEL` | Log level | No |

## Coding Conventions

### Python
- **Formatter**: ruff
- **Type checker**: mypy (strict mode)
- **Line length**: 100 characters
- **Docstring**: Google style

### TypeScript
- **Formatter**: Prettier (Next.js default)
- **Linter**: ESLint
- **Types**: Use strict type definitions

## Important Design Decisions

### v0.1 Scope Limitations
1. **No command execution**: Shell commands disabled for security in v0.1
2. **Patch output only**: Agents output only Unified diff format patches
3. **GitHub PAT auth**: v0.1 uses PAT (GitHub App in v0.2)

### Security
- API keys encrypted at rest using Fernet (AES-128)
- Workspaces isolated per execution
- Forbidden paths (`.git`, `.env`, etc.) blocked

## Roadmap

### v0.2
- [ ] Docker sandbox for command execution
- [ ] GitHub App authentication
- [ ] Review/Meta agent
- [ ] PR comment-triggered re-runs

### v0.3
- [ ] Multi-user support
- [ ] Cost and budget management
- [ ] Policy injection

## Troubleshooting

### Common Issues

**Q: Docker build fails**
A: Try `docker compose build --no-cache`

**Q: API keys not saving**
A: Check that `DURSOR_ENCRYPTION_KEY` is set

**Q: Cannot create PR**
A: Verify `DURSOR_GITHUB_PAT` has `repo` scope
