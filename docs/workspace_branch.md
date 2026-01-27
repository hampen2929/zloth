# Workspace & Branch Management

このドキュメントでは、zlothにおけるワークスペースとブランチ管理の設計と実装について説明します。

> **Note**: このドキュメントは `branch_worktree.md` と `worktree_workflow_diagram.md` の内容を統合し、より包括的なガイドを提供します。

## 概要

zlothは、AIエージェントによるコード生成・編集をサポートするために、独立したワークスペース（Clone方式）を使用します。各Runは独自のワークスペースで実行され、ブランチ情報は `Run.base_ref` に保存されます。

### 主要コンセプト

| 概念 | 説明 |
|------|------|
| **Clone方式** | 各Runに対してリポジトリの浅いクローン（shallow clone）を作成 |
| **base_ref** | 作業の基点となるブランチ（Run作成時に決定） |
| **working_branch** | AIが編集を行う作業ブランチ（自動生成） |
| **Workspace Isolation** | 各実行が独立したファイルシステム空間で動作 |

## アーキテクチャ

### サービス構成

```mermaid
graph TB
    subgraph Services["Core Services"]
        RS[RunService]
        WS[WorkspaceService]
        GS[GitService]
        PS[PRService]
        RepoS[RepoService]
    end

    subgraph Adapters["Workspace Adapters"]
        CWA[CloneWorkspaceAdapter]
        RWM[RunWorkspaceManager]
    end

    subgraph Storage["Storage"]
        DB[(Database)]
        FS[(File System)]
    end

    RS --> RWM
    RWM --> CWA
    CWA --> WS
    RS --> GS
    PS --> GS
    RepoS --> FS
    WS --> FS
    RS --> DB
    PS --> DB
```

### サービス責務

| サービス | 責務 | 主要操作 |
|---------|------|---------|
| **RunService** | Run実行の全体制御 | create_runs, execute_job |
| **WorkspaceService** | Clone方式のワークスペース管理 | create_workspace, sync_with_remote, merge_base_branch |
| **GitService** | Git操作ユーティリティ | push_with_retry, get_diff, checkout |
| **PRService** | PR作成・更新 | create, update, regenerate_description |
| **RepoService** | リポジトリ管理 | select, clone, update_selected_branch |

## ディレクトリ構成

```
workspaces/
├── {workspace_uuid}/                # メインリポジトリのクローン
│   ├── .git/
│   ├── src/
│   └── ...
│
└── run_{run_id}/                    # Run のCloneワークスペース（shallow clone）
    ├── .git/
    └── [作業ファイル]
```

## データモデル

### エンティティ関係

```mermaid
erDiagram
    Repo ||--o{ Task : "has"
    Task ||--o{ Run : "has"
    Task ||--o{ PR : "has"

    Repo {
        string id PK
        string repo_url
        string default_branch "GitHubのデフォルト"
        string selected_branch "ユーザー選択"
        string workspace_path "クローン先パス"
    }

    Task {
        string id PK
        string repo_id FK
        string title
    }

    Run {
        string id PK
        string task_id FK
        string base_ref "作業の基点ブランチ"
        string working_branch "作業ブランチ名"
        string worktree_path "Workspaceパス"
        string commit_sha
        string session_id "CLI session ID"
    }

    PR {
        string id PK
        string task_id FK
        string branch "PRのheadブランチ"
        int number
    }
```

### base_ref の優先順位

Run作成時の `base_ref` は以下の優先順位で決定されます：

1. `data.base_ref` - API呼び出し時に明示的に指定された場合
2. `repo.selected_branch` - ユーザーがBacklog作成時に選択したブランチ
3. `repo.default_branch` - GitHubのデフォルトブランチ

## ワークフロー

### Phase 1: ブランチ選択（Frontend）

```mermaid
sequenceDiagram
    participant U as User
    participant NB as NewBacklogModal
    participant BS as BranchSelector
    participant API as GitHub API

    U->>NB: リポジトリ選択
    NB->>API: listBranches(owner, repo)
    API-->>NB: ブランチ一覧
    NB->>BS: ブランチ一覧を渡す
    BS-->>U: ブランチ選択UI表示
    U->>BS: ブランチ選択
    BS->>NB: selectedBranch更新
```

