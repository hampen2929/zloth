# Multi-Agent Tools 並列実行機能

## 概要

Claude Code、Codex CLI、Gemini CLI の複数Agent toolを同時に実行し、結果を比較できる機能を実装する。これにより、ユーザーは同じタスクに対して複数のAgentの結果を並列で取得し、最適な結果を選択してPRを作成できる。

## 現状の課題

現在のシステムでは：
- `ExecutorType` で単一のCLI Agent（claude_code, codex_cli, gemini_cli）のみを選択可能
- 複数のAgentを同時に実行するには、手動で複数回実行する必要がある
- patch_agent（LLMモデル）は複数選択可能だが、CLI Agentは単一選択のみ

## ゴール

1. **複数Agent選択UI**: ユーザーが複数のCLI Agentを選択できるUIを提供
2. **並列実行**: 選択されたAgent toolを並列で実行
3. **結果比較UI**: 実行結果を個別のカードで表示し、それぞれの進捗・結果を確認可能

## 設計

### Phase 1: データモデル拡張

#### 1.1 RunCreate モデルの拡張

```python
# domain/models.py

class RunCreate(BaseModel):
    """Request for creating Runs."""
    
    instruction: str = Field(..., description="Natural language instruction")
    model_ids: list[str] | None = Field(
        None, description="List of model profile IDs to run (for patch_agent)"
    )
    base_ref: str | None = Field(None, description="Base branch/commit")
    
    # 既存: 単一executor
    executor_type: ExecutorType = Field(
        default=ExecutorType.PATCH_AGENT,
        description="Executor type (for backward compatibility)",
    )
    
    # 新規: 複数executor
    executor_types: list[ExecutorType] | None = Field(
        None,
        description="List of executor types to run in parallel",
    )
    
    message_id: str | None = Field(None, description="ID of the triggering message")
```

#### 1.2 TypeScript型定義の更新

```typescript
// types.ts

export interface RunCreate {
  instruction: string;
  model_ids?: string[];
  base_ref?: string;
  executor_type?: ExecutorType;
  executor_types?: ExecutorType[];  // 新規
  message_id?: string;
}
```

### Phase 2: バックエンド実装

#### 2.1 RunService の拡張

```python
# services/run_service.py

async def create_runs(self, task_id: str, data: RunCreate) -> list[Run]:
    """Create runs for multiple models or CLI agents (parallel execution)."""
    
    # Task検証
    task = await self.task_dao.get(task_id)
    if not task:
        raise ValueError(f"Task not found: {task_id}")
    
    repo = await self.repo_service.get(task.repo_id)
    if not repo:
        raise ValueError(f"Repo not found: {task.repo_id}")
    
    runs = []
    
    # 新規: 複数executor_typesが指定された場合
    if data.executor_types and len(data.executor_types) > 0:
        for executor_type in data.executor_types:
            if executor_type in {
                ExecutorType.CLAUDE_CODE,
                ExecutorType.CODEX_CLI,
                ExecutorType.GEMINI_CLI,
            }:
                run = await self._create_cli_run(
                    task_id=task_id,
                    repo=repo,
                    instruction=data.instruction,
                    base_ref=data.base_ref or repo.default_branch,
                    executor_type=executor_type,
                    message_id=data.message_id,
                )
                runs.append(run)
        return runs
    
    # 既存のロジック（後方互換性）
    # ... existing code ...
```

#### 2.2 ワークツリー分離の考慮

複数のCLI Agentを並列実行する場合、各Agentは独立したワークツリーで作業する必要がある。

