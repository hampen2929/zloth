# タスク分解機能 設計ドキュメント

## 概要

ヒアリング時に得られた文章（要件や課題の説明）を貼り付けて、**Agent tool（Claude Code / Codex CLI / Gemini CLI）を使ってコードベースを理解した上で**、機能追加やバグ修正のタスクに分解し、一括登録する機能を追加します。

## ユースケース

```
1. ユーザーがクライアントからヒアリングを実施
2. ヒアリング内容をテキストとして記録
3. dursor にヒアリング文章を貼り付け
4. Agent tool がコードベースを読み込み、既存実装との整合性を考慮してタスクに分解
5. 分解されたタスクを確認・編集
6. 選択したタスクを一括登録
7. 個別のタスクを選択して実行（既存機能）
```

## Agent tool を使う理由

単純な LLM API 呼び出しではなく Agent tool を使用する理由:

1. **コードベースの理解**: Agent は実際のコードを読んで既存実装を把握できる
2. **整合性の確保**: 既存のアーキテクチャ、命名規則、パターンに沿ったタスク分解
3. **実現可能性の判断**: コードを見て、タスクの難易度や依存関係を正確に評価
4. **具体的な実装方針**: どのファイルを変更すべきかなど、具体的な指針を含められる

---

## UI 配置案

### 案1: サイドバーにボタン追加（推奨）

```
┌─────────────────────┐
│ dursor             │
├─────────────────────┤
│ [+ New Task]       │  ← 既存
│ [✦ Breakdown]      │  ← 新規追加
├─────────────────────┤
│ Search tasks...    │
│ 3 tasks | Newest ▼ │
├─────────────────────┤
│ Task 1             │
│ Task 2             │
│ ...                │
└─────────────────────┘
```

**メリット**:
- 既存の「New Task」ボタンと並べることで、タスク作成の2つの方法として明確
- サイドバーは常に表示されるため、アクセスしやすい
- 既存UIへの影響が最小限

**実装箇所**: `apps/web/src/components/Sidebar.tsx`

### 案2: ホームページにタブ切り替え

```
┌───────────────────────────────────────────┐
│  [Single Task] | [Breakdown]              │
├───────────────────────────────────────────┤
│                                           │
│  ┌─────────────────────────────────────┐  │
│  │ ヒアリング内容をペースト...         │  │
│  │                                     │  │
│  └─────────────────────────────────────┘  │
│                                           │
│  [分解する]                               │
└───────────────────────────────────────────┘
```

**メリット**:
- ホームページの既存入力エリアを再利用できる
- 単一タスクと分解モードを切り替えられる

**デメリット**:
- ホームページの役割が複雑になる
- 既存UIの大幅な変更が必要

### 案3: 新規ページ追加 `/breakdown`

専用ページを作成し、より大きな入力エリアと分解結果表示を持つ。

**メリット**:
- 大量のテキスト入力に適したUI設計が可能
- 複雑なワークフローを収容できる

**デメリット**:
- 新しいルートの追加
- UIの一貫性維持に注意が必要

---

## 推奨案: 案1（サイドバー + モーダル）

サイドバーに「Breakdown」ボタンを追加し、クリックするとモーダルが開く方式を推奨します。

### 理由
1. 既存UIへの影響が最小限
2. モーダル形式により、どのページからでもアクセス可能
3. 設定モーダル（`SettingsModal`）と同様のパターンで実装でき、コードの一貫性を維持

---

## UI 詳細設計

### Breakdown モーダル

