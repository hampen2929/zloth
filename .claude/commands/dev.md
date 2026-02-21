# Development Server

Start development servers for the dursor project.

## Instructions

### Backend (FastAPI)

```bash
cd apps/api
source .venv/bin/activate 2>/dev/null || true
python -m dursor_api.main
# or with reload:
# uvicorn dursor_api.main:app --reload --port 8000
```

Server runs at: http://localhost:8000

### Frontend (Next.js)

```bash
cd apps/web
npm run dev
```

Server runs at: http://localhost:3000

### Both (Docker Compose)

```bash
docker compose up -d --build
```

- API: http://localhost:8000
- Web: http://localhost:3000

## User Request

$ARGUMENTS

## Task

1. Determine which server to start (backend, frontend, both, or docker)
2. If no specific target is mentioned, ask the user
3. Start the appropriate server(s)
4. For long-running processes, use background execution
5. Report the URLs where services are available
