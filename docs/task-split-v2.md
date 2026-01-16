# タスク分解機能 v2 改善計画

## 概要

v1の実装で発覚した課題を解決し、より実用的なタスク管理を実現するための改善計画。

## v1 の課題

### 課題1: タスクの粒度が小さすぎる

**現象**: 
- 「黒だけでなく白い画面も使えるようにしたい」のような単一の機能リクエストに対して、数十個のTaskが生成される
- タスク数が多すぎて管理が困難

**原因**:
- 現在のプロンプトが実装の詳細レベルまでタスクを分解している
- `small/medium/large`のサイズ指針が細かすぎる実装タスクを誘発している

**v2の方針**:
- **1機能リクエスト = 1タスク** を原則とする
- 細かい実装ステップはタスク内のサブタスク（チェックリスト）として表現
- 機能単位での管理を重視し、PRとの対応を明確化

### 課題2: サイドバーに増えるだけのUXが微妙

**現象**:
- Breakdownで分解したタスクがサイドバーに直接追加される
- 大量のタスクが一度に追加されると既存タスクが埋もれる
- 分解結果の全体像を把握しづらい

**原因**:
- Breakdown結果がTaskと直接結びついている
- 分解されたアイテムを管理する専用の場所がない

**v2の方針**:
- **Backlog** という新しい概念を導入
- Backlogページで分解・管理を行い、準備ができたらTaskに昇格
- サイドバーのBreakdownボタンを廃止し、Backlogへのナビゲーションに変更

---

## 新しいデータモデル

### Backlog（新規）

分解された要件アイテムを保持する。TaskとBreakdownの中間的な存在。

```python
class BacklogItem(BaseModel):
    """バックログアイテム"""
    id: str
    repo_id: str
    title: str
    description: str
    type: BrokenDownTaskType  # feature, bug_fix, refactoring, docs, test
    estimated_size: EstimatedSize  # small, medium, large
    target_files: list[str] = []
    implementation_hint: str | None = None
    tags: list[str] = []
    subtasks: list[SubTask] = []  # 新規: サブタスク（実装ステップ）
    status: BacklogStatus  # draft, ready, in_progress, done
    task_id: str | None = None  # Task に昇格した場合のリンク
    created_at: datetime
    updated_at: datetime

class SubTask(BaseModel):
    """サブタスク（実装ステップ）"""
    id: str
    title: str
    completed: bool = False

class BacklogStatus(str, Enum):
    DRAFT = "draft"       # 分解直後、未整理
    READY = "ready"       # 着手可能
    IN_PROGRESS = "in_progress"  # Task化して作業中
    DONE = "done"         # 完了
```

### 階層構造の整理

```
Breakdown（文章入力）
    ↓ 分解
BacklogItem（機能単位のアイテム）
    ├─ SubTask（実装ステップ1）
    ├─ SubTask（実装ステップ2）
    └─ SubTask（実装ステップ3）
    ↓ 昇格（Start Work）
Task（作業単位）
    ↓ 実行
Run（AI実行）
    ↓ 作成
PR
```

---

## API 設計変更

### 新規エンドポイント

#### Backlog CRUD

```
GET  /v1/backlog              # 一覧取得（フィルタ: repo_id, status）
POST /v1/backlog              # 新規作成（手動）
GET  /v1/backlog/{id}         # 詳細取得
PUT  /v1/backlog/{id}         # 更新
DELETE /v1/backlog/{id}       # 削除
POST /v1/backlog/{id}/start   # Task化して作業開始
```

#### Breakdown（変更）

`POST /v1/breakdown` のレスポンスを変更:
- 現在: 分解結果を直接返す
- 変更後: 分解結果をBacklogItemとして保存し、IDを返す

```json
// Request（変更なし）
{
  "content": "ヒアリング文章...",
  "executor_type": "claude_code",
  "repo_id": "repo-id"
}

// Response（変更）
{
  "breakdown_id": "breakdown-123",
  "status": "succeeded",
  "backlog_items": [
    {
      "id": "backlog-item-1",
      "title": "ダークモード対応",
      "description": "アプリ全体でダーク/ライトモードを切り替え可能にする",
      "type": "feature",
      "estimated_size": "medium",
      "subtasks": [
        { "id": "st-1", "title": "テーマコンテキストの作成", "completed": false },
        { "id": "st-2", "title": "カラー変数の定義", "completed": false },
        { "id": "st-3", "title": "トグルコンポーネントの実装", "completed": false }
      ],
      "status": "draft"
    }
  ],
  "summary": "1件の機能要件を特定しました"
}
```

