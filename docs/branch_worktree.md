# ブランチ選択とワークスペース管理

このドキュメントでは、zlothにおけるブランチ選択からワークスペース作成、PR作成までのフローを説明します。

> 注: 旧仕様では「git worktree」による分離をサポートしていましたが、現在は **Clone方式に統一** されています。
> DBフィールド名などに `worktree_*` が残っている場合がありますが、互換のための名称であり、実体は clone ワークスペースです。

## 概要

zlothでは、ユーザーが選択したブランチを基点として作業を行います。各Runは独立したCloneワークスペースで実行され、ブランチ情報は`Run.base_ref`に保存されます。

```mermaid
flowchart TB
    subgraph Frontend
        A[NewBacklogModal] --> B[BranchSelector]
        B --> C[ブランチ選択]
    end

    subgraph Backend
        D[RepoService.select] --> E[Repo作成/更新]
        E --> F[selected_branch保存]

        G[RunService.create_runs] --> H[base_ref決定]
        H --> I[WorkspaceService.create_workspace]
        I --> J[Workspace作成]

        K[PRService.create] --> L[PR作成]
    end

    C --> D
    F --> G
    J --> K
```

## エンティティ関係

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
        string worktree_path "Workspaceパス（互換名）"
        string commit_sha
    }

    PR {
        string id PK
        string task_id FK
        string branch "PRのheadブランチ"
        int number
    }
```

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

## データフロー

### 1. ブランチ選択（フロントエンド）

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

### 2. リポジトリ選択（バックエンド）

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
- `apps/api/src/zloth_api/services/repo_service.py` (select メソッド)
- `apps/api/src/zloth_api/routes/repos.py`

### 3. Run作成とWorkspace

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant RuS as RunService
    participant WS as WorkspaceService
    participant Exec as Executor

    FE->>RuS: create_runs({instruction, ...})

    Note over RuS: base_ref決定
    RuS->>RuS: base_ref = data.base_ref<br/>or repo.selected_branch<br/>or repo.default_branch

    RuS->>WS: create_workspace(repo_url, base_branch, run_id)

    Note over WS: Workspace作成（shallow clone）
    WS->>WS: git clone --depth 1 --single-branch -b {base} {url}
    WS->>WS: git checkout -b {branch}
    WS-->>RuS: WorkspaceInfo {path, branch_name}

    RuS->>Exec: execute(workspace_path, instruction)
    Exec-->>RuS: 実行結果

    RuS->>WS: commit & push
    RuS-->>FE: Run {base_ref, working_branch, ...}
```

**base_ref の優先順位:**
1. `data.base_ref` - API呼び出し時に明示的に指定された場合
2. `repo.selected_branch` - ユーザーがBacklog作成時に選択したブランチ
3. `repo.default_branch` - GitHubのデフォルトブランチ

**関連ファイル:**
- `apps/api/src/zloth_api/services/run_service.py` (create_runs メソッド)
- `apps/api/src/zloth_api/services/workspace_service.py` (create_workspace メソッド)

### 4. PR作成

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant PS as PRService
    participant GH as GitHub API

    FE->>PS: create({selected_run_id, title, ...})

    PS->>PS: run = get_run(selected_run_id)

    Note over PS: ベースブランチ決定
    PS->>PS: base = run.base_ref or repo.default_branch

    PS->>GH: create_pull_request(<br/>head=run.working_branch,<br/>base=base)
    GH-->>PS: PR作成完了
    PS-->>FE: PR {url, number}
```

**重要:** PRのベースブランチは`run.base_ref`を使用します。これにより、Run作成時に選択されていたブランチが正しくPRのベースになります。

**関連ファイル:**
- `apps/api/src/zloth_api/services/pr_service.py`

## ブランチ命名規則

作業ブランチは以下の形式で生成されます：

```
{prefix}/{short_run_id}
```

- `prefix`: ユーザー設定（デフォルト: `zloth`）
- `short_run_id`: Run IDの先頭8文字

例: `zloth/a1b2c3d4`

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

    Note1[Repoは共有されるが<br/>各Runは独自のbase_refを保持]
```

**重要なポイント:**
- 同じリポジトリに対して複数のタスクを作成可能
- 各タスクで異なるブランチを選択可能
- `Repo.selected_branch`は最新の選択で上書きされる
- しかし、各`Run.base_ref`はRun作成時の値を保持
- PR作成時は`run.base_ref`を使用するため、正しいベースブランチが設定される

## トラブルシューティング

### PRのベースブランチが意図と異なる

**原因:** 古いバージョンでは`repo.default_branch`を使用していたため、後から作成したタスクのブランチ選択が影響していた。

**解決:** `run.base_ref`を使用するように修正済み

### Workspaceの作成に失敗する

**確認事項:**
1. ベースブランチがリモートに存在するか
2. `workspaces/`ディレクトリの書き込み権限
3. 既存の `run_{run_id}` ディレクトリが壊れていないか（必要ならクリーンアップ）

**関連ログ:**
```python
logger.info(f"Creating clone-based workspace for run {run_id[:8]}")
```

## 関連ファイル一覧

| カテゴリ | ファイル | 役割 |
|---------|----------|------|
| Frontend | `apps/web/src/components/NewBacklogModal.tsx` | Backlog作成UI |
| Frontend | `apps/web/src/components/BranchSelector.tsx` | ブランチ選択コンポーネント |
| Backend | `apps/api/src/zloth_api/services/repo_service.py` | リポジトリ管理 |
| Backend | `apps/api/src/zloth_api/services/run_service.py` | Run実行管理 |
| Backend | `apps/api/src/zloth_api/services/git_service.py` | Git操作（push/retry 等） |
| Backend | `apps/api/src/zloth_api/services/pr_service.py` | PR作成・更新 |
| Domain | `apps/api/src/zloth_api/domain/models.py` | Repo, Run, PR モデル定義 |
