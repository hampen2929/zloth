# Worktree Workflow Diagram

このドキュメントでは、tazunaにおけるGit worktreeの作成から実装、commit、pushまでの全体フローを図示します。

## 全体アーキテクチャ

```mermaid
graph TB
    subgraph User["User (UI)"]
        UI[Web Interface]
    end

    subgraph Orchestrator["tazuna (Orchestrator)"]
        RS[RunService]
        GS[GitService]
        PS[PRService]
        EX[Executor]
    end

    subgraph Agent["AI Agent (CLI)"]
        CC[Claude Code]
        CX[Codex]
        GM[Gemini]
    end

    subgraph Storage["Storage"]
        GIT[(Git Repository)]
        WT[(Worktree)]
        DB[(Database)]
    end

    UI -->|1. Create Task/Run| RS
    RS -->|2. Create Worktree| GS
    GS -->|git worktree add| WT
    RS -->|3. Execute CLI| EX
    EX -->|Run| CC
    EX -->|Run| CX
    EX -->|Run| GM
    CC -->|File Edit Only| WT
    CX -->|File Edit Only| WT
    GM -->|File Edit Only| WT
    RS -->|4. Stage/Commit/Push| GS
    GS -->|git add/commit/push| GIT
    RS -->|5. Save Results| DB
    UI -->|6. Create PR| PS
    PS -->|GitHub API| GIT
```

## サービス間の責務分担

| サービス | 責務 | Git操作 |
|---------|------|---------|
| **RunService** | Run実行の全体制御 | GitServiceを呼び出し |
| **GitService** | Git操作の集約 | worktree, add, commit, push, pull, fetch |
| **Executor** | CLI実行 | なし（ファイル編集のみ） |
| **PRService** | PR作成・更新 | GitHub API経由 |

## Phase 1: Worktree作成フロー

```mermaid
sequenceDiagram
    participant RS as RunService
    participant GS as GitService
    participant Git as Git CLI

    RS->>GS: create_worktree(repo, base_branch, run_id)

    Note over GS: branch_name = "tazuna/{run_id[:8]}"
    Note over GS: worktree_path = "worktrees/run_{run_id}"

    GS->>Git: git fetch origin --prune
    Git-->>GS: (リモート同期)

    GS->>Git: git worktree add -b {branch_name} {path} origin/{base_branch}
    Git-->>GS: Worktree作成完了

    GS-->>RS: WorktreeInfo {path, branch_name, base_branch}
```

### Worktreeディレクトリ構造

```
workspaces/
├── {workspace_uuid}/                # メインリポジトリ
│   ├── .git/
│   │   └── worktrees/               # Worktree管理ディレクトリ
│   │       ├── run_{run_id_1}/
│   │       └── run_{run_id_2}/
│   └── [ソースファイル]
│
└── worktrees/
    ├── run_{run_id_1}/              # Worktree 1 (独立した作業領域)
    │   ├── .git                     # 親リポジトリへの参照ファイル
    │   └── [ソースファイル]
    │
    └── run_{run_id_2}/              # Worktree 2
        ├── .git
        └── [ソースファイル]
```

## Phase 2: CLI実行フロー

```mermaid
sequenceDiagram
    participant RS as RunService
    participant EX as Executor
    participant CLI as AI Agent CLI
    participant WT as Worktree

    RS->>EX: execute(worktree_path, instruction, constraints)

    Note over EX: constraintsに以下を含む:<br/>- git commit/push禁止<br/>- .git, .env アクセス禁止

    EX->>CLI: subprocess起動

    loop ファイル編集
        CLI->>WT: Read file
        WT-->>CLI: File content
        CLI->>WT: Write/Edit file
        WT-->>CLI: Success
    end

    CLI-->>EX: ExecutorResult {success, summary, session_id}
    EX-->>RS: ExecutorResult
```

### Executor制約 (AgentConstraints)

```python
forbidden_commands = [
    "git commit",
    "git push",
    "git checkout",
    "git reset --hard",
    "git rebase",
    "git merge",
]

forbidden_paths = [
    ".git",
    ".env",
    ".env.*",
    "*.key",
    "*.pem",
]
```

## Phase 3: Commit & Pushフロー

