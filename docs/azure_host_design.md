# dursor Azure ホスティング設計書

本ドキュメントは dursor を Microsoft Azure 上にホスティングするためのアーキテクチャ設計を記載します。

## エグゼクティブサマリー

dursor は現在、SQLite による永続化とインメモリ状態管理を持つ単一インスタンス・セルフホスト型アプリケーションとして設計されています。Azure 上でスケーラブルにデプロイするには、ステートフルなコンポーネントを分散システム向けに置き換え、適切な認証を実装し、Azure ネイティブサービスを活用する必要があります。

## 現状アーキテクチャの課題

| コンポーネント | 現状 | クラウド移行時の課題 |
|--------------|------|---------------------|
| データベース | SQLite（ファイルベース） | 水平スケーリング不可、単一障害点 |
| タスクキュー | インメモリ asyncio.Task | 再起動で消失、分散不可 |
| Git ワークスペース | ローカルファイルシステム | インスタンス間で共有不可 |
| トークンキャッシュ | インメモリ dict | 再起動で消失 |
| バックグラウンドジョブ | asyncio Tasks | 永続化なし、フェイルオーバー不可 |
| 認証 | なし | マルチテナント非対応 |

## 提案する Azure アーキテクチャ

```mermaid
flowchart TB
    subgraph Internet["インターネット"]
        Users[ユーザー/ブラウザ]
        GitHub[GitHub API]
        LLM[LLM プロバイダー<br/>OpenAI/Anthropic/Google]
    end

    subgraph Azure["Azure Cloud"]
        subgraph FrontDoor["Azure Front Door"]
            WAF[Web Application Firewall]
            CDN[CDN（静的アセット用）]
        end

        subgraph AppService["Azure Container Apps"]
            subgraph APIPool["API プール（オートスケール）"]
                API1[API インスタンス 1]
                API2[API インスタンス 2]
                APIx[API インスタンス N]
            end

            subgraph WebPool["Web プール（オートスケール）"]
                Web1[Web インスタンス 1]
                Web2[Web インスタンス 2]
            end

            subgraph Workers["Worker プール（オートスケール）"]
                Worker1[Celery Worker 1]
                Worker2[Celery Worker 2]
                WorkerN[Celery Worker N]
            end
        end

        subgraph Data["データ層"]
            PostgreSQL[(Azure Database<br/>for PostgreSQL)]
            Redis[(Azure Cache<br/>for Redis)]
            BlobStorage[(Azure Blob<br/>Storage)]
        end

        subgraph Security["セキュリティ"]
            KeyVault[Azure Key Vault]
            EntraID[Microsoft Entra ID]
            ManagedIdentity[Managed Identity]
        end

        subgraph Monitoring["監視"]
            AppInsights[Application Insights]
            LogAnalytics[Log Analytics]
            Alerts[Azure Alerts]
        end
    end

    Users --> WAF
    WAF --> CDN
    CDN --> WebPool
    CDN --> APIPool

    APIPool --> PostgreSQL
    APIPool --> Redis
    APIPool --> BlobStorage
    APIPool --> GitHub
    APIPool --> LLM

    Workers --> PostgreSQL
    Workers --> Redis
    Workers --> BlobStorage
    Workers --> GitHub
    Workers --> LLM

    APIPool --> KeyVault
    Workers --> KeyVault

    EntraID --> APIPool
    ManagedIdentity --> Data
    ManagedIdentity --> KeyVault

    APIPool --> AppInsights
    Workers --> AppInsights
    WebPool --> AppInsights
```

## コンポーネント設計

### 1. コンピュート層

#### Azure Container Apps

Azure App Service より推奨される理由：
- ネイティブコンテナサポート
- KEDA による組み込みオートスケーリング
- マイクロサービスデプロイの簡素化
- コスト効率の良い scale-to-zero 機能

```mermaid
flowchart LR
    subgraph ContainerApps["Azure Container Apps 環境"]
        subgraph API["API サービス"]
            direction TB
            A1[レプリカ 1]
            A2[レプリカ 2]
            An[レプリカ N]
        end

        subgraph Web["Web サービス"]
            direction TB
            W1[レプリカ 1]
            W2[レプリカ 2]
        end

        subgraph Worker["Worker サービス"]
            direction TB
            WK1[Worker 1]
            WK2[Worker 2]
            WKn[Worker N]
        end
    end

    API <--> Redis[(Redis)]
    Worker <--> Redis
    API <--> PostgreSQL[(PostgreSQL)]
    Worker <--> PostgreSQL
```

