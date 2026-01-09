# 看板（Kanban）機能 実装計画

## 概要

dursor に看板ページを追加し、タスクの進捗を視覚的に管理できるようにする。

## ステータス定義

| ステータス | 説明 | 判定条件 |
|-----------|------|----------|
| **Backlog** | タスク作成済み、未着手 | Runが0件 |
| **ToDo** | 実行待ち | すべてのRunがqueued |
| **InProgress** | AIが実装中 | 1つ以上のRunがrunning |
| **InReview** | 人間のレビュー待ち | すべてのRunが完了(succeeded/failed/canceled)かつPRがない or PRがopenで未マージ |
| **Done** | 完了 | PRがマージされた |
| **Archived** | アーカイブ済み | 明示的にis_archived=true |

## 現状分析

### 既存のデータモデル

#### Task（`apps/api/src/dursor_api/domain/models.py`）
```python
class Task(BaseModel):
    id: str
    repo_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime
    # ステータスフィールドなし
```

#### Run
```python
class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
```

#### PR
```python
class PR(BaseModel):
    id: str
    task_id: str
    number: int
    url: str
    branch: str
    title: str
    body: str | None
    latest_commit: str
    status: str  # 現状は "open" のみ
    created_at: datetime
    updated_at: datetime
```

### 課題
1. **Taskにステータスフィールドがない** - 看板ステータスはRun/PRの状態から動的に計算する必要がある
2. **PRのマージ状態が追跡されていない** - GitHub APIからマージ状態を取得・更新する必要がある
3. **アーカイブ機能がない** - Taskに`is_archived`フィールドを追加する必要がある

---

## 実装計画

### フェーズ1: バックエンド拡張

#### 1.1 データベーススキーマ変更

```sql
-- apps/api/src/dursor_api/storage/schema.sql

-- tasks テーブルに is_archived カラムを追加
ALTER TABLE tasks ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0;

-- prs テーブルの status カラムを拡張（open, merged, closed）
-- 既存データの status は "open" のまま
```

#### 1.2 ドメインモデル拡張

```python
# apps/api/src/dursor_api/domain/enums.py

class TaskKanbanStatus(str, Enum):
    """Task kanban status (computed from runs and PRs)."""
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"
    ARCHIVED = "archived"


class PRStatus(str, Enum):
    """PR status on GitHub."""
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"
```

```python
# apps/api/src/dursor_api/domain/models.py

class Task(BaseModel):
    id: str
    repo_id: str
    title: str | None
    is_archived: bool = False  # 追加
    created_at: datetime
    updated_at: datetime


class TaskWithKanbanStatus(Task):
    """Task with computed kanban status."""
    kanban_status: TaskKanbanStatus
    run_count: int = 0
    pr_count: int = 0
    latest_pr_status: str | None = None


class KanbanColumn(BaseModel):
    """Kanban column with tasks."""
    status: TaskKanbanStatus
    tasks: list[TaskWithKanbanStatus]
    count: int


class KanbanBoard(BaseModel):
    """Full kanban board response."""
    columns: list[KanbanColumn]
    total_tasks: int
```

#### 1.3 DAO拡張

```python
# apps/api/src/dursor_api/storage/dao.py

class TaskDAO:
    async def update_archived(self, task_id: str, is_archived: bool) -> None:
        """Update task archived status."""
        ...

    async def list_with_status(self, repo_id: str | None = None) -> list[dict]:
        """List tasks with run/PR aggregation for kanban status calculation."""
        # JOIN query to get run counts, PR statuses, etc.
        ...


class PRDAO:
    async def update_status(self, pr_id: str, status: str) -> None:
        """Update PR status (open/merged/closed)."""
        ...
```

#### 1.4 看板サービス

