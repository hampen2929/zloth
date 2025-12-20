# Development Guide

## Environment Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- Git
- Docker & Docker Compose (optional)

### Backend (FastAPI)

```bash
cd apps/api

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies (including dev)
pip install -e ".[dev]"

# Configure environment
cp ../../.env.example ../../.env
# Edit .env

# Start dev server
python -m dursor_api.main
# or
uvicorn dursor_api.main:app --reload --port 8000
```

### Frontend (Next.js)

```bash
cd apps/web

# Install dependencies
npm install

# Start dev server
npm run dev
```

### Docker Compose

```bash
# Configure environment
cp .env.example .env
# Edit .env

# Build & start
docker compose up -d --build

# View logs
docker compose logs -f api
docker compose logs -f web

# Stop
docker compose down
```

## Code Quality

### Python

```bash
cd apps/api

# Lint
ruff check src/

# Auto-fix
ruff check --fix src/

# Format
ruff format src/

# Type check
mypy src/
```

### TypeScript

```bash
cd apps/web

# Lint
npm run lint

# Type check
npx tsc --noEmit
```

## Testing

### Backend

```bash
cd apps/api

# Run all tests
pytest

# With coverage
pytest --cov=dursor_api

# Specific test
pytest tests/test_runs.py -v
```

### Frontend

```bash
cd apps/web

# Run tests (after setup)
npm test
```

## Debugging

### Backend

**VSCode launch.json:**
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["dursor_api.main:app", "--reload", "--port", "8000"],
      "cwd": "${workspaceFolder}/apps/api",
      "envFile": "${workspaceFolder}/.env"
    }
  ]
}
```

**Change log level:**
```bash
DURSOR_LOG_LEVEL=DEBUG python -m dursor_api.main
```

### Frontend

**React Developer Tools:**
Install the Chrome extension

**API call inspection:**
Browser DevTools > Network tab

## Adding New Features

### 1. New API Endpoint

```bash
# 1. Add domain model
apps/api/src/dursor_api/domain/models.py

# 2. Update schema (if needed)
apps/api/src/dursor_api/storage/schema.sql

# 3. Add DAO
apps/api/src/dursor_api/storage/dao.py

# 4. Add service
apps/api/src/dursor_api/services/new_service.py

# 5. Add route
apps/api/src/dursor_api/routes/new_route.py

# 6. Register router in main.py
apps/api/src/dursor_api/main.py

# 7. Add DI in dependencies.py
apps/api/src/dursor_api/dependencies.py
```

### 2. New LLM Provider

```python
# apps/api/src/dursor_api/agents/llm_router.py

# 1. Add enum
class Provider(str, Enum):
    NEW_PROVIDER = "new_provider"

# 2. Add method to LLMClient
async def _generate_new_provider(self, messages, system):
    # Implementation
    pass

# 3. Add branch to generate method
elif self.config.provider == Provider.NEW_PROVIDER:
    return await self._generate_new_provider(messages, system)
```

### 3. New Frontend Page

```bash
# 1. Create page
apps/web/src/app/new-page/page.tsx

# 2. Create component
apps/web/src/components/NewComponent.tsx

# 3. Add type definitions
apps/web/src/types.ts

# 4. Add API calls
apps/web/src/lib/api.ts
```

## Database Migration

v0.1 uses SQLite with manual migration.

```bash
# 1. Edit schema.sql
apps/api/src/dursor_api/storage/schema.sql

# 2. Delete existing DB (dev environment)
rm data/dursor.db

# 3. Restart to auto-create
python -m dursor_api.main
```

### Production Migration

```sql
-- Example: Add new column
ALTER TABLE runs ADD COLUMN new_column TEXT;
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DURSOR_HOST` | API server host | `0.0.0.0` |
| `DURSOR_PORT` | API server port | `8000` |
| `DURSOR_DEBUG` | Debug mode | `false` |
| `DURSOR_LOG_LEVEL` | Log level | `INFO` |
| `DURSOR_ENCRYPTION_KEY` | Encryption key | Required |
| `DURSOR_GITHUB_PAT` | GitHub PAT | Required (for PR creation) |
| `DURSOR_WORKSPACES_DIR` | Workspaces path | `./workspaces` |
| `DURSOR_DATA_DIR` | Data directory | `./data` |

## Troubleshooting

### Common Issues

**Q: `ModuleNotFoundError: No module named 'dursor_api'`**

A: Activate virtual environment and run `pip install -e .`

**Q: Frontend cannot connect to API**

A:
1. Check if API server is running
2. Verify rewrites config in `next.config.js`
3. Check for CORS errors

**Q: SQLite error: `no such table`**

A: Delete `data/dursor.db` and restart

**Q: Git clone fails**

A:
1. Verify repository URL is correct
2. For private repos, check PAT has permissions

**Q: Cannot create PR**

A:
1. Check `DURSOR_GITHUB_PAT` is set
2. Verify PAT has `repo` scope
3. Check push permission to repository

## Performance

### Recommended Settings

```bash
# Increase workers (production)
uvicorn dursor_api.main:app --workers 4

# Timeout settings
uvicorn dursor_api.main:app --timeout-keep-alive 120
```

### Profiling

```python
# Profile with cProfile
python -m cProfile -o profile.stats -m dursor_api.main
```