**構成:**

| サービス | 最小レプリカ | 最大レプリカ | CPU | メモリ | スケールトリガー |
|---------|------------|------------|-----|--------|----------------|
| API | 2 | 10 | 0.5 | 1Gi | HTTP リクエスト |
| Web | 2 | 5 | 0.25 | 512Mi | HTTP リクエスト |
| Worker | 1 | 20 | 1.0 | 2Gi | Redis キュー長 |

### 2. データベース層

#### Azure Database for PostgreSQL - Flexible Server

SQLite を PostgreSQL に置き換える理由：
- 水平読み取りレプリカによる ACID 準拠
- コネクションプーリング（PgBouncer 組み込み）
- 自動フェイルオーバーによる高可用性
- ポイントインタイムリストア

**スキーママイグレーション:**

```sql
-- SQLite から PostgreSQL への主な変更点

-- INTEGER PRIMARY KEY の代わりに SERIAL を使用
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,  -- 旧: INTEGER PRIMARY KEY
    ...
);

-- TEXT の代わりに JSONB を使用（JSON カラム）
ALTER TABLE runs
    ALTER COLUMN files_changed TYPE JSONB USING files_changed::JSONB,
    ALTER COLUMN logs TYPE JSONB USING logs::JSONB;

-- コネクションプーリングサポートの追加
-- Azure Portal で PgBouncer を設定
```

**構成:**

| 設定 | 開発環境 | 本番環境 |
|-----|---------|---------|
| SKU | Burstable B1ms | General Purpose D4s_v3 |
| ストレージ | 32 GB | 256 GB |
| バックアップ保持期間 | 7 日 | 35 日 |
| 高可用性 | 無効 | ゾーン冗長 |
| 読み取りレプリカ | 0 | 2 |

### 3. キャッシュ層

#### Azure Cache for Redis

インメモリキャッシュを Redis に置き換える理由：
- 分散セッション/トークンストレージ
- タスクキューバックエンド（Celery ブローカー）
- リアルタイム更新のための Pub/Sub
- レート制限

**使用パターン:**

```mermaid
flowchart LR
    subgraph API["API インスタンス"]
        A1[インスタンス 1]
        A2[インスタンス 2]
    end

    subgraph Redis["Azure Cache for Redis"]
        Cache[トークンキャッシュ]
        Queue[Celery キュー]
        PubSub[Pub/Sub チャンネル]
        RateLimit[レート制限カウンター]
    end

    A1 --> Cache
    A2 --> Cache
    A1 --> Queue
    A2 --> Queue
    A1 --> PubSub
    A2 --> PubSub
```

**構成:**

| 設定 | 開発環境 | 本番環境 |
|-----|---------|---------|
| SKU | Basic C0 | Premium P1 |
| メモリ | 250 MB | 6 GB |
| クラスタリング | 無効 | 有効（3 シャード） |
| Geo レプリケーション | なし | あり |

### 4. ストレージ層

#### Azure Blob Storage

ローカルファイルシステムを以下で置き換え：
- リポジトリアーカイブ用の Blob Storage
- worktree マウント用の Azure Files（SMB/NFS）（必要に応じて）
- クリーンアップのためのライフサイクル管理

**ストレージ戦略:**

```mermaid
flowchart TB
    subgraph BlobStorage["Azure Blob Storage"]
        subgraph Containers["コンテナ"]
            Workspaces[workspaces/]
            Artifacts[artifacts/]
            Temp[temp/]
        end

        subgraph Lifecycle["ライフサイクル管理"]
            Hot[Hot 層<br/>アクティブなリポジトリ]
            Cool[Cool 層<br/>30日以上非アクティブ]
            Archive[Archive 層<br/>90日以上非アクティブ]
            Delete[削除<br/>365日後]
        end
    end

    Workspaces --> Hot
    Hot -->|30日| Cool
    Cool -->|90日| Archive
    Temp -->|7日| Delete
```

**コンテナ構造:**

