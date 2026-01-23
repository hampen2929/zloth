# Architecture Design

## System Overview

```mermaid
flowchart TB
    subgraph UI["Web UI (Next.js)"]
        Home[Home Page]
        Settings[Settings]
        TaskPage[Task Page]
        Kanban[Kanban Board]
        Backlog[Backlog]
        Metrics[Metrics]
    end

    subgraph API["API Server (FastAPI)"]
        Routes[Routes]
        Services[Services]
        Roles[Role Services]
        Executors[Executors]
        Agents[Agents]
        Storage[Storage]
        Queue[Queue]
    end

    subgraph External["External Services"]
        SQLite[(SQLite DB)]
        Workspace[Workspace<br/>Clone/Worktree]
        LLM[LLM APIs<br/>OpenAI/Anthropic/Google]
        CLI[CLI Tools<br/>Claude/Codex/Gemini]
        GitHub[GitHub API]
    end

    UI -->|HTTP/REST| API
    Routes --> Services
    Services --> Roles
    Roles --> Executors
    Roles --> Agents
    Services --> Storage
    Services --> Queue
    Storage --> SQLite
    Executors --> Workspace
    Executors --> CLI
    Agents --> Workspace
    Agents --> LLM
    Services --> GitHub
```

## Layer Architecture

### 1. Routes Layer (`routes/`)

Receives HTTP requests and delegates to appropriate services.

```python
# Example: routes/runs.py
@router.post("/tasks/{task_id}/runs")
async def create_runs(
    task_id: str,
    data: RunCreate,
    run_service: RunService = Depends(get_run_service),
) -> RunsCreated:
    runs = await run_service.create_runs(task_id, data)
    return RunsCreated(run_ids=[r.id for r in runs])
```

**Responsibilities**:
- Request validation (Pydantic)
- Authentication/Authorization (planned for v0.2)
- Response formatting

**Available Endpoints**:
| Category | Endpoints |
|----------|-----------|
| Models | GET/POST/DELETE `/v1/models` |
| Repos | POST `/v1/repos/clone` |
| Tasks | GET/POST `/v1/tasks`, `/v1/tasks/{id}/messages` |
| Runs | POST `/v1/tasks/{id}/runs`, GET `/v1/runs/{id}` |
| PRs | POST `/v1/tasks/{id}/prs`, PUT `/v1/prs/{id}` |
| Reviews | POST `/v1/tasks/{id}/reviews`, GET `/v1/reviews/{id}` |
| Breakdown | POST `/v1/breakdown` |
| Kanban | GET `/v1/kanban` |
| Backlog | GET/POST/PUT/DELETE `/v1/backlog` |

### 2. Services Layer (`services/`)

Implements business logic.

```python
# Example: services/run_service.py
class RunService(BaseRoleService[Run, RunCreate, RunResult]):
    async def create_runs(self, task_id: str, data: RunCreate) -> list[Run]:
        # 1. Verify task exists
        # 2. Create Run records for each model
        # 3. Enqueue for execution
        # 4. Return run list
```

**Core Services**:
| Service | Description |
|---------|-------------|
| `RunService` | Implementation role - code generation |
| `ReviewService` | Review role - code review execution |
| `BreakdownService` | Breakdown role - task decomposition |
| `PRService` | Pull request creation/management |
| `WorkspaceService` | Clone-based workspace isolation |
| `GitService` | Centralized git operations |
| `AgenticOrchestrator` | Autonomous development cycle |
| `CIPollingService` | CI status polling |
| `GithubService` | GitHub API integration |
| `CryptoService` | API key encryption |

### 3. Role Services (`roles/`)

All AI roles inherit from `BaseRoleService` for consistent execution patterns.