**関連ファイル:**
- `apps/web/src/components/NewBacklogModal.tsx`
- `apps/web/src/components/BranchSelector.tsx`

### Phase 2: リポジトリ選択（Backend）

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant RS as RepoService
    participant GS as GitService
    participant DB as Database

    FE->>RS: select({owner, repo, branch})
    RS->>DB: find_by_url(repo_url)

    alt リポジトリが既存
        RS->>DB: update_selected_branch(id, branch)
    else 新規クローン
        RS->>GS: clone(repo_url, workspace_path)
        GS-->>RS: クローン完了
        RS->>DB: create(repo_data)
    end

    RS-->>FE: Repo {selected_branch}
```

**関連ファイル:**
- `apps/api/src/zloth_api/services/repo_service.py`
- `apps/api/src/zloth_api/routes/repos.py`

### Phase 3: ワークスペース作成

```mermaid
sequenceDiagram
    participant RS as RunService
    participant RWM as RunWorkspaceManager
    participant WS as WorkspaceService
    participant Git as Git CLI

    RS->>RWM: get_reusable_workspace(existing_run, repo, base_ref)

    alt 再利用可能なワークスペースあり
        RWM-->>RS: ExecutionWorkspaceInfo
    else 新規作成
        RS->>RWM: create_workspace(run_id, repo, base_ref)
        RWM->>WS: create_workspace(repo_url, base_branch, run_id)
        
        Note over WS: branch_name = "zloth/{run_id[:8]}"
        Note over WS: workspace_path = "workspaces/run_{run_id}"
        
        WS->>Git: git clone --depth 1 --single-branch -b {base} {url}
        Git-->>WS: Clone完了
        
        WS->>Git: git checkout -b {branch_name}
        Git-->>WS: ブランチ作成完了
        
        WS-->>RWM: WorkspaceInfo
        RWM-->>RS: ExecutionWorkspaceInfo
    end
```

**関連ファイル:**
- `apps/api/src/zloth_api/services/run_service.py`
- `apps/api/src/zloth_api/services/run_workspace_manager.py`
- `apps/api/src/zloth_api/services/workspace_service.py`

### Phase 4: リモート同期

```mermaid
flowchart TD
    A[Run開始] --> B{リモート更新チェック}
    B -->|is_behind_remote| C{リモートが先行?}
    C -->|No| D[同期不要]
    C -->|Yes| E[sync_with_remote]
    E --> F{コンフリクト?}
    F -->|No| G[Pull完了]
    F -->|Yes| H[コンフリクト指示生成]
    H --> I[AIに解消を依頼]
    D --> J[CLI実行]
    G --> J
    I --> J
```

### Phase 5: CLI実行とCommit/Push

```mermaid
sequenceDiagram
    participant RS as RunService
    participant EX as Executor
    participant AI as AI Agent
    participant WS as WorkspaceService
    participant Git as Git

    RS->>EX: execute(workspace_path, instruction)
    EX->>AI: CLI起動

    loop ファイル編集
        AI->>AI: ファイル読み込み
        AI->>AI: ファイル編集/作成
    end

    AI-->>EX: ExecutorResult
    EX-->>RS: 完了

    Note over RS: ファイル編集完了後

    RS->>WS: stage_all()
    WS->>Git: git add -A

    RS->>WS: get_diff()
    WS->>Git: git diff HEAD --cached
    Git-->>WS: patch

    alt 変更あり
        RS->>WS: commit(message)
        WS->>Git: git commit
        Git-->>WS: commit_sha

        RS->>WS: push(branch, auth_url)
        WS->>Git: git push -u origin {branch}
        Git-->>WS: success
    else 変更なし
        Note over RS: Skip commit/push
    end
```

### Phase 6: PR作成

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant PS as PRService
    participant GH as GitHub API

    FE->>PS: create({selected_run_id, title, ...})

    PS->>PS: run = get_run(selected_run_id)

    Note over PS: ベースブランチ決定
    PS->>PS: base = run.base_ref or repo.default_branch

    PS->>GH: create_pull_request(head=run.working_branch, base=base)
    GH-->>PS: PR作成完了
    PS-->>FE: PR {url, number}
```

