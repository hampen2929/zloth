# Docker commands
build:
	git pull && \
	docker compose down && \
	docker compose up -d --build

log:
	docker compose logs -f

venv:
	uv venv

# Local development - install dependencies
install-api:
	cd apps/api && uv sync --extra dev

install-web:
	cd apps/web && npm install

install: install-api install-web

# Local development - run servers
API_HOST ?= 0.0.0.0

dev-api:
	@API_PORT=$${API_PORT:-$$(python3 -c 'exec("import socket\nfor port in range(8000, 8011):\n    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n    try:\n        s.bind((\"0.0.0.0\", port))\n    except OSError:\n        continue\n    else:\n        s.close()\n        print(port)\n        break\nelse:\n    print(8000)\n")')}; \
	echo "API will run on: http://localhost:$$API_PORT"; \
	cd apps/api && PYTHONPATH=src uvicorn dursor_api.main:app --host $(API_HOST) --port $$API_PORT --reload

dev-web:
	@API_PORT=$${API_PORT:-8000}; \
	API_URL=$${API_URL:-http://localhost:$$API_PORT}; \
	cd apps/web && API_URL=$$API_URL npm run dev

# Run both API and Web servers in parallel
dev:
	@echo "Starting API and Web servers..."
	@API_PORT=$${API_PORT:-$$(python3 -c 'exec("import socket\nfor port in range(8000, 8011):\n    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n    try:\n        s.bind((\"0.0.0.0\", port))\n    except OSError:\n        continue\n    else:\n        s.close()\n        print(port)\n        break\nelse:\n    print(8000)\n")')}; \
	API_URL=$${API_URL:-http://localhost:$$API_PORT}; \
	echo "API will run on: $$API_URL"; \
	trap 'kill 0' EXIT; \
	(cd apps/api && PYTHONPATH=src uvicorn dursor_api.main:app --host $(API_HOST) --port $$API_PORT --reload) & \
	(cd apps/web && API_URL=$$API_URL npm run dev)

# CLI Agents Installation
# Claude Code CLI (Anthropic)
# https://docs.anthropic.com/en/docs/claude-code
install-claude-cli:
	npm install -g @anthropic-ai/claude-code

# OpenAI Codex CLI
# https://github.com/openai/codex
install-codex-cli:
	npm install -g @openai/codex

# Google Gemini CLI
# https://github.com/google-gemini/gemini-cli
install-gemini-cli:
	npm install -g @google/gemini-cli

# Install all CLI agents
install-cli: install-claude-cli install-codex-cli install-gemini-cli
	@echo "All CLI agents installed successfully!"

# Check CLI agent availability
check-cli:
	@echo "Checking CLI agents..."
	@echo -n "Claude Code: " && (which claude && claude --version 2>/dev/null || echo "Not installed")
	@echo -n "Codex: " && (which codex && codex --version 2>/dev/null || echo "Not installed")
	@echo -n "Gemini CLI: " && (which gemini && gemini --version 2>/dev/null || echo "Not installed")