```mermaid
classDiagram
    class BaseRoleService~TRecord,TCreate,TResult~ {
        <<abstract>>
        #dao: BaseDAO
        #queue: RoleQueueAdapter
        #output_manager: OutputManager
        +create() TRecord
        +get() TRecord | None
        +list_by_task() list~TRecord~
        +enqueue_execution() None
        +cancel_execution() bool
        #_execute()* TResult
        #publish_log() Awaitable~None~
    }

    class RunService {
        -executors: dict
        +create_runs() list~Run~
        #_execute() RunResult
    }

    class ReviewService {
        -executors: dict
        +create_review() Review
        #_execute() ReviewResult
    }

    class BreakdownService {
        -executors: dict
        +create_breakdown() TaskBreakdownResponse
        #_execute() BreakdownResult
    }

    BaseRoleService <|-- RunService
    BaseRoleService <|-- ReviewService
    BaseRoleService <|-- BreakdownService
```

**Role Registry**:
```python
# roles/registry.py
RoleRegistry.register("implementation", RunService)
RoleRegistry.register("review", ReviewService)
RoleRegistry.register("breakdown", BreakdownService)
```

### 4. Executors Layer (`executors/`)

CLI tool integration for code generation.

```mermaid
classDiagram
    class BaseExecutor {
        <<abstract>>
        +execute(worktree_path, instruction, constraints, on_output, resume_session_id) ExecutorResult
        #_parse_diff() str
        #_build_instruction_with_constraints() str
        #_generate_summary() str
    }

    class ClaudeCodeExecutor {
        -cli_path: str
        +execute() ExecutorResult
        -_parse_stream_json() ExecutorResult
    }

    class CodexExecutor {
        -cli_path: str
        +execute() ExecutorResult
    }

    class GeminiExecutor {
        -cli_path: str
        +execute() ExecutorResult
    }

    class ExecutorResult {
        +success: bool
        +summary: str
        +patch: str
        +files_changed: list~FileDiff~
        +logs: list~str~
        +warnings: list~str~
        +error: str | None
        +session_id: str | None
    }

    BaseExecutor <|-- ClaudeCodeExecutor
    BaseExecutor <|-- CodexExecutor
    BaseExecutor <|-- GeminiExecutor
    BaseExecutor --> ExecutorResult
```

**Executor Types**:
| Type | Tool | Use Case |
|------|------|----------|
| `PATCH_AGENT` | LLM API | Direct API-based patch generation |
| `CLAUDE_CODE` | Claude Code CLI | Session-persistent code generation |
| `CODEX_CLI` | Codex CLI | Review-focused operations |
| `GEMINI_CLI` | Gemini CLI | Multi-modal code generation |

### 5. Agents Layer (`agents/`)

LLM interaction and patch generation via direct API calls.

```mermaid
classDiagram
    class BaseAgent {
        <<abstract>>
        +run(request) AgentResult
        +validate_request(request) list~str~
    }

    class PatchAgent {
        -llm_client: LLMClient
        +run(request) AgentResult
        -_gather_files()
        -_build_prompt()
        -_extract_patch()
        -_parse_patch()
    }

    class LLMRouter {
        -_clients: dict
        +get_client(config) LLMClient
    }

    class LLMClient {
        -config: LLMConfig
        +generate(messages, system) str
        -_generate_openai()
        -_generate_anthropic()
        -_generate_google()
    }

    BaseAgent <|-- PatchAgent
    PatchAgent --> LLMClient
    LLMRouter --> LLMClient
```

**Agent Interface**:
```python
@dataclass
class AgentRequest:
    workspace_path: str      # Working directory
    base_ref: str           # Base branch/commit
    instruction: str        # Natural language instruction
    context: dict | None    # Additional context
    constraints: AgentConstraints  # Constraints (forbidden paths, etc.)

@dataclass
class AgentResult:
    summary: str            # Human-readable summary
    patch: str              # Unified diff
    files_changed: list     # List of changed files
    logs: list[str]         # Operation logs
    warnings: list[str]     # Warnings

@dataclass
class AgentConstraints:
    max_files_changed: int | None
    forbidden_paths: list[str]      # .git, .env, *.key, etc.
    forbidden_commands: list[str]   # git commit, push, etc.
    allowed_git_commands: list[str] # git status, diff, log, etc.

    def to_prompt(self) -> str:
        """Inject constraints into agent prompt"""
```

