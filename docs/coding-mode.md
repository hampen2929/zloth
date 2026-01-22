# Coding Mode 設計ドキュメント

## 概要

zlothに3つの実装モードを搭載し、プロジェクトの性質やチームの運用方針に応じて最適な開発フローを選択可能にする。

### 3つのモード

| モード | 日本語名 | 概要 |
|--------|----------|------|
| **Interactive** | 対話型コーディング | ユーザーがAIと会話しながら実装・レビュー |
| **Semi Auto** | 半自動コーディング | AIが実装〜CI〜レビュー解決まで自走、人間が最終確認してMerge |
| **Full Auto** | 完全自動コーディング | AIが実装〜CI〜レビュー解決〜Mergeまで完全自動 |

```mermaid
graph LR
    subgraph "Interactive"
        I1[人間が指示] --> I2[AIが実装]
        I2 --> I3[人間がレビュー]
        I3 --> I4[人間がMerge]
    end

    subgraph "Semi Auto"
        S1[人間が指示] --> S2[AIが自走]
        S2 --> S3[CI/Review自動解決]
        S3 --> S4[人間がMerge]
    end

    subgraph "Full Auto"
        F1[人間が指示] --> F2[AIが自走]
        F2 --> F3[CI/Review自動解決]
        F3 --> F4[自動Merge]
    end
```

---

## 各モードの詳細

### 1. Interactive Coding（対話型コーディング）

#### 特徴

- **Human-in-the-loop**: 各ステップで人間が確認・指示
- **細かい制御**: 実装方針をリアルタイムで調整可能
- **学習効果**: AIとの対話から開発者が学べる

#### ユースケース

- 新機能の設計段階での検討
- 複雑なビジネスロジックの実装
- チームメンバーのオンボーディング
- AIの出力品質を確認したい場合

#### フロー図

```mermaid
sequenceDiagram
    participant U as User
    participant D as zloth
    participant AI as AI Agent
    participant GH as GitHub

    U->>D: タスク作成 & 指示
    D->>AI: 実装依頼
    AI->>D: コード生成
    D->>U: 結果表示

    loop 対話ループ
        U->>D: フィードバック/追加指示
        D->>AI: 修正依頼
        AI->>D: 修正コード
        D->>U: 結果表示
    end

    U->>D: PR作成指示
    D->>GH: PR作成
    GH->>GH: CI実行

    alt CI失敗
        GH->>D: CI結果通知
        D->>U: CI失敗通知
        U->>D: 修正指示
        D->>AI: 修正依頼
    end

    U->>D: レビュー依頼
    D->>AI: コードレビュー実行
    AI->>D: レビュー結果
    D->>U: レビュー結果表示

    alt レビュー指摘あり
        U->>D: 修正指示
        D->>AI: 修正依頼
    end

    U->>GH: Merge（手動）
```

#### 状態遷移図

```mermaid
stateDiagram-v2
    [*] --> IDLE: タスク作成

    IDLE --> CODING: ユーザー指示
    CODING --> WAITING_FEEDBACK: コード生成完了

    WAITING_FEEDBACK --> CODING: 追加指示
    WAITING_FEEDBACK --> PR_CREATED: PR作成指示

    PR_CREATED --> CI_RUNNING: CI開始
    CI_RUNNING --> CI_FAILED: CI失敗
    CI_RUNNING --> CI_PASSED: CI成功

    CI_FAILED --> CODING: 修正指示

    CI_PASSED --> REVIEWING: レビュー依頼
    REVIEWING --> REVIEW_FEEDBACK: レビュー完了

    REVIEW_FEEDBACK --> CODING: 修正指示
    REVIEW_FEEDBACK --> READY_TO_MERGE: 承認

    READY_TO_MERGE --> MERGED: 手動Merge
    MERGED --> [*]
```

---

### 2. Semi Auto Coding（半自動コーディング）

#### 特徴

- **CI自動修正**: CI失敗時にAIが自動で修正
- **レビュー自動対応**: レビュー指摘をAIが自動で解決
- **最終確認は人間**: Mergeの判断は人間が行う
- **イテレーション上限**: 無限ループ防止のため回数制限あり

#### ユースケース

- 定型的な機能追加・バグ修正
- CIが整備されたプロジェクト
- 開発者の時間を節約したいが、最終チェックは必要な場合
- チーム開発での品質保証

#### フロー図

