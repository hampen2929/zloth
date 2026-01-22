# Workspace Workflow Diagram

このドキュメントでは、zlothにおけるワークスペースの作成から実装、commit、pushまでの全体フローを図示します。

## 分離モード

zlothは2つのワークスペース分離モードをサポートしています：

| モード | 設定値 | 特徴 |
|--------|--------|------|
| **Clone方式** (推奨/デフォルト) | `use_clone_isolation=true` | フルgit clone。リモート同期・コンフリクト解消が容易 |
| **Worktree方式** (レガシー) | `use_clone_isolation=false` | git worktree。高速だがgit操作に制約あり |

## 全体アーキテクチャ

```mermaid
graph TB
    subgraph User["User (UI)"]
        UI[Web Interface]
    end

    subgraph Orchestrator["zloth (Orchestrator)"]
        RS[RunService]
        WS[WorkspaceService]
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
        WORK[(Workspace)]
        DB[(Database)]
    end

    UI -->|1. Create Task/Run| RS
    RS -->|2. Create Workspace| WS
    WS -->|shallow clone| WORK
    RS -->|3. Execute CLI| EX
    EX -->|Run| CC
    EX -->|Run| CX
    EX -->|Run| GM
    CC -->|File Edit Only| WORK
    CX -->|File Edit Only| WORK
    GM -->|File Edit Only| WORK
    RS -->|4. Stage/Commit/Push| WS
    WS -->|git add/commit/push| GIT
    RS -->|5. Save Results| DB
    UI -->|6. Create PR| PS
    PS -->|GitHub API| GIT
```

## サービス間の責務分担

| サービス | 責務 | Git操作 |
|---------|------|---------|
| **RunService** | Run実行の全体制御 | WorkspaceService/GitServiceを呼び出し |
| **WorkspaceService** | Clone方式のワークスペース管理 | clone, sync, merge, push |
| **GitService** | Worktree方式（レガシー） | worktree, add, commit, push |
| **Executor** | CLI実行 | なし（ファイル編集のみ） |
| **PRService** | PR作成・更新 | GitHub API経由 |

## ユースケース1: リモートブランチの更新

PRの「Update Branch」ボタンでベースブランチの更新を取り込む場合のフロー。

```mermaid
sequenceDiagram
    participant U as User
    participant T as zloth
    participant AI as AI Agent
    participant W as Workspace
    participant GH as GitHub

    Note over U,GH: 初回実装 → PR作成
    U->>T: New Task + 指示
    T->>W: shallow clone
    T->>AI: 指示実行
    AI->>W: ファイル編集
    T->>W: commit & push
    T->>GH: PR作成

    Note over GH: Mainブランチに更新が入る
    GH->>GH: Main更新
    U->>GH: "Update Branch" クリック
    GH->>GH: PRブランチにmainをマージ

    Note over U,GH: 追加実装（リモート反映込み）
    U->>T: 追加指示
    T->>W: git fetch origin
    T->>W: is_behind_remote? → Yes
    T->>W: sync_with_remote (pull)
    Note over W: リモートの変更を取り込み
    T->>AI: 追加指示実行
    AI->>W: ファイル編集
    T->>W: commit & push
    W->>GH: push成功（PRに自動反映）
```

### Clone方式のポイント

- 独立したCloneなので`git pull`が問題なく動作
- `sync_with_remote()`でリモートの最新状態を取得
- 認証付きURLでプライベートリポジトリにも対応

## ユースケース2: ベースブランチとのコンフリクト解消

PRがベースブランチ（main/master）とコンフリクトを起こした場合の解消フロー。

```mermaid
sequenceDiagram
    participant U as User
    participant T as zloth
    participant AI as AI Agent
    participant W as Workspace
    participant GH as GitHub

    Note over U,GH: 初回実装 → PR作成
    U->>T: New Task + 指示
    T->>W: shallow clone
    T->>AI: 指示実行
    T->>W: commit & push
    T->>GH: PR作成

    Note over GH: Mainブランチに競合する変更が入る
    GH->>GH: Main更新（競合発生）
    GH->>GH: PR表示: "This branch has conflicts"

    Note over U,GH: コンフリクト解消
    U->>T: "コンフリクトを解消して"

    T->>W: unshallow (履歴取得)
    T->>W: merge_base_branch(main)
    W-->>T: CONFLICT detected

    Note over T: コンフリクトファイルを検出

    T->>AI: コンフリクト解消指示<br/>"以下のファイルにコンフリクトあり..."
    AI->>W: コンフリクトマーカー解消<br/>(<<<< ==== >>>>を編集)

    Note over T: AIがコンフリクト解消後

    T->>W: git add (resolved files)
    T->>W: complete_merge (マージコミット)
    T->>W: git push
    W->>GH: push成功
    GH->>GH: PR: Conflicts resolved ✓
```

### コンフリクト解消のポイント