### 6. Storage Layer (`storage/`)

Data persistence with SQLite.

```mermaid
classDiagram
    class Database {
        -db_path: Path
        -_connection: Connection
        +connect()
        +disconnect()
        +initialize()
    }

    class ModelProfileDAO {
        +create()
        +get()
        +list()
        +delete()
    }

    class RepoDAO {
        +create()
        +get()
        +find_by_url()
    }

    class TaskDAO {
        +create()
        +get()
        +list()
        +update_kanban_status()
    }

    class RunDAO {
        +create()
        +get()
        +list()
        +update_status()
    }

    class PRDAO {
        +create()
        +get()
        +list()
        +update()
    }

    class ReviewDAO {
        +create()
        +get()
        +list()
        +update_status()
    }

    class BacklogDAO {
        +create()
        +get()
        +list()
        +promote_to_task()
    }

    class AgenticRunDAO {
        +create()
        +get()
        +update_phase()
    }

    Database <-- ModelProfileDAO
    Database <-- RepoDAO
    Database <-- TaskDAO
    Database <-- RunDAO
    Database <-- PRDAO
    Database <-- ReviewDAO
    Database <-- BacklogDAO
    Database <-- AgenticRunDAO
```

## Data Flow

### 1. Run Creation to Completion

```mermaid
sequenceDiagram
    participant U as User
    participant A as API
    participant RS as RunService
    participant Q as RoleQueueAdapter
    participant EX as Executor
    participant CLI as CLI Tool

    U->>A: POST /tasks/{id}/runs
    A->>RS: create_runs()
    RS->>RS: Create Run records (QUEUED)
    RS->>Q: enqueue_execution(run_id)
    RS-->>A: return run_ids
    A-->>U: 201 Created

    Q->>RS: _execute_run()
    RS->>RS: Update status (RUNNING)
    RS->>RS: Create workspace (clone)
    RS->>EX: execute(workspace, instruction)
    EX->>CLI: Run CLI tool
    CLI-->>EX: output stream
    EX->>EX: Parse diff
    EX-->>RS: ExecutorResult
    RS->>RS: Git commit & push branch
    RS->>RS: Update status (SUCCEEDED)
    RS->>RS: Cleanup workspace
```

### 2. Review Flow

```mermaid
sequenceDiagram
    participant U as User
    participant A as API
    participant RVS as ReviewService
    participant EX as CodexExecutor
    participant CLI as Codex CLI

    U->>A: POST /tasks/{id}/reviews
    A->>RVS: create_review()
    RVS->>RVS: Create Review record (QUEUED)
    RVS->>RVS: Get target run diffs
    RVS->>EX: execute(workspace, review_instruction)
    EX->>CLI: Run Codex review
    CLI-->>EX: Review output (JSON)
    EX-->>RVS: ExecutorResult
    RVS->>RVS: Parse review feedbacks
    RVS->>RVS: Save ReviewFeedbackItems
    RVS->>RVS: Update status (SUCCEEDED)
    RVS-->>A: ReviewResult
    A-->>U: Review with feedbacks
```

### 3. PR Creation Flow

```mermaid
sequenceDiagram
    participant U as User
    participant A as API
    participant PS as PRService
    participant GH as GitHub API

    U->>A: POST /tasks/{id}/prs
    A->>PS: create()
    PS->>PS: Get Run with pre-pushed branch
    PS->>PS: Generate PR title/description (LLM)
    PS->>GH: Create PR via API
    GH-->>PS: PR number, URL
    PS->>PS: Save PR record
    PS-->>A: PRCreated
    A-->>U: 201 Created
```

### 4. Agentic Execution Flow