```mermaid
sequenceDiagram
    participant U as User
    participant D as zloth Orchestrator
    participant AI as AI Agent (Coder)
    participant R as AI Agent (Reviewer)
    participant GH as GitHub
    participant CI as CI (GitHub Actions)

    U->>D: タスク作成 & 指示 (Semi Auto)
    D->>D: Semi Auto モード開始

    rect rgb(200, 220, 255)
        Note over D,AI: Phase 1: 自動コーディング
        D->>AI: 実装依頼
        AI->>D: コード生成
        D->>GH: Commit & Push
        D->>GH: PR作成
    end

    rect rgb(255, 220, 200)
        Note over D,CI: Phase 2: CI自動修正ループ
        loop CI失敗 & イテレーション < MAX
            CI->>D: Webhook: CI失敗
            D->>D: エラーログ解析
            D->>AI: 修正指示 + エラーログ
            AI->>D: 修正コード
            D->>GH: Commit & Push
            CI->>CI: CI再実行
        end
    end

    rect rgb(220, 255, 220)
        Note over D,R: Phase 3: 自動レビュー対応ループ
        CI->>D: Webhook: CI成功
        loop レビュー指摘あり & イテレーション < MAX
            D->>R: コードレビュー依頼
            R->>D: レビュー結果
            alt 指摘あり
                D->>AI: 修正指示 + レビューフィードバック
                AI->>D: 修正コード
                D->>GH: Commit & Push
            end
        end
    end

    rect rgb(255, 255, 200)
        Note over D,U: Phase 4: 人間による最終確認
        D->>U: PR準備完了通知
        U->>GH: PRレビュー & 確認
        U->>GH: Merge（手動）
    end

    GH->>D: Webhook: PR Merged
    D->>D: タスク完了
```

#### 状態遷移図

```mermaid
stateDiagram-v2
    [*] --> STARTED: Semi Auto開始

    STARTED --> CODING: 実装開始
    CODING --> WAITING_CI: PR作成 & Push

    WAITING_CI --> FIXING_CI: CI失敗 (Webhook)
    WAITING_CI --> REVIEWING: CI成功 (Webhook)

    FIXING_CI --> WAITING_CI: 修正Push
    FIXING_CI --> FAILED: CI修正回数超過

    REVIEWING --> FIXING_REVIEW: レビュー指摘あり
    REVIEWING --> AWAITING_HUMAN: レビューApprove

    FIXING_REVIEW --> WAITING_CI: 修正Push
    FIXING_REVIEW --> FAILED: レビュー修正回数超過

    AWAITING_HUMAN --> MERGED: 人間がMerge
    AWAITING_HUMAN --> CODING: 人間が追加修正指示

    MERGED --> COMPLETED
    COMPLETED --> [*]
    FAILED --> [*]
```

#### イテレーション管理

```mermaid
graph TB
    subgraph "イテレーション制限"
        A[CI修正] --> B{CI回数 < 5?}
        B -->|Yes| C[修正実行]
        B -->|No| D[FAILED: CI修正上限]

        E[レビュー修正] --> F{Review回数 < 3?}
        F -->|Yes| G[修正実行]
        F -->|No| H[FAILED: Review修正上限]

        I[トータル] --> J{合計 < 10?}
        J -->|Yes| K[継続]
        J -->|No| L[FAILED: 総イテレーション上限]
    end
```

---

### 3. Full Auto Coding（完全自動コーディング）

#### 特徴

- **Human-out-of-the-loop**: 人間の介入なしで完全自動化
- **厳格なマージ条件**: 品質を担保するためのGate
- **自動ロールバック**: 問題発生時の自動対処
- **監査ログ**: すべての操作を記録

#### ユースケース

- 依存ライブラリの自動アップデート
- 定型的なリファクタリング
- ボイラープレートコードの生成
- 高信頼性のCIが整備されたプロジェクト
- 夜間/週末の自動開発

#### フロー図