```
dursor-storage/
├── workspaces/
│   └── {repo_uuid}/
│       └── repo.tar.gz          # 圧縮されたリポジトリ
├── artifacts/
│   └── {run_id}/
│       └── patch.diff           # 生成されたパッチ
└── temp/
    └── {run_id}/
        └── worktree/            # 一時的な worktree（Azure Files マウント）
```

### 5. 長時間実行タスクの非同期通信アーキテクチャ

Claude Code や Codex などの AI エージェントは実行に数分〜数十分かかるため、特別な非同期通信設計が必要です。

#### 課題

| 課題 | 説明 |
|-----|------|
| 実行時間 | Claude Code/Codex は 5〜30 分以上かかることがある |
| HTTP タイムアウト | Azure Front Door のデフォルトタイムアウトは 30 秒 |
| コネクション維持 | 長時間の HTTP 接続は不安定 |
| スケールアウト | 実行中にインスタンスが変わる可能性 |

#### 解決策: Celery + Redis Pub/Sub + SSE

**Container Apps は長時間実行タスクに対応可能です。** ただし、以下の設計パターンを採用する必要があります：

```mermaid
sequenceDiagram
    participant Browser as ブラウザ
    participant API as API サーバー
    participant Redis as Redis
    participant Worker as Celery Worker
    participant Claude as Claude Code CLI

    Note over Browser,Claude: フェーズ1: タスク投入

    Browser->>API: POST /v1/tasks/ID/runs
    API->>Redis: タスクをキューに投入
    API->>API: DB に run 作成 status: queued
    API-->>Browser: 202 Accepted + run_id

    Note over Browser,Claude: フェーズ2: SSE 接続確立

    Browser->>API: GET /v1/runs/ID/stream SSE
    API->>Redis: SUBSCRIBE run:ID:events
    API-->>Browser: SSE 接続確立

    Note over Browser,Claude: フェーズ3: 長時間実行（5〜30分）

    Worker->>Redis: タスク取得
    Worker->>Worker: DB 更新（status: running）
    Worker->>Redis: PUBLISH 進捗イベント
    Redis-->>API: 進捗イベント
    API-->>Browser: SSE progress event

    Worker->>Claude: エージェント実行開始

    loop 実行中（数分〜数十分）
        Claude-->>Worker: 中間出力
        Worker->>Redis: PUBLISH 進捗イベント
        Redis-->>API: 進捗イベント
        API-->>Browser: SSE log event
    end

    Claude-->>Worker: 完了 + パッチ
    Worker->>Worker: DB 更新（status: completed, patch）
    Worker->>Redis: PUBLISH 完了イベント
    Redis-->>API: 完了イベント
    API-->>Browser: SSE completed event
```

#### Azure Container Apps での SSE 設定

**重要:** Azure Container Apps は SSE（Server-Sent Events）をネイティブでサポートしています。

```yaml
# Container Apps Ingress 設定
ingress:
  external: true
  targetPort: 8000
  transport: http
  # SSE 用の設定
  clientRequestTimeout: 3600  # 1時間（SSE 接続用）
```

**Azure Front Door 設定:**

```bicep
// SSE 対応のための Front Door 設定
resource frontDoorRoute 'Microsoft.Cdn/profiles/afdEndpoints/routes@2023-05-01' = {
  properties: {
    originGroup: {
      id: originGroup.id
    }
    // SSE 用のタイムアウト延長
    forwardingProtocol: 'HttpOnly'
    // レスポンスタイムアウト: 最大 240 秒
    // ただし SSE は chunked なので実質無制限
  }
}
```

#### 代替案: WebSocket

SSE が不安定な場合は WebSocket を検討：

```mermaid
flowchart LR
    subgraph Browser["ブラウザ"]
        WS[WebSocket クライアント]
    end

    subgraph Azure["Azure"]
        subgraph SignalR["Azure SignalR Service"]
            Hub[SignalR Hub]
        end

        subgraph API["API サーバー"]
            Endpoint["WebSocket Endpoint"]
        end

        subgraph Worker["Worker"]
            Agent[エージェント実行]
        end
    end

    WS <-->|WebSocket| Hub
    Hub <--> Endpoint
    Agent -->|進捗通知| Hub
```

**Azure SignalR Service の利点:**
- マネージドな WebSocket インフラ
- 自動スケーリング
- 接続の永続化と再接続処理
- Container Apps との統合が容易