1. **unshallow**: Shallow cloneを解除して完全な履歴を取得（merge-baseに必要）
2. **merge_base_branch**: ベースブランチをマージ、コンフリクトを検出
3. **AIへの指示**: コンフリクトファイルと解消方法を含む詳細な指示を生成
4. **complete_merge**: AIが解消後、マージコミットを完了

## Phase 1: ワークスペース作成

```mermaid
sequenceDiagram
    participant RS as RunService
    participant WS as WorkspaceService
    participant Git as Git CLI

    RS->>WS: create_workspace(repo, base_branch, run_id)

    Note over WS: branch_name = "zloth/{run_id[:8]}"
    Note over WS: workspace_path = "workspaces/run_{run_id}"

    WS->>Git: git clone --depth 1 --single-branch -b {base} {url}
    Git-->>WS: Clone完了

    WS->>Git: git checkout -b {branch_name}
    Git-->>WS: ブランチ作成完了

    WS-->>RS: WorkspaceInfo {path, branch_name, base_branch}
```

## Phase 2: リモート同期

```mermaid
flowchart TD
    A[Run開始] --> B{リモート更新チェック}
    B -->|is_behind_remote| C{リモートが先行?}
    C -->|No| D[同期不要]
    C -->|Yes| E[sync_with_remote]
    E --> F{コンフリクト解消指示?}
    F -->|No| G[Pull完了]
    F -->|Yes| H[unshallow]
    H --> I[merge_base_branch]
    I --> J{コンフリクト?}
    J -->|No| K[マージ完了]
    J -->|Yes| L[コンフリクト指示生成]
    L --> M[AIに解消を依頼]
    D --> N[CLI実行]
    G --> N
    K --> N
    M --> N
```

## Phase 3: CLI実行とCommit/Push

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

## 全体ワークフロー（統合図）

```mermaid
flowchart TD
    subgraph Phase1["Phase 1: ワークスペース作成"]
        A[Task/Run作成] --> B{既存ワークスペースあり?}
    B -->|Yes| C{有効?}
        B -->|No| D[shallow clone]
        C -->|Yes| E[再利用]
        C -->|No| D
        D --> F[ブランチ作成]
        E --> G[WorkspaceInfo]
        F --> G
    end

    subgraph Phase2["Phase 2: リモート同期"]
        G --> H{リモート先行?}
        H -->|No| I[同期不要]
        H -->|Yes| J[sync_with_remote]
        J --> K{コンフリクト解消要求?}
        K -->|No| I
        K -->|Yes| L[merge_base_branch]
        L --> M{コンフリクト?}
        M -->|No| I
        M -->|Yes| N[コンフリクト指示追加]
        N --> I
    end

    subgraph Phase3["Phase 3: CLI実行"]
        I --> O[Executor.execute]
        O --> P[AI Agent起動]
        P --> Q[ファイル編集]
        Q --> R[ExecutorResult]
    end

    subgraph Phase4["Phase 4: Commit & Push"]
        R --> S{変更あり?}
        S -->|No| T[完了: No Changes]
        S -->|Yes| U[git add -A]
        U --> V[git diff]
        V --> W[Commit Message生成]
        W --> X[git commit]
        X --> Y[git push]
        Y --> Z[Run結果保存]
    end

    subgraph Phase5["Phase 5: PR (Optional)"]
        Z --> AA{PR作成?}
        AA -->|Yes| AB[GitHub API: Create PR]
        AB --> AC[PR URL返却]
        AA -->|No| AD[完了]
    end

    style Phase1 fill:#e1f5fe
    style Phase2 fill:#fff3e0
    style Phase3 fill:#e8f5e9
    style Phase4 fill:#fce4ec
    style Phase5 fill:#f3e5f5
```

## WorkspaceService主要メソッド

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

## 設定

`apps/api/src/zloth_api/config.py`:

```python
# Workspace Isolation Mode
use_clone_isolation: bool = Field(
    default=True,
    description="Use git clone instead of worktree for workspace isolation. "
    "Clone mode provides better support for remote sync and conflict resolution.",
)
```

環境変数での設定:

```bash
ZLOTH_USE_CLONE_ISOLATION=true  # Clone方式（推奨）
ZLOTH_USE_CLONE_ISOLATION=false # Worktree方式（レガシー）
```

### 互換メモ（Clone優先ポリシー）

- `use_clone_isolation=true` の場合、過去のRunで作成された「worktreeベースのワークスペース」は再利用しません。
- 既存のワークツリーが見つかった場合でも、Clone方式の新しいワークスペースを作成して実行します（安全なリモート同期のため）。

## 関連ファイル

| ファイル | 役割 |
|---------|------|
| `apps/api/src/zloth_api/services/workspace_service.py` | Clone方式のワークスペース管理 |
| `apps/api/src/zloth_api/services/git_service.py` | Worktree方式（レガシー） |
| `apps/api/src/zloth_api/services/run_service.py` | Run実行制御 |
| `apps/api/src/zloth_api/services/pr_service.py` | PR作成・更新 |
| `apps/api/src/zloth_api/config.py` | 設定 |
