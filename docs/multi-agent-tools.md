# Coding Agent Tools 並列実行機能

## 概要

Claude Code、Codex CLI、Gemini CLI の複数Coding Agent Toolsを同時に実行し、結果を比較できる機能を実装する。これにより、ユーザーは同じタスクに対して複数のAgentの結果を並列で取得し、最適な結果を選択してPRを作成できる。

## 対象

- **対象**: Claude Code, Codex CLI, Gemini CLI（CLI-based Coding Agents）
- **対象外**: patch_agent（LLMモデルベース）は本機能の対象外

## 現状の課題

現在のシステムでは：
- `ExecutorType` で単一のCLI Agent（claude_code, codex_cli, gemini_cli）のみを選択可能
- 複数のAgentを同時に実行するには、手動で複数回実行する必要がある
- 各Agentの結果を効率的に比較する手段がない

## ゴール

1. **複数Agent選択UI**: ユーザーが複数のCoding Agent Toolsを選択できるUIを提供
2. **並列実行**: 選択されたAgent toolsを並列で実行
3. **結果比較UI**: 実行結果を個別のカードで表示し、それぞれの進捗・結果を確認可能

## 設計

### Phase 1: データモデル拡張

#### 1.1 RunCreate モデルの拡張

```python
# domain/models.py

class RunCreate(BaseModel):
    """Request for creating Runs."""
    
    instruction: str = Field(..., description="Natural language instruction")
    base_ref: str | None = Field(None, description="Base branch/commit")
    
    # 既存: 単一executor（後方互換性）
    executor_type: ExecutorType = Field(
        default=ExecutorType.CLAUDE_CODE,
        description="Executor type (for backward compatibility)",
    )
    
    # 新規: 複数executor（並列実行用）
    executor_types: list[ExecutorType] | None = Field(
        None,
        description="List of CLI executor types to run in parallel (claude_code, codex_cli, gemini_cli)",
    )
    
    message_id: str | None = Field(None, description="ID of the triggering message")
    
    # 削除または非推奨: model_ids は本機能では使用しない
    # model_ids: list[str] | None = Field(None, description="Deprecated")
```

#### 1.2 TypeScript型定義の更新

```typescript
// types.ts

export interface RunCreate {
  instruction: string;
  base_ref?: string;
  executor_type?: ExecutorType;
  executor_types?: ExecutorType[];  // 新規: 並列実行用
  message_id?: string;
}
```

### Phase 2: バックエンド実装

#### 2.1 RunService の拡張

```python
# services/run_service.py

# 有効なCLI Agent Types
CLI_AGENT_TYPES = {
    ExecutorType.CLAUDE_CODE,
    ExecutorType.CODEX_CLI,
    ExecutorType.GEMINI_CLI,
}

async def create_runs(self, task_id: str, data: RunCreate) -> list[Run]:
    """Create runs for multiple CLI agents (parallel execution)."""
    
    # Task検証
    task = await self.task_dao.get(task_id)
    if not task:
        raise ValueError(f"Task not found: {task_id}")
    
    repo = await self.repo_service.get(task.repo_id)
    if not repo:
        raise ValueError(f"Repo not found: {task.repo_id}")
    
    runs = []
    
    # 複数executor_typesが指定された場合（並列実行）
    if data.executor_types and len(data.executor_types) > 0:
        # CLI Agent Typesのみ許可
        valid_types = [et for et in data.executor_types if et in CLI_AGENT_TYPES]
        if not valid_types:
            raise ValueError(
                f"Invalid executor types. Must be one of: {[e.value for e in CLI_AGENT_TYPES]}"
            )
        
        for executor_type in valid_types:
            run = await self._create_cli_run(
                task_id=task_id,
                repo=repo,
                instruction=data.instruction,
                base_ref=data.base_ref or repo.default_branch,
                executor_type=executor_type,
                message_id=data.message_id,
                force_new_worktree=True,  # 並列実行時は必ず新規worktree
            )
            runs.append(run)
        return runs
    
    # 単一executor_typeが指定された場合（後方互換性）
    if data.executor_type in CLI_AGENT_TYPES:
        run = await self._create_cli_run(
            task_id=task_id,
            repo=repo,
            instruction=data.instruction,
            base_ref=data.base_ref or repo.default_branch,
            executor_type=data.executor_type,
            message_id=data.message_id,
        )
        runs.append(run)
        return runs
    
    raise ValueError(
        f"Invalid executor type: {data.executor_type}. "
        f"Must be one of: {[e.value for e in CLI_AGENT_TYPES]}"
    )
```

