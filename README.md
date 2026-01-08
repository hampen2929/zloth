# cursor

> BYO API Key / Multi-model Parallel Execution / Conversation-driven PR Development

**cursor** is a self-hostable cloud coding agent that lets you:
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

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Git
- GitHub Personal Access Token (for PR operations)

### Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/cursor.git
   cd cursor
   ```

2. **Set up the API server**
   ```bash
   cd apps/api
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
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
   python -m cursor_api.main

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
cursor/
├── apps/
│   ├── api/                    # FastAPI backend
│   │   └── src/cursor_api/
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
| `CURSOR_ENCRYPTION_KEY` | Key for encrypting API keys | Yes |
| `CURSOR_GITHUB_PAT` | GitHub token for PR operations | Yes |
| `CURSOR_DEBUG` | Enable debug mode | No |
| `CURSOR_LOG_LEVEL` | Log level (DEBUG/INFO/WARNING/ERROR) | No |

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