### 廃止エンドポイント

- `POST /v1/tasks/bulk` - BacklogからのTask作成に置き換え

---

## プロンプト改善

### v1 プロンプトの問題点

```python
# v1: 詳細な実装タスクを生成してしまう
BREAKDOWN_INSTRUCTION_TEMPLATE = """
...
7. Size estimation guide:
   - small: 1-2 file changes, few hours
   - medium: 3-5 file changes, about 1 day
   - large: Multiple modules, several days
...
"""
```

### v2 プロンプト

```python
BREAKDOWN_INSTRUCTION_TEMPLATE_V2 = """
あなたはソフトウェア開発の要件分析の専門家です。
以下の要望を、**機能単位**の開発タスクに整理してください。

## 重要な指針

### 粒度について
- **1つの機能リクエスト = 1つのタスク** が原則
- 「ダークモード対応」「検索機能追加」「認証実装」などの機能レベル
- 実装の詳細ステップは `subtasks` として列挙
- 目安: 1タスク = 1 Pull Request で完結できる単位

### 粒度の例
❌ 悪い例（細かすぎる）:
- タスク1: ThemeContext を作成
- タスク2: useTheme フックを実装
- タスク3: ダークモード用CSS変数を定義
- タスク4: ToggleButton コンポーネントを作成

✅ 良い例（適切な粒度）:
- タスク: ダークモード対応
  - subtask: テーマコンテキストの作成
  - subtask: カラー変数の定義
  - subtask: トグルコンポーネントの実装

### 分解のルール
1. ユーザーの要望を機能レベルで分類
2. 技術的な実装ステップは subtasks に
3. 関連性の高い要素は1つのタスクにまとめる
4. PRで説明可能な単位を意識する

## 要望
{content}

## 出力形式
`.dursor-breakdown.json` に以下の形式で出力:

```json
{{
  "codebase_analysis": {{
    "files_analyzed": <number>,
    "relevant_modules": ["関連モジュール"],
    "tech_stack": ["技術スタック"]
  }},
  "tasks": [
    {{
      "title": "機能レベルのタイトル（30文字以内）",
      "description": "この機能で実現すること、なぜ必要かの説明",
      "type": "feature | bug_fix | refactoring | docs | test",
      "estimated_size": "small | medium | large",
      "target_files": ["変更対象のファイルパス"],
      "implementation_hint": "全体的な実装方針（既存コード参照）",
      "tags": ["タグ"],
      "subtasks": [
        {{ "title": "実装ステップ1" }},
        {{ "title": "実装ステップ2" }}
      ]
    }}
  ]
}}
```

## サイズの目安（タスク単位）
- small: 1-2日で完了、シンプルな変更
- medium: 3-5日、複数モジュールに影響
- large: 1週間以上、大きな機能追加やリファクタリング
"""
```

---

## UI 設計変更

### 現在の構造

```
サイドバー
├─ [+ New Task]
├─ [✦ Breakdown]  ← モーダルを開く
└─ Task 一覧
```

### v2 の構造

```
サイドバー
├─ [+ New Task]
├─ [📋 Backlog]   ← Backlogページへ遷移
├─ ─────────────
└─ Task 一覧（作業中のみ）

Backlogページ (/backlog)
├─ ヘッダー
│   ├─ タイトル「Backlog」
│   └─ [✦ Breakdown] ボタン  ← Breakdownモーダルを開く
├─ フィルター
│   └─ Status: All / Draft / Ready / In Progress / Done
├─ Backlog 一覧
│   ├─ BacklogCard
│   │   ├─ タイトル
│   │   ├─ タイプ・サイズバッジ
│   │   ├─ サブタスク進捗
│   │   └─ [Start Work] ボタン
│   └─ ...
└─ 空状態
    └─ "Breakdownで要件を分解しよう"
```

### 新規ページ: `/backlog`