```
┌──────────────────────────────────────────────────────────┐
│  ✦ タスク分解                                      [×]   │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  リポジトリ: [owner/repo ▼]    ブランチ: [main ▼]       │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ ヒアリング内容を貼り付けてください...              │  │
│  │                                                    │  │
│  │ 例:                                               │  │
│  │ ・ログイン画面でパスワードを間違えると           │  │
│  │   エラーメッセージが表示されない                 │  │
│  │ ・ユーザー一覧に検索機能が欲しい                 │  │
│  │ ・管理者のみアクセスできるページを作りたい       │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  Agent: [◉ Claude Code] [○ Codex CLI] [○ Gemini CLI]    │
│         ↑ コードベースを読んでタスク分解                 │
│                                                          │
│  [分解する]                                              │
│                                                          │
├──────────────────────────────────────────────────────────┤
│  📋 分解中...                                            │
│  ┌────────────────────────────────────────────────────┐  │
│  │ > Analyzing codebase structure...                  │  │
│  │ > Found 45 TypeScript files                        │  │
│  │ > Checking existing authentication implementation..│  │
│  │ > Analyzing user management module...              │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
├──────────────────────────────────────────────────────────┤
│  分解結果 (3件)                                          │
│                                                          │
│  ☑ 🐛 ログイン画面のエラーメッセージ表示修正            │
│      バグ修正 | 推定: 小                                 │
│      対象: src/components/LoginForm.tsx                  │
│      詳細: handleSubmit関数でcatch時のsetError呼び出し   │
│           が欠落している                                │
│                                                          │
│  ☑ ✨ ユーザー一覧に検索機能を追加                       │
│      機能追加 | 推定: 中                                 │
│      対象: src/pages/users/index.tsx, src/lib/api.ts    │
│      詳細: 既存のuseSWRパターンに合わせてフィルタ機能... │
│                                                          │
│  ☑ 🔒 管理者専用ページのアクセス制御実装                 │
│      機能追加 | 推定: 大                                 │
│      対象: src/middleware.ts, src/lib/auth.ts           │
│      詳細: 既存のNextAuth設定を拡張してロールベース...   │
│                                                          │
├──────────────────────────────────────────────────────────┤
│  [選択したタスクを登録 (3件)]              [キャンセル]  │
└──────────────────────────────────────────────────────────┘
```

### 状態遷移

```
入力中 → 分解中(Agent実行 + ログストリーミング) → 結果表示 → タスク選択 → 登録中 → 完了
```

---

## API 設計

### 新規エンドポイント

#### `POST /v1/breakdown`

Agent tool を使ってヒアリング文章をタスクに分解する。

**Request:**

```json
{
  "content": "ヒアリング文章...",
  "executor_type": "claude_code",
  "repo_id": "repo-id",
  "context": {
    "language": "ja",
    "additional_info": "オプショナルな追加コンテキスト"
  }
}
```

**Response:**

```json
{
  "breakdown_id": "breakdown-123",
  "tasks": [
    {
      "title": "ログイン画面のエラーメッセージ表示修正",
      "description": "パスワード認証失敗時にエラーメッセージが表示されない問題を修正する",
      "type": "bug_fix",
      "estimated_size": "small",
      "target_files": ["src/components/LoginForm.tsx"],
      "implementation_hint": "handleSubmit関数のcatchブロックでsetError()を呼び出す",
      "tags": ["auth", "ui"]
    },
    {
      "title": "ユーザー一覧に検索機能を追加",
      "description": "ユーザー名・メールアドレスでフィルタリングできる検索機能を実装",
      "type": "feature",
      "estimated_size": "medium",
      "target_files": ["src/pages/users/index.tsx", "src/lib/api.ts"],
      "implementation_hint": "既存のuseSWRパターンを使用し、クエリパラメータでフィルタリング",
      "tags": ["user-management", "search"]
    }
  ],
  "summary": "コードベースを分析し、3件のタスクに分解しました",
  "original_content": "ヒアリング文章...",
  "codebase_analysis": {
    "files_analyzed": 45,
    "relevant_modules": ["auth", "user-management"],
    "tech_stack": ["Next.js", "TypeScript", "Tailwind CSS"]
  }
}
```

#### `GET /v1/breakdown/{breakdown_id}/logs`

タスク分解のログを取得（ストリーミング用）。

**Response:**

```json
{
  "logs": [
    { "line_number": 1, "content": "Analyzing codebase structure...", "timestamp": 1234567890 },
    { "line_number": 2, "content": "Found 45 TypeScript files", "timestamp": 1234567891 }
  ],
  "is_complete": false,
  "total_lines": 2
}
```

#### `POST /v1/tasks/bulk`

複数タスクを一括登録する。

**Request:**

```json
{
  "repo_id": "repo-id",
  "tasks": [
    {
      "title": "タスク1",
      "description": "説明1"
    },
    {
      "title": "タスク2",
      "description": "説明2"
    }
  ]
}
```

