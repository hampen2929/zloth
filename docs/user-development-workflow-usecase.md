# dursor を使った開発ワークフロー ユースケース

このドキュメントでは、dursor を活用したヒアリングベースの開発ワークフローについて説明します。

## 概要

dursor は、ヒアリングで得た要件をAIによるタスク分解から実装・レビュー・マージまでを一貫して管理できるプラットフォームです。人間が要件定義とレビューに集中し、AIがコード実装を担当する協働開発ワークフローを実現します。

## ワークフロー全体図

```mermaid
flowchart TD
    subgraph "ヒアリングフェーズ"
        A[👤 クライアントヒアリング] --> B[📝 要件文書の作成]
    end

    subgraph "タスク分解フェーズ"
        B --> C[✨ Task Breakdown]
        C --> D{タスク確認}
        D -->|修正が必要| C
        D -->|OK| E[📋 Backlog に追加]
    end

    subgraph "計画フェーズ"
        E --> F[🎯 ToDo に移動]
        F --> G[優先度の設定]
    end

    subgraph "実装フェーズ"
        G --> H[🤖 AI にアサイン]
        H --> I[⚙️ InProgress]
        I --> J{実行完了?}
        J -->|エラー| K[追加 Run 作成]
        K --> I
        J -->|成功| L[👁️ InReview]
    end

    subgraph "PR作成フェーズ"
        L --> M[🔀 人間が PR 作成]
    end

    subgraph "レビュー・マージフェーズ"
        M --> N[👁️ 人間がコードレビュー]
        N --> O{レビュー結果}
        O -->|修正が必要| P[追加指示を送信]
        P --> I
        O -->|承認| Q[✅ PR マージ]
        Q --> R[Done]
    end

    style A fill:#e1f5fe
    style C fill:#f3e5f5
    style H fill:#fff3e0
    style L fill:#e8f5e9
    style M fill:#dbeafe
    style R fill:#c8e6c9
```

## 各フェーズの詳細

### 1. ヒアリングフェーズ

クライアントや関係者から要件をヒアリングし、文書化するフェーズです。

```mermaid
sequenceDiagram
    participant C as クライアント
    participant D as 開発者
    participant Doc as 要件文書

    C->>D: 課題・要望を説明
    D->>C: 質問・確認
    C->>D: 詳細を回答
    D->>Doc: ヒアリング内容を記録
    Note over Doc: - 現在の課題<br/>- 期待する機能<br/>- 優先度
```

**アウトプット例:**
```
・ログイン画面でパスワードを間違えるとエラーメッセージが表示されない
・ユーザー一覧に検索機能が欲しい
・管理者のみアクセスできるページを作りたい
```

---

### 2. タスク分解フェーズ（Task Breakdown）

ヒアリング内容を dursor の Breakdown 機能でタスクに分解します。

```mermaid
flowchart LR
    subgraph "入力"
        A[📝 ヒアリング文書]
        B[📂 リポジトリ選択]
        C[🌿 ブランチ選択]
        D[🤖 Agent 選択]
    end

    subgraph "Agent処理"
        E[コードベース分析]
        F[既存実装の把握]
        G[タスク生成]
    end

    subgraph "出力"
        H[📋 分解されたタスク]
    end

    A --> E
    B --> E
    C --> E
    D --> E
    E --> F --> G --> H
```

**使用する機能:**
- **Breakdown Modal** (`/backlog` ページの「Breakdown」ボタン)
- **対応 Agent**: Claude Code / Codex CLI / Gemini CLI

**Agent が行う処理:**
1. リポジトリのコードベースを分析
2. 既存のアーキテクチャ・パターンを把握
3. ヒアリング内容を具体的なタスクに分解
4. 各タスクに対象ファイル・実装ヒントを付与

**分解結果の例:**

| タスク | タイプ | サイズ | 対象ファイル |
|--------|--------|--------|--------------|
| ログインエラーメッセージ表示修正 | bug_fix | small | `src/components/LoginForm.tsx` |
| ユーザー一覧検索機能追加 | feature | medium | `src/pages/users/index.tsx`, `src/lib/api.ts` |
| 管理者専用ページ実装 | feature | large | `src/middleware.ts`, `src/lib/auth.ts` |