```mermaid
sequenceDiagram
    participant RS as RunService
    participant GS as GitService
    participant Git as Git CLI
    participant Remote as GitHub

    Note over RS: CLI実行完了後

    RS->>GS: stage_all(worktree_path)
    GS->>Git: git add -A
    Git-->>GS: Staged

    RS->>GS: get_diff(worktree_path, staged=True)
    GS->>Git: git diff HEAD --cached
    Git-->>GS: Unified diff (patch)
    GS-->>RS: patch

    alt 変更あり
        RS->>RS: generate_commit_message(instruction, summary)
        RS->>GS: commit(worktree_path, message)
        GS->>Git: git commit -m "{message}"
        Git-->>GS: commit_sha
        GS-->>RS: commit_sha

        RS->>GS: push_with_retry(worktree_path, branch, auth_url)
        GS->>Git: git push -u origin {branch}

        alt Push成功
            Git-->>GS: Success
        else non-fast-forward エラー
            GS->>Git: git fetch origin
            GS->>Git: git pull origin {branch}
            GS->>Git: git push -u origin {branch}
            Git-->>GS: Success (リトライ成功)
        end

        GS-->>RS: PushResult {success}
    else 変更なし
        RS->>RS: Skip commit/push
    end

    RS->>RS: Save run status (patch, commit_sha, etc.)
```

### Push With Retry ロジック

```mermaid
flowchart TD
    A[git push開始] --> B{Push成功?}
    B -->|Yes| C[完了]
    B -->|No| D{non-fast-forward<br/>エラー?}
    D -->|No| E[エラー終了]
    D -->|Yes| F[git fetch origin]
    F --> G[git pull origin branch]
    G --> H{リトライ回数 < 2?}
    H -->|Yes| I[git push リトライ]
    I --> B
    H -->|No| J[Conflict detected<br/>エラー終了]
```

## Phase 4: 会話継続時のWorktree再利用フロー

```mermaid
sequenceDiagram
    participant U as User
    participant RS as RunService
    participant GS as GitService
    participant EX as Executor
    participant Git as Git CLI

    U->>RS: 追加指示 (既存Task)

    RS->>RS: 既存のWorktree/セッション検索

    alt 既存Worktreeあり
        RS->>GS: is_behind_remote(worktree_path, branch)
        GS->>Git: git rev-list HEAD..origin/{branch}
        Git-->>GS: behind_count

        alt リモートより遅れている
            RS->>GS: pull(worktree_path, branch)
            GS->>Git: git pull origin {branch}
            Git-->>GS: 同期完了
        end

        RS->>EX: execute(worktree_path, instruction, session_id)
        Note over EX: session_idで会話を継続
    else 新規Worktree必要
        RS->>GS: create_worktree(repo, base_branch, run_id)
        GS-->>RS: WorktreeInfo
        RS->>EX: execute(worktree_path, instruction)
    end

    EX-->>RS: ExecutorResult

    Note over RS: 以降はPhase 3と同じ<br/>(stage → commit → push)
```

## 全体ワークフロー (統合図)

```mermaid
flowchart TD
    subgraph Phase1["Phase 1: Worktree作成"]
        A[Task/Run作成] --> B[base_ref決定]
        B --> C[git fetch origin]
        C --> D[git worktree add -b branch path origin/base]
        D --> E[WorktreeInfo保存]
    end

    subgraph Phase2["Phase 2: CLI実行"]
        E --> F[Executor.execute]
        F --> G[AI Agent起動]
        G --> H{ファイル編集}
        H --> I[ExecutorResult]
    end

    subgraph Phase3["Phase 3: Commit & Push"]
        I --> J{変更あり?}
        J -->|Yes| K[git add -A]
        J -->|No| L[完了: No Changes]
        K --> M[git diff]
        M --> N[Commit Message生成]
        N --> O[git commit]
        O --> P[git push with retry]
        P --> Q[Run結果保存]
    end

    subgraph Phase4["Phase 4: 会話継続 (Optional)"]
        Q --> R{追加指示?}
        R -->|Yes| S[Worktree再利用チェック]
        S --> T{Worktree有効?}
        T -->|Yes| U[Remote同期]
        T -->|No| B
        U --> F
        R -->|No| V[完了]
    end

    subgraph Phase5["Phase 5: PR作成 (Optional)"]
        V --> W{PR作成?}
        W -->|Yes| X[GitHub API: Create PR]
        X --> Y[PR URL返却]
        W -->|No| Z[Branch Only完了]
    end

    style Phase1 fill:#e1f5fe
    style Phase2 fill:#fff3e0
    style Phase3 fill:#e8f5e9
    style Phase4 fill:#fce4ec
    style Phase5 fill:#f3e5f5
```

## PR作成フロー