```mermaid
sequenceDiagram
    participant U as User
    participant D as zloth Orchestrator
    participant AI as AI Agent (Coder)
    participant R as AI Agent (Reviewer)
    participant GH as GitHub
    participant CI as CI (GitHub Actions)

    U->>D: タスク作成 & 指示 (Full Auto)
    D->>D: Full Auto モード開始

    rect rgb(200, 220, 255)
        Note over D,AI: Phase 1: 自動コーディング
        D->>AI: 実装依頼
        AI->>D: コード生成
        D->>GH: Commit & Push
        D->>GH: PR作成
    end

    rect rgb(255, 220, 200)
        Note over D,CI: Phase 2: CI自動修正ループ
        loop CI失敗 & イテレーション < MAX
            CI->>D: Webhook: CI失敗
            D->>D: エラーログ解析
            D->>AI: 修正指示 + エラーログ
            AI->>D: 修正コード
            D->>GH: Commit & Push
            CI->>CI: CI再実行
        end
    end

    rect rgb(220, 255, 220)
        Note over D,R: Phase 3: 自動レビュー対応ループ
        CI->>D: Webhook: CI成功
        loop レビュー指摘あり & イテレーション < MAX
            D->>R: コードレビュー依頼
            R->>D: レビュー結果
            alt 指摘あり
                D->>AI: 修正指示 + レビューフィードバック
                AI->>D: 修正コード
                D->>GH: Commit & Push
            end
        end
    end

    rect rgb(200, 255, 255)
        Note over D,GH: Phase 4: 自動マージ
        D->>D: マージ条件チェック
        alt すべての条件クリア
            D->>GH: Squash Merge実行
            D->>GH: ブランチ削除
            D->>D: タスク完了
        else 条件未達
            D->>D: FAILED
            D->>U: 失敗通知
        end
    end

    opt 通知
        D->>U: 完了通知（Slack/Email等）
    end
```

#### マージ条件 (Merge Gates)

```mermaid
graph TB
    subgraph "必須条件 (All Must Pass)"
        G1[CI Green]
        G2[Review Score >= 0.75]
        G3[No Conflicts]
        G4[Tests Pass]
        G5[Type Check Pass]
        G6[Lint Clean]
        G7[Format Check]
        G8[Security Scan Clean]
        G9[Coverage >= 80%]
    end

    G1 --> M{All Pass?}
    G2 --> M
    G3 --> M
    G4 --> M
    G5 --> M
    G6 --> M
    G7 --> M
    G8 --> M
    G9 --> M

    M -->|Yes| MERGE[Auto Merge]
    M -->|No| FAIL[Fail & Notify]
```

#### 状態遷移図

```mermaid
stateDiagram-v2
    [*] --> STARTED: Full Auto開始

    STARTED --> CODING: 実装開始
    CODING --> WAITING_CI: PR作成 & Push

    WAITING_CI --> FIXING_CI: CI失敗 (Webhook)
    WAITING_CI --> REVIEWING: CI成功 (Webhook)

    FIXING_CI --> WAITING_CI: 修正Push
    FIXING_CI --> FAILED: CI修正回数超過

    REVIEWING --> FIXING_REVIEW: レビュー指摘あり
    REVIEWING --> MERGE_CHECK: レビューApprove

    FIXING_REVIEW --> WAITING_CI: 修正Push
    FIXING_REVIEW --> FAILED: レビュー修正回数超過

    MERGE_CHECK --> MERGING: 全条件クリア
    MERGE_CHECK --> FAILED: 条件未達

    MERGING --> COMPLETED: Merge成功
    MERGING --> FAILED: Merge失敗

    COMPLETED --> [*]
    FAILED --> [*]
```

---

## アーキテクチャ

### AI Role Layer

各コーディングモードは、共通の **AI Role** インターフェースを使用して実装・レビューを実行する。
AI Role の詳細は [AI Role リファクタリング計画](./refactoring-ai-role.md) を参照。

```mermaid
flowchart TB
    subgraph "Coding Mode Layer"
        IC[Interactive Controller]
        SC[Semi Auto Controller]
        FC[Full Auto Controller]
    end

    subgraph "AI Role Layer"
        IR[Implementation Role<br/>RunService]
        RR[Review Role<br/>ReviewService]
        BR[Breakdown Role<br/>BreakdownService]
    end

    subgraph "Executor Layer"
        CE[Claude Code]
        CX[Codex CLI]
        GE[Gemini CLI]
    end

    IC --> IR
    IC --> RR
    SC --> IR
    SC --> RR
    FC --> IR
    FC --> RR

    IR --> CE
    IR --> CX
    IR --> GE
    RR --> CE
    RR --> CX
    RR --> GE
```

#### 各モードで使用するAI Role

| モード | Implementation Role | Review Role |
|--------|---------------------|-------------|
| Interactive | ユーザー指示で実行 | ユーザーがReviewボタンで実行 |
| Semi Auto | 自動実行 | CI成功後に自動実行 |
| Full Auto | 自動実行 | CI成功後に自動実行 |

### システム全体像

