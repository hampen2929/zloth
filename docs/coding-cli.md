# Coding CLI Integration

## Overview

dursor delegates actual code generation to external coding CLIs (Codex, Claude Code, Gemini CLI) running inside Docker containers. This architecture provides:

- **Isolation**: Each run executes in a dedicated container
- **Security**: Sandboxed environment prevents malicious code execution
- **Flexibility**: Support for multiple coding CLIs with unified interface
- **Reproducibility**: Consistent execution environment

## System Architecture

```mermaid
flowchart TB
    subgraph API["API Server (FastAPI)"]
        RS[RunService]
        CS[ContainerService]
        GS[GitService]
    end

    subgraph DockerHost["Docker Host"]
        subgraph Container1["Container (Run 1)"]
            CLI1[Coding CLI<br/>Claude Code]
            WS1[Workspace]
        end
        subgraph Container2["Container (Run 2)"]
            CLI2[Coding CLI<br/>Codex]
            WS2[Workspace]
        end
        subgraph Container3["Container (Run N)"]
            CLI3[Coding CLI<br/>Gemini CLI]
            WS3[Workspace]
        end
    end

    subgraph External["External Services"]
        LLM[LLM APIs<br/>OpenAI/Anthropic/Google]
        GH[GitHub]
    end

    RS --> CS
    RS --> GS
    CS -->|create| Container1
    CS -->|create| Container2
    CS -->|create| Container3
    CLI1 --> LLM
    CLI2 --> LLM
    CLI3 --> LLM
    GS --> GH
```

## Execution Flow

### Complete Lifecycle

```mermaid
sequenceDiagram
    participant U as User
    participant A as API Server
    participant CS as ContainerService
    participant GS as GitService
    participant D as Docker
    participant CLI as Coding CLI
    participant GH as GitHub

    U->>A: POST /tasks/{id}/runs

    rect rgb(230, 240, 255)
        Note over A,D: 1. Workspace Creation
        A->>GS: Create feature branch
        GS->>GS: git checkout -b feature/run-{id}
        A->>CS: Create container
        CS->>D: docker run (with workspace mount)
        D-->>CS: Container ID
    end

    rect rgb(255, 240, 230)
        Note over CS,CLI: 2. Coding CLI Execution
        CS->>CLI: Execute with instruction
        CLI->>CLI: Analyze codebase
        CLI->>CLI: Generate changes
        CLI-->>CS: Exit (changes in workspace)
    end

    rect rgb(230, 255, 240)
        Note over A,GH: 3. Post-processing
        A->>GS: Commit changes
        GS->>GS: git add -A && git commit
        A->>GS: Push to remote
        GS->>GH: git push origin feature/run-{id}
        A->>A: Generate summary
    end

    A-->>U: RunResult (summary, branch, diff)
```

### Parallel Execution

```mermaid
flowchart LR
    subgraph Input
        I[Instruction]
    end

    subgraph Parallel["Parallel Container Execution"]
        direction TB
        C1[Container 1<br/>Claude Code]
        C2[Container 2<br/>Codex]
        C3[Container 3<br/>Gemini CLI]
    end

    subgraph Output
        B1[Branch 1<br/>run-xxx-claude]
        B2[Branch 2<br/>run-xxx-codex]
        B3[Branch 3<br/>run-xxx-gemini]
    end

    I --> C1
    I --> C2
    I --> C3
    C1 --> B1
    C2 --> B2
    C3 --> B3
```

## Supported Coding CLIs

| CLI | Provider | Model | Environment Variable |
|-----|----------|-------|---------------------|
| Claude Code | Anthropic | Claude 3.5/4 | `ANTHROPIC_API_KEY` |
| Codex | OpenAI | GPT-4 / Codex | `OPENAI_API_KEY` |
| Gemini CLI | Google | Gemini Pro | `GOOGLE_API_KEY` |

## Container Configuration

### Base Image

```dockerfile
# Dockerfile.coding-cli
FROM ubuntu:22.04

# Install common dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    nodejs \
    npm \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install coding CLIs
RUN npm install -g @anthropic-ai/claude-code \
    && npm install -g @openai/codex \
    && pip3 install gemini-cli

# Set up workspace
WORKDIR /workspace

# Entry point script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
```