```mermaid
sequenceDiagram
    participant U as User
    participant PS as PRService
    participant RunDAO as RunDAO
    participant GH as GitHub API

    U->>PS: create_from_run(task_id, run_id, pr_data)

    PS->>RunDAO: get(run_id)
    RunDAO-->>PS: Run {working_branch, commit_sha, base_ref}

    Note over PS: ブランチは既にpush済み

    PS->>GH: create_pull_request(<br/>head=working_branch,<br/>base=base_ref,<br/>title, body)
    GH-->>PS: {number, html_url}

    PS->>PS: DB保存 (PR entity)
    PS-->>U: PR {url, number}
```

## Worktreeクリーンアップフロー

```mermaid
flowchart TD
    A[クリーンアップ開始] --> B{トリガー}

    B -->|Run キャンセル| C[delete_branch=True]
    B -->|PR作成| D[delete_branch=False]

    C --> E[.gitファイル読み込み]
    D --> E

    E --> F[親リポジトリ特定]
    F --> G[git worktree remove --force]

    G --> H{ブランチ削除?}
    H -->|Yes| I[git branch -D branch_name]
    H -->|No| J[ブランチ保持]

    I --> K[完了]
    J --> K

    G -->|失敗時| L[手動ディレクトリ削除]
    L --> K
```

## サービス実装詳細

### GitService主要メソッド

| メソッド | 用途 | Git コマンド |
|---------|------|-------------|
| `create_worktree()` | Worktree作成 | `git worktree add -b` |
| `cleanup_worktree()` | Worktree削除 | `git worktree remove` |
| `stage_all()` | 全変更をステージング | `git add -A` |
| `get_diff()` | Diff取得 | `git diff HEAD --cached` |
| `commit()` | コミット作成 | `git commit -m` |
| `push()` | プッシュ | `git push -u origin` |
| `push_with_retry()` | リトライ付きプッシュ | `git push` + `git pull` + retry |
| `pull()` | プル | `git pull origin` |
| `is_behind_remote()` | リモートとの差分チェック | `git rev-list` |

### RunService実行フロー詳細

```mermaid
stateDiagram-v2
    [*] --> PENDING: Run作成
    PENDING --> RUNNING: 実行開始

    RUNNING --> RUNNING: CLI実行中
    RUNNING --> STAGING: CLI完了

    STAGING --> COMMITTING: git add完了
    COMMITTING --> PUSHING: git commit完了
    PUSHING --> SUCCEEDED: git push成功

    RUNNING --> FAILED: CLI失敗
    PUSHING --> FAILED: Push失敗

    PENDING --> CANCELED: キャンセル
    RUNNING --> CANCELED: キャンセル

    SUCCEEDED --> [*]
    FAILED --> [*]
    CANCELED --> [*]
```

## 設計思想: Orchestrator管理パターン

tazunaでは「Orchestrator管理パターン」を採用しています。

### なぜAI AgentにGit操作させないのか

```mermaid
graph LR
    subgraph "❌ Agent管理パターン"
        A1[Agent 1] -->|独自タイミングでcommit| G1[Git]
        A2[Agent 2] -->|異なる形式でpush| G1
        A3[Agent 3] -->|予期しないrebase| G1
    end

    subgraph "✅ Orchestrator管理パターン"
        O[tazuna] -->|統一されたワークフロー| G2[Git]
        B1[Agent 1] -->|ファイル編集のみ| WT[Worktree]
        B2[Agent 2] -->|ファイル編集のみ| WT
        B3[Agent 3] -->|ファイル編集のみ| WT
    end
```

### メリット

| 観点 | Orchestrator管理 |
|-----|-----------------|
| **一貫性** | 全Agentで同一のGitワークフロー |
| **制御** | Commit/Pushタイミングが明確 |
| **デバッグ** | フェーズ分離で問題特定が容易 |
| **マルチモデル** | 統一形式でDiff比較が容易 |

## 関連ファイル

| ファイル | 役割 |
|---------|------|
| `apps/api/src/tazuna_api/services/git_service.py` | Git操作の集約 |
| `apps/api/src/tazuna_api/services/run_service.py` | Run実行制御 |
| `apps/api/src/tazuna_api/services/pr_service.py` | PR作成・更新 |
| `apps/api/src/tazuna_api/executors/base_executor.py` | Executor基底クラス |
| `apps/api/src/tazuna_api/executors/claude_code_executor.py` | Claude Code実行 |
| `apps/api/src/tazuna_api/domain/models.py` | ドメインモデル定義 |