```
┌─────────────────────────────────────────────────────────────┐
│  📋 Backlog                              [✦ Breakdown]     │
├─────────────────────────────────────────────────────────────┤
│  Filter: [All ▼]  [Search...]                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ✨ ダークモード対応                      [Medium]   │   │
│  │ アプリ全体でダーク/ライトモードを切り替え可能に     │   │
│  │                                                     │   │
│  │ Subtasks: ○○○ (0/3)                                │   │
│  │ ┌─ ☐ テーマコンテキストの作成                      │   │
│  │ ├─ ☐ カラー変数の定義                              │   │
│  │ └─ ☐ トグルコンポーネントの実装                    │   │
│  │                                                     │   │
│  │ Tags: #ui #theme                     [Start Work]   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 🐛 ログインエラー表示の修正             [Small]     │   │
│  │ パスワード間違い時にエラーメッセージを表示           │   │
│  │                                                     │   │
│  │ Subtasks: ●○ (1/2)                                 │   │
│  │                                                     │   │
│  │ Tags: #auth #bug             [▶ 作業中] [View Task] │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Breakdown モーダル（変更）

Breakdownモーダルの結果画面を変更:
- 「Create X Tasks」→「Add to Backlog」

```
┌──────────────────────────────────────────────────────────┐
│  ✦ タスク分解                                      [×]   │
├──────────────────────────────────────────────────────────┤
│  分解結果 (2件)                                          │
│                                                          │
│  ☑ ✨ ダークモード対応                                   │
│      機能追加 | 推定: Medium                             │
│      ▸ 3 subtasks                                       │
│                                                          │
│  ☑ 🐛 ログインエラー表示の修正                           │
│      バグ修正 | 推定: Small                              │
│      ▸ 2 subtasks                                       │
│                                                          │
├──────────────────────────────────────────────────────────┤
│  [Add to Backlog (2件)]                  [キャンセル]    │
└──────────────────────────────────────────────────────────┘
```

### サイドバー変更

```tsx
// Sidebar.tsx
// Before
<button onClick={onBreakdownClick}>
  <SparklesIcon />
  Breakdown
</button>

// After
<Link href="/backlog">
  <ClipboardDocumentListIcon />
  Backlog
</Link>
```

---

## バックエンド実装計画

### 1. データベーススキーマ追加

```sql
-- schema.sql に追加

CREATE TABLE IF NOT EXISTS backlog_items (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    type TEXT NOT NULL DEFAULT 'feature',
    estimated_size TEXT NOT NULL DEFAULT 'medium',
    target_files TEXT NOT NULL DEFAULT '[]',  -- JSON array
    implementation_hint TEXT,
    tags TEXT NOT NULL DEFAULT '[]',  -- JSON array
    subtasks TEXT NOT NULL DEFAULT '[]',  -- JSON array
    status TEXT NOT NULL DEFAULT 'draft',
    task_id TEXT,  -- Reference to task if promoted
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repo_id) REFERENCES repos(id),
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE INDEX idx_backlog_items_repo_id ON backlog_items(repo_id);
CREATE INDEX idx_backlog_items_status ON backlog_items(status);
```

### 2. 新しいDAO: `BacklogDAO`

```python
# storage/dao.py に追加

class BacklogDAO:
    """Data access object for backlog items."""

    async def create(
        self,
        repo_id: str,
        title: str,
        description: str = "",
        type: BrokenDownTaskType = BrokenDownTaskType.FEATURE,
        estimated_size: EstimatedSize = EstimatedSize.MEDIUM,
        target_files: list[str] | None = None,
        implementation_hint: str | None = None,
        tags: list[str] | None = None,
        subtasks: list[dict] | None = None,
    ) -> BacklogItem:
        """Create a new backlog item."""
        ...

    async def get(self, id: str) -> BacklogItem | None:
        """Get a backlog item by ID."""
        ...

    async def list(
        self,
        repo_id: str | None = None,
        status: BacklogStatus | None = None,
    ) -> list[BacklogItem]:
        """List backlog items with optional filters."""
        ...

    async def update(self, id: str, **kwargs) -> BacklogItem | None:
        """Update a backlog item."""
        ...

    async def delete(self, id: str) -> bool:
        """Delete a backlog item."""
        ...

    async def promote_to_task(self, id: str) -> Task:
        """Promote a backlog item to a task."""
        ...
```

### 3. 新しいルート: `routes/backlog.py`

```python
# routes/backlog.py