#### 2.2 ワークツリー分離

複数のCLI Agentを並列実行する場合、各Agentは独立したワークツリーで作業する。

```python
async def _create_cli_run(
    self,
    task_id: str,
    repo: Any,
    instruction: str,
    base_ref: str,
    executor_type: ExecutorType,
    message_id: str | None = None,
    force_new_worktree: bool = False,  # 並列実行時はTrue
) -> Run:
    """Create and start a CLI-based run."""
    
    # 並列実行時は、各Runに独立したworktreeが必要
    if force_new_worktree:
        existing_run = None  # worktree再利用をスキップ
    else:
        # 同一executor_typeの既存worktreeを再利用（会話継続用）
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
│ ┌─────────────────────────────────────┐                    │
│ │ Claude Code, Codex, Gemini CLI  ▼   │        🖼️  ↑       │
│ └─────────────────────────────────────┘                    │
│                                                             │
│ ┌─────────────────────────────────────┐                    │
│ │ Use Multiple Agents       [●]       │                    │
│ │                                     │                    │
│ │ ☑ Claude Code             1x ▼     │                    │
│ │ ☑ Codex                   1x ▼     │                    │
│ │ ☑ Gemini CLI              1x ▼     │                    │
│ └─────────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

**コンポーネント構成**:
- `AgentSelector`: Coding Agent選択用ドロップダウン（新規/既存ExecutorSelectorを置き換え）
- `AgentCheckboxItem`: 各Agentのチェックボックス
- `UseMultipleAgentsToggle`: マルチエージェントモードの切り替えトグル

#### 3.2 新規コンポーネント: AgentSelector

```tsx
// components/AgentSelector.tsx

'use client';

import { useState, useRef, useCallback } from 'react';
import type { ExecutorType } from '@/types';
import { cn } from '@/lib/utils';
import { useClickOutside } from '@/hooks';
import {
  ChevronDownIcon,
  CheckIcon,
  CommandLineIcon,
} from '@heroicons/react/24/outline';

interface AgentSelectorProps {
  selectedAgents: ExecutorType[];
  onAgentsChange: (agents: ExecutorType[]) => void;
  useMultipleAgents: boolean;
  onUseMultipleAgentsChange: (value: boolean) => void;
  disabled?: boolean;
}

const AGENT_OPTIONS: { 
  type: ExecutorType; 
  name: string; 
  description: string;
  color: string;
}[] = [
  { 
    type: 'claude_code', 
    name: 'Claude Code', 
    description: 'Anthropic Claude CLI',
    color: 'text-purple-400',
  },
  { 
    type: 'codex_cli', 
    name: 'Codex', 
    description: 'OpenAI Codex CLI',
    color: 'text-green-400',
  },
  { 
    type: 'gemini_cli', 
    name: 'Gemini CLI', 
    description: 'Google Gemini CLI',
    color: 'text-blue-400',
  },
];