---

### 3. バックログ管理フェーズ（Backlog）

分解されたタスクをバックログで管理し、実装順序を決定します。

```mermaid
stateDiagram-v2
    [*] --> Draft: タスク分解完了
    Draft --> Ready: レビュー完了
    Ready --> InProgress: 作業開始
    InProgress --> Done: 完了

    note right of Draft: 内容の確認・編集
    note right of Ready: 実装準備完了
```

**Backlog ページの機能:**
- タスク一覧の表示・フィルタリング
- ステータス管理（Draft → Ready → In Progress → Done）
- タスク詳細の編集

**操作フロー:**
1. Breakdown 結果を確認
2. 必要に応じてタスク内容を編集
3. Ready ステータスに変更してバックログに追加

---

### 4. ToDo 管理フェーズ（Kanban: Backlog → ToDo）

やるべきタスクを Kanban ボードの ToDo カラムに移動します。

```mermaid
flowchart LR
    subgraph "Kanban Board"
        A[Backlog]
        B[ToDo]
        C[InProgress]
        D[InReview]
        E[Done]
    end

    A -->|手動移動| B
    B -->|AIにアサイン| C
    C -->|Run完了| D
    D -->|PRマージ| E

    style B fill:#3b82f6,color:#fff
```

**操作:**
- Kanban ボード (`/kanban`) でタスクカードをドラッグ＆ドロップ
- または「→ ToDo」ボタンをクリック

**ToDo に移動する基準:**
- 優先度が高い
- 依存関係が解決済み
- 実装の準備が整っている

---

### 5. AI 実装フェーズ（Kanban: ToDo → InProgress）

優先度の高いタスクを AI にアサインして実装を依頼します。

```mermaid
sequenceDiagram
    participant U as 開発者
    participant T as Task 画面
    participant A as AI Agent
    participant W as Worktree

    U->>T: タスクを開く
    U->>T: 実装指示を入力
    U->>T: Executor/Model を選択
    U->>T: Run を作成
    T->>A: 実行開始
    A->>W: コードベース読み込み
    A->>W: コード変更を生成
    A->>T: 結果を返却
    T->>U: Diff を表示
```

**使用する機能:**
- **Task 詳細画面** (`/tasks/[taskId]`)
- **ChatCodeView** コンポーネント

**選択可能な Executor:**

| タイプ | 説明 | 用途 |
|--------|------|------|
| `patch_agent` | LLM API 直接呼び出し | シンプルな変更 |
| `claude_code` | Claude Code CLI | 複雑な実装 |
| `codex_cli` | Codex CLI | OpenAI ベースの実装 |
| `gemini_cli` | Gemini CLI | Google AI ベースの実装 |

**並列実行の活用:**
```mermaid
flowchart TD
    T[タスク] --> R1[Run: Claude Code]
    T --> R2[Run: Codex CLI]
    T --> R3[Run: Gemini CLI]
    R1 --> C[結果を比較]
    R2 --> C
    R3 --> C
    C --> B[ベストな結果を採用]
```

---

### 6. PR 作成フェーズ（Kanban: InProgress → InReview）

AI の実装が完了したら、人間が PR を作成します。

```mermaid
flowchart TD
    A[Run 完了] --> B[InReview に自動遷移]
    B --> C[Diff を確認]
    C --> D{PR 作成可能?}
    D -->|問題あり| E[追加指示を送信]
    E --> F[新しい Run を作成]
    F --> G[InProgress に戻る]
    D -->|OK| H[🔀 PR を作成]

    style B fill:#8b5cf6,color:#fff
    style H fill:#3b82f6,color:#fff
```

**PR 作成前の確認:**
- Diff の内容が要件を満たしているか
- 明らかなバグやエラーがないか
- PR を作成する準備が整っているか

**PR 作成機能:**
- Task 詳細画面の「Create PR」ボタン
- タイトル・説明文の自動生成
- テンプレートに基づく PR 説明

---

### 7. レビュー・マージフェーズ（GitHub PR レビュー → Done）

PR 作成後、GitHub 上でコードレビューを行い、マージします。

