# アーキテクチャ設計

## システム概要

```mermaid
flowchart TB
    subgraph UI["Web UI (Next.js)"]
        Home[ホームページ]
        Settings[設定]
        TaskPage[タスクページ]
        Kanban[カンバンボード]
        Backlog[バックログ]
        Metrics[メトリクス]
    end

    subgraph API["APIサーバー (FastAPI)"]
        Routes[ルート]
        Services[サービス]
        Roles[ロールサービス]
        Executors[エグゼキューター]
        Agents[エージェント]
        Storage[ストレージ]
        Queue[キュー]
    end

    subgraph External["外部サービス"]
        SQLite[(SQLite DB)]
        Workspace[ワークスペース<br/>Clone/Worktree]
        LLM[LLM APIs<br/>OpenAI/Anthropic/Google]
        CLI[CLIツール<br/>Claude/Codex/Gemini]
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

## レイヤーアーキテクチャ

### 1. ルートレイヤー (`routes/`)

HTTPリクエストを受信し、適切なサービスに委譲します。

```python
# 例: routes/runs.py
@router.post("/tasks/{task_id}/runs")
async def create_runs(
    task_id: str,
    data: RunCreate,
    run_service: RunService = Depends(get_run_service),
) -> RunsCreated:
    runs = await run_service.create_runs(task_id, data)
    return RunsCreated(run_ids=[r.id for r in runs])
```

**責務**:
- リクエストバリデーション (Pydantic)
- 認証/認可 (v0.2で予定)
- レスポンスフォーマット

**利用可能なエンドポイント**:
| カテゴリ | エンドポイント |
|----------|-----------|
| モデル | GET/POST/DELETE `/v1/models` |
| リポジトリ | POST `/v1/repos/clone` |
| タスク | GET/POST `/v1/tasks`, `/v1/tasks/{id}/messages` |
| 実行 | POST `/v1/tasks/{id}/runs`, GET `/v1/runs/{id}` |
| PR | POST `/v1/tasks/{id}/prs`, PUT `/v1/prs/{id}` |
| レビュー | POST `/v1/tasks/{id}/reviews`, GET `/v1/reviews/{id}` |
| 分解 | POST `/v1/breakdown` |
| カンバン | GET `/v1/kanban` |
| バックログ | GET/POST/PUT/DELETE `/v1/backlog` |

### 2. サービスレイヤー (`services/`)

ビジネスロジックを実装します。

```python
# 例: services/run_service.py
class RunService(BaseRoleService[Run, RunCreate, RunResult]):
    async def create_runs(self, task_id: str, data: RunCreate) -> list[Run]:
        # 1. タスクの存在確認
        # 2. 各モデルのRunレコード作成
        # 3. 実行キューに追加
        # 4. 実行リストを返却
```

**主要サービス**:
| サービス | 説明 |
|---------|-------------|
| `RunService` | 実装ロール - コード生成 |
| `ReviewService` | レビューロール - コードレビュー実行 |
| `BreakdownService` | 分解ロール - タスク分解 |
| `PRService` | プルリクエスト作成/管理 |
| `WorkspaceService` | クローンベースのワークスペース分離 |
| `GitService` | 一元化されたgit操作 |
| `JobWorker` | SQLiteバックドの永続ジョブキュー |
| `AgenticOrchestrator` | 自律的開発サイクル |
| `CIPollingService` | CIステータスポーリング |
| `GithubService` | GitHub API連携 |
| `CryptoService` | APIキー暗号化 |

### 3. ロールサービス (`roles/`)

すべてのAIロールは`BaseRoleService`を継承し、一貫した実行パターンを持ちます。

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

**ロールレジストリ**:
```python
# roles/registry.py
RoleRegistry.register("implementation", RunService)
RoleRegistry.register("review", ReviewService)
RoleRegistry.register("breakdown", BreakdownService)
```

### 4. エグゼキューターレイヤー (`executors/`)

コード生成のためのCLIツール連携。

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

**エグゼキュータータイプ**:
| タイプ | ツール | 用途 |
|------|------|----------|
| `PATCH_AGENT` | LLM API | APIベースの直接パッチ生成 |
| `CLAUDE_CODE` | Claude Code CLI | セッション永続化対応のコード生成 |
| `CODEX_CLI` | Codex CLI | レビュー特化の操作 |
| `GEMINI_CLI` | Gemini CLI | マルチモーダルコード生成 |

### 5. エージェントレイヤー (`agents/`)

直接API呼び出しによるLLM連携とパッチ生成。

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

**エージェントインターフェース**:
```python
@dataclass
class AgentRequest:
    workspace_path: str      # 作業ディレクトリ
    base_ref: str           # ベースブランチ/コミット
    instruction: str        # 自然言語での指示
    context: dict | None    # 追加コンテキスト
    constraints: AgentConstraints  # 制約（禁止パス等）

