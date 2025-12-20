# Architecture Design

## System Overview

```mermaid
flowchart TB
    subgraph UI["Web UI (Next.js)"]
        Home[Home Page]
        Settings[Settings]
        TaskPage[Task Page]
        RunCompare[Run Comparison]
    end

    subgraph API["API Server (FastAPI)"]
        Routes[Routes]
        Services[Services]
        Agents[Agents]
        Storage[Storage]
        Queue[Queue]
    end

    subgraph External["External Services"]
        SQLite[(SQLite DB)]
        Workspace[Workspace<br/>Git Clone]
        LLM[LLM APIs<br/>OpenAI/Anthropic/Google]
        GitHub[GitHub API]
    end

    UI -->|HTTP/REST| API
    Routes --> Services
    Services --> Agents
    Services --> Storage
    Services --> Queue
    Storage --> SQLite
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

### 2. Services Layer (`services/`)

Implements business logic.

```python
# Example: services/run_service.py
class RunService:
    async def create_runs(self, task_id: str, data: RunCreate) -> list[Run]:
        # 1. Verify task exists
        # 2. Create Run records for each model
        # 3. Enqueue for execution
        # 4. Return run list
```

**Responsibilities**:
- Transaction management
- Domain logic
- Coordination of multiple DAOs

### 3. Agents Layer (`agents/`)

LLM interaction and patch generation.

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

### 4. Storage Layer (`storage/`)

Data persistence.

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

    Database <-- ModelProfileDAO
    Database <-- RepoDAO
    Database <-- TaskDAO
    Database <-- RunDAO
    Database <-- PRDAO
```

## Data Flow

### 1. Run Creation to Completion

```mermaid
sequenceDiagram
    participant U as User
    participant A as API
    participant RS as RunService
    participant Q as Queue
    participant PA as PatchAgent
    participant LLM as LLM API

    U->>A: POST /tasks/{id}/runs
    A->>RS: create_runs()
    RS->>RS: Create Run records (QUEUED)
    RS->>Q: enqueue(run_id)
    RS-->>A: return run_ids
    A-->>U: 201 Created

    Q->>RS: _execute_run()
    RS->>RS: Update status (RUNNING)
    RS->>RS: Create workspace copy
    RS->>PA: run(AgentRequest)
    PA->>PA: Read files
    PA->>PA: Build prompt
    PA->>LLM: generate()
    LLM-->>PA: response
    PA->>PA: Extract patch
    PA-->>RS: AgentResult
    RS->>RS: Update status (SUCCEEDED)
    RS->>RS: Delete workspace
```

### 2. PR Creation Flow

```mermaid
sequenceDiagram
    participant U as User
    participant A as API
    participant PS as PRService
    participant Git as Git/GitHub

    U->>A: POST /tasks/{id}/prs
    A->>PS: create()
    PS->>PS: Get patch from Run
    PS->>Git: Create new branch
    PS->>Git: Apply patch
    PS->>Git: Commit & Push
    PS->>Git: Create PR via API
    PS->>PS: Save PR record
    PS-->>A: PRCreated
    A-->>U: 201 Created
```

## Parallel Execution Model

### v0.1: In-Memory Queue

```python
class QueueAdapter:
    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}

    def enqueue(self, run_id: str, coro: Callable) -> None:
        task = asyncio.create_task(coro())
        self._tasks[run_id] = task
```

**Characteristics**:
- Simple implementation
- Queue lost on server restart
- Operates within single process

### v0.2+: Distributed Queue (Planned)

```mermaid
flowchart LR
    API[API Server] --> Redis[(Redis Queue)]
    Redis --> W1[Worker 1]
    Redis --> W2[Worker 2]
    Redis --> W3[Worker N]
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

### Workspace Isolation

```
workspaces/
├── {repo_id}/           # Original clone
├── run_{run_id_1}/      # Run copy (deleted after execution)
├── run_{run_id_2}/
└── ...
```

### Forbidden Paths

```python
forbidden_paths = [
    ".git",
    ".env",
    "*.secret",
    "*.key",
    "credentials.*",
]
```

## Scalability Considerations

### Current (v0.1)
- Single process
- SQLite
- In-memory queue

### Future (v0.2+)
- Multiple workers
- PostgreSQL
- Redis/Celery

### Migration Path

```python
# Abstracted interface
class QueueAdapter(ABC):
    @abstractmethod
    def enqueue(self, run_id: str, coro: Callable) -> None: ...

    @abstractmethod
    def cancel(self, run_id: str) -> bool: ...

# v0.1 implementation
class InMemoryQueueAdapter(QueueAdapter): ...

# v0.2 implementation
class CeleryQueueAdapter(QueueAdapter): ...
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
        string latest_commit
        string workspace_path
        datetime created_at
    }

    Task {
        string id PK
        string repo_id FK
        string title
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
        string instruction
        string status
        string patch
        datetime created_at
    }

    PR {
        string id PK
        string task_id FK
        int number
        string url
        string branch
        string status
        datetime created_at
    }

    Repo ||--o{ Task : contains
    Task ||--o{ Message : has
    Task ||--o{ Run : executes
    Task ||--o{ PR : creates
    ModelProfile ||--o{ Run : uses
```