#### 推奨パターン: ハイブリッドアプローチ

```python
# routes/runs.py - 長時間実行タスクの SSE エンドポイント

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import redis.asyncio as redis
import json

router = APIRouter()

@router.get("/v1/runs/{run_id}/stream")
async def stream_run_events(run_id: str, request: Request):
    """
    長時間実行タスクのリアルタイムストリーミング

    - Redis Pub/Sub でイベントを購読
    - SSE 形式でクライアントに配信
    - クライアント切断を検知して購読解除
    """
    async def event_generator():
        redis_client = redis.from_url("rediss://...")
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"run:{run_id}:events")

        try:
            # 初期状態を送信
            run = await get_run(run_id)
            yield f"data: {json.dumps({'type': 'initial', 'status': run.status})}\n\n"

            # イベントストリーム
            async for message in pubsub.listen():
                if await request.is_disconnected():
                    break

                if message["type"] == "message":
                    event_data = json.loads(message["data"])
                    yield f"data: {json.dumps(event_data)}\n\n"

                    # 完了イベントで終了
                    if event_data.get("type") in ["completed", "failed", "cancelled"]:
                        break
        finally:
            await pubsub.unsubscribe(f"run:{run_id}:events")
            await redis_client.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # nginx バッファリング無効化
        }
    )
```

#### 接続断対応とリカバリー

長時間実行中に接続が切れた場合の対応：

```mermaid
sequenceDiagram
    participant Browser as ブラウザ
    participant API as API
    participant DB as PostgreSQL

    Note over Browser,DB: 接続断からの復旧

    Browser->>API: GET /v1/runs/ID/stream?last_event_id=xxx
    API->>DB: run 状態取得

    alt 実行中
        API->>DB: last_event_id 以降のログ取得
        API-->>Browser: 過去イベント再送 + ストリーム再開
    else 完了済み
        API-->>Browser: 完了イベント送信
    end
```

**実装のポイント:**

```python
# services/run_service.py

class RunService:
    async def get_events_since(self, run_id: str, last_event_id: str | None) -> list[dict]:
        """
        指定イベント以降のログを取得（SSE 再接続用）
        """
        run = await self.run_dao.get(run_id)
        if not run:
            raise ValueError(f"Run not found: {run_id}")

        # DB に保存されたログから last_event_id 以降を抽出
        logs = json.loads(run.logs or "[]")

        if last_event_id:
            # last_event_id 以降のログを返す
            found = False
            result = []
            for log in logs:
                if found:
                    result.append(log)
                if log.get("event_id") == last_event_id:
                    found = True
            return result

        return logs
```

#### Container Apps の制約と対策

| 制約 | 値 | 対策 |
|-----|-----|------|
| HTTP リクエストタイムアウト | 最大 240 秒 | SSE/WebSocket を使用 |
| アイドルタイムアウト | 4 分 | Keep-alive ping を送信 |
| インスタンス再起動 | 随時発生 | Redis で状態を永続化 |
| スケールイン | キュー空で発生 | 最小レプリカを 1 以上に |

**Keep-alive 実装:**

```python
async def event_generator():
    last_ping = time.time()

    async for message in pubsub.listen():
        # 30 秒ごとに ping を送信
        if time.time() - last_ping > 30:
            yield f": ping\n\n"  # SSE コメント（keep-alive）
            last_ping = time.time()

        # 通常のイベント処理
        if message["type"] == "message":
            yield f"data: {json.dumps(message['data'])}\n\n"
```

#### アーキテクチャ比較

| パターン | 長所 | 短所 | 推奨シナリオ |
|---------|------|------|------------|
| **SSE + Redis Pub/Sub** | シンプル、標準的、低コスト | 単方向のみ | ほとんどのケースで推奨 |
| **WebSocket + SignalR** | 双方向通信、高信頼性 | 追加コスト、複雑性 | インタラクティブ操作が必要な場合 |
| **ポーリング** | 最もシンプル | 遅延、リソース消費 | フォールバック用 |

**結論:** Container Apps は長時間実行タスクの非同期通信に対応可能です。SSE + Redis Pub/Sub パターンを採用し、適切な keep-alive とリカバリー機構を実装することで、数十分のエージェント実行でも安定した通信が可能です。

### 6. タスクキューアーキテクチャ

#### Celery + Redis