```mermaid
stateDiagram-v2
    [*] --> CODING
    CODING --> WAITING_CI: Run completed
    WAITING_CI --> REVIEWING: CI passed
    WAITING_CI --> FIXING_CI: CI failed
    FIXING_CI --> WAITING_CI: Fix run completed
    REVIEWING --> MERGE_CHECK: Review approved
    REVIEWING --> FIXING_REVIEW: Review rejected
    FIXING_REVIEW --> REVIEWING: Fix run completed
    MERGE_CHECK --> MERGING: All checks pass
    MERGE_CHECK --> AWAITING_HUMAN: Needs approval (SEMI_AUTO)
    AWAITING_HUMAN --> MERGING: Human approved
    MERGING --> COMPLETED: Merge success
    MERGING --> FAILED: Merge failed
    CODING --> FAILED: Error
    FIXING_CI --> FAILED: Max iterations
    FIXING_REVIEW --> FAILED: Max iterations
```

**Coding Modes**:
| Mode | Description |
|------|-------------|
| `INTERACTIVE` | User controls each step |
| `SEMI_AUTO` | Auto-fix CI/review, human approval for merge |
| `FULL_AUTO` | Fully autonomous from coding to merge |

## Workspace Isolation

### Clone-Based Workspaces (Default)

```mermaid
flowchart LR
    subgraph Original["Original Repository"]
        OR[Remote Origin]
    end

    subgraph Workspaces["workspaces/"]
        W1["run_xxx/<br/>Shallow Clone"]
        W2["run_yyy/<br/>Shallow Clone"]
        W3["run_zzz/<br/>Shallow Clone"]
    end

    OR -->|git clone --depth=1| W1
    OR -->|git clone --depth=1| W2
    OR -->|git clone --depth=1| W3
```

**Benefits**:
- Independent from parent repository state
- Better support for remote sync
- No worktree lock issues
- Shallow clone (depth=1) for efficiency

### Worktree-Based Workspaces (Alternative)

```mermaid
flowchart LR
    subgraph Parent["Parent Repository"]
        REPO["repos/repo_id/"]
    end

    subgraph Worktrees["worktrees/"]
        WT1["run_xxx/"]
        WT2["run_yyy/"]
    end

    REPO -->|git worktree add| WT1
    REPO -->|git worktree add| WT2
```

**Configuration**:
```python
# settings.py
use_clone_based_workspaces: bool = True  # Default: clone-based
workspaces_dir: Path   # For clones
worktrees_dir: Path    # For worktrees (separate to avoid inheriting CLAUDE.md)
```

## Parallel Execution Model

### Queue-Based Execution

```python
class RoleQueueAdapter:
    def __init__(self, max_concurrent: int = 5):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._tasks: dict[str, asyncio.Task] = {}

    async def enqueue(self, id: str, coro: Callable) -> None:
        async with self._semaphore:
            task = asyncio.create_task(coro())
            self._tasks[id] = task

    def cancel(self, id: str) -> bool:
        if task := self._tasks.get(id):
            return task.cancel()
        return False
```

**Characteristics**:
- Semaphore-based concurrency control
- Configurable timeout enforcement
- Automatic cleanup of completed tasks
- In-memory for v0.1 (replaceable with Celery/Redis)

### Scalability Path

```mermaid
flowchart LR
    subgraph v0.1["v0.1 (Current)"]
        API1[API Server] --> IMQ[In-Memory Queue]
    end

    subgraph v0.2["v0.2+ (Planned)"]
        API2[API Server] --> Redis[(Redis Queue)]
        Redis --> W1[Worker 1]
        Redis --> W2[Worker 2]
        Redis --> WN[Worker N]
    end
```

## Security Architecture

### API Key Encryption

```mermaid
flowchart LR
    A[User Input<br/>plaintext] --> B[CryptoService.encrypt]
    B -->|Fernet AES-128| C[(DB Storage<br/>encrypted)]
    C --> D[CryptoService.decrypt]
    D --> E[Plaintext<br/>for API call]
```

### Constraint Injection

Constraints are injected into agent/executor prompts:

```python
# Example constraints
AgentConstraints(
    forbidden_paths=[".git", ".env", "*.secret", "*.key", "credentials.*"],
    forbidden_commands=["git commit", "git push", "rm -rf"],
    allowed_git_commands=["git status", "git diff", "git log", "git show"],
)

# Injected into prompt as:
# "You MUST NOT modify files matching: .git, .env, *.secret..."
# "You MUST NOT execute: git commit, git push, rm -rf..."
```