```python
async def _create_cli_run(
    self,
    task_id: str,
    repo: Any,
    instruction: str,
    base_ref: str,
    executor_type: ExecutorType,
    message_id: str | None = None,
    # 新規: 並列実行時はworktree再利用を無効化するオプション
    force_new_worktree: bool = False,
) -> Run:
    """Create and start a CLI-based run."""
    
    # 並列実行時は、同じmessage_idで複数Runが作成される
    # 各Runには独立したworktreeが必要
    if force_new_worktree:
        existing_run = None  # worktree再利用をスキップ
    else:
        existing_run = await self.run_dao.get_latest_worktree_run(
            task_id=task_id,
            executor_type=executor_type,
        )
    
    # ... rest of implementation
```

### Phase 3: フロントエンド実装

#### 3.1 UI設計（画像1に基づく）

```
┌─────────────────────────────────────────────────────────────┐
│ Ask Cursor to build, fix bugs, explore                      │
│                                                             │
│                                                             │
│                                                             │
│ ┌─────────────────────────────────┐                        │
│ │ Opus 4.5, GPT-5.2, Gemini 3 Pro ▼│          🖼️  ↑         │
│ └─────────────────────────────────┘                        │
│                                                             │
│ ┌─────────────────────────────────┐                        │
│ │ Use Multiple Models     [●]     │                        │
│ │                                 │                        │
│ │ ☑ Opus 4.5              1x ▼   │                        │
│ │ ☑ GPT-5.2               1x ▼   │                        │
│ │ ☑ Gemini 3 Pro          1x ▼   │                        │
│ └─────────────────────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

**コンポーネント構成**:
- `MultiAgentSelector`: 複数Agent選択用ドロップダウン
- `AgentCheckboxItem`: 各Agentのチェックボックス＋実行回数設定
- `UseMultipleModelsToggle`: マルチモデルモードの切り替えトグル

#### 3.2 新規コンポーネント: MultiAgentSelector

```tsx
// components/MultiAgentSelector.tsx

interface MultiAgentSelectorProps {
  selectedAgents: ExecutorType[];
  onAgentsChange: (agents: ExecutorType[]) => void;
  disabled?: boolean;
}

const AGENT_OPTIONS: { type: ExecutorType; name: string; icon: string }[] = [
  { type: 'claude_code', name: 'Claude Code', icon: '🟣' },
  { type: 'codex_cli', name: 'Codex', icon: '🟢' },
  { type: 'gemini_cli', name: 'Gemini', icon: '🔵' },
];

