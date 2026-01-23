# 複数Executor出力比較機能 実装計画

## 概要

複数のExecutor(Claude Code, Codex, Gemini CLI等)で並列実行したタスクの出力を比較・評価する機能を実装します。

## 現状の理解

### 現在のアーキテクチャ
- **Task**: 会話単位(1タスク = 1ゴール)
- **Run**: Executor毎の実行単位、`message_id`で同一指示のRunをグループ化
- **ChatCodeView**: メインのUI、Executorカード(`claude_code`, `codex_cli`, `gemini_cli`)を表示
- **RunResultCard**: 各Runの結果表示(Summary, Diff, Logs)

### 重要なデータ構造
```typescript
interface Run {
  id: string;
  task_id: string;
  message_id: string | null;  // 同一指示のグループ化キー
  executor_type: ExecutorType;
  status: RunStatus;
  summary: string | null;
  patch: string | null;       // Unified diff
  files_changed: FileDiff[];
}
```

## 実装計画

### Phase 1: フロントエンド - Compareボタンの追加

#### 1.1 Compareボタンの配置
**ファイル**: `apps/web/src/components/ChatCodeView.tsx`

- Executorカードの右側に「Compare」ボタンを追加
- 位置: `uniqueExecutorTypes.length > 0`のセクション内(line 650付近)
- 条件: 2つ以上のExecutorが存在し、かついずれかが`succeeded`状態の場合のみ表示

```tsx
// Executorカードセクションに追加
<div className="flex gap-2 overflow-x-auto pb-1">
  {uniqueExecutorTypes.map((executorType) => (...))}

  {/* Compare Button with Model Dropdown */}
  {canCompare && (
    <CompareButton
      taskId={taskId}
      executorTypes={uniqueExecutorTypes}
      runs={runs}
    />
  )}
</div>
```

#### 1.2 CompareButtonコンポーネントの作成
**新規ファイル**: `apps/web/src/components/CompareButton.tsx`

```tsx
interface CompareButtonProps {
  taskId: string;
  executorTypes: ExecutorType[];
  runs: Run[];
}

// ドロップダウンで比較を実行するモデル(LLM)を選択
// 選択肢: 登録済みのModelProfile + オプションでCLI Executor
```

### Phase 2: 比較ページの作成

#### 2.1 ルーティング
**新規ファイル**: `apps/web/src/app/tasks/[taskId]/compare/page.tsx`

- URL: `/tasks/{taskId}/compare?model={modelId}`
- クエリパラメータでモデルIDを渡す

#### 2.2 ComparePageコンポーネント
**新規ファイル**: `apps/web/src/app/tasks/[taskId]/compare/page.tsx`

```tsx
export default function ComparePage({ params, searchParams }) {
  const { taskId } = params;
  const { model: modelId } = searchParams;

  // 1. タスクの全Runを取得
  // 2. 成功したRunをExecutor毎にグループ化
  // 3. 選択されたモデルで比較APIを呼び出し
  // 4. 結果を表示
}
```

#### 2.3 比較結果表示コンポーネント
**新規ファイル**: `apps/web/src/components/comparison/`

```
comparison/
├── ComparisonView.tsx       # メインコンテナ
├── ComparisonHeader.tsx     # ヘッダー(戻るボタン、タイトル)
├── ComparisonSummary.tsx    # 比較サマリー表示
├── ComparisonDiffView.tsx   # 差分比較ビュー
└── ComparisonMetrics.tsx    # メトリクス比較
```

### Phase 3: バックエンドAPI

#### 3.1 比較エンドポイント
**新規**: `POST /v1/tasks/{task_id}/compare`

```python
class CompareRequest(BaseModel):
    run_ids: list[str]           # 比較対象のRun ID
    model_id: str | None = None  # 比較に使用するLLMモデルID
    executor_type: ExecutorType | None = None  # またはCLI Executor

class CompareResult(BaseModel):
    comparison_id: str
    status: str                  # pending, running, completed, failed
    analysis: str | None         # LLMによる比較分析結果
    metrics: dict[str, Any]      # 統計情報
    created_at: datetime
```