### Container Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Creating: docker create
    Creating --> Running: docker start
    Running --> Executing: CLI running
    Executing --> Committing: Changes complete
    Committing --> Pushing: git commit
    Pushing --> Cleanup: git push
    Cleanup --> [*]: docker rm

    Executing --> Failed: Error/Timeout
    Failed --> Cleanup
```

## Service Interfaces

### ContainerService

```python
class ContainerService:
    """Manages Docker containers for coding CLI execution"""

    async def create_container(
        self,
        run_id: str,
        cli_type: CodingCLI,
        workspace_path: str,
        api_key: str,
    ) -> ContainerInfo:
        """Create a new container for code generation"""
        pass

    async def execute(
        self,
        container_id: str,
        instruction: str,
        timeout: int = 600,
    ) -> ExecutionResult:
        """Execute coding CLI with instruction"""
        pass

    async def cleanup(self, container_id: str) -> None:
        """Remove container and temporary resources"""
        pass
```

### GitService

```python
class GitService:
    """Manages Git operations for workspaces"""

    async def create_branch(
        self,
        workspace_path: str,
        branch_name: str,
        base_ref: str = "main",
    ) -> None:
        """Create a new feature branch"""
        pass

    async def commit_changes(
        self,
        workspace_path: str,
        message: str,
    ) -> str:
        """Stage and commit all changes, returns commit SHA"""
        pass

    async def push_branch(
        self,
        workspace_path: str,
        branch_name: str,
    ) -> None:
        """Push branch to remote origin"""
        pass

    async def get_diff(
        self,
        workspace_path: str,
        base_ref: str,
    ) -> str:
        """Get unified diff from base ref"""
        pass
```

## Execution Details

### 1. Workspace Creation

```mermaid
flowchart TD
    A[Start] --> B[Clone/Copy Repository]
    B --> C[Create Feature Branch]
    C --> D{Branch exists?}
    D -->|Yes| E[Checkout existing]
    D -->|No| F[Create new branch]
    E --> G[Create Docker Container]
    F --> G
    G --> H[Mount Workspace Volume]
    H --> I[Inject API Key as Env]
    I --> J[Container Ready]
```

### Branch Naming Convention

```
feature/run-{run_id}-{cli_type}

Examples:
- feature/run-abc123-claude
- feature/run-abc123-codex
- feature/run-abc123-gemini
```

### 2. Coding CLI Execution

```mermaid
flowchart TD
    A[Container Start] --> B[Load Instruction]
    B --> C[Initialize CLI]
    C --> D[Read Codebase Context]
    D --> E[Send to LLM API]
    E --> F[Receive Response]
    F --> G[Apply Changes to Files]
    G --> H{More changes?}
    H -->|Yes| E
    H -->|No| I[Exit Container]
```

### CLI Invocation Commands

```bash
# Claude Code
claude-code --instruction "$INSTRUCTION" --workspace /workspace --non-interactive

# Codex
codex --prompt "$INSTRUCTION" --dir /workspace --auto-apply

# Gemini CLI
gemini-cli code --task "$INSTRUCTION" --path /workspace --apply
```

### Timeout and Resource Limits

```yaml
container:
  timeout: 600        # 10 minutes max
  memory: 4g          # 4GB RAM limit
  cpu: 2              # 2 CPU cores
  network: limited    # Only LLM API access
```

### 3. Post-processing

```mermaid
flowchart TD
    A[CLI Complete] --> B[Check Exit Code]
    B -->|Success| C[Stage Changes]
    B -->|Failure| L[Log Error]
    C --> D[Generate Commit Message]
    D --> E[Create Commit]
    E --> F[Push to Remote]
    F --> G{Push Success?}
    G -->|Yes| H[Generate Summary]
    G -->|No| I[Retry with Backoff]
    I --> F
    H --> J[Store Result]
    J --> K[Cleanup Container]
    L --> K
```

### Commit Message Format

```
[dursor] {summary}

Run ID: {run_id}
CLI: {cli_type}
Instruction: {instruction_truncated}