### Orchestrator Pattern

zloth manages all git operations; agents/executors only edit files:

```mermaid
flowchart TB
    subgraph Agent["Agent/Executor"]
        Edit[Edit Files Only]
    end

    subgraph zloth["zloth Orchestrator"]
        WS[Create Workspace]
        Commit[Git Commit]
        Push[Git Push]
        PR[Create PR]
    end

    WS --> Agent
    Agent --> Commit
    Commit --> Push
    Push --> PR
```

## Entity Relationships

```mermaid
erDiagram
    ModelProfile {
        string id PK
        string provider
        string model_name
        string display_name
        string api_key_encrypted
        datetime created_at
    }

    Repo {
        string id PK
        string repo_url
        string default_branch
        string selected_branch
        string latest_commit
        string workspace_path
        datetime created_at
    }

    Task {
        string id PK
        string repo_id FK
        string title
        string coding_mode
        string kanban_status
        datetime created_at
        datetime updated_at
    }

    Message {
        string id PK
        string task_id FK
        string role
        string content
        datetime created_at
    }

    Run {
        string id PK
        string task_id FK
        string model_id FK
        string executor_type
        string instruction
        string status
        string patch
        json files_changed
        json logs
        string session_id
        datetime created_at
    }

    Review {
        string id PK
        string task_id FK
        json target_run_ids
        string executor_type
        string status
        string overall_summary
        float overall_score
        datetime created_at
    }

    ReviewFeedback {
        string id PK
        string review_id FK
        string file_path
        int line_start
        int line_end
        string severity
        string category
        string title
        string description
        string suggestion
    }

    PR {
        string id PK
        string task_id FK
        int number
        string url
        string branch
        string title
        string body
        string status
        datetime created_at
    }

    BacklogItem {
        string id PK
        string repo_id FK
        string title
        string description
        string type
        string estimated_size
        json target_files
        json subtasks
        string task_id FK "nullable - if promoted"
        datetime created_at
    }

    AgenticRun {
        string id PK
        string task_id FK
        string mode
        string phase
        int ci_iterations
        int review_iterations
        int total_iterations
        int pr_number
        string error
        datetime created_at
    }

    CICheck {
        string id PK
        string task_id FK
        string pr_id FK
        string status
        string workflow_run_id
        json jobs
        json failed_jobs
        datetime created_at
    }

    Repo ||--o{ Task : contains
    Repo ||--o{ BacklogItem : has
    Task ||--o{ Message : has
    Task ||--o{ Run : executes
    Task ||--o{ Review : reviews
    Task ||--o{ PR : creates
    Task ||--o| AgenticRun : orchestrates
    ModelProfile ||--o{ Run : uses
    Review ||--o{ ReviewFeedback : contains
    BacklogItem ||--o| Task : promotes_to
    PR ||--o{ CICheck : has
```

## Domain Enums

### Execution Status
```python
class RoleExecutionStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"

# Alias for backward compatibility
RunStatus = RoleExecutionStatus
```

### Executor Types
```python
class ExecutorType(str, Enum):
    PATCH_AGENT = "patch_agent"    # Direct LLM API
    CLAUDE_CODE = "claude_code"    # Claude Code CLI
    CODEX_CLI = "codex"            # Codex CLI
    GEMINI_CLI = "gemini"          # Gemini CLI
```

### LLM Providers
```python
class Provider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
```

### Coding Modes
```python
class CodingMode(str, Enum):
    INTERACTIVE = "interactive"  # User controls each step
    SEMI_AUTO = "semi_auto"      # Auto-fix, human approval for merge
    FULL_AUTO = "full_auto"      # Fully autonomous
```

### Review Types
```python
class ReviewSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class ReviewCategory(str, Enum):
    SECURITY = "security"
    BUG = "bug"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    BEST_PRACTICE = "best_practice"
    STYLE = "style"
    DOCUMENTATION = "documentation"
    TEST = "test"
```