```mermaid
flowchart TB
    subgraph User["User Interface"]
        UI[Web UI]
        API_Client[API Client]
    end

    subgraph Orchestrator["zloth Orchestrator"]
        ModeSelector[Mode Selector]
        InteractiveCtrl[Interactive Controller]
        SemiAutoCtrl[Semi Auto Controller]
        FullAutoCtrl[Full Auto Controller]
        StateManager[State Manager]
    end

    subgraph Executors["Executors"]
        ClaudeCode[Claude Code Executor]
        CodexCLI[Codex CLI Executor]
        GeminiCLI[Gemini CLI Executor]
        ReviewerExec[Reviewer Executor]
    end

    subgraph Services["Services"]
        CIWatcher[CI Watcher]
        MergeService[Merge Service]
        NotifyService[Notification Service]
    end

    subgraph External["External"]
        GitHub[GitHub API]
        GitHubActions[GitHub Actions]
        Slack[Slack/Email]
    end

    UI --> API_Client
    API_Client --> ModeSelector

    ModeSelector --> InteractiveCtrl
    ModeSelector --> SemiAutoCtrl
    ModeSelector --> FullAutoCtrl

    InteractiveCtrl --> StateManager
    SemiAutoCtrl --> StateManager
    FullAutoCtrl --> StateManager

    StateManager --> ClaudeCode
    StateManager --> CodexCLI
    StateManager --> GeminiCLI
    StateManager --> ReviewerExec

    ClaudeCode --> GitHub
    CIWatcher --> GitHubActions
    MergeService --> GitHub
    NotifyService --> Slack

    GitHubActions -->|Webhook| CIWatcher
    CIWatcher --> StateManager
```

### モード別コントローラー

```mermaid
classDiagram
    class BaseController {
        <<abstract>>
        +task: Task
        +state: CodingState
        +start()
        +handle_event(event)
        #on_coding_complete()
        #on_ci_result(result)
        #on_review_result(result)
    }

    class InteractiveController {
        +start()
        +handle_user_message(msg)
        +request_review()
        -wait_for_user_input()
    }

    class SemiAutoController {
        +start()
        +auto_fix_ci(errors)
        +auto_fix_review(issues)
        -check_iteration_limits()
        -notify_ready_for_merge()
    }

    class FullAutoController {
        +start()
        +auto_fix_ci(errors)
        +auto_fix_review(issues)
        +auto_merge()
        -check_merge_conditions()
        -execute_merge()
    }

    BaseController <|-- InteractiveController
    BaseController <|-- SemiAutoController
    BaseController <|-- FullAutoController
```

---

## データモデル

### CodingMode Enum

```python
class CodingMode(str, Enum):
    """コーディングモード"""
    INTERACTIVE = "interactive"
    SEMI_AUTO = "semi_auto"
    FULL_AUTO = "full_auto"
```

### CodingState

```python
class CodingPhase(str, Enum):
    """コーディングフェーズ"""
    IDLE = "idle"
    CODING = "coding"
    WAITING_CI = "waiting_ci"
    FIXING_CI = "fixing_ci"
    REVIEWING = "reviewing"
    FIXING_REVIEW = "fixing_review"
    AWAITING_HUMAN = "awaiting_human"  # Semi Auto only
    MERGE_CHECK = "merge_check"        # Full Auto only
    MERGING = "merging"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CodingState:
    """コーディング状態"""
    task_id: str
    mode: CodingMode
    phase: CodingPhase
    iteration: int = 0
    ci_iterations: int = 0
    review_iterations: int = 0
    pr_number: int | None = None
    current_sha: str | None = None
    last_ci_result: CIResult | None = None
    last_review_result: ReviewResult | None = None
    error: str | None = None
    started_at: datetime
    last_activity: datetime
```

### Task拡張

```python
class TaskCreate(BaseModel):
    repo_id: str
    title: str | None = None
    coding_mode: CodingMode = CodingMode.INTERACTIVE  # 新規追加
```

### イテレーション制限

```python
@dataclass
class IterationLimits:
    """モード別イテレーション制限"""
    # Interactive: 制限なし（人間が制御）

    # Semi Auto / Full Auto
    max_ci_iterations: int = 5
    max_review_iterations: int = 3
    max_total_iterations: int = 10

    # Full Auto only
    min_review_score: float = 0.75
    coverage_threshold: float = 80.0

    # Timeouts
    timeout_minutes: int = 60
    ci_wait_timeout_minutes: int = 15
```

---

## API設計

### エンドポイント