Generated by dursor coding agent
```

### Summary Generation

```python
class SummaryGenerator:
    """Generate human-readable summary of changes"""

    def generate(
        self,
        diff: str,
        instruction: str,
        cli_type: str,
    ) -> RunSummary:
        return RunSummary(
            files_changed=self._count_files(diff),
            lines_added=self._count_additions(diff),
            lines_removed=self._count_deletions(diff),
            description=self._summarize_changes(diff),
            branch=f"feature/run-{run_id}-{cli_type}",
            commit_sha=commit_sha,
        )
```

## Error Handling

### Retry Strategy

```mermaid
flowchart TD
    A[Operation] --> B{Success?}
    B -->|Yes| C[Continue]
    B -->|No| D{Retryable?}
    D -->|No| E[Fail with Error]
    D -->|Yes| F{Retry count < 3?}
    F -->|No| E
    F -->|Yes| G[Exponential Backoff]
    G --> A
```

### Error Categories

| Error Type | Retryable | Action |
|------------|-----------|--------|
| Container creation failed | Yes | Retry with backoff |
| CLI timeout | No | Report timeout error |
| Git push rejected | Yes | Pull & retry |
| API rate limit | Yes | Wait & retry |
| Invalid instruction | No | Return validation error |

## Security Considerations

### Container Isolation

```mermaid
flowchart TB
    subgraph Host["Host System"]
        API[API Server]
        Vol[Volume Mount<br/>Read-Write]
    end

    subgraph Container["Docker Container"]
        CLI[Coding CLI]
        WS[/workspace]
        Net[Network<br/>Limited]
    end

    API -.->|Control| Container
    Vol <-->|Files| WS
    Net -->|HTTPS only| LLM[LLM APIs]
```

### Security Measures

1. **Network Isolation**: Containers only access whitelisted LLM API endpoints
2. **Volume Mounts**: Limited to workspace directory only
3. **No Privileged Mode**: Containers run as non-root user
4. **Resource Limits**: CPU, memory, and time constraints
5. **API Key Injection**: Keys passed as environment variables, not stored in container

### Forbidden Operations

```python
BLOCKED_COMMANDS = [
    "rm -rf /",
    "curl | bash",
    "wget | sh",
    "sudo",
    "chmod 777",
]

FORBIDDEN_PATHS = [
    ".git/config",
    ".env",
    "*.pem",
    "*.key",
    "credentials.*",
]
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DURSOR_DOCKER_HOST` | Docker daemon socket | `unix:///var/run/docker.sock` |
| `DURSOR_CONTAINER_IMAGE` | Base image for CLI containers | `dursor/coding-cli:latest` |
| `DURSOR_CONTAINER_TIMEOUT` | Max execution time (seconds) | `600` |
| `DURSOR_CONTAINER_MEMORY` | Memory limit | `4g` |
| `DURSOR_CONTAINER_CPU` | CPU limit | `2` |

### Docker Compose Extension

```yaml
# docker-compose.override.yml
services:
  api:
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - DURSOR_DOCKER_HOST=unix:///var/run/docker.sock

  coding-cli:
    build:
      context: ./docker/coding-cli
      dockerfile: Dockerfile
    image: dursor/coding-cli:latest
```

## Monitoring and Logging

### Container Logs

```python
async def stream_logs(container_id: str) -> AsyncIterator[str]:
    """Stream container logs in real-time"""
    async for line in docker.logs(container_id, stream=True):
        yield line.decode()
```

### Metrics

```mermaid
flowchart LR
    C[Container] -->|Logs| L[Log Aggregator]
    C -->|Metrics| M[Metrics Collector]
    L --> D[Dashboard]
    M --> D
```

| Metric | Description |
|--------|-------------|
| `container_execution_time` | Time spent in container |
| `container_memory_usage` | Peak memory usage |
| `cli_success_rate` | Success rate by CLI type |
| `git_push_retries` | Number of push retries |

## Roadmap

### Current (v0.2)

- [x] Basic Docker container support
- [x] Claude Code integration
- [ ] Codex integration
- [ ] Gemini CLI integration
- [ ] Container pooling for faster startup

### Future (v0.3+)

- [ ] Custom container images per repository
- [ ] Persistent container sessions
- [ ] Real-time log streaming to UI
- [ ] Container resource autoscaling