インメモリ asyncio キューを Celery に置き換える理由：
- 永続的なタスクキュー
- 分散ワーカースケーリング
- タスクリトライとデッドレター処理
- タスク結果バックエンド

```mermaid
sequenceDiagram
    participant API as API サーバー
    participant Redis as Redis ブローカー
    participant Worker as Celery Worker
    participant DB as PostgreSQL
    participant GitHub as GitHub API
    participant LLM as LLM プロバイダー

    API->>Redis: run タスクをキューに投入
    API->>DB: run ステータス更新（queued）
    API-->>User: run ID を返却

    Worker->>Redis: タスク取得
    Worker->>DB: ステータス更新（running）
    Worker->>GitHub: リポジトリ clone/fetch
    Worker->>LLM: エージェント実行
    LLM-->>Worker: パッチ結果
    Worker->>DB: 結果保存
    Worker->>Redis: 完了イベント発行

    API->>Redis: イベント購読
    Redis-->>API: 完了通知
    API-->>User: SSE 更新
```

**Celery 設定:**

```python
# celery_config.py
from celery import Celery

app = Celery(
    'dursor',
    broker='rediss://:password@dursor-redis.redis.cache.windows.net:6380/0',
    backend='rediss://:password@dursor-redis.redis.cache.windows.net:6380/1',
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # 長時間実行タスク用の設定
    task_time_limit=3600,      # ハードリミット: 1時間
    task_soft_time_limit=3000, # ソフトリミット: 50分
    task_routes={
        'dursor.tasks.run_agent': {'queue': 'agent'},
        'dursor.tasks.poll_ci': {'queue': 'polling'},
        'dursor.tasks.poll_pr': {'queue': 'polling'},
    },
)
```

**長時間タスクの実装例:**

```python
# tasks/agent_tasks.py
from celery import shared_task
import redis.asyncio as redis

@shared_task(bind=True, max_retries=3)
def run_agent_task(self, run_id: str, workspace_path: str, instruction: str):
    """
    Claude Code/Codex エージェントを実行する長時間タスク

    - 実行時間: 5〜30分
    - Redis Pub/Sub で進捗を配信
    - DB に結果を保存
    """
    redis_client = redis.from_url("rediss://...")

    try:
        # 進捗通知
        async def publish_progress(message: str):
            await redis_client.publish(
                f"run:{run_id}:events",
                json.dumps({"type": "progress", "message": message})
            )

        # エージェント実行
        executor = ClaudeCodeExecutor(...)
        result = await executor.execute(
            workspace_path=workspace_path,
            instruction=instruction,
            progress_callback=publish_progress,
        )

        # 完了通知
        await redis_client.publish(
            f"run:{run_id}:events",
            json.dumps({
                "type": "completed",
                "patch": result.patch,
                "summary": result.summary,
            })
        )

        return {"status": "completed", "run_id": run_id}

    except Exception as e:
        # エラー通知
        await redis_client.publish(
            f"run:{run_id}:events",
            json.dumps({"type": "failed", "error": str(e)})
        )
        raise self.retry(exc=e, countdown=60)
```

### 7. セキュリティアーキテクチャ

#### Microsoft Entra ID (Azure AD)

認証・認可の実装：

```mermaid
flowchart LR
    User[ユーザー] --> EntraID[Microsoft Entra ID]
    EntraID --> Token[JWT トークン]
    Token --> API[dursor API]
    API --> RBAC{RBAC チェック}
    RBAC -->|認可| Resource[リソース]
    RBAC -->|拒否| Error[403 Forbidden]
```

**認証フロー:**

1. ユーザーが Microsoft Entra ID で認証
2. クレーム付き JWT トークンを受け取る
3. API が各リクエストでトークンを検証
4. RBAC がリソースアクセスを決定

**ロール定義:**

| ロール | 権限 |
|-------|------|
| Admin | フルアクセス、ユーザー管理、GitHub App 設定 |
| Developer | タスク作成、エージェント実行、PR 作成 |
| Viewer | タスクと PR の読み取り専用アクセス |

#### Azure Key Vault

機密設定の保存：

| シークレット | 用途 |
|-------------|------|
| `dursor-encryption-key` | API キー暗号化 |
| `github-app-private-key` | GitHub App 認証 |
| `postgresql-connection-string` | データベース接続 |
| `redis-connection-string` | キャッシュ接続 |