@dataclass
class AgentResult:
    summary: str            # 人間が読める要約
    patch: str              # Unified diff
    files_changed: list     # 変更ファイルリスト
    logs: list[str]         # 操作ログ
    warnings: list[str]     # 警告

@dataclass
class AgentConstraints:
    max_files_changed: int | None
    forbidden_paths: list[str]      # .git, .env, *.key など
    forbidden_commands: list[str]   # git commit, push など
    allowed_git_commands: list[str] # git status, diff, log など

    def to_prompt(self) -> str:
        """制約をエージェントプロンプトに注入"""
```

### 6. ストレージレイヤー (`storage/`)

SQLiteによるデータ永続化。

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

## データフロー

### 1. Run作成から完了まで

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant A as API
    participant RS as RunService
    participant JD as JobDAO
    participant JW as JobWorker
    participant EX as Executor
    participant CLI as CLIツール

    U->>A: POST /tasks/{id}/runs
    A->>RS: create_runs()
    RS->>RS: Runレコード作成 (QUEUED)
    RS->>JD: create_job(kind=run.execute)
    JD-->>RS: Job作成完了
    RS-->>A: run_ids返却
    A-->>U: 201 Created

    JW->>JD: claim_next() ポーリング
    JD-->>JW: Jobを取得・ロック
    JW->>RS: _execute_run()
    RS->>RS: ステータス更新 (RUNNING)
    RS->>RS: ワークスペース作成 (clone)
    RS->>EX: execute(workspace, instruction)
    EX->>CLI: CLIツール実行
    CLI-->>EX: 出力ストリーム
    EX->>EX: diff解析
    EX-->>RS: ExecutorResult
    RS->>RS: Git commit & push branch
    RS->>RS: ステータス更新 (SUCCEEDED)
    RS->>RS: ワークスペース削除
    JW->>JD: complete(job_id)
```

### 2. レビューフロー

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant A as API
    participant RVS as ReviewService
    participant JD as JobDAO
    participant JW as JobWorker
    participant EX as CodexExecutor
    participant CLI as Codex CLI

    U->>A: POST /tasks/{id}/reviews
    A->>RVS: create_review()
    RVS->>RVS: Reviewレコード作成 (QUEUED)
    RVS->>JD: create_job(kind=review.execute)
    JD-->>RVS: Job作成完了
    RVS-->>A: ReviewCreated
    A-->>U: 201 Created

    JW->>JD: claim_next() ポーリング
    JD-->>JW: Jobを取得・ロック
    JW->>RVS: _execute_review()
    RVS->>RVS: 対象Runのdiff取得
    RVS->>EX: execute(workspace, review_instruction)
    EX->>CLI: Codexレビュー実行
    CLI-->>EX: レビュー出力 (JSON)
    EX-->>RVS: ExecutorResult
    RVS->>RVS: レビューフィードバック解析
    RVS->>RVS: ReviewFeedbackItems保存
    RVS->>RVS: ステータス更新 (SUCCEEDED)
    JW->>JD: complete(job_id)
```

### 3. PR作成フロー

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant A as API
    participant PS as PRService
    participant GH as GitHub API

    U->>A: POST /tasks/{id}/prs
    A->>PS: create()
    PS->>PS: プッシュ済みブランチのRun取得
    PS->>PS: PRタイトル/説明生成 (LLM)
    PS->>GH: API経由でPR作成
    GH-->>PS: PR番号, URL
    PS->>PS: PRレコード保存
    PS-->>A: PRCreated
    A-->>U: 201 Created
```

### 4. Agentic実行フロー