```python
# apps/api/src/dursor_api/services/kanban_service.py

class KanbanService:
    def __init__(
        self,
        task_dao: TaskDAO,
        run_dao: RunDAO,
        pr_dao: PRDAO,
        github_service: GitHubService,
    ):
        ...

    def _compute_kanban_status(
        self,
        task: Task,
        runs: list[Run],
        prs: list[PR],
    ) -> TaskKanbanStatus:
        """Compute kanban status from task state."""
        # Archived takes precedence
        if task.is_archived:
            return TaskKanbanStatus.ARCHIVED

        # Check if any PR is merged
        if any(pr.status == "merged" for pr in prs):
            return TaskKanbanStatus.DONE

        # No runs = Backlog
        if not runs:
            return TaskKanbanStatus.BACKLOG

        # All runs queued = ToDo
        if all(r.status == RunStatus.QUEUED for r in runs):
            return TaskKanbanStatus.TODO

        # Any run running = InProgress
        if any(r.status == RunStatus.RUNNING for r in runs):
            return TaskKanbanStatus.IN_PROGRESS

        # All runs completed = InReview
        completed_statuses = {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELED}
        if all(r.status in completed_statuses for r in runs):
            return TaskKanbanStatus.IN_REVIEW

        # Fallback
        return TaskKanbanStatus.BACKLOG

    async def get_board(self, repo_id: str | None = None) -> KanbanBoard:
        """Get full kanban board."""
        ...

    async def archive_task(self, task_id: str) -> Task:
        """Archive a task."""
        ...

    async def unarchive_task(self, task_id: str) -> Task:
        """Unarchive a task."""
        ...

    async def sync_pr_status(self, task_id: str, pr_id: str) -> PR:
        """Sync PR status from GitHub."""
        # Call GitHub API to get PR state (open/merged/closed)
        ...
```

#### 1.5 APIエンドポイント

```python
# apps/api/src/dursor_api/routes/kanban.py

router = APIRouter(prefix="/kanban", tags=["kanban"])


@router.get("", response_model=KanbanBoard)
async def get_kanban_board(
    repo_id: str | None = None,
    kanban_service: KanbanService = Depends(get_kanban_service),
) -> KanbanBoard:
    """Get kanban board with all columns."""
    return await kanban_service.get_board(repo_id)


@router.post("/tasks/{task_id}/archive", response_model=Task)
async def archive_task(
    task_id: str,
    kanban_service: KanbanService = Depends(get_kanban_service),
) -> Task:
    """Archive a task."""
    return await kanban_service.archive_task(task_id)


@router.post("/tasks/{task_id}/unarchive", response_model=Task)
async def unarchive_task(
    task_id: str,
    kanban_service: KanbanService = Depends(get_kanban_service),
) -> Task:
    """Unarchive a task."""
    return await kanban_service.unarchive_task(task_id)


@router.post("/tasks/{task_id}/prs/{pr_id}/sync-status", response_model=PR)
async def sync_pr_status(
    task_id: str,
    pr_id: str,
    kanban_service: KanbanService = Depends(get_kanban_service),
) -> PR:
    """Sync PR status from GitHub (check if merged/closed)."""
    return await kanban_service.sync_pr_status(task_id, pr_id)
```

#### 1.6 GitHub Service拡張

```python
# apps/api/src/dursor_api/services/github_service.py

class GitHubService:
    async def get_pull_request_status(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> dict:
        """Get PR status from GitHub API.
        
        Returns:
            {
                "state": "open" | "closed",
                "merged": bool,
                "merged_at": str | None,
            }
        """
        # GET /repos/{owner}/{repo}/pulls/{pr_number}
        ...
```

---

### フェーズ2: フロントエンド実装

#### 2.1 型定義追加

```typescript
// apps/web/src/types.ts

export type TaskKanbanStatus = 
  | 'backlog'
  | 'todo'
  | 'in_progress'
  | 'in_review'
  | 'done'
  | 'archived';

export interface TaskWithKanbanStatus extends Task {
  kanban_status: TaskKanbanStatus;
  run_count: number;
  pr_count: number;
  latest_pr_status: string | null;
}

export interface KanbanColumn {
  status: TaskKanbanStatus;
  tasks: TaskWithKanbanStatus[];
  count: number;
}

export interface KanbanBoard {
  columns: KanbanColumn[];
  total_tasks: number;
}
```

#### 2.2 APIクライアント追加

```typescript
// apps/web/src/lib/api.ts

export const kanbanApi = {
  getBoard: (repoId?: string) => {
    const params = repoId ? `?repo_id=${repoId}` : '';
    return fetchApi<KanbanBoard>(`/kanban${params}`);
  },

  archiveTask: (taskId: string) =>
    fetchApi<Task>(`/kanban/tasks/${taskId}/archive`, { method: 'POST' }),

  unarchiveTask: (taskId: string) =>
    fetchApi<Task>(`/kanban/tasks/${taskId}/unarchive`, { method: 'POST' }),

  syncPRStatus: (taskId: string, prId: string) =>
    fetchApi<PR>(`/kanban/tasks/${taskId}/prs/${prId}/sync-status`, {
      method: 'POST',
    }),
};
```

