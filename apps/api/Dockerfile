FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install git for repository operations
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY pyproject.toml .
RUN uv pip install --system --no-cache .

# Copy source code
COPY src/ src/

# Create necessary directories
RUN mkdir -p /app/workspaces /app/data

# Set environment variables
ENV PYTHONPATH=/app/src
ENV DURSOR_BASE_DIR=/app
ENV DURSOR_WORKSPACES_DIR=/app/workspaces
ENV DURSOR_DATA_DIR=/app/data

EXPOSE 8000

CMD ["uvicorn", "dursor_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