```yaml
# タスク作成（モード指定）
POST /v1/tasks:
  request:
    repo_id: string
    title: string?
    coding_mode: "interactive" | "semi_auto" | "full_auto"
  response:
    task: Task

# 自動実行開始（Semi Auto / Full Auto）
POST /v1/tasks/{task_id}/auto-start:
  request:
    instruction: string
    executor_types: ExecutorType[]
  response:
    status: "started"
    state: CodingState

# 状態取得
GET /v1/tasks/{task_id}/coding-state:
  response:
    state: CodingState

# 自動実行キャンセル
POST /v1/tasks/{task_id}/auto-cancel:
  response:
    cancelled: boolean

# イベント通知（Webhook）
POST /v1/webhooks/ci:
  request:
    event: "ci_completed"
    pr_number: int
    conclusion: "success" | "failure"
    jobs: dict

# 人間によるMerge承認（Semi Auto）
POST /v1/tasks/{task_id}/approve-merge:
  response:
    merged: boolean
```

### WebSocket（リアルタイム更新）

```yaml
# 状態変更の購読
WS /v1/tasks/{task_id}/subscribe:
  events:
    - type: "phase_changed"
      data: { phase: CodingPhase, iteration: int }
    - type: "ci_result"
      data: { success: boolean, details: object }
    - type: "review_result"
      data: { approved: boolean, score: float, issues: array }
    - type: "completed"
      data: { merged: boolean, pr_url: string }
    - type: "failed"
      data: { error: string, phase: CodingPhase }
```

---

## モード比較表

| 項目 | Interactive | Semi Auto | Full Auto |
|------|-------------|-----------|-----------|
| **人間の介入** | 各ステップ | 最終Mergeのみ | なし |
| **CI失敗時** | 人間が判断 | AI自動修正 | AI自動修正 |
| **レビュー指摘** | 人間が判断 | AI自動対応 | AI自動対応 |
| **Merge** | 手動 | 手動 | 自動 |
| **イテレーション制限** | なし | あり | あり |
| **マージ条件** | なし | なし | 厳格 |
| **適用シナリオ** | 設計検討、複雑実装 | 定型作業、時間節約 | 定型作業、夜間実行 |
| **リスク** | 低 | 中 | 高 |
| **効率** | 低〜中 | 中〜高 | 高 |

---

## UI設計

### モード選択UI

```mermaid
graph TB
    subgraph "タスク作成画面"
        A[リポジトリ選択]
        B[タスクタイトル]

        subgraph "モード選択"
            M1["🎯 Interactive<br/>対話しながら実装"]
            M2["🚀 Semi Auto<br/>AIが自走、最後に確認"]
            M3["⚡ Full Auto<br/>完全自動化"]
        end

        C[指示入力]
        D[実行ボタン]
    end

    A --> B
    B --> M1
    B --> M2
    B --> M3
    M1 --> C
    M2 --> C
    M3 --> C
    C --> D
```

### 実行状態表示

```mermaid
graph LR
    subgraph "Semi Auto / Full Auto 進捗表示"
        P1[Coding] --> P2[CI]
        P2 --> P3[Review]
        P3 --> P4[Merge]

        style P1 fill:#4caf50
        style P2 fill:#ffeb3b
        style P3 fill:#e0e0e0
        style P4 fill:#e0e0e0
    end

    subgraph "詳細情報"
        I1["イテレーション: 3/10"]
        I2["CI修正: 2/5"]
        I3["Review修正: 0/3"]
        I4["経過時間: 15:32"]
    end
```

---

## セキュリティ考慮事項

### Full Auto モード固有のリスク

```mermaid
graph TB
    subgraph "リスク"
        R1[意図しないコードがMergeされる]
        R2[無限ループでリソース消費]
        R3[機密情報の漏洩]
        R4[破壊的変更の自動適用]
    end

    subgraph "対策"
        M1[厳格なマージ条件Gate]
        M2[イテレーション上限]
        M3[Forbidden Patterns]
        M4[Protected Branches]
        M5[監査ログ]
    end

    R1 --> M1
    R2 --> M2
    R3 --> M3
    R4 --> M4
    R4 --> M5
```

### 禁止パターン

```python
FORBIDDEN_PATTERNS = [
    # 機密情報
    r"(?i)(api[_-]?key|secret|password|token)\s*=\s*['\"][^'\"]+['\"]",
    r"sk-[a-zA-Z0-9]{48}",  # OpenAI
    r"ghp_[a-zA-Z0-9]{36}",  # GitHub PAT
    r"AKIA[0-9A-Z]{16}",    # AWS Access Key

    # 破壊的操作
    r"git push --force",
    r"git reset --hard",
    r"DROP DATABASE",
    r"rm -rf /",
]
```