**アクセスパターン:**

```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

credential = DefaultAzureCredential()
client = SecretClient(
    vault_url="https://dursor-vault.vault.azure.net/",
    credential=credential
)

encryption_key = client.get_secret("dursor-encryption-key").value
```

### 8. ネットワークアーキテクチャ

```mermaid
flowchart TB
    subgraph Internet["インターネット"]
        Users[ユーザー]
        GitHub[GitHub]
        LLM[LLM APIs]
    end

    subgraph Azure["Azure"]
        subgraph PublicZone["パブリックゾーン"]
            FrontDoor[Azure Front Door]
        end

        subgraph VNet["Virtual Network (10.0.0.0/16)"]
            subgraph AppSubnet["App サブネット (10.0.1.0/24)"]
                ContainerApps[Container Apps]
            end

            subgraph DataSubnet["Data サブネット (10.0.2.0/24)"]
                PostgreSQL[(PostgreSQL)]
                Redis[(Redis)]
            end

            subgraph PrivateEndpoints["プライベートエンドポイント"]
                BlobPE[Blob Storage PE]
                KeyVaultPE[Key Vault PE]
            end
        end

        subgraph Storage["ストレージ"]
            BlobStorage[(Blob Storage)]
            KeyVault[(Key Vault)]
        end
    end

    Users --> FrontDoor
    FrontDoor --> ContainerApps
    ContainerApps --> PostgreSQL
    ContainerApps --> Redis
    ContainerApps --> BlobPE --> BlobStorage
    ContainerApps --> KeyVaultPE --> KeyVault
    ContainerApps --> GitHub
    ContainerApps --> LLM
```

**ネットワークセキュリティ:**

- すべての Azure PaaS サービスにプライベートエンドポイント
- トラフィックを制限するネットワークセキュリティグループ（NSG）
- DDoS 対策のための Azure Front Door + WAF
- GitHub と LLM プロバイダー IP 用のサービスタグ

### 9. 監視とオブザーバビリティ

#### Application Insights

```mermaid
flowchart LR
    subgraph Apps["アプリケーション"]
        API[API サービス]
        Web[Web サービス]
        Worker[Worker サービス]
    end

    subgraph AppInsights["Application Insights"]
        Traces[分散トレース]
        Metrics[メトリクス]
        Logs[ログ]
        Availability[可用性テスト]
    end

    subgraph Alerts["アラート"]
        ErrorRate[エラー率 > 1%]
        Latency[P95 > 2s]
        QueueDepth[キュー > 100]
    end

    API --> Traces
    API --> Metrics
    API --> Logs
    Web --> Traces
    Web --> Logs
    Worker --> Traces
    Worker --> Logs

    Metrics --> Alerts
    Logs --> Alerts
```

**主要メトリクス:**

| メトリクス | 警告 | クリティカル |
|-----------|------|------------|
| API エラー率 | > 1% | > 5% |
| API P95 レイテンシ | > 2s | > 5s |
| Worker キュー深度 | > 50 | > 200 |
| データベース接続数 | > 80% | > 95% |
| Redis メモリ | > 70% | > 90% |
| エージェント実行時間 | > 30分 | > 60分 |

### 10. 災害復旧

**復旧目標:**

| ティア | RTO | RPO | 戦略 |
|-------|-----|-----|------|
| 開発 | 4 時間 | 24 時間 | 単一リージョン、日次バックアップ |
| 本番 | 15 分 | 5 分 | マルチリージョン、継続的レプリケーション |

**バックアップ戦略:**

```mermaid
flowchart LR
    subgraph Primary["東日本（プライマリ）"]
        DB1[(PostgreSQL)]
        Redis1[(Redis)]
        Blob1[(Blob Storage)]
    end

    subgraph Secondary["西日本（セカンダリ）"]
        DB2[(PostgreSQL<br/>読み取りレプリカ)]
        Redis2[(Redis<br/>Geo レプリカ)]
        Blob2[(Blob Storage<br/>GRS)]
    end

    DB1 -->|非同期レプリケーション| DB2
    Redis1 -->|Geo レプリケーション| Redis2
    Blob1 -->|GRS| Blob2
```

## 環境設定

### 開発環境

