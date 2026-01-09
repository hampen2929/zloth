# something

[![CI](https://github.com/hampen2929/dursor/actions/workflows/ci.yml/badge.svg)](https://github.com/hampen2929/dursor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/hampen2929/dursor.svg?style=social&label=Star)](https://github.com/hampen2929/dursor)
[![GitHub issues](https://img.shields.io/github/issues/hampen2929/dursor.svg)](https://github.com/hampen2929/dursor/issues)
[![GitHub pull requests](https://img.shields.io/github/issues-pr/hampen2929/dursor.svg)](https://github.com/hampen2929/dursor/pulls)

> BYO API Key / Multi-model Parallel Execution / Conversation-driven PR Development

**dursor** is a self-hostable cloud coding agent that lets you:
- Use your own API keys (OpenAI, Anthropic, Google)
- Run multiple models in parallel on the same task
- Compare outputs side-by-side and choose the best
- Create and update PRs through natural conversation

## Features

- **Multi-model Comparison**: Run the same task on GPT-4, Claude, and Gemini simultaneously
- **Visual Diff Viewer**: Compare generated patches side-by-side
- **Conversation-driven**: Iterate on your code through chat, refining the output
- **PR Integration**: Create and update GitHub PRs directly from the UI
- **Self-hosted**: Run locally or on your own infrastructure
- **BYO API Keys**: Securely store and use your own LLM API keys

## Who is dursor for?

dursor is designed for:

- **People who prefer a web-based chat interface**
  - Tired of AI conversations in CLI tools
  - Tired of AI-assisted coding in IDEs
  - Want a simple, intuitive chat experience for code generation

- **People who want to run AI agents on localhost with their own API keys**
  - Full control over your development environment
  - Self-hosted solution that keeps your code and data within your network
  - Works with your existing API keys (BYO API Key)

- **People who want to use multiple AI models**
  - Compare outputs from different models side-by-side
  - Choose the best implementation from multiple options
  - Not locked into a single AI provider

### Comparison Matrix

|  | dursor | Cursor (Cloud Agents) | Cursor (IDE) | AI Coding CLIs (Claude Code, Codex, Gemini) | AI Coding Cloud (Claude Code, Codex, Gemini) |
|---|:---:|:---:|:---:|:---:|:---:|
| Web-based chat interface | ✅ | ✅ | ❌ | ❌ | ✅ |
| On-premises / Localhost | ✅ | ❌ | ✅ | ✅ | ❌ |
| Multiple AI models | ✅ | ✅ | ✅ | ❌ | ❌ |
| BYO API Key | ✅ | ❌ | ✅ | ✅ | ❌ |
| OSS | ✅ | ❌ | ❌ | ✅ | ❌ |
| CLI integration | ✅* | ❌ | ❌ | ✅ | ❌ |
| IDE integration | ❌ | ❌ | ✅ | ❌ | ❌ |

*dursor runs AI Coding CLIs on localhost behind the scenes

> **dursor is the OSS solution that combines a web-based chat interface, localhost deployment, multiple AI models, BYO API Key support, and CLI integration.**

## Quick Start

### Prerequisites

- Python 3.13+
- Node.js 20+
- Git
- GitHub Personal Access Token (for PR operations)

### Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/hampen2929/dursor.git
   cd dursor
   ```

2. **Set up the API server**
   ```bash
   cd apps/api
   uv sync --extra dev
   ```

3. **Set up the web frontend**
   ```bash
   cd apps/web
   npm install
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Start the servers**
   ```bash
   # Terminal 1: API server
   cd apps/api
   uv run python -m dursor_api.main

   # Terminal 2: Web frontend
   cd apps/web
   npm run dev
   ```

6. **Open http://localhost:3000**

### Docker Setup

```bash
# Copy and configure environment
cp .env.example .env
# Edit .env with your settings

# Start services
docker-compose up -d
```

## Usage

1. **Add your API keys** in Settings
2. **Enter a GitHub repository URL** on the home page
3. **Select models** to run in parallel
4. **Enter your instructions** (e.g., "Add input validation to the user form")
5. **Compare outputs** from different models
6. **Create a PR** with your chosen implementation

## Project Structure

```
dursor/
├── apps/
│   ├── api/                    # FastAPI backend
│   │   └── src/dursor_api/
│   │       ├── agents/         # LLM agents (PatchAgent)
│   │       ├── domain/         # Pydantic models
│   │       ├── routes/         # API endpoints
│   │       ├── services/       # Business logic
│   │       └── storage/        # SQLite DAO
│   └── web/                    # Next.js frontend
│       └── src/
│           ├── app/            # Pages (App Router)
│           ├── components/     # React components
│           └── lib/            # API client
├── workspaces/                 # Git clones (gitignored)
├── data/                       # SQLite database (gitignored)
├── docker-compose.yml
└── .env.example
```

## API Endpoints

### Models
- `GET /v1/models` - List model profiles
- `POST /v1/models` - Create model profile
- `DELETE /v1/models/{id}` - Delete model profile

### Repositories
- `POST /v1/repos/clone` - Clone a repository

### Tasks
- `POST /v1/tasks` - Create a task
- `GET /v1/tasks/{id}` - Get task details
- `POST /v1/tasks/{id}/messages` - Add a message

### Runs
- `POST /v1/tasks/{id}/runs` - Create runs (parallel execution)
- `GET /v1/runs/{id}` - Get run details
- `POST /v1/runs/{id}/cancel` - Cancel a run

### Pull Requests
- `POST /v1/tasks/{id}/prs` - Create a PR
- `POST /v1/tasks/{id}/prs/{prId}/update` - Update a PR

## Configuration

| Variable | Description | Required |
|----------|-------------|----------|
| `DURSOR_ENCRYPTION_KEY` | Key for encrypting API keys | Yes |
| `DURSOR_GITHUB_PAT` | GitHub token for PR operations | Yes |
| `DURSOR_DEBUG` | Enable debug mode | No |
| `DURSOR_LOG_LEVEL` | Log level (DEBUG/INFO/WARNING/ERROR) | No |

## Security

- API keys are encrypted at rest using Fernet (AES-128)
- Workspaces are isolated per task
- Agents are restricted to workspace directories
- Forbidden paths (`.git`, `.env`, secrets) are blocked

## Roadmap

### v0.2
- Docker sandbox for command execution (tests, linting)
- GitHub App authentication
- Review/Meta agent for comparing outputs
- PR comment-triggered re-runs

### v0.3
- Multi-user support
- Cost tracking and budget limits
- Policy injection (e.g., MISRA compliance)

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

## License

MIT License - see [LICENSE](LICENSE) for details.