**重要:** PRのベースブランチは `run.base_ref` を使用します。これにより、Run作成時に選択されていたブランチが正しくPRのベースになります。

## コンフリクト解消フロー

PRがベースブランチとコンフリクトを起こした場合の解消フロー：

```mermaid
sequenceDiagram
    participant U as User
    participant T as zloth
    participant AI as AI Agent
    participant W as Workspace
    participant GH as GitHub

    Note over U,GH: コンフリクト検出
    GH->>GH: PR表示: "This branch has conflicts"

    Note over U,GH: コンフリクト解消
    U->>T: "コンフリクトを解消して"

    T->>W: unshallow (履歴取得)
    T->>W: merge_base_branch(main)
    W-->>T: CONFLICT detected

    Note over T: コンフリクトファイルを検出

    T->>AI: コンフリクト解消指示
    AI->>W: コンフリクトマーカー解消

    Note over T: AIがコンフリクト解消後

    T->>W: git add (resolved files)
    T->>W: complete_merge (マージコミット)
    T->>W: git push
    W->>GH: push成功
    GH->>GH: PR: Conflicts resolved ✓
```

## WorkspaceService API

### 主要メソッド

| メソッド | 用途 | Git操作 |
|---------|------|---------|
| `create_workspace()` | ワークスペース作成 | `git clone --depth 1` |
| `sync_with_remote()` | リモート同期 | `git fetch` + `git pull` |
| `is_behind_remote()` | リモート先行チェック | `git rev-list` |
| `unshallow()` | 浅いクローン解除 | `git fetch --unshallow` |
| `merge_base_branch()` | ベースブランチマージ | `git merge origin/{base}` |
| `get_conflict_files()` | コンフリクトファイル取得 | `git diff --name-only -U` |
| `complete_merge()` | マージ完了 | `git add` + `git commit` |
| `stage_all()` | 全変更ステージング | `git add -A` |
| `get_diff()` | Diff取得 | `git diff HEAD --cached` |
| `commit()` | コミット作成 | `git commit` |
| `push()` | プッシュ | `git push -u origin` |
| `cleanup_workspace()` | ワークスペース削除 | ディレクトリ削除 |

### 使用例

```python
from zloth_api.services.workspace_service import WorkspaceService

# ワークスペースサービスの初期化
workspace_service = WorkspaceService()

# ワークスペース作成
workspace_info = await workspace_service.create_workspace(
    repo_url="https://github.com/owner/repo",
    base_branch="main",
    run_id="abc12345-...",
    auth_url="https://x-access-token:token@github.com/owner/repo",
)

# リモート同期
if await workspace_service.is_behind_remote(
    workspace_info.path,
    branch=workspace_info.branch_name,
    auth_url=auth_url,
):
    result = await workspace_service.sync_with_remote(
        workspace_info.path,
        branch=workspace_info.branch_name,
        auth_url=auth_url,
    )
    if result.has_conflicts:
        # コンフリクト処理
        conflict_files = result.conflict_files
        # AIに解消を依頼...

# 変更のコミットとプッシュ
await workspace_service.stage_all(workspace_info.path)
diff = await workspace_service.get_diff(workspace_info.path, staged=True)
if diff:
    commit_sha = await workspace_service.commit(workspace_info.path, "feat: add feature")
    await workspace_service.push(
        workspace_info.path,
        branch=workspace_info.branch_name,
        auth_url=auth_url,
    )
```

## ブランチ命名規則

作業ブランチは以下の形式で生成されます：

```
{prefix}/{short_run_id}
```

- `prefix`: ユーザー設定（デフォルト: `zloth`）
- `short_run_id`: Run IDの先頭8文字

例: `zloth/a1b2c3d4`

## 設定

### 環境変数

| 変数 | 説明 | デフォルト |
|------|------|---------|
| `ZLOTH_USE_CLONE_ISOLATION` | Clone方式を使用（常にtrue） | `true` |
| `ZLOTH_WORKSPACES_DIR` | ワークスペースディレクトリ | `workspaces/` |