```yaml
# Container Apps - 開発
api:
  minReplicas: 1
  maxReplicas: 2
  resources:
    cpu: 0.25
    memory: 512Mi

web:
  minReplicas: 1
  maxReplicas: 1
  resources:
    cpu: 0.25
    memory: 256Mi

worker:
  minReplicas: 1
  maxReplicas: 3
  resources:
    cpu: 0.5
    memory: 1Gi

# Database - 開発
postgresql:
  sku: Burstable_B1ms
  storage: 32GB
  haEnabled: false

# Cache - 開発
redis:
  sku: Basic_C0
```

### 本番環境

```yaml
# Container Apps - 本番
api:
  minReplicas: 2
  maxReplicas: 10
  resources:
    cpu: 0.5
    memory: 1Gi

web:
  minReplicas: 2
  maxReplicas: 5
  resources:
    cpu: 0.25
    memory: 512Mi

worker:
  minReplicas: 2
  maxReplicas: 20
  resources:
    cpu: 1.0
    memory: 2Gi

# Database - 本番
postgresql:
  sku: GeneralPurpose_D4s_v3
  storage: 256GB
  haEnabled: true
  readReplicas: 2

# Cache - 本番
redis:
  sku: Premium_P1
  clustering: true
  geoReplication: true
```

## コスト見積もり

### 月額コスト（円）

| リソース | 開発 | 本番 |
|---------|------|------|
| Container Apps (API) | ¥5,000 | ¥30,000 |
| Container Apps (Web) | ¥3,000 | ¥15,000 |
| Container Apps (Worker) | ¥8,000 | ¥50,000 |
| PostgreSQL | ¥4,000 | ¥60,000 |
| Redis | ¥3,000 | ¥45,000 |
| Blob Storage | ¥1,000 | ¥10,000 |
| Azure Front Door | ¥5,000 | ¥20,000 |
| Key Vault | ¥500 | ¥2,000 |
| Application Insights | ¥2,000 | ¥15,000 |
| **合計** | **¥31,500** | **¥247,000** |

*注: 中程度の使用量に基づく見積もり。実際のコストは使用量により変動します。*

## マイグレーション計画

### フェーズ 1: データベースマイグレーション

```mermaid
gantt
    title フェーズ 1: データベースマイグレーション
    dateFormat  YYYY-MM-DD
    section 準備
    PostgreSQL セットアップ        :p1, 2024-01-01, 3d
    マイグレーションスクリプト作成  :p2, after p1, 5d
    ローカルでテスト               :p3, after p2, 3d
    section 実行
    Azure（開発）にデプロイ        :e1, after p3, 2d
    データ整合性検証              :e2, after e1, 2d
    パフォーマンステスト           :e3, after e2, 3d
    section カットオーバー
    最終マイグレーション           :c1, after e3, 1d
    本番検証                      :c2, after c1, 2d
```

### フェーズ 2: キューマイグレーション

```mermaid
gantt
    title フェーズ 2: キューマイグレーション
    dateFormat  YYYY-MM-DD
    section 開発
    Celery タスク実装             :d1, 2024-01-15, 5d
    Redis 統合                   :d2, after d1, 3d
    Worker コンテナ更新           :d3, after d2, 3d
    section テスト
    統合テスト                    :t1, after d3, 5d
    負荷テスト                    :t2, after t1, 3d
    section デプロイ
    Azure にデプロイ              :dep1, after t2, 2d
    監視と最適化                  :dep2, after dep1, 5d
```

### フェーズ 3: ストレージマイグレーション

```mermaid
gantt
    title フェーズ 3: ストレージマイグレーション
    dateFormat  YYYY-MM-DD
    section 開発
    Blob Storage SDK 実装         :d1, 2024-02-01, 5d
    ワークスペースサービス更新     :d2, after d1, 5d
    ライフサイクルポリシー追加     :d3, after d2, 2d
    section テスト
    大規模リポジトリでテスト       :t1, after d3, 5d
    パフォーマンス最適化          :t2, after t1, 3d
    section デプロイ
    デプロイとデータ移行           :dep1, after t2, 3d
```

### フェーズ 4: セキュリティ実装