export function AgentSelector({
  selectedAgents,
  onAgentsChange,
  useMultipleAgents,
  onUseMultipleAgentsChange,
  disabled = false,
}: AgentSelectorProps) {
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useClickOutside(dropdownRef, () => setShowDropdown(false), showDropdown);

  const toggleAgent = useCallback((type: ExecutorType) => {
    if (useMultipleAgents) {
      // マルチモード: トグル
      if (selectedAgents.includes(type)) {
        onAgentsChange(selectedAgents.filter(a => a !== type));
      } else {
        onAgentsChange([...selectedAgents, type]);
      }
    } else {
      // シングルモード: 置き換え
      onAgentsChange([type]);
      setShowDropdown(false);
    }
  }, [selectedAgents, onAgentsChange, useMultipleAgents]);

  const getDisplayText = () => {
    if (selectedAgents.length === 0) return 'Select agent';
    if (selectedAgents.length === 1) {
      return AGENT_OPTIONS.find(a => a.type === selectedAgents[0])?.name || 'Select agent';
    }
    const names = selectedAgents
      .map(a => AGENT_OPTIONS.find(o => o.type === a)?.name)
      .filter(Boolean);
    return names.join(', ');
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* トリガーボタン */}
      <button
        onClick={() => setShowDropdown(!showDropdown)}
        disabled={disabled}
        className={cn(
          'flex items-center gap-2 px-3 py-2 rounded-lg',
          'bg-gray-800 border border-gray-700',
          'text-sm text-gray-300 hover:text-white',
          'transition-colors',
          disabled && 'opacity-50 cursor-not-allowed',
        )}
      >
        <CommandLineIcon className="w-4 h-4" />
        <span className="truncate max-w-[200px]">{getDisplayText()}</span>
        <ChevronDownIcon 
          className={cn('w-4 h-4 transition-transform', showDropdown && 'rotate-180')} 
        />
      </button>

      {/* ドロップダウン */}
      {showDropdown && (
        <div className="absolute bottom-full left-0 mb-2 w-80 bg-gray-800 border border-gray-700 rounded-lg shadow-xl overflow-hidden z-20 animate-in fade-in slide-in-from-bottom-2 duration-200">
          {/* マルチエージェントトグル */}
          <div className="p-3 border-b border-gray-700">
            <label className="flex items-center justify-between cursor-pointer">
              <span className="text-sm text-gray-300">Use Multiple Agents</span>
              <div 
                className={cn(
                  'w-10 h-6 rounded-full transition-colors relative',
                  useMultipleAgents ? 'bg-green-600' : 'bg-gray-600',
                )}
                onClick={() => onUseMultipleAgentsChange(!useMultipleAgents)}
              >
                <div 
                  className={cn(
                    'w-4 h-4 bg-white rounded-full absolute top-1 transition-transform',
                    useMultipleAgents ? 'translate-x-5' : 'translate-x-1',
                  )}
                />
              </div>
            </label>
          </div>

          {/* Agent一覧 */}
          <div className="max-h-60 overflow-y-auto">
            {AGENT_OPTIONS.map(agent => {
              const isSelected = selectedAgents.includes(agent.type);
              return (
                <button
                  key={agent.type}
                  onClick={() => toggleAgent(agent.type)}
                  className={cn(
                    'w-full px-3 py-3 text-left flex items-center gap-3',
                    'hover:bg-gray-700 transition-colors',
                    'focus:outline-none focus:bg-gray-700',
                  )}
                >
                  {/* チェックボックス/ラジオ */}
                  <div
                    className={cn(
                      'w-5 h-5 flex items-center justify-center flex-shrink-0',
                      useMultipleAgents ? 'rounded border' : 'rounded-full border',
                      isSelected 
                        ? 'bg-blue-600 border-blue-600' 
                        : 'border-gray-600',
                    )}
                  >
                    {isSelected && <CheckIcon className="w-3 h-3 text-white" />}
                  </div>
                  
                  {/* Agent情報 */}
                  <div className="flex-1 min-w-0">
                    <div className={cn('text-sm font-medium', agent.color)}>
                      {agent.name}
                    </div>
                    <div className="text-xs text-gray-500">{agent.description}</div>
                  </div>
                </button>
              );
            })}
          </div>

          {/* フッター（マルチモード時のみ） */}
          {useMultipleAgents && (
            <div className="p-2 border-t border-gray-700 flex justify-between items-center">
              <span className="text-xs text-gray-500">
                {selectedAgents.length} agent{selectedAgents.length !== 1 ? 's' : ''} selected
              </span>
              <button
                onClick={() => {
                  if (selectedAgents.length === AGENT_OPTIONS.length) {
                    onAgentsChange([]);
                  } else {
                    onAgentsChange(AGENT_OPTIONS.map(a => a.type));
                  }
                }}
                className="text-xs text-blue-400 hover:text-blue-300"
              >
                {selectedAgents.length === AGENT_OPTIONS.length ? 'Deselect all' : 'Select all'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

#### 3.3 ChatPanel の更新

```tsx
// components/ChatPanel.tsx

'use client';

import { useState, useRef, useEffect } from 'react';
import { tasksApi, runsApi } from '@/lib/api';
import type { Message, ExecutorType } from '@/types';
import { Button } from './ui/Button';
import { AgentSelector } from './AgentSelector';
import { useToast } from './ui/Toast';

interface ChatPanelProps {
  taskId: string;
  messages: Message[];
  initialAgents?: ExecutorType[];
  onRunsCreated: () => void;
}

export function ChatPanel({
  taskId,
  messages,
  initialAgents = ['claude_code'],
  onRunsCreated,
}: ChatPanelProps) {
  const [input, setInput] = useState('');
  const [selectedAgents, setSelectedAgents] = useState<ExecutorType[]>(initialAgents);
  const [useMultipleAgents, setUseMultipleAgents] = useState(false);
  const [loading, setLoading] = useState(false);
  const { success, error } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || selectedAgents.length === 0) return;

    const messageContent = input.trim();
    setInput('');
    setLoading(true);

    try {
      // メッセージを追加
      const message = await tasksApi.addMessage(taskId, {
        role: 'user',
        content: messageContent,
      });

      // Run作成
      if (useMultipleAgents && selectedAgents.length > 1) {
        // 複数Agent並列実行
        await runsApi.create(taskId, {
          instruction: messageContent,
          executor_types: selectedAgents,
          message_id: message.id,
        });
        success(`Started ${selectedAgents.length} agent runs in parallel`);
      } else {
        // 単一Agent実行
        await runsApi.create(taskId, {
          instruction: messageContent,
          executor_type: selectedAgents[0],
          message_id: message.id,
        });
        const agentName = selectedAgents[0] === 'claude_code' ? 'Claude Code' 
          : selectedAgents[0] === 'codex_cli' ? 'Codex' : 'Gemini CLI';
        success(`Started ${agentName} run`);
      }

      onRunsCreated();
    } catch (err) {
      console.error('Failed to create runs:', err);
      error('Failed to create runs. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-900 rounded-lg border border-gray-800">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* ... existing message rendering ... */}
      </div>

      {/* Agent Selection */}
      <div className="border-t border-gray-800 p-3">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs text-gray-500">Agent:</span>
          <AgentSelector
            selectedAgents={selectedAgents}
            onAgentsChange={setSelectedAgents}
            useMultipleAgents={useMultipleAgents}
            onUseMultipleAgentsChange={setUseMultipleAgents}
            disabled={loading}
          />
        </div>

        {/* 並列実行時の説明 */}
        {useMultipleAgents && selectedAgents.length > 1 && (
          <div className="flex items-center gap-2 p-2 bg-blue-900/20 rounded-lg border border-blue-800/30 mb-2">
            <span className="text-xs text-blue-300">
              {selectedAgents.length} agents will run in parallel, each in isolated worktrees
            </span>
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="border-t border-gray-800 p-3">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Enter your instructions..."
            rows={3}
            className="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded resize-none text-sm"
            disabled={loading}
          />
          <Button
            type="submit"
            disabled={loading || !input.trim() || selectedAgents.length === 0}
            isLoading={loading}
            className="self-end"
          >
            Run
          </Button>
        </div>
      </form>
    </div>
  );
}
```

#### 3.4 結果表示UI（画像2に基づく）

```
┌────────────────────────────────────────────────────────────────┐
│ Task breakdown feature  hampen2929/dursor ↗ ↙                  │
│                                                                │
│ ┌────────────────┐ ┌────────────────┐ ┌────────────────┐      │
│ │ Claude Code  ⏳│ │ Codex        ⏳│ │ Gemini CLI     │      │
│ │ Working for    │ │ Working for    │ │   +102         │      │
│ │ 2m 30s         │ │ 2m 7s          │ │   ✓ 完了       │      │
│ └────────────────┘ └────────────────┘ └────────────────┘      │
└────────────────────────────────────────────────────────────────┘
```

#### 3.5 RunsPanel の拡張

```tsx
// components/RunsPanel.tsx

'use client';

import { useState, useMemo, useEffect } from 'react';
import type { Run, RunStatus, ExecutorType } from '@/types';
import { cn } from '@/lib/utils';
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  ClockIcon,
  ArrowPathIcon,
  CommandLineIcon,
} from '@heroicons/react/24/outline';

interface RunsPanelProps {
  runs: Run[];
  selectedRunId: string | null;
  onSelectRun: (runId: string) => void;
  isLoading?: boolean;
}

const STATUS_CONFIG: Record<RunStatus, { color: string; icon: React.ReactNode }> = {
  queued: { color: 'text-gray-400', icon: <ClockIcon className="w-4 h-4" /> },
  running: { color: 'text-yellow-400', icon: <ArrowPathIcon className="w-4 h-4 animate-spin" /> },
  succeeded: { color: 'text-green-400', icon: <CheckCircleIcon className="w-4 h-4" /> },
  failed: { color: 'text-red-400', icon: <ExclamationCircleIcon className="w-4 h-4" /> },
  canceled: { color: 'text-gray-500', icon: <XCircleIcon className="w-4 h-4" /> },
};

const AGENT_COLORS: Record<ExecutorType, string> = {
  claude_code: 'border-purple-500/50 bg-purple-900/10',
  codex_cli: 'border-green-500/50 bg-green-900/10',
  gemini_cli: 'border-blue-500/50 bg-blue-900/10',
  patch_agent: 'border-gray-500/50 bg-gray-900/10',
};

const AGENT_NAMES: Record<ExecutorType, string> = {
  claude_code: 'Claude Code',
  codex_cli: 'Codex',
  gemini_cli: 'Gemini CLI',
  patch_agent: 'Patch Agent',
};

function formatDuration(createdAt: string): string {
  const start = new Date(createdAt).getTime();
  const now = Date.now();
  const seconds = Math.floor((now - start) / 1000);
  
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds}s`;
}

// 並列実行されたRunのカードコンポーネント
function AgentRunCard({ 
  run, 
  isSelected, 
  onClick 
}: { 
  run: Run; 
  isSelected: boolean; 
  onClick: () => void;
}) {
  const [duration, setDuration] = useState(formatDuration(run.created_at));
  const statusConfig = STATUS_CONFIG[run.status];
  const agentName = AGENT_NAMES[run.executor_type];
  const agentColor = AGENT_COLORS[run.executor_type];

  // 実行中の場合は経過時間を更新
  useEffect(() => {
    if (run.status !== 'running' && run.status !== 'queued') return;
    
    const interval = setInterval(() => {
      setDuration(formatDuration(run.created_at));
    }, 1000);
    
    return () => clearInterval(interval);
  }, [run.status, run.created_at]);

  const totalAdded = run.files_changed?.reduce((sum, f) => sum + f.added_lines, 0) || 0;

  return (
    <button
      onClick={onClick}
      className={cn(
        'min-w-[160px] p-3 rounded-lg border-2 transition-all',
        agentColor,
        isSelected 
          ? 'ring-2 ring-blue-500 ring-offset-2 ring-offset-gray-900' 
          : 'hover:border-opacity-100',
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <CommandLineIcon className="w-4 h-4 text-gray-400" />
          <span className="font-medium text-sm text-gray-100">{agentName}</span>
        </div>
        <span className={statusConfig.color}>{statusConfig.icon}</span>
      </div>

      {(run.status === 'running' || run.status === 'queued') && (
        <div className="text-xs text-gray-400">
          Working for {duration}
        </div>
      )}

      {run.status === 'succeeded' && (
        <div className="text-xs text-green-400 font-mono">
          +{totalAdded}
        </div>
      )}

      {run.status === 'failed' && run.error && (
        <div className="text-xs text-red-400 truncate">
          {run.error}
        </div>
      )}
    </button>
  );
}

export function RunsPanel({
  runs,
  selectedRunId,
  onSelectRun,
  isLoading = false,
}: RunsPanelProps) {
  // message_idでグループ化（同じメッセージで並列実行されたRunをまとめる）
  const groupedRuns = useMemo(() => {
    const groups: { 
      key: string; 
      instruction: string; 
      runs: Run[];
      isParallel: boolean;
    }[] = [];
    const groupMap = new Map<string, { instruction: string; runs: Run[] }>();

    for (const run of runs) {
      const groupKey = run.message_id || `legacy:${run.id}`;
      
      if (groupMap.has(groupKey)) {
        groupMap.get(groupKey)!.runs.push(run);
      } else {
        groupMap.set(groupKey, { instruction: run.instruction, runs: [run] });
      }
    }

    // マップから配列に変換
    for (const [key, value] of groupMap) {
      groups.push({ 
        key, 
        ...value,
        isParallel: value.runs.length > 1,
      });
    }

    return groups;
  }, [runs]);

  return (
    <div className="flex flex-col h-full bg-gray-900 rounded-lg border border-gray-800">
      <div className="p-4 border-b border-gray-800">
        <h2 className="font-semibold text-gray-100">Runs</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {groupedRuns.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            No runs yet. Enter instructions to start.
          </div>
        ) : (
          groupedRuns.map((group) => (
            <div key={group.key} className="space-y-2">
              {/* インストラクション */}
              <div className="text-xs text-gray-500 px-1 truncate" title={group.instruction}>
                {group.instruction.slice(0, 60)}
                {group.instruction.length > 60 && '...'}
              </div>

              {/* 並列実行の場合: 横並びカード */}
              {group.isParallel ? (
                <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-thin">
                  {group.runs.map((run) => (
                    <AgentRunCard
                      key={run.id}
                      run={run}
                      isSelected={selectedRunId === run.id}
                      onClick={() => onSelectRun(run.id)}
                    />
                  ))}
                </div>
              ) : (
                // 単一実行の場合: 通常表示
                group.runs.map((run) => (
                  <AgentRunCard
                    key={run.id}
                    run={run}
                    isSelected={selectedRunId === run.id}
                    onClick={() => onSelectRun(run.id)}
                  />
                ))
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
```

### Phase 4: API仕様

#### 4.1 エンドポイント

既存のエンドポイントを使用（後方互換性維持）:

```
POST /tasks/{task_id}/runs
```

#### 4.2 リクエスト例

**単一Agent実行（後方互換）**:
```json
{
  "instruction": "Fix the login bug",
  "executor_type": "claude_code",
  "message_id": "msg_123"
}
```

**複数Agent並列実行（新機能）**:
```json
{
  "instruction": "Fix the login bug",
  "executor_types": ["claude_code", "codex_cli", "gemini_cli"],
  "message_id": "msg_123"
}
```

#### 4.3 レスポンス

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
   - CLI Agent Typesのバリデーション
   - 各Agentに独立したworktree作成（`force_new_worktree=True`）
3. [ ] ユニットテストの追加

#### Step 2: フロントエンド型定義（推定: 30分）

1. [ ] `types.ts`に`executor_types`追加
2. [ ] `model_ids`を削除または非推奨化

#### Step 3: UIコンポーネント（推定: 3-4時間）

1. [ ] `AgentSelector`コンポーネント作成
   - マルチエージェントモード切り替えトグル
   - Agent選択チェックボックス/ラジオ
2. [ ] `ChatPanel`の更新
   - `ExecutorSelector`を`AgentSelector`に置き換え
   - 複数Agent並列実行のサポート
3. [ ] `RunsPanel`の拡張
   - `AgentRunCard`コンポーネント追加
   - 並列実行Runの横並び表示
   - 経過時間のリアルタイム表示

#### Step 4: 統合テスト（推定: 1-2時間）

1. [ ] バックエンドテスト
   - 複数executor_types指定時のRun作成
   - worktree分離の確認
2. [ ] フロントエンドテスト
   - Agent選択UI
   - 並列実行結果の表示

### Phase 6: 考慮事項

#### 6.1 リソース管理

| 項目 | 単一実行 | 3Agent並列 |
|------|----------|------------|
| ワークツリー数 | 1 | 3 |
| メモリ使用量 | ~500MB | ~1.5GB |
| ディスク容量 | レポジトリサイズ×1 | レポジトリサイズ×3 |

#### 6.2 エラーハンドリング

```python
async def create_runs(self, task_id: str, data: RunCreate) -> list[Run]:
    """1つのAgentが失敗しても他は継続する"""
    runs = []
    errors = []
    
    for executor_type in data.executor_types or []:
        try:
            run = await self._create_cli_run(
                task_id=task_id,
                repo=repo,
                instruction=data.instruction,
                base_ref=data.base_ref or repo.default_branch,
                executor_type=executor_type,
                message_id=data.message_id,
                force_new_worktree=True,
            )
            runs.append(run)
        except Exception as e:
            errors.append(f"{executor_type.value}: {str(e)}")
            logger.error(f"Failed to create run for {executor_type}: {e}")
    
    # 全て失敗した場合のみエラー
    if not runs and errors:
        raise ValueError(f"All agent runs failed: {', '.join(errors)}")
    
    return runs
```

#### 6.3 セッション継続

並列実行後の会話継続は、特定のAgentを選択して行う：

```typescript
// 並列実行後、特定のAgentで会話継続
const continueWithAgent = async (runId: string, message: string) => {
  const run = await runsApi.get(runId);
  
  const newMessage = await tasksApi.addMessage(taskId, {
    role: 'user',
    content: message,
  });
  
  // 選択したRunと同じexecutor_typeで継続
  await runsApi.create(taskId, {
    instruction: message,
    executor_type: run.executor_type,
    message_id: newMessage.id,
  });
};
```

### Phase 7: 将来の拡張

1. **結果比較ビュー**: Side-by-side diff表示
2. **自動選択**: 最良の結果を自動で選択するヒューリスティック
3. **コスト表示**: 各Agent実行の推定コスト/時間
4. **優先度設定**: Agentの実行優先度設定
5. **実行回数設定**: 同一Agentを複数回実行（例: Claude Code x 2）

## まとめ

この機能により、ユーザーはClaude Code、Codex、Gemini CLIの3つのCoding Agent Toolsを並列実行し、最適な結果を効率的に比較・選択できるようになる。

**主なメリット**:
- 複数Agentの結果を一度に取得
- 各Agentの強みを活かした最適解の選択
- 結果比較による品質向上

**実装のポイント**:
- 後方互換性を維持（単一executor_typeも引き続きサポート）
- 各Agentは独立したworktreeで実行（競合なし）
- 部分的失敗への対応（1つ失敗しても他は継続）