```mermaid
stateDiagram-v2
    [*] --> CODING
    CODING --> WAITING_CI: Run完了
    WAITING_CI --> REVIEWING: CI成功
    WAITING_CI --> FIXING_CI: CI失敗
    FIXING_CI --> WAITING_CI: 修正Run完了
    REVIEWING --> MERGE_CHECK: レビュー承認
    REVIEWING --> FIXING_REVIEW: レビュー却下
    FIXING_REVIEW --> REVIEWING: 修正Run完了
    MERGE_CHECK --> MERGING: 全チェック通過
    MERGE_CHECK --> AWAITING_HUMAN: 承認待ち (SEMI_AUTO)
    AWAITING_HUMAN --> MERGING: 人間が承認
    MERGING --> COMPLETED: マージ成功
    MERGING --> FAILED: マージ失敗
    CODING --> FAILED: エラー
    FIXING_CI --> FAILED: 最大反復回数
    FIXING_REVIEW --> FAILED: 最大反復回数
```

**コーディングモード**:
| モード | 説明 |
|------|-------------|
| `INTERACTIVE` | ユーザーが各ステップを制御 |
| `SEMI_AUTO` | CI/レビュー自動修正、マージは人間承認 |
| `FULL_AUTO` | コーディングからマージまで完全自律 |

## ワークスペース分離

### クローンベースワークスペース (デフォルト)

