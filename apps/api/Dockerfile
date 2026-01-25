FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install git for repository operations and curl for healthcheck
RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*

# Install Node.js 22.x for Claude CLI
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Install dependencies
COPY pyproject.toml .
RUN uv pip install --system --no-cache .

# Copy source code
COPY src/ src/

# Create necessary directories
RUN mkdir -p /app/workspaces /app/data

# Set environment variables
ENV PYTHONPATH=/app/src
ENV ZLOTH_BASE_DIR=/app
ENV ZLOTH_WORKSPACES_DIR=/app/workspaces
ENV ZLOTH_DATA_DIR=/app/data

EXPOSE 8000

CMD ["uvicorn", "zloth_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