#### 3.2 比較サービス
**新規ファイル**: `apps/api/src/zloth_api/services/compare_service.py`

```python
class CompareService:
    async def create_comparison(
        self,
        task_id: str,
        run_ids: list[str],
        model_id: str | None,
        executor_type: ExecutorType | None,
    ) -> CompareResult:
        # 1. 対象Runの取得と検証
        # 2. 各Runのsummary, patch, files_changedを収集
        # 3. LLM/CLIで比較分析を実行
        # 4. 結果を返却
```

#### 3.3 比較プロンプト
LLMに渡す比較プロンプトの構造:

```
You are comparing code changes from multiple AI coding agents for the same task.

## Task Instruction
{original_instruction}

## Agent Outputs

### Claude Code
Summary: {claude_summary}
Files Changed: {claude_files}
Patch:
{claude_patch}

### Codex
Summary: {codex_summary}
Files Changed: {codex_files}
Patch:
{codex_patch}

### Gemini CLI
...

## Your Analysis
Please provide:
1. **Approach Comparison**: How each agent approached the problem
2. **Code Quality**: Compare code quality, readability, maintainability
3. **Completeness**: Did each solution fully address the requirements?
4. **Potential Issues**: Any bugs, edge cases, or concerns
5. **Recommendation**: Which solution would you recommend and why?
```

### Phase 4: データモデルの拡張

#### 4.1 Comparison テーブル
**更新**: `apps/api/src/zloth_api/storage/schema.sql`

```sql
CREATE TABLE IF NOT EXISTS comparisons (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    run_ids TEXT NOT NULL,         -- JSON array of run IDs
    model_id TEXT,                  -- LLM model used for comparison
    executor_type TEXT,             -- or CLI executor type
    status TEXT NOT NULL DEFAULT 'pending',
    analysis TEXT,                  -- LLM analysis result
    metrics TEXT,                   -- JSON metrics
    error TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
```

#### 4.2 DAO更新
**更新**: `apps/api/src/zloth_api/storage/dao.py`

```python
class ComparisonDAO:
    async def create(self, comparison: Comparison) -> None
    async def get(self, comparison_id: str) -> Comparison | None
    async def update(self, comparison_id: str, **kwargs) -> None
    async def list_by_task(self, task_id: str) -> list[Comparison]
```

### Phase 5: UI詳細設計

#### 5.1 比較ボタンのデザイン
```
┌──────────────────────────────────────────────────────────────┐
│ [Claude Code ✓] [Codex ✓] [Gemini ✓]    [Compare ▼]         │
│                                          ├─────────────────┤ │
│                                          │ Compare with:   │ │
│                                          │ ○ GPT-4o        │ │
│                                          │ ○ Claude 3.5    │ │
│                                          │ ○ Claude Code   │ │
│                                          │ ○ Codex         │ │
│                                          └─────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

#### 5.2 比較ページのレイアウト
```
┌──────────────────────────────────────────────────────────────┐
│ [← Back to Task]           Comparison Results                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ Comparing: Claude Code vs Codex vs Gemini CLI                │
│ Analyzed by: GPT-4o                                          │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ ┌─ Analysis ────────────────────────────────────────────┐   │
│ │                                                        │   │
│ │ ## Approach Comparison                                 │   │
│ │ - Claude Code: Created a new utility module...         │   │
│ │ - Codex: Modified existing functions...                │   │
│ │ - Gemini: Implemented inline changes...                │   │
│ │                                                        │   │
│ │ ## Code Quality                                        │   │
│ │ ...                                                    │   │
│ │                                                        │   │
│ │ ## Recommendation                                      │   │
│ │ Claude Code's approach is recommended because...       │   │
│ │                                                        │   │
│ └────────────────────────────────────────────────────────┘   │
│                                                              │
├─ Metrics ────────────────────────────────────────────────────┤
│                                                              │
│ ┌───────────────┬───────────────┬───────────────┬─────────┐ │
│ │ Metric        │ Claude Code   │ Codex         │ Gemini  │ │
│ ├───────────────┼───────────────┼───────────────┼─────────┤ │
│ │ Files Changed │ 3             │ 2             │ 4       │ │
│ │ Lines Added   │ 45            │ 33            │ 52      │ │
│ │ Lines Removed │ 7             │ 5             │ 12      │ │
│ │ Execution Time│ 4.2s          │ 3.8s          │ 5.1s    │ │
│ └───────────────┴───────────────┴───────────────┴─────────┘ │
│                                                              │
├─ Diff Comparison ────────────────────────────────────────────┤
│ ┌─ Files ─────┐ ┌─ Side-by-Side Diff ─────────────────────┐ │
│ │ src/api.ts  │ │ Claude Code        │ Codex              │ │
│ │ src/util.ts │ │ + new line 1       │ + different line 1 │ │
│ │ tests/...   │ │ + new line 2       │ + different line 2 │ │
│ └─────────────┘ └─────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Phase 6: 実装順序

