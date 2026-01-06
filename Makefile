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
	cd apps/api && uv pip install -e ".[dev]"

install-web:
	cd apps/web && npm install

install: install-api install-web

# Local development - run servers
dev-api:
	cd apps/api && PYTHONPATH=src uvicorn dursor_api.main:app --host 0.0.0.0 --port 8000 --reload

dev-web:
	cd apps/web && npm run dev

# Run both API and Web servers in parallel
dev:
	@echo "Starting API and Web servers..."
	@trap 'kill 0' EXIT; \
	(cd apps/api && PYTHONPATH=src uvicorn dursor_api.main:app --host 0.0.0.0 --port 8000 --reload) & \
	(cd apps/web && npm run dev)

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