router = APIRouter(prefix="/backlog", tags=["backlog"])

@router.get("", response_model=list[BacklogItem])
async def list_backlog_items(...) -> list[BacklogItem]: ...

@router.post("", response_model=BacklogItem, status_code=201)
async def create_backlog_item(...) -> BacklogItem: ...

@router.get("/{item_id}", response_model=BacklogItem)
async def get_backlog_item(...) -> BacklogItem: ...

@router.put("/{item_id}", response_model=BacklogItem)
async def update_backlog_item(...) -> BacklogItem: ...

@router.delete("/{item_id}", status_code=204)
async def delete_backlog_item(...) -> None: ...

@router.post("/{item_id}/start", response_model=Task)
async def start_work_on_backlog_item(...) -> Task:
    """Promote backlog item to task and start working on it."""
    ...
```

### 4. BreakdownService 変更

```python
# services/breakdown_service.py

class BreakdownService:
    def __init__(
        self,
        repo_dao: RepoDAO,
        backlog_dao: BacklogDAO,  # 新規追加
        output_manager: OutputManager,
    ):
        self.backlog_dao = backlog_dao
        ...

    async def _execute_breakdown(self, ...) -> TaskBreakdownResponse:
        # ... 分解実行 ...
        
        # 変更: BacklogItemとして保存
        backlog_items = []
        for task_data in parsed_tasks:
            item = await self.backlog_dao.create(
                repo_id=request.repo_id,
                title=task_data.title,
                description=task_data.description,
                type=task_data.type,
                estimated_size=task_data.estimated_size,
                target_files=task_data.target_files,
                implementation_hint=task_data.implementation_hint,
                tags=task_data.tags,
                subtasks=task_data.subtasks,  # 新規
            )
            backlog_items.append(item)
        
        return TaskBreakdownResponse(
            breakdown_id=breakdown_id,
            status=BreakdownStatus.SUCCEEDED,
            backlog_items=backlog_items,  # 変更
            ...
        )
```

---

## フロントエンド実装計画

### 1. 新しい型定義

```typescript
// types.ts に追加

export interface SubTask {
  id: string;
  title: string;
  completed: boolean;
}

export type BacklogStatus = 'draft' | 'ready' | 'in_progress' | 'done';