1. **バックエンド基盤** (必須)
   - [ ] Comparisonモデルの定義 (`domain/models.py`)
   - [ ] スキーマ更新 (`storage/schema.sql`)
   - [ ] ComparisonDAO (`storage/dao.py`)
   - [ ] CompareService (`services/compare_service.py`)
   - [ ] APIルート (`routes/compare.py`)

2. **フロントエンド基盤** (必須)
   - [ ] API クライアント拡張 (`lib/api.ts`)
   - [ ] 型定義追加 (`types.ts`)

3. **UIコンポーネント** (必須)
   - [ ] CompareButton (`components/CompareButton.tsx`)
   - [ ] ChatCodeViewへの統合
   - [ ] 比較ページ (`app/tasks/[taskId]/compare/page.tsx`)
   - [ ] ComparisonView (`components/comparison/ComparisonView.tsx`)

4. **比較結果表示** (必須)
   - [ ] ComparisonHeader (戻るボタン)
   - [ ] ComparisonSummary (LLM分析結果)
   - [ ] ComparisonMetrics (統計比較)
   - [ ] ComparisonDiffView (差分比較)

5. **ポーリング/リアルタイム更新** (推奨)
   - [ ] 比較実行中のステータス表示
   - [ ] SWRによる結果ポーリング

### Phase 7: ファイル変更一覧

#### 新規作成
```
apps/api/src/zloth_api/
├── domain/models.py         # Comparison モデル追加
├── routes/compare.py        # 比較API エンドポイント
└── services/compare_service.py  # 比較ロジック

apps/web/src/
├── app/tasks/[taskId]/compare/
│   └── page.tsx             # 比較ページ
├── components/
│   ├── CompareButton.tsx    # 比較ボタン
│   └── comparison/
│       ├── ComparisonView.tsx
│       ├── ComparisonHeader.tsx
│       ├── ComparisonSummary.tsx
│       ├── ComparisonMetrics.tsx
│       └── ComparisonDiffView.tsx
└── lib/
    └── comparison-utils.ts  # 比較ユーティリティ
```

#### 更新
```
apps/api/src/zloth_api/
├── main.py                  # compare routerの登録
├── storage/schema.sql       # comparisons テーブル追加
├── storage/dao.py           # ComparisonDAO追加
└── dependencies.py          # compare_service DI追加

apps/web/src/
├── components/ChatCodeView.tsx  # CompareButton統合
├── lib/api.ts               # compare API追加
└── types.ts                 # Comparison型追加
```

## 技術的考慮事項

### パフォーマンス
- 比較は非同期で実行し、ポーリングで結果を取得
- 大きなパッチの場合、要約して比較

### セキュリティ
- 比較に使用するモデルのAPIキーは暗号化されたものを使用
- 比較結果にはセンシティブ情報が含まれる可能性があるため、適切なアクセス制御

### エラーハンドリング
- モデルAPI呼び出し失敗時のリトライ
- タイムアウト設定 (比較は長時間かかる可能性あり)

## 見積もり

| Phase | 作業内容 | 複雑度 |
|-------|----------|--------|
| 1 | Compareボタン | 低 |
| 2 | 比較ページ | 中 |
| 3 | バックエンドAPI | 中 |
| 4 | データモデル | 低 |
| 5 | UI詳細 | 中 |
| 6 | 統合テスト | 中 |