**Response:**

```json
{
  "created_tasks": [
    { "id": "task-id-1", "title": "タスク1" },
    { "id": "task-id-2", "title": "タスク2" }
  ],
  "count": 2
}
```

---

## バックエンド実装計画

### 1. 新しいサービス: `BreakdownService`

```
apps/api/src/dursor_api/services/breakdown_service.py
```

**責務**:
- ヒアリング文章と分解指示を受け取る
- 適切な Executor（ClaudeCodeExecutor / CodexExecutor / GeminiExecutor）を選択
- Executor を実行してタスク分解を実行
- 結果のパースとバリデーション

```python
class BreakdownService:
    def __init__(
        self,
        claude_executor: ClaudeCodeExecutor,
        codex_executor: CodexExecutor,
        gemini_executor: GeminiExecutor,
        repo_dao: RepoDAO,
        worktree_service: WorktreeService,
        output_manager: OutputManager,
    ):
        self.executors = {
            ExecutorType.CLAUDE_CODE: claude_executor,
            ExecutorType.CODEX_CLI: codex_executor,
            ExecutorType.GEMINI_CLI: gemini_executor,
        }
        # ...

    async def breakdown(
        self,
        request: TaskBreakdownRequest,
    ) -> TaskBreakdownResponse:
        """ヒアリング文章をタスクに分解する。
        
        1. リポジトリのワークツリーを準備
        2. 分解用プロンプトを構築
        3. 選択されたExecutorで実行
        4. 結果をパースしてタスクリストを返す
        """
        # Worktree準備
        worktree = await self.worktree_service.create(repo_id)
        
        # 分解用プロンプト構築
        instruction = self._build_breakdown_instruction(request.content)
        
        # Executor実行
        executor = self.executors[request.executor_type]
        result = await executor.execute(
            worktree_path=worktree.path,
            instruction=instruction,
            on_output=lambda line: self.output_manager.add_line(breakdown_id, line),
        )
        
        # 結果パース
        return self._parse_breakdown_result(result)
```

### 2. 新しいルート: `routes/breakdown.py`

```
apps/api/src/dursor_api/routes/breakdown.py
```

**エンドポイント**:
- `POST /v1/breakdown` - タスク分解実行
- `GET /v1/breakdown/{breakdown_id}/logs` - ログ取得
- `POST /v1/tasks/bulk` - 一括登録（または `routes/tasks.py` に追加）

### 3. ドメインモデル追加

```python
# domain/models.py に追加

class TaskBreakdownRequest(BaseModel):
    """タスク分解リクエスト"""
    content: str = Field(..., description="ヒアリング文章")
    executor_type: ExecutorType = Field(
        default=ExecutorType.CLAUDE_CODE,
        description="分解に使用するAgent tool"
    )
    repo_id: str = Field(..., description="対象リポジトリID")
    context: dict[str, Any] | None = None

class BrokenDownTask(BaseModel):
    """分解されたタスク"""
    title: str
    description: str
    type: str  # "feature", "bug_fix", "refactoring", "docs", "test"
    estimated_size: str  # "small", "medium", "large"
    target_files: list[str] = []  # 変更対象ファイル
    implementation_hint: str | None = None  # 実装のヒント
    tags: list[str] = []

class CodebaseAnalysis(BaseModel):
    """コードベース分析結果"""
    files_analyzed: int
    relevant_modules: list[str]
    tech_stack: list[str]

class TaskBreakdownResponse(BaseModel):
    """タスク分解レスポンス"""
    breakdown_id: str
    tasks: list[BrokenDownTask]
    summary: str
    original_content: str
    codebase_analysis: CodebaseAnalysis | None = None

class TaskBulkCreate(BaseModel):
    """タスク一括作成リクエスト"""
    repo_id: str
    tasks: list[TaskCreate]

class TaskBulkCreated(BaseModel):
    """タスク一括作成レスポンス"""
    created_tasks: list[Task]
    count: int
```

### 4. プロンプト設計

Agent tool に渡すプロンプトは、コードベースを読んでタスク分解するよう指示します。