export interface BacklogItem {
  id: string;
  repo_id: string;
  title: string;
  description: string;
  type: BrokenDownTaskType;
  estimated_size: EstimatedSize;
  target_files: string[];
  implementation_hint: string | null;
  tags: string[];
  subtasks: SubTask[];
  status: BacklogStatus;
  task_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface BacklogItemCreate {
  repo_id: string;
  title: string;
  description?: string;
  type?: BrokenDownTaskType;
  estimated_size?: EstimatedSize;
  target_files?: string[];
  implementation_hint?: string;
  tags?: string[];
  subtasks?: { title: string }[];
}

export interface BacklogItemUpdate {
  title?: string;
  description?: string;
  type?: BrokenDownTaskType;
  estimated_size?: EstimatedSize;
  target_files?: string[];
  implementation_hint?: string;
  tags?: string[];
  subtasks?: SubTask[];
  status?: BacklogStatus;
}
```

### 2. 新しい API クライアント

```typescript
// lib/api.ts に追加

export const backlogApi = {
  list: (repoId?: string, status?: BacklogStatus) => {
    const params = new URLSearchParams();
    if (repoId) params.set('repo_id', repoId);
    if (status) params.set('status', status);
    const query = params.toString();
    return fetchApi<BacklogItem[]>(`/backlog${query ? `?${query}` : ''}`);
  },

  create: (data: BacklogItemCreate) =>
    fetchApi<BacklogItem>('/backlog', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  get: (id: string) => fetchApi<BacklogItem>(`/backlog/${id}`),

  update: (id: string, data: BacklogItemUpdate) =>
    fetchApi<BacklogItem>(`/backlog/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  delete: (id: string) =>
    fetchApi<void>(`/backlog/${id}`, { method: 'DELETE' }),

  startWork: (id: string) =>
    fetchApi<Task>(`/backlog/${id}/start`, { method: 'POST' }),
};
```

### 3. 新しいページ: `/backlog`

```
apps/web/src/app/
├─ backlog/
│   └─ page.tsx      # Backlog ページ
```

### 4. 新しいコンポーネント

```
apps/web/src/components/
├─ BacklogCard.tsx        # Backlogアイテムカード
├─ BacklogList.tsx        # Backlog一覧
├─ SubtaskList.tsx        # サブタスク一覧
└─ BacklogFilters.tsx     # フィルターコンポーネント
```

### 5. Sidebar 変更

```tsx
// Sidebar.tsx

// Before
<button onClick={onBreakdownClick}>
  <SparklesIcon className="w-4 h-4" />
  Breakdown
</button>

// After
<Link
  href="/backlog"
  className={cn(
    'flex items-center justify-center gap-2 w-full py-2.5 px-3',
    'bg-purple-600 hover:bg-purple-700 rounded-lg',
    ...
  )}
>
  <ClipboardDocumentListIcon className="w-4 h-4" />
  Backlog
</Link>
```

### 6. BreakdownModal 変更

```tsx
// BreakdownModal.tsx

// 結果画面のボタン変更
<Button onClick={handleAddToBacklog}>
  Add to Backlog ({selectedTasks.size})
</Button>

const handleAddToBacklog = async () => {
  // backlogApi.create を使用
  // 成功後、/backlog ページへ遷移
  router.push('/backlog');
};
```

---

## 実装順序

### Phase 1: バックエンド基盤（3-4時間）

1. [ ] BacklogStatus enum 追加（`domain/enums.py`）
2. [ ] SubTask, BacklogItem モデル追加（`domain/models.py`）
3. [ ] backlog_items テーブル作成（`storage/schema.sql`）
4. [ ] BacklogDAO 実装（`storage/dao.py`）
5. [ ] routes/backlog.py 実装
6. [ ] テスト追加

### Phase 2: プロンプト改善（1-2時間）

7. [ ] BREAKDOWN_INSTRUCTION_TEMPLATE_V2 実装
8. [ ] subtasks のパース処理追加
9. [ ] BreakdownService を BacklogDAO 連携に変更

### Phase 3: フロントエンド基盤（4-5時間）

10. [ ] 型定義追加（`types.ts`）
11. [ ] API クライアント追加（`lib/api.ts`）
12. [ ] BacklogCard コンポーネント作成
13. [ ] SubtaskList コンポーネント作成
14. [ ] BacklogList コンポーネント作成
15. [ ] `/backlog` ページ作成

### Phase 4: UI 統合（2-3時間）

16. [ ] Sidebar の Breakdown → Backlog 変更
17. [ ] BreakdownModal の結果処理を Backlog 連携に変更
18. [ ] BacklogページにBreakdownボタン追加
19. [ ] ClientLayout から Breakdown モーダルの呼び出し方変更

### Phase 5: 改善・テスト（2-3時間）

20. [ ] Backlog → Task 昇格フロー実装
21. [ ] サブタスクのチェック状態更新機能
22. [ ] E2E テスト追加
23. [ ] プロンプトの微調整

---

## 工数見積もり

| Phase | 内容 | 見積もり |
|-------|------|----------|
| Phase 1 | バックエンド基盤 | 3-4時間 |
| Phase 2 | プロンプト改善 | 1-2時間 |
| Phase 3 | フロントエンド基盤 | 4-5時間 |
| Phase 4 | UI 統合 | 2-3時間 |
| Phase 5 | 改善・テスト | 2-3時間 |
| **合計** | | **12-17時間** |

---

## マイグレーション計画

### 既存データの扱い

1. **既存のTask**: そのまま維持（変更なし）
2. **Breakdownで作成されたTask**: Backlogには移行しない（過去データ）
3. **新規Breakdown**: v2以降はBacklogItemとして保存

### 後方互換性

- `/v1/tasks/bulk` は当面維持（deprecated）
- 既存の Task 関連 API は変更なし

---

## 将来の拡張

### v2.1 候補

- [ ] Backlog アイテムのドラッグ&ドロップ並び替え
- [ ] Backlog アイテムの優先度設定
- [ ] Backlog からの一括 Task 化
- [ ] サブタスクの見積もり時間

### v3 候補

- [ ] Backlog アイテムの依存関係管理
- [ ] マイルストーン機能
- [ ] チーム間での Backlog 共有
