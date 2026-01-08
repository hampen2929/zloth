# Multi-Agent Tools Execution Plan

This document outlines the plan to support parallel execution of multiple Agent tools (Claude Code, Codex, Gemini) in dursor.

## 概要

現在、Agentの実行は単一のExecutor Type（Patch Agent, Claude Code, Codex, Gemini）のいずれかを選択する排他方式となっています。
これを拡張し、一度のインストラクション送信で複数の異なるAgent Tool（例: Claude CodeとGemini）を並列に実行できるようにします。

## 目標

1.  **実行時の複数選択**: ユーザーは実行前に複数のAgent Tool（Executor）を選択できる。
2.  **並列実行**: バックエンドは選択されたすべてのAgent Toolに対してRunを作成し、並列に処理を開始する。
3.  **結果の並列表示**: 実行結果パネルに、それぞれのAgent Toolの実行結果が個別のカードとして表示される。

## 仕様変更計画

### 1. Backend (`apps/api`)

#### データモデルの変更
`RunCreate` モデル (`src/dursor_api/domain/models.py`) を拡張し、複数のExecutor設定を受け取れるようにします。

```python
class ExecutorConfig(BaseModel):
    executor_type: ExecutorType
    model_id: str | None = None  # PatchAgentの場合のみ必要

class RunCreate(BaseModel):
    instruction: str
    # 既存のフィールド（後方互換性のため維持するが、内部的には executors に変換される）
    model_ids: list[str] | None = None 
    executor_type: ExecutorType | None = None
    
    # 新しいフィールド
    executors: list[ExecutorConfig] | None = None
    
    base_ref: str | None = None
    message_id: str | None = None
```

#### サービスロジックの変更
`RunService.create_runs` (`src/dursor_api/services/run_service.py`) を改修します。

-   `executors` リストが提供された場合、それをイテレートして各Executorに対して `_create_cli_run` または PatchAgent用のRun作成処理を呼び出します。
-   既存の `executor_type` / `model_ids` パラメータが提供された場合は、それを `executors` リストに変換して処理を共通化します。
-   戻り値として作成されたすべての `Run` オブジェクトのリストを返します。

### 2. Frontend (`apps/web`)

#### 型定義の変更
`types.ts` に `ExecutorConfig` を追加し、`RunCreate` インターフェースを更新します。

#### ChatPanel コンポーネント (`components/ChatPanel.tsx`)
UIをラジオボタン方式からチェックボックス方式（複数選択可能）に変更します。

-   **State管理**: `currentExecutor` (単一) の代わりに、選択されたExecutorのリストを管理します。
    -   例: `selectedExecutors: { type: ExecutorType, modelId?: string }[]`
-   **UI**:
    -   「Models (Patch Agent)」, 「Claude Code」, 「Codex」, 「Gemini」 を独立してトグルできるようにします。
    -   「Models」が選択されている場合のみ、Patch Agent用のモデル選択リストを表示します。
-   **API呼び出し**:
    -   `handleSubmit` で、選択されたすべてのExecutor構成を `executors` 配列としてAPIに送信します。

## 実装ステップ

### Step 1: Backend APIの改修

1.  `apps/api/src/dursor_api/domain/models.py`: `ExecutorConfig` クラスを追加し、`RunCreate` を更新。
2.  `apps/api/src/dursor_api/services/run_service.py`: `create_runs` メソッドをリファクタリングし、複数Executorのループ処理に対応させる。

### Step 2: Frontend UIの改修

1.  `apps/web/src/types.ts`: 型定義の更新。
2.  `apps/web/src/components/ChatPanel.tsx`:
    -   Executor選択ロジックを複数選択に対応させる。
    -   APIリクエストの構築ロジックを更新。

## 考慮事項

-   **後方互換性**: 既存のAPIクライアント（もしあれば）が壊れないよう、`executor_type` フィールドも維持します。
-   **リソース制限**: 同時に多数のCLIツールを起動するとリソース（CPU/メモリ/ディスクIO）を消費するため、将来的に並列数の制限が必要になる可能性がありますが、現時点では制限なしとします。
-   **表示**: `RunsPanel` は既に `message_id` でグルーピングして表示する機能を持っているため、大きな変更は不要と予想されます。