```python
BREAKDOWN_INSTRUCTION_TEMPLATE = """
あなたはソフトウェア開発のタスク分解の専門家です。
以下のヒアリング内容を、具体的な開発タスクに分解してください。

## 重要: コードベースの分析
1. まず、このリポジトリのコードベースを確認してください
2. 既存の実装パターン、アーキテクチャ、命名規則を把握してください
3. 各タスクが既存のコードとどう関連するか具体的に示してください

## ヒアリング内容
{content}

## 出力形式
以下のJSON形式で `.dursor-breakdown.json` ファイルに出力してください:

```json
{{
  "codebase_analysis": {{
    "files_analyzed": <分析したファイル数>,
    "relevant_modules": ["関連するモジュール名"],
    "tech_stack": ["使用技術"]
  }},
  "tasks": [
    {{
      "title": "簡潔なタスクタイトル（50文字以内）",
      "description": "タスクの詳細説明。実装方針を含む",
      "type": "feature | bug_fix | refactoring | docs | test",
      "estimated_size": "small | medium | large",
      "target_files": ["変更対象のファイルパス"],
      "implementation_hint": "具体的な実装方法のヒント（既存コードを参照）",
      "tags": ["関連するタグ"]
    }}
  ]
}}
```

## ルール
1. **必ずコードを読んでから**タスクを作成すること
2. target_files は実際に存在するファイルパスを指定
3. implementation_hint は既存のコードパターンを参照して具体的に
4. 各タスクは独立して実行可能な単位にする
5. バグ修正と機能追加は分けて記載する
6. 依存関係がある場合は description に記載する
7. 推定サイズは以下を目安に:
   - small: 1-2ファイルの変更、数時間で完了
   - medium: 3-5ファイルの変更、1日程度
   - large: 複数モジュールにまたがる変更、数日以上
"""
```

---

## フロントエンド実装計画

### 1. 新しいコンポーネント

```
apps/web/src/components/
├── BreakdownModal.tsx        # メインモーダル
├── BreakdownTaskCard.tsx     # 分解されたタスクカード
├── BreakdownTaskList.tsx     # タスクリスト
└── BreakdownLogs.tsx         # ログ表示（StreamingLogsを参考）
```

### 2. API クライアント追加

```typescript
// lib/api.ts に追加

export const breakdownApi = {
  analyze: (data: TaskBreakdownRequest) =>
    fetchApi<TaskBreakdownResponse>('/breakdown', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getLogs: (breakdownId: string, fromLine: number = 0) =>
    fetchApi<{
      logs: OutputLine[];
      is_complete: boolean;
      total_lines: number;
    }>(`/breakdown/${breakdownId}/logs?from_line=${fromLine}`),
};

// tasksApi に追加
export const tasksApi = {
  // ... existing methods
  
  bulkCreate: (data: TaskBulkCreate) =>
    fetchApi<TaskBulkCreated>('/tasks/bulk', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};
```

### 3. TypeScript 型定義追加

```typescript
// types.ts に追加

export type TaskType = 'feature' | 'bug_fix' | 'refactoring' | 'docs' | 'test';
export type EstimatedSize = 'small' | 'medium' | 'large';

export interface TaskBreakdownRequest {
  content: string;
  executor_type: ExecutorType;  // 'claude_code' | 'codex_cli' | 'gemini_cli'
  repo_id: string;
  context?: Record<string, unknown>;
}

export interface BrokenDownTask {
  title: string;
  description: string;
  type: TaskType;
  estimated_size: EstimatedSize;
  target_files: string[];
  implementation_hint: string | null;
  tags: string[];
}

export interface CodebaseAnalysis {
  files_analyzed: number;
  relevant_modules: string[];
  tech_stack: string[];
}

export interface TaskBreakdownResponse {
  breakdown_id: string;
  tasks: BrokenDownTask[];
  summary: string;
  original_content: string;
  codebase_analysis: CodebaseAnalysis | null;
}

export interface TaskBulkCreate {
  repo_id: string;
  tasks: Array<{
    title: string;
    description?: string;
  }>;
}

export interface TaskBulkCreated {
  created_tasks: Task[];
  count: number;
}
```

### 4. Sidebar.tsx の変更

