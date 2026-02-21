# Test Runner

Run tests for the dursor project.

## Instructions

Based on the user's request, run the appropriate tests:

### Backend Tests (FastAPI/Python)

```bash
cd apps/api
source .venv/bin/activate 2>/dev/null || true
pytest $ARGUMENTS
```

Common options:
- `pytest` - Run all tests
- `pytest --cov=dursor_api` - Run with coverage
- `pytest tests/test_specific.py -v` - Run specific test file
- `pytest -k "test_name"` - Run tests matching pattern

### Frontend Tests (Next.js/TypeScript)

```bash
cd apps/web
npm test $ARGUMENTS
```

## User Request

$ARGUMENTS

## Task

1. Determine which tests to run based on the request (backend, frontend, or both)
2. If no specific target is mentioned, ask the user which to run
3. Execute the tests
4. Report results clearly, highlighting any failures
