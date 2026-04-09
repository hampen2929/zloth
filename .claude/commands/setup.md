# Project Setup

Set up the dursor development environment.

## Instructions

### Prerequisites Check

- Python 3.11+
- Node.js 20+
- Git
- Docker & Docker Compose (optional)

### Backend Setup

```bash
cd apps/api

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### Frontend Setup

```bash
cd apps/web

# Install dependencies
npm install
```

### Environment Configuration

```bash
# Copy example env file
cp .env.example .env

# Required: Generate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Add this to DURSOR_ENCRYPTION_KEY in .env
```

### Database Initialization

The database is auto-created on first API server start.

### Verify Setup

```bash
# Backend
cd apps/api && pytest

# Frontend
cd apps/web && npm run build
```

## User Request

$ARGUMENTS

## Task

1. Check what parts of setup are needed
2. Verify prerequisites are installed
3. Run the appropriate setup commands
4. Configure environment if needed
5. Verify the setup works
6. Report any issues found