```mermaid
sequenceDiagram
    participant D as dursor
    participant G as GitHub
    participant H as 人間（PR作成者）
    participant R as レビュアー

    D->>G: PR を作成
    Note over G: - ブランチ作成<br/>- Diff をコミット<br/>- PR をオープン
    H->>R: レビュー依頼
    R->>G: コードレビュー
    alt 修正が必要
        R->>H: 修正リクエスト
        H->>D: 追加指示を送信
        D->>D: 新しい Run を作成
        D->>G: PR を更新
        R->>G: 再レビュー
    end
    R->>G: Approve
    H->>G: Merge
    G->>D: マージ検出
    D->>D: Done に自動遷移
```

**レビュー観点:**
- コードの品質・可読性
- 要件との整合性
- セキュリティ上の問題
- テストの有無

**フィードバックの送信（修正が必要な場合）:**
```
修正してください:
- エラーハンドリングを追加
- 入力バリデーションを強化
- コメントを追加
```

**Done への遷移:**
- GitHub で PR がマージされると自動的に Done に遷移
- Kanban ボードの「Sync」ボタンで手動同期も可能

---

## ステータス遷移まとめ

```mermaid
stateDiagram-v2
    [*] --> Backlog: タスク作成

    Backlog --> ToDo: 手動移動
    ToDo --> Backlog: 手動で戻す

    ToDo --> InProgress: Run 作成
    Backlog --> InProgress: Run 作成

    InProgress --> InReview: Run 完了（自動）
    InReview --> InProgress: 追加 Run 作成

    InReview --> Done: PR マージ（自動）

    Backlog --> Archived: 手動アーカイブ
    ToDo --> Archived: 手動アーカイブ
    InReview --> Archived: 手動アーカイブ
    Archived --> Backlog: リストア

    Done --> [*]
```

| 遷移 | 方法 | トリガー |
|------|------|----------|
| → Backlog | 手動 | 初期状態 / リストア |
| Backlog → ToDo | 手動 | ドラッグ＆ドロップ / ボタン |
| ToDo → InProgress | 自動 | Run が running になった時 |
| InProgress → InReview | 自動 | すべての Run が完了した時 |
| InReview → Done | 自動 | PR がマージされた時 |
| → Archived | 手動 | アーカイブボタン |

---

## 典型的なワークフロー例

### シナリオ: ログイン機能のバグ修正

```mermaid
timeline
    title ログインエラー表示バグ修正
    section 1. ヒアリング
        クライアント報告 : パスワード間違いでエラーが出ない
    section 2. 分解
        Breakdown 実行 : Agent がコードを分析
                       : LoginForm.tsx の catch 処理漏れを特定
    section 3. 計画
        Backlog 確認 : タスク内容を確認
        ToDo 移動 : 優先度高として移動
    section 4. 実装
        AI にアサイン : Claude Code で実装
        Diff 確認 : setError 呼び出し追加を確認
    section 5. PR 作成
        Diff を確認 : 実装内容が正しいことを確認
        PR 作成 : GitHub に PR を作成
    section 6. レビュー・マージ
        コードレビュー : チームメンバーがレビュー
        マージ完了 : Done に自動遷移
```

---

## ベストプラクティス

### 1. ヒアリング時
- 具体的な再現手順を記録する
- 期待する動作を明確にする
- 優先度・緊急度を確認する

### 2. タスク分解時
- 適切な Agent を選択する（複雑な変更は CLI Agent を推奨）
- 分解結果を必ずレビューする
- 大きすぎるタスクは手動で分割する

### 3. 実装時
- 複数モデルで並列実行して結果を比較する
- 追加指示は具体的に記述する
- テストの追加も指示に含める

### 4. PR 作成時
- Diff を丁寧に確認してから PR を作成する
- PR テンプレートを活用する
- テスト手順を明記する
- 関連 Issue をリンクする

### 5. レビュー時
- コードの品質・可読性を確認する
- セキュリティ上の問題がないか確認する
- 不明点は追加質問する

---

## 関連ドキュメント

- [Kanban 機能設計](./kanban.md)
- [タスク分解機能設計](./task-split.md)
- [API 設計](./api.md)
- [アーキテクチャ](./architecture.md)