#### 2.3 看板ページ

```
apps/web/src/app/kanban/
├── page.tsx          # 看板メインページ
└── components/
    ├── KanbanBoard.tsx    # 看板ボード全体
    ├── KanbanColumn.tsx   # 各カラム
    ├── KanbanCard.tsx     # タスクカード
    └── KanbanFilters.tsx  # フィルター・検索
```

##### ページ構造

```tsx
// apps/web/src/app/kanban/page.tsx
'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { kanbanApi } from '@/lib/api';
import { KanbanBoard } from './components/KanbanBoard';
import { KanbanFilters } from './components/KanbanFilters';

export default function KanbanPage() {
  const [selectedRepo, setSelectedRepo] = useState<string | null>(null);
  
  const { data: board, isLoading, mutate } = useSWR(
    ['kanban', selectedRepo],
    () => kanbanApi.getBoard(selectedRepo ?? undefined),
    { refreshInterval: 5000 }
  );

  return (
    <div className="h-screen flex flex-col">
      <header className="p-4 border-b border-gray-800">
        <h1 className="text-xl font-bold">Kanban Board</h1>
        <KanbanFilters
          selectedRepo={selectedRepo}
          onRepoChange={setSelectedRepo}
        />
      </header>
      
      <main className="flex-1 overflow-x-auto p-4">
        {isLoading ? (
          <KanbanSkeleton />
        ) : board ? (
          <KanbanBoard board={board} onUpdate={mutate} />
        ) : (
          <EmptyState />
        )}
      </main>
    </div>
  );
}
```

##### カラムコンポーネント

```tsx
// apps/web/src/app/kanban/components/KanbanColumn.tsx

interface KanbanColumnProps {
  column: KanbanColumn;
  onArchive: (taskId: string) => void;
  onUnarchive: (taskId: string) => void;
}

const COLUMN_CONFIG: Record<TaskKanbanStatus, {
  label: string;
  color: string;
  icon: React.ComponentType;
}> = {
  backlog: { label: 'Backlog', color: 'gray', icon: InboxIcon },
  todo: { label: 'ToDo', color: 'blue', icon: ClipboardIcon },
  in_progress: { label: 'In Progress', color: 'yellow', icon: CogIcon },
  in_review: { label: 'In Review', color: 'purple', icon: EyeIcon },
  done: { label: 'Done', color: 'green', icon: CheckCircleIcon },
  archived: { label: 'Archived', color: 'gray', icon: ArchiveBoxIcon },
};

export function KanbanColumn({ column, onArchive, onUnarchive }: KanbanColumnProps) {
  const config = COLUMN_CONFIG[column.status];
  
  return (
    <div className="flex-shrink-0 w-80 bg-gray-900 rounded-lg">
      <div className="p-3 border-b border-gray-800 flex items-center gap-2">
        <config.icon className="w-5 h-5" />
        <span className="font-medium">{config.label}</span>
        <span className="ml-auto text-sm text-gray-500">{column.count}</span>
      </div>
      
      <div className="p-2 space-y-2 max-h-[calc(100vh-200px)] overflow-y-auto">
        {column.tasks.map((task) => (
          <KanbanCard
            key={task.id}
            task={task}
            onArchive={onArchive}
            onUnarchive={onUnarchive}
          />
        ))}
      </div>
    </div>
  );
}
```

##### タスクカード

```tsx
// apps/web/src/app/kanban/components/KanbanCard.tsx

interface KanbanCardProps {
  task: TaskWithKanbanStatus;
  onArchive: (taskId: string) => void;
  onUnarchive: (taskId: string) => void;
}

export function KanbanCard({ task, onArchive, onUnarchive }: KanbanCardProps) {
  return (
    <Link
      href={`/tasks/${task.id}`}
      className="block p-3 bg-gray-800 rounded-lg hover:bg-gray-750 transition-colors"
    >
      <div className="font-medium text-sm truncate">
        {task.title || 'Untitled Task'}
      </div>
      
      <div className="mt-2 flex items-center gap-2 text-xs text-gray-500">
        {task.run_count > 0 && (
          <span className="flex items-center gap-1">
            <PlayIcon className="w-3 h-3" />
            {task.run_count} runs
          </span>
        )}
        {task.pr_count > 0 && (
          <span className="flex items-center gap-1">
            <CodeBracketIcon className="w-3 h-3" />
            {task.pr_count} PRs
          </span>
        )}
      </div>
      
      <div className="mt-2 flex items-center justify-between">
        <span className="text-xs text-gray-600">
          {formatRelativeTime(task.updated_at)}
        </span>
        
        {/* Archive/Unarchive button */}
        {task.kanban_status === 'archived' ? (
          <button
            onClick={(e) => {
              e.preventDefault();
              onUnarchive(task.id);
            }}
            className="text-xs text-blue-400 hover:text-blue-300"
          >
            Restore
          </button>
        ) : task.kanban_status === 'in_review' && (
          <button
            onClick={(e) => {
              e.preventDefault();
              onArchive(task.id);
            }}
            className="text-xs text-gray-400 hover:text-gray-300"
          >
            Archive
          </button>
        )}
      </div>
    </Link>
  );
}
```