```mermaid
flowchart LR
    subgraph Original["元リポジトリ"]
        OR[リモートオリジン]
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

**メリット**:
- 親リポジトリの状態から独立
- リモート同期のサポートが良好
- worktreeロック問題なし
- Shallow clone (depth=1) で効率的

### Worktreeベースワークスペース (廃止)

Worktree方式は実装の複雑性・分岐増加の要因となるため、現在は **Clone方式に統一** されています。
互換のため設定値が残っている場合がありますが、Worktree方式の選択は無視されます。

## 並列実行モデル

### SQLiteバックドジョブキュー

```python
class JobWorker:
    """SQLiteに永続化されたジョブを処理するバックグラウンドワーカー"""

    def __init__(
        self,
        *,
        job_dao: JobDAO,
        handlers: Mapping[JobKind, JobHandler],
        max_concurrent: int | None = None,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self._job_dao = job_dao
        self._handlers = dict(handlers)
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._running: dict[str, asyncio.Task] = {}

    async def _run_loop(self) -> None:
        """キューに入ったジョブをポーリングして実行"""
        while not self._stop_event.is_set():
            job = await self._job_dao.claim_next(locked_by=self._worker_id)
            if job:
                task = asyncio.create_task(self._execute_job(job))
                self._running[job.id] = task
```

**特徴**:
- プロセス再起動後も生存（ジョブはSQLiteに永続化）
- セマフォベースの同時実行制御
- claim_next()によるジョブロック（競合回避）
- 完了タスクの自動クリーンアップ
- スタートアップリカバリー（前回クラッシュからの復旧）

**ジョブステータス遷移**:
```mermaid
stateDiagram-v2
    [*] --> queued: 作成
    queued --> running: claim_next()
    running --> succeeded: 完了
    running --> failed: エラー
    running --> canceled: キャンセル
    queued --> canceled: キャンセル
```

### スケーラビリティパス

```mermaid
flowchart LR
    subgraph v0.1["v0.1 (現在)"]
        API1[APIサーバー] --> SQLiteQ[(SQLiteキュー)]
        SQLiteQ --> JW1[JobWorker]
    end

    subgraph v0.2["v0.2+ (計画)"]
        API2[APIサーバー] --> Redis[(Redisキュー)]
        Redis --> W1[Worker 1]
        Redis --> W2[Worker 2]
        Redis --> WN[Worker N]
    end
```

## セキュリティアーキテクチャ

### APIキー暗号化

```mermaid
flowchart LR
    A[ユーザー入力<br/>平文] --> B[CryptoService.encrypt]
    B -->|Fernet AES-128| C[(DB保存<br/>暗号化)]
    C --> D[CryptoService.decrypt]
    D --> E[平文<br/>API呼び出し用]
```

### 制約インジェクション

制約はエージェント/エグゼキューターのプロンプトに注入されます:

```python
# 制約の例
AgentConstraints(
    forbidden_paths=[".git", ".env", "*.secret", "*.key", "credentials.*"],
    forbidden_commands=["git commit", "git push", "rm -rf"],
    allowed_git_commands=["git status", "git diff", "git log", "git show"],
)

# プロンプトへの注入例:
# "以下のファイルを変更してはいけません: .git, .env, *.secret..."
# "以下のコマンドを実行してはいけません: git commit, git push, rm -rf..."
```

### オーケストレーターパターン

zlothがすべてのgit操作を管理し、エージェント/エグゼキューターはファイル編集のみを行います:

```mermaid
flowchart TB
    subgraph Agent["エージェント/エグゼキューター"]
        Edit[ファイル編集のみ]
    end

    subgraph zloth["zlothオーケストレーター"]
        WS[ワークスペース作成]
        Commit[Git Commit]
        Push[Git Push]
        PR[PR作成]
    end

    WS --> Agent
    Agent --> Commit
    Commit --> Push
    Push --> PR
```

## エンティティ関係

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

    Job {
        string id PK
        string kind
        string ref_id
        string status
        json payload
        int attempts
        int max_attempts
        datetime available_at
        datetime locked_at
        string locked_by
        string last_error
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
        string task_id FK "nullable - 昇格時"
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
    Run ||--o| Job : queued_via
    Review ||--o| Job : queued_via
```

## ドメインEnum

### 実行ステータス
```python
class RoleExecutionStatus(str, Enum):
    QUEUED = "queued"       # キュー待ち
    RUNNING = "running"     # 実行中
    SUCCEEDED = "succeeded" # 成功
    FAILED = "failed"       # 失敗
    CANCELED = "canceled"   # キャンセル

# 後方互換性のためのエイリアス
RunStatus = RoleExecutionStatus
```

### エグゼキュータータイプ
```python
class ExecutorType(str, Enum):
    PATCH_AGENT = "patch_agent"    # 直接LLM API
    CLAUDE_CODE = "claude_code"    # Claude Code CLI
    CODEX_CLI = "codex"            # Codex CLI
    GEMINI_CLI = "gemini"          # Gemini CLI
```

### ジョブ種別
```python
class JobKind(str, Enum):
    RUN_EXECUTE = "run.execute"        # Run実行ジョブ
    REVIEW_EXECUTE = "review.execute"  # レビュー実行ジョブ
```

### ジョブステータス
```python
class JobStatus(str, Enum):
    QUEUED = "queued"       # キュー待ち
    RUNNING = "running"     # 実行中
    SUCCEEDED = "succeeded" # 成功
    FAILED = "failed"       # 失敗
    CANCELED = "canceled"   # キャンセル
```

### LLMプロバイダー
```python
class Provider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
```

### コーディングモード
```python
class CodingMode(str, Enum):
    INTERACTIVE = "interactive"  # ユーザーが各ステップを制御
    SEMI_AUTO = "semi_auto"      # 自動修正、マージは人間承認
    FULL_AUTO = "full_auto"      # 完全自律
```

### レビュータイプ
```python
class ReviewSeverity(str, Enum):
    CRITICAL = "critical"  # 重大
    HIGH = "high"          # 高
    MEDIUM = "medium"      # 中
    LOW = "low"            # 低

class ReviewCategory(str, Enum):
    SECURITY = "security"              # セキュリティ
    BUG = "bug"                        # バグ
    PERFORMANCE = "performance"        # パフォーマンス
    MAINTAINABILITY = "maintainability" # 保守性
    BEST_PRACTICE = "best_practice"    # ベストプラクティス
    STYLE = "style"                    # スタイル
    DOCUMENTATION = "documentation"    # ドキュメント
    TEST = "test"                      # テスト
```

### カンバンステータス
```python
class TaskKanbanStatus(str, Enum):
    # 基本ステータス (DBに保存)
    BACKLOG = "backlog"    # バックログ
    TODO = "todo"          # 予定
    ARCHIVED = "archived"  # アーカイブ

    # 計算ステータス (動的)
    IN_PROGRESS = "in_progress"  # 実行中のRunあり
    IN_REVIEW = "in_review"      # アクティブなレビューあり
    GATING = "gating"            # CI/マージ待ち
    DONE = "done"                # PRマージ済み
```

## 設定

### 環境変数

| 変数 | 説明 | デフォルト |
|----------|-------------|---------|
| `ZLOTH_ENCRYPTION_KEY` | APIキー暗号化キー | 必須 |
| `ZLOTH_GITHUB_APP_ID` | GitHub App ID | - |
| `ZLOTH_GITHUB_APP_PRIVATE_KEY` | GitHub App秘密鍵 (base64) | - |
| `ZLOTH_GITHUB_APP_INSTALLATION_ID` | GitHub AppインストールID | - |
| `ZLOTH_DEBUG` | デバッグモード | `false` |
| `ZLOTH_LOG_LEVEL` | ログレベル | `INFO` |
| `ZLOTH_CLAUDE_CLI_PATH` | Claude Code CLIパス | `claude` |
| `ZLOTH_CODEX_CLI_PATH` | Codex CLIパス | `codex` |
| `ZLOTH_GEMINI_CLI_PATH` | Gemini CLIパス | `gemini` |
| `ZLOTH_WORKSPACES_DIR` | クローンワークスペースディレクトリ | `~/.zloth/workspaces` |
| `ZLOTH_WORKTREES_DIR` | Worktreeディレクトリ | `~/.zloth/worktrees` |
| `ZLOTH_DATA_DIR` | データベースディレクトリ | `~/.zloth/data` |
| `ZLOTH_USE_CLONE_BASED_WORKSPACES` | クローンベース分離を使用 | `true` |

### Agentic設定

| 設定 | 説明 | デフォルト |
|---------|-------------|---------|
| `max_ci_iterations` | CI修正の最大試行回数 | 3 |
| `max_review_iterations` | レビュー修正の最大試行回数 | 3 |
| `max_total_iterations` | 全体の最大反復回数 | 10 |
| `ci_polling_interval` | CIポーリング間隔（秒） | 30 |
| `ci_polling_timeout` | CIポーリングタイムアウト（分） | 30 |

## フロントエンドアーキテクチャ

### アプリ構造 (Next.js 14)

```
apps/web/src/
├── app/                    # App Router
│   ├── layout.tsx
│   ├── page.tsx           # ホーム（タスク一覧）
│   ├── tasks/             # タスク詳細ビュー
│   ├── repos/             # リポジトリ選択
│   ├── settings/          # 設定ページ
│   ├── kanban/            # カンバンボード
│   ├── backlog/           # バックログ管理
│   └── metrics/           # 開発メトリクス
├── components/
│   ├── ui/                # 基本UIコンポーネント
│   ├── ChatPanel.tsx      # メッセージ入力/表示
│   ├── RunsPanel.tsx      # Run一覧
│   ├── RunDetailPanel.tsx # Run詳細とdiff
│   ├── ReviewPanel.tsx    # コードレビュー表示
│   ├── DiffViewer.tsx     # シンタックスハイライト付きdiff
│   ├── BreakdownModal.tsx # タスク分解UI
│   ├── ExecutorSelector.tsx # エグゼキューター選択
│   └── ...
├── lib/
│   └── api.ts             # TypeScript APIクライアント
└── types.ts               # 型定義
```

### 主要コンポーネント

| コンポーネント | 説明 |
|-----------|-------------|
| `ChatPanel` | メッセージ履歴付き会話インターフェース |
| `RunsPanel` | ステータス付き並列Run一覧 |
| `RunDetailPanel` | Run出力、diffビューア、PRアクション |
| `ReviewPanel` | コードレビューフィードバック表示 |
| `DiffViewer` | シンタックスハイライト付きUnified diff |
| `ExecutorSelector` | エグゼキュータータイプ選択（Claude/Codex/Gemini） |
| `BreakdownModal` | タスク分解UI |
| `StreamingLogs` | リアルタイムログ表示 |

## ロードマップ

### v0.2
- [ ] Dockerサンドボックスでのコマンド実行
- [x] GitHub App認証
- [x] Agenticオーケストレーター（自律的開発サイクル）
- [x] コードレビュー統合
- [x] クローンベースワークスペース分離
- [x] SQLiteバックドの永続ジョブキュー
- [ ] マルチユーザーサポート

### v0.3
- [ ] 分散キュー (Redis/Celery)
- [ ] PostgreSQLサポート
- [ ] コストと予算管理
- [ ] ポリシーインジェクション
- [ ] WebhookベースCI連携