### Kanban Status
```python
class TaskKanbanStatus(str, Enum):
    # Base status (stored in DB)
    BACKLOG = "backlog"
    TODO = "todo"
    ARCHIVED = "archived"

    # Computed status (dynamic)
    IN_PROGRESS = "in_progress"  # Has running runs
    IN_REVIEW = "in_review"      # Has active review
    GATING = "gating"            # Waiting for CI/merge
    DONE = "done"                # PR merged
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ZLOTH_ENCRYPTION_KEY` | API key encryption key | Required |
| `ZLOTH_GITHUB_APP_ID` | GitHub App ID | - |
| `ZLOTH_GITHUB_APP_PRIVATE_KEY` | GitHub App private key (base64) | - |
| `ZLOTH_GITHUB_APP_INSTALLATION_ID` | GitHub App installation ID | - |
| `ZLOTH_DEBUG` | Debug mode | `false` |
| `ZLOTH_LOG_LEVEL` | Log level | `INFO` |
| `ZLOTH_CLAUDE_CLI_PATH` | Claude Code CLI path | `claude` |
| `ZLOTH_CODEX_CLI_PATH` | Codex CLI path | `codex` |
| `ZLOTH_GEMINI_CLI_PATH` | Gemini CLI path | `gemini` |
| `ZLOTH_WORKSPACES_DIR` | Clone workspaces directory | `~/.zloth/workspaces` |
| `ZLOTH_WORKTREES_DIR` | Worktrees directory | `~/.zloth/worktrees` |
| `ZLOTH_DATA_DIR` | Database directory | `~/.zloth/data` |
| `ZLOTH_USE_CLONE_BASED_WORKSPACES` | Use clone-based isolation | `true` |

### Agentic Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `max_ci_iterations` | Max CI fix attempts | 3 |
| `max_review_iterations` | Max review fix attempts | 3 |
| `max_total_iterations` | Max total iterations | 10 |
| `ci_polling_interval` | CI poll interval (seconds) | 30 |
| `ci_polling_timeout` | CI poll timeout (minutes) | 30 |

## Frontend Architecture

### App Structure (Next.js 14)

```
apps/web/src/
├── app/                    # App Router
│   ├── layout.tsx
│   ├── page.tsx           # Home (task list)
│   ├── tasks/             # Task detail view
│   ├── repos/             # Repository selection
│   ├── settings/          # Settings page
│   ├── kanban/            # Kanban board
│   ├── backlog/           # Backlog management
│   └── metrics/           # Development metrics
├── components/
│   ├── ui/                # Base UI components
│   ├── ChatPanel.tsx      # Message input/display
│   ├── RunsPanel.tsx      # Run list
│   ├── RunDetailPanel.tsx # Run details with diff
│   ├── ReviewPanel.tsx    # Code review display
│   ├── DiffViewer.tsx     # Syntax-highlighted diff
│   ├── BreakdownModal.tsx # Task decomposition
│   ├── ExecutorSelector.tsx # Executor selection
│   └── ...
├── lib/
│   └── api.ts             # TypeScript API client
└── types.ts               # Type definitions
```

### Key Components

| Component | Description |
|-----------|-------------|
| `ChatPanel` | Conversation interface with message history |
| `RunsPanel` | List of parallel runs with status |
| `RunDetailPanel` | Run output, diff viewer, PR actions |
| `ReviewPanel` | Code review feedback display |
| `DiffViewer` | Syntax-highlighted unified diff |
| `ExecutorSelector` | Select executor type (Claude/Codex/Gemini) |
| `BreakdownModal` | Task decomposition UI |
| `StreamingLogs` | Real-time log display |

## Roadmap

### v0.2
- [ ] Docker sandbox for command execution
- [x] GitHub App authentication
- [x] Agentic orchestrator (autonomous development cycle)
- [x] Code review integration
- [x] Clone-based workspace isolation
- [ ] Multi-user support

### v0.3
- [ ] Distributed queue (Redis/Celery)
- [ ] PostgreSQL support
- [ ] Cost and budget management
- [ ] Policy injection
- [ ] Webhook-based CI integration
