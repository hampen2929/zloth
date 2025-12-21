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