export function MultiAgentSelector({
  selectedAgents,
  onAgentsChange,
  disabled = false,
}: MultiAgentSelectorProps) {
  const [showDropdown, setShowDropdown] = useState(false);
  
  const toggleAgent = (type: ExecutorType) => {
    if (selectedAgents.includes(type)) {
      onAgentsChange(selectedAgents.filter(a => a !== type));
    } else {
      onAgentsChange([...selectedAgents, type]);
    }
  };
  
  const getDisplayText = () => {
    if (selectedAgents.length === 0) return 'Select agents';
    if (selectedAgents.length === 1) {
      return AGENT_OPTIONS.find(a => a.type === selectedAgents[0])?.name;
    }
    return `${selectedAgents.length} agents selected`;
  };
  
  return (
    <div className="relative">
      <button
        onClick={() => setShowDropdown(!showDropdown)}
        disabled={disabled}
        className="flex items-center gap-2 px-3 py-2 ..."
      >
        <span>{getDisplayText()}</span>
        <ChevronDownIcon className="w-4 h-4" />
      </button>
      
      {showDropdown && (
        <div className="absolute bottom-full mb-2 w-72 bg-gray-800 ...">
          {/* マルチエージェントトグル */}
          <div className="p-3 border-b border-gray-700">
            <label className="flex items-center gap-2">
              <input type="checkbox" ... />
              <span>Use Multiple Agents</span>
            </label>
          </div>
          
          {/* Agent一覧 */}
          {AGENT_OPTIONS.map(agent => (
            <button
              key={agent.type}
              onClick={() => toggleAgent(agent.type)}
              className="w-full px-3 py-2.5 ..."
            >
              <div className="flex items-center gap-3">
                <CheckIcon ... />
                <span>{agent.icon}</span>
                <span>{agent.name}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

#### 3.3 ChatPanel の拡張

```tsx
// components/ChatPanel.tsx

interface ChatPanelProps {
  taskId: string;
  messages: Message[];
  models: ModelProfile[];
  executorType?: ExecutorType;
  executorTypes?: ExecutorType[];  // 新規: 複数Agent
  initialModelIds?: string[];
  onRunsCreated: () => void;
}

export function ChatPanel({
  taskId,
  messages,
  models,
  executorType = 'patch_agent',
  executorTypes = [],  // 新規
  initialModelIds,
  onRunsCreated,
}: ChatPanelProps) {
  const [useMultiAgent, setUseMultiAgent] = useState(false);
  const [selectedAgents, setSelectedAgents] = useState<ExecutorType[]>([]);
  const [currentExecutor, setCurrentExecutor] = useState<ExecutorType>(executorType);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    
    // 新規: 複数Agent実行
    if (useMultiAgent && selectedAgents.length > 0) {
      await runsApi.create(taskId, {
        instruction: messageContent,
        executor_types: selectedAgents,  // 複数指定
        message_id: message.id,
      });
      success(`Started ${selectedAgents.length} agent runs`);
      return;
    }
    
    // 既存のロジック（単一executor）
    // ... existing code ...
  };
  
  return (
    <div className="...">
      {/* ... existing UI ... */}
      
      {/* マルチエージェント選択UI */}
      {useMultiAgent ? (
        <MultiAgentSelector
          selectedAgents={selectedAgents}
          onAgentsChange={setSelectedAgents}
        />
      ) : (
        // 既存のExecutorSelector
        <ExecutorSelector ... />
      )}
    </div>
  );
}
```

#### 3.4 結果表示UI（画像2に基づく）

```
┌────────────────────────────────────────────────────────────────┐
│ Task breakdown feature  hampen2929/dursor ↗ ↙                  │
│                                                                │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│ │ Opus 4.5   ⏳│ │ GPT-5.2    ⏳│ │ Gemini 3 Pro │            │
│ │Working for   │ │Working for   │ │   +102       │            │
│ │2m 30s        │ │2m 7s         │ │   (完了)      │            │
│ └──────────────┘ └──────────────┘ └──────────────┘            │
└────────────────────────────────────────────────────────────────┘
```

**RunsPanel の拡張**:

```tsx
// components/RunsPanel.tsx

// 既存のグループ化ロジックを拡張
// message_idでグループ化された後、同じメッセージに複数Agentの結果を表示

const groupedRuns = useMemo(() => {
  const groups: { key: string; instruction: string; runs: Run[] }[] = [];
  // ... existing grouping logic ...
  return groups;
}, [filteredRuns]);

// 新規: 並列Agentカード表示
function ParallelAgentCards({ runs }: { runs: Run[] }) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-2">
      {runs.map(run => (
        <AgentResultCard
          key={run.id}
          run={run}
          isSelected={selectedRunId === run.id}
          onClick={() => onSelectRun(run.id)}
        />
      ))}
    </div>
  );
}

// 新規: 各Agentの結果カード
function AgentResultCard({ run, isSelected, onClick }: AgentResultCardProps) {
  const agentName = getAgentDisplayName(run.executor_type);
  const statusConfig = STATUS_CONFIG[run.status];
  
  return (
    <button
      onClick={onClick}
      className={cn(
        'min-w-[180px] p-3 rounded-lg border',
        isSelected ? 'border-blue-600 bg-blue-900/20' : 'border-gray-700 bg-gray-800',
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="font-medium text-sm">{agentName}</span>
        <span className={statusConfig.color}>{statusConfig.icon}</span>
      </div>
      
      {run.status === 'running' && (
        <div className="text-xs text-gray-400">
          Working for {formatDuration(run.created_at)}
        </div>
      )}
      
      {run.status === 'succeeded' && run.files_changed && (
        <div className="text-xs text-green-400">
          +{run.files_changed.reduce((sum, f) => sum + f.added_lines, 0)}
        </div>
      )}
    </button>
  );
}
```

### Phase 4: API変更

#### 4.1 エンドポイント

既存のエンドポイントをそのまま使用（後方互換性維持）:

```
POST /tasks/{task_id}/runs
```

リクエストボディ:
```json
{
  "instruction": "Fix the login bug",
  "executor_types": ["claude_code", "codex_cli", "gemini_cli"],
  "message_id": "msg_123"
}
```

レスポンス:
```json
{
  "run_ids": ["run_1", "run_2", "run_3"]
}
```

### Phase 5: 実装順序

#### Step 1: バックエンド（推定: 2-3時間）

1. [ ] `RunCreate`モデルに`executor_types`フィールド追加
2. [ ] `RunService.create_runs()`の拡張
   - 複数executor_types対応
   - 各CLIに独立したworktree作成
3. [ ] ユニットテストの追加

#### Step 2: フロントエンド型定義（推定: 30分）

1. [ ] `types.ts`に`executor_types`追加
2. [ ] API client (`api.ts`) の型更新

#### Step 3: UIコンポーネント（推定: 3-4時間）

1. [ ] `MultiAgentSelector`コンポーネント作成
2. [ ] `ChatPanel`の拡張
   - マルチエージェントモード切り替え
   - 複数Agent選択UI
3. [ ] `RunsPanel`の拡張
   - 並列実行されたRunのカード表示
   - 横スクロール対応

#### Step 4: 統合テスト（推定: 1-2時間）

1. [ ] E2Eテストの追加
2. [ ] 手動テスト
   - 複数Agent同時選択
   - 並列実行と結果表示
   - エラーハンドリング

### Phase 6: 考慮事項

#### 6.1 リソース管理

- **ワークツリー数**: 並列実行時は最大3つのworktreeが作成される
- **メモリ使用量**: 各CLI Agentは独立したプロセスで実行
- **ディスク容量**: 各worktreeがレポジトリのコピーを持つ

#### 6.2 エラーハンドリング

```python
# 1つのAgentが失敗しても他は継続
async def create_runs(self, task_id: str, data: RunCreate) -> list[Run]:
    runs = []
    errors = []
    
    for executor_type in data.executor_types or []:
        try:
            run = await self._create_cli_run(...)
            runs.append(run)
        except Exception as e:
            errors.append(f"{executor_type}: {str(e)}")
            logger.error(f"Failed to create run for {executor_type}: {e}")
    
    if not runs and errors:
        raise ValueError(f"All agent runs failed: {', '.join(errors)}")
    
    return runs
```

#### 6.3 後方互換性

- `executor_type`（単数）は引き続きサポート
- `executor_types`が指定された場合はそちらを優先
- 既存のUIは変更なしで動作

#### 6.4 セッション継続

並列実行されたRunは独立したセッションを持つため、後続メッセージでの会話継続は特定のAgentを選択する必要がある。

```typescript
// 後続メッセージ送信時
if (selectedRunForContinuation) {
  await runsApi.create(taskId, {
    instruction: message,
    executor_type: selectedRunForContinuation.executor_type,
    message_id: newMessage.id,
  });
}
```

### Phase 7: 将来の拡張

1. **実行回数設定**: 各Agentを複数回実行（例: Claude Code x 2）
2. **結果比較ビュー**: Side-by-side diff表示
3. **自動選択**: 最良の結果を自動で選択
4. **コスト表示**: 各Agent実行のコスト推定
5. **優先度設定**: Agentの実行優先度設定

## まとめ

この機能により、ユーザーは複数のAI Agentを同時に実行し、最適な結果を効率的に選択できるようになる。実装は後方互換性を維持しつつ、段階的に進める。