```tsx
// 既存の New Task ボタンの下に追加
<button
  onClick={() => onBreakdownClick()}
  className={cn(
    'flex items-center justify-center gap-2 w-full py-2.5 px-3',
    'bg-purple-600 hover:bg-purple-700 rounded-lg',
    'text-sm font-medium transition-colors',
    'focus:outline-none focus:ring-2 focus:ring-purple-500'
  )}
>
  <SparklesIcon className="w-4 h-4" />
  Breakdown
</button>
```

### 5. ClientLayout.tsx の変更

```tsx
// BreakdownModal の状態管理を追加
const [breakdownOpen, setBreakdownOpen] = useState(false);

// Sidebar に props を追加
<Sidebar
  onSettingsClick={() => setSettingsOpen(true)}
  onBreakdownClick={() => setBreakdownOpen(true)}
/>

// モーダルを追加
<BreakdownModal
  isOpen={breakdownOpen}
  onClose={() => setBreakdownOpen(false)}
/>
```

### 6. Agent セレクター

既存の `ExecutorSelector` コンポーネントを参考に、CLI Executor のみ選択できるセレクターを作成:

```tsx
// BreakdownModal.tsx 内
<div className="flex items-center gap-4">
  <span className="text-sm text-gray-400">Agent:</span>
  {(['claude_code', 'codex_cli', 'gemini_cli'] as const).map((type) => (
    <label key={type} className="flex items-center gap-2 cursor-pointer">
      <input
        type="radio"
        name="executor"
        value={type}
        checked={executorType === type}
        onChange={() => setExecutorType(type)}
        className="text-purple-500"
      />
      <span className="text-sm text-gray-200">
        {type === 'claude_code' && 'Claude Code'}
        {type === 'codex_cli' && 'Codex CLI'}
        {type === 'gemini_cli' && 'Gemini CLI'}
      </span>
    </label>
  ))}
</div>
```

---

## 実装順序

### Phase 1: バックエンド基盤

1. [ ] ドメインモデル追加（`domain/models.py`, `domain/enums.py`）
2. [ ] `BreakdownService` 実装
3. [ ] `routes/breakdown.py` 実装
4. [ ] 結果パース用ユーティリティ実装
5. [ ] テスト追加

### Phase 2: フロントエンド基盤

6. [ ] 型定義追加（`types.ts`）
7. [ ] API クライアント追加（`lib/api.ts`）
8. [ ] `BreakdownModal` コンポーネント作成
9. [ ] `BreakdownTaskCard` コンポーネント作成
10. [ ] `BreakdownLogs` コンポーネント作成（既存の `StreamingLogs` を参考）

### Phase 3: UI 統合

11. [ ] `Sidebar.tsx` にボタン追加
12. [ ] `ClientLayout.tsx` にモーダル統合
13. [ ] E2E テスト追加

### Phase 4: 改善

14. [ ] タスク編集機能（分解結果の修正）
15. [ ] プロンプトの調整・改善
16. [ ] エラーハンドリング強化

---

## 工数見積もり

| Phase | 内容 | 見積もり |
|-------|------|----------|
| Phase 1 | バックエンド基盤 | 6-8時間 |
| Phase 2 | フロントエンド基盤 | 5-7時間 |
| Phase 3 | UI 統合 | 2-3時間 |
| Phase 4 | 改善 | 3-5時間 |
| **合計** | | **16-23時間** |

---

## 考慮事項

### セキュリティ

- ヒアリング文章に機密情報が含まれる可能性があるため、ログに残さない
- Agent tool はワークツリー内でのみ動作し、外部へのアクセスは制限

### UX

- Agent 実行中のログストリーミング表示（既存の Run 実行時と同様）
- 分解結果の編集機能（タイトル・説明の微調整）
- 分解失敗時の適切なエラーメッセージ
- Agent 選択時にどの Agent がインストール済みかを表示

### パフォーマンス

- Agent 実行のタイムアウト設定（既存の Executor と同様）
- 大規模コードベースでの分析時間の目安を表示

### 拡張性

- 複数言語対応（日本語/英語のプロンプト切り替え）
- カスタムプロンプトのサポート（将来）
- タスクテンプレート機能（将来）

### Agent tool の可用性

- CLI がインストールされていない場合のエラーハンドリング
- 各 Agent の認証状態チェック（Claude Code は `~/.claude` の認証情報を使用）