### config.py

```python
# apps/api/src/zloth_api/config.py

# Workspace Isolation Mode
use_clone_isolation: bool = Field(
    default=True,
    description="Use git clone instead of worktree for workspace isolation. "
    "Clone mode provides better support for remote sync and conflict resolution.",
)
```

> **Note**: `use_clone_isolation=false` は廃止されており、現在は無視されます。zlothは常にClone方式を使用します。

## 複数タスクでの挙動

```mermaid
flowchart TB
    subgraph "Task 1 (develop選択)"
        R1[Repo] --> |selected_branch=develop| T1[Task 1]
        T1 --> Run1[Run 1]
        Run1 --> |base_ref=develop| W1[Workspace 1]
        W1 --> PR1[PR → develop]
    end

    subgraph "Task 2 (main選択)"
        R1 --> |selected_branch=main| T2[Task 2]
        T2 --> Run2[Run 2]
        Run2 --> |base_ref=main| W2[Workspace 2]
        W2 --> PR2[PR → main]
    end

    Note1[Repoは共有されるが各Runは独自のbase_refを保持]
```

**重要なポイント:**
- 同じリポジトリに対して複数のタスクを作成可能
- 各タスクで異なるブランチを選択可能
- `Repo.selected_branch` は最新の選択で上書きされる
- しかし、各 `Run.base_ref` はRun作成時の値を保持
- PR作成時は `run.base_ref` を使用するため、正しいベースブランチが設定される

## トラブルシューティング

### PRのベースブランチが意図と異なる

**原因:** 古いバージョンでは `repo.default_branch` を使用していたため、後から作成したタスクのブランチ選択が影響していた。

**解決:** `run.base_ref` を使用するように修正済み

### Workspaceの作成に失敗する

**確認事項:**
1. ベースブランチがリモートに存在するか
2. `workspaces/` ディレクトリの書き込み権限
3. 既存の `run_{run_id}` ディレクトリが壊れていないか

**関連ログ:**
```
INFO: Creating clone-based workspace for run abc12345
```

### リモート同期が失敗する

**確認事項:**
1. GitHub App の認証情報が正しいか
2. リポジトリへの書き込み権限があるか
3. ネットワーク接続が正常か

### コンフリクトが解消できない

**確認事項:**
1. `unshallow()` が実行されているか（マージには履歴が必要）
2. AIの解消結果にコンフリクトマーカーが残っていないか
3. 全てのコンフリクトファイルがステージされているか

## 関連ドキュメント

| ドキュメント | 内容 |
|------------|------|
| `branch_worktree.md` | ブランチ選択とワークスペース管理の詳細 |
| `worktree_workflow_diagram.md` | ワークフロー図の詳細 |
| `git_operation_design.md` | Git操作の設計 |
| `push_with_retry.md` | プッシュのリトライ機構 |

## 関連ファイル一覧

| カテゴリ | ファイル | 役割 |
|---------|----------|------|
| Frontend | `apps/web/src/components/NewBacklogModal.tsx` | Backlog作成UI |
| Frontend | `apps/web/src/components/BranchSelector.tsx` | ブランチ選択コンポーネント |
| Backend | `apps/api/src/zloth_api/services/repo_service.py` | リポジトリ管理 |
| Backend | `apps/api/src/zloth_api/services/run_service.py` | Run実行管理 |
| Backend | `apps/api/src/zloth_api/services/workspace_service.py` | ワークスペース管理 |
| Backend | `apps/api/src/zloth_api/services/run_workspace_manager.py` | Run用ワークスペースマネージャー |
| Backend | `apps/api/src/zloth_api/services/workspace_adapters.py` | ワークスペースアダプター |
| Backend | `apps/api/src/zloth_api/services/git_service.py` | Git操作 |
| Backend | `apps/api/src/zloth_api/services/pr_service.py` | PR作成・更新 |
| Domain | `apps/api/src/zloth_api/domain/models.py` | Repo, Run, PR モデル定義 |