### モード別権限

| 操作 | Interactive | Semi Auto | Full Auto |
|------|-------------|-----------|-----------|
| ファイル編集 | ✅ | ✅ | ✅ |
| Git commit | ✅ | ✅ | ✅ |
| Git push | ✅ | ✅ | ✅ |
| PR作成 | ✅ | ✅ | ✅ |
| Auto Merge | ❌ | ❌ | ✅（条件付き）|
| Force Push | ❌ | ❌ | ❌ |
| Protected Branch変更 | ❌ | ❌ | ❌ |

---

## 通知設計

### 通知タイミング

```mermaid
graph TB
    subgraph "Interactive"
        N1[なし（UIで直接確認）]
    end

    subgraph "Semi Auto"
        N2[PR準備完了]
        N3[失敗時]
    end

    subgraph "Full Auto"
        N4[完了時]
        N5[失敗時]
        N6[警告（高イテレーション）]
    end
```

### 通知チャネル

- Slack Webhook
- Email
- GitHub Notification
- Discord Webhook（将来）

---

## 設定

### 環境変数

```bash
# モード設定
ZLOTH_DEFAULT_CODING_MODE=interactive  # デフォルトモード

# イテレーション制限
ZLOTH_MAX_CI_ITERATIONS=5
ZLOTH_MAX_REVIEW_ITERATIONS=3
ZLOTH_MAX_TOTAL_ITERATIONS=10

# Full Auto専用
ZLOTH_AUTO_MERGE_ENABLED=true
ZLOTH_MIN_REVIEW_SCORE=0.75
ZLOTH_COVERAGE_THRESHOLD=80

# 通知
ZLOTH_SLACK_WEBHOOK_URL=https://hooks.slack.com/...
ZLOTH_NOTIFY_ON_COMPLETE=true
ZLOTH_NOTIFY_ON_FAILURE=true

# タイムアウト
ZLOTH_TIMEOUT_MINUTES=60
ZLOTH_CI_WAIT_TIMEOUT_MINUTES=15
```

### プロジェクト設定（.zloth.yml）

```yaml
coding:
  default_mode: semi_auto

  interactive:
    # 特別な設定なし

  semi_auto:
    max_ci_iterations: 5
    max_review_iterations: 3
    notify_ready: true

  full_auto:
    enabled: true  # false で無効化
    max_ci_iterations: 5
    max_review_iterations: 3
    min_review_score: 0.8
    coverage_threshold: 85
    merge_method: squash
    delete_branch_after_merge: true

notifications:
  slack:
    webhook_url: ${SLACK_WEBHOOK_URL}
    channels:
      on_complete: "#dev-notifications"
      on_failure: "#dev-alerts"
```

---

## 実装ロードマップ

### Phase 1: 基盤構築

- [ ] `CodingMode` enum 追加
- [ ] `CodingState` モデル追加
- [ ] `BaseController` 抽象クラス実装
- [ ] Task テーブルに `coding_mode` カラム追加

### Phase 2: Interactive Mode（既存機能整理）

- [ ] `InteractiveController` 実装
- [ ] 既存フローのリファクタリング
- [ ] UI でのモード表示

### Phase 3: Semi Auto Mode

- [ ] `SemiAutoController` 実装
- [ ] CI Webhook ハンドラー実装
- [ ] レビュー自動実行
- [ ] 「Merge待ち」通知機能
- [ ] UI 進捗表示

### Phase 4: Full Auto Mode

- [ ] `FullAutoController` 実装
- [ ] マージ条件チェッカー
- [ ] Auto Merge 実行
- [ ] 監査ログ
- [ ] 完了/失敗通知

### Phase 5: 拡張機能

- [ ] WebSocket リアルタイム更新
- [ ] Slack/Discord 通知連携
- [ ] プロジェクト設定ファイルサポート
- [ ] ダッシュボード（統計表示）

---

## 関連ドキュメント

- [Agentic Zloth](./agentic-zloth.md) - Semi Auto / Full Auto の詳細実装
- [Code Review Feature](./review.md) - ReviewService の詳細仕様
- [AI Role Refactoring](./refactoring-ai-role.md) - AI Role 共通インターフェース
- [Architecture](./architecture.md)
- [Multi AI Coding Tool](./ai-coding-tool-multiple.md)
- [Git Operation Design](./git_operation_design.md)
