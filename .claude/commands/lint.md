# Code Quality Checker

Run linting and type checking for the dursor project.

## Instructions

Based on the user's request, run the appropriate checks:

### Backend (Python)

```bash
cd apps/api
source .venv/bin/activate 2>/dev/null || true

# Lint with ruff
ruff check src/

# Format check
ruff format --check src/

# Type check
mypy src/
```

To auto-fix issues:
```bash
ruff check --fix src/
ruff format src/
```

### Frontend (TypeScript)

```bash
cd apps/web

# ESLint
npm run lint

# Type check
npx tsc --noEmit
```

## User Request

$ARGUMENTS

## Task

1. Determine which checks to run (backend, frontend, or both)
2. If no specific target is mentioned, run both
3. Execute the checks
4. Report issues found and suggest fixes
5. If requested, auto-fix issues that can be automatically resolved