#### 2.4 ナビゲーション追加

```tsx
// apps/web/src/components/Sidebar.tsx に追加

<Link
  href="/kanban"
  className={cn(
    'flex items-center gap-2 w-full py-2.5 px-3',
    'bg-gray-800 hover:bg-gray-700 rounded-lg',
    'text-sm font-medium transition-colors'
  )}
>
  <ViewColumnsIcon className="w-4 h-4" />
  Kanban Board
</Link>
```

---

### フェーズ3: 追加機能（将来）

#### 3.1 ドラッグ＆ドロップ（オプション）

- `@dnd-kit/core` または `react-beautiful-dnd` を使用
- 一部のカラム間移動のみ許可（例: InReview → Archived）
- 自動計算されるステータスは手動移動不可

#### 3.2 PRマージ検出の自動化

- WebhookまたはPollingでPRのマージ状態を自動検出
- バックグラウンドジョブでPR状態を定期的に同期

#### 3.3 フィルター・ソート機能

- リポジトリでフィルタリング
- 作成日/更新日でソート
- 検索機能

---

## ファイル変更一覧

### バックエンド
| ファイル | 変更内容 |
|---------|----------|
| `storage/schema.sql` | tasks.is_archived追加 |
| `domain/enums.py` | TaskKanbanStatus, PRStatus追加 |
| `domain/models.py` | TaskWithKanbanStatus, KanbanBoard追加 |
| `storage/dao.py` | TaskDAO.update_archived等追加 |
| `services/kanban_service.py` | **新規作成** |
| `services/github_service.py` | get_pull_request_status追加 |
| `routes/kanban.py` | **新規作成** |
| `main.py` | kanban router登録 |
| `dependencies.py` | get_kanban_service追加 |

### フロントエンド
| ファイル | 変更内容 |
|---------|----------|
| `types.ts` | TaskKanbanStatus等追加 |
| `lib/api.ts` | kanbanApi追加 |
| `app/kanban/page.tsx` | **新規作成** |
| `app/kanban/components/` | **新規作成** |
| `components/Sidebar.tsx` | Kanbanリンク追加 |

---

## 実装優先順位

1. **Phase 1-1**: DBスキーマ変更（is_archived追加）
2. **Phase 1-2**: ドメインモデル・enum追加
3. **Phase 1-3**: DAO拡張
4. **Phase 1-4**: KanbanService実装
5. **Phase 1-5**: APIエンドポイント実装
6. **Phase 2-1**: フロントエンド型定義
7. **Phase 2-2**: APIクライアント
8. **Phase 2-3**: 看板ページ・コンポーネント
9. **Phase 2-4**: Sidebar ナビゲーション追加

---

## テスト計画

### バックエンド
- [ ] `test_kanban_service.py`: ステータス計算ロジックのユニットテスト
- [ ] `test_kanban_routes.py`: APIエンドポイントのE2Eテスト

### フロントエンド
- [ ] 看板ページの表示テスト
- [ ] アーカイブ/アンアーカイブ操作テスト
- [ ] フィルタリング機能テスト

---

## 考慮事項

### パフォーマンス
- タスク数が増えた場合のクエリ最適化（JOINによる一括取得）
- フロントエンドでの仮想スクロール導入を検討

### UX
- 看板ステータスは自動計算されるため、ユーザーが直接移動できないことを明示
- アーカイブのみユーザーが明示的に操作可能
- PRマージ後は自動的にDoneへ移動

### セキュリティ
- 既存の認可パターンに従う（v0.2で認証追加予定）