```mermaid
gantt
    title フェーズ 4: セキュリティ実装
    dateFormat  YYYY-MM-DD
    section 開発
    Entra ID 統合                 :d1, 2024-02-15, 7d
    RBAC 実装                     :d2, after d1, 5d
    Key Vault 統合                :d3, after d2, 3d
    section テスト
    セキュリティテスト            :t1, after d3, 5d
    ペネトレーションテスト         :t2, after t1, 5d
    section デプロイ
    本番デプロイ                  :dep1, after t2, 2d
```

## Infrastructure as Code

### Bicep テンプレート構造

```
infra/
├── main.bicep                 # メインデプロイ
├── modules/
│   ├── container-apps.bicep   # Container Apps 環境
│   ├── postgresql.bicep       # PostgreSQL Flexible Server
│   ├── redis.bicep           # Azure Cache for Redis
│   ├── storage.bicep         # Blob Storage アカウント
│   ├── keyvault.bicep        # Key Vault
│   ├── frontdoor.bicep       # Front Door + WAF
│   ├── monitoring.bicep      # Application Insights
│   └── networking.bicep      # VNet + NSG
├── parameters/
│   ├── dev.bicepparam        # 開発パラメータ
│   └── prod.bicepparam       # 本番パラメータ
└── scripts/
    ├── deploy.sh             # デプロイスクリプト
    └── migrate-db.sh         # データベースマイグレーション
```

### サンプル Bicep（Container Apps）

```bicep
// modules/container-apps.bicep
param location string
param environmentName string
param apiImageTag string
param webImageTag string
param workerImageTag string

resource containerAppEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: '${environmentName}-env'
  location: location
  properties: {
    daprAIConnectionString: applicationInsights.properties.ConnectionString
    vnetConfiguration: {
      infrastructureSubnetId: subnet.id
    }
  }
}

resource apiApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: '${environmentName}-api'
  location: location
  properties: {
    managedEnvironmentId: containerAppEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        // SSE 用のタイムアウト設定
        clientRequestTimeout: 3600
      }
      secrets: [
        {
          name: 'db-connection-string'
          keyVaultUrl: 'https://${keyVault.name}.vault.azure.net/secrets/postgresql-connection-string'
          identity: managedIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: 'dursor.azurecr.io/api:${apiImageTag}'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'DATABASE_URL'
              secretRef: 'db-connection-string'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 2
        maxReplicas: 10
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '100'
              }
            }
          }
        ]
      }
    }
  }
}

resource workerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: '${environmentName}-worker'
  location: location
  properties: {
    managedEnvironmentId: containerAppEnvironment.id
    configuration: {
      // Worker は外部 ingress 不要
      secrets: [
        {
          name: 'redis-connection-string'
          keyVaultUrl: 'https://${keyVault.name}.vault.azure.net/secrets/redis-connection-string'
          identity: managedIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: 'dursor.azurecr.io/worker:${workerImageTag}'
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            {
              name: 'CELERY_BROKER_URL'
              secretRef: 'redis-connection-string'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 20
        rules: [
          {
            name: 'queue-scaling'
            custom: {
              type: 'redis'
              metadata: {
                listName: 'celery'
                listLength: '10'
              }
            }
          }
        ]
      }
    }
  }
}
```

## まとめ

本設計は、dursor の Azure デプロイにおいてスケーラブル、セキュア、かつコスト効率の良いアーキテクチャを提供します。

**主なポイント:**

1. **スケーラビリティ**: Celery ワーカーを持つオートスケーリング Container Apps が変動負荷に対応
2. **信頼性**: 自動フェイルオーバーを持つマルチ AZ PostgreSQL と Redis
3. **セキュリティ**: Entra ID 認証、Key Vault シークレット、プライベートエンドポイント
4. **オブザーバビリティ**: アラート付きの完全な Application Insights 統合
5. **コスト効率**: scale-to-zero 機能により開発コストを最小化
6. **長時間実行タスク対応**: SSE + Redis Pub/Sub により、数十分のエージェント実行でも安定した非同期通信が可能

**Container Apps は長時間実行タスクの非同期通信に適しています。** SSE と Redis Pub/Sub を組み合わせることで、Claude Code や Codex の長時間実行（5〜30分）を適切にハンドリングできます。追加の複雑性が必要な場合は、Azure SignalR Service による WebSocket 対応も選択肢となります。

マイグレーションはデータベースマイグレーションから開始し、段階的に分散コンポーネントを追加していくことで実行できます。
