# SQLite vs PostgreSQL 比較

zlothプロジェクトにおけるSQLiteとPostgreSQLの比較分析。

## 概要比較表

| 観点 | SQLite | PostgreSQL |
|------|--------|------------|
| **アーキテクチャ** | 組み込み型（単一ファイル） | クライアント/サーバー型 |
| **同時接続** | 制限あり（書き込みロック） | 高い同時接続性 |
| **スケーラビリティ** | 垂直のみ | 水平・垂直両対応 |
| **運用コスト** | ゼロ（依存なし） | 中〜高（サーバー管理必要） |
| **セットアップ** | 不要 | 必要 |
| **バックアップ** | ファイルコピー | pg_dump / レプリケーション |
| **データサイズ上限** | 〜140TB（実用は数GB） | 無制限（TB級対応） |

---

## 詳細比較

### 1. パフォーマンス

#### SQLite

```
✅ 読み取り性能：単一接続では非常に高速
✅ レイテンシ：ネットワーク遅延なし（ローカルファイル）
❌ 書き込み：データベース全体のロック（WALモードでも制限あり）
❌ 同時書き込み：サポートなし
```

**zlothでの影響**:
- 単一Workerでの実行は問題なし
- 複数Workerの並列実行時にボトルネック発生

#### PostgreSQL

```
✅ 読み取り性能：高速（インデックス最適化、パラレルクエリ）
✅ 書き込み：行レベルロック（高い同時実行性）
✅ 同時接続：数千接続対応
⚠️ レイテンシ：ネットワーク遅延あり（ローカルでは最小）
```

**zlothでの影響**:
- 複数API Server、複数Workerの同時アクセスに対応
- Run実行のステータス更新が競合しない

### 2. 同時実行性

```mermaid
flowchart LR
    subgraph SQLite["SQLite"]
        direction TB
        W1_S[Worker 1] -->|書き込み| DB_S[(DB)]
        W2_S[Worker 2] -.->|待機| DB_S
        W3_S[Worker 3] -.->|待機| DB_S
    end

    subgraph PostgreSQL["PostgreSQL"]
        direction TB
        W1_P[Worker 1] -->|書き込み| DB_P[(DB)]
        W2_P[Worker 2] -->|書き込み| DB_P
        W3_P[Worker 3] -->|書き込み| DB_P
    end
```

| シナリオ | SQLite | PostgreSQL |
|---------|--------|------------|
| 単一Worker | ✅ 最適 | ✅ 良好 |
| 2-3 Worker | ⚠️ 競合あり | ✅ 良好 |
| 4+ Worker | ❌ ボトルネック | ✅ 良好 |
| 複数API Server | ❌ 非推奨 | ✅ 最適 |

### 3. 機能比較

| 機能 | SQLite | PostgreSQL |
|------|--------|------------|
| ACID準拠 | ✅ | ✅ |
| JSON型 | ✅（基本） | ✅（高度なクエリ対応） |
| 全文検索 | ✅（FTS5） | ✅（GIN/GiST） |
| 配列型 | ❌ | ✅ |
| ENUM型 | ❌ | ✅ |
| パーティショニング | ❌ | ✅ |
| レプリケーション | ❌ | ✅ |
| ポイントインタイムリカバリ | ❌ | ✅ |
| 拡張機能 | 限定的 | 豊富（PostGIS等） |

### 4. 運用面

#### SQLite

| 項目 | 評価 |
|------|------|
| バックアップ | 🟢 ファイルコピーのみ |
| 監視 | 🟡 ファイルサイズのみ |
| マイグレーション | 🟢 シンプル |
| 障害復旧 | 🟡 ファイル復元 |
| スケールアップ | 🔴 限界あり |

#### PostgreSQL

| 項目 | 評価 |
|------|------|
| バックアップ | 🟢 多様な選択肢 |
| 監視 | 🟢 豊富なメトリクス |
| マイグレーション | 🟡 複雑だが柔軟 |
| 障害復旧 | 🟢 PITR対応 |
| スケールアップ | 🟢 レプリカ追加可能 |

### 5. コスト比較

#### 初期コスト

| 項目 | SQLite | PostgreSQL |
|------|--------|------------|
| ソフトウェア | 無料 | 無料 |
| セットアップ工数 | 0時間 | 2-4時間 |
| インフラ | 不要 | サーバー必要 |

#### 運用コスト（月額目安）

| 環境 | SQLite | PostgreSQL（セルフホスト） | PostgreSQL（マネージド） |
|------|--------|-------------------------|------------------------|
| ローカル開発 | ¥0 | ¥0 | - |
| 小規模本番 | ¥0 | ¥3,000〜 | ¥5,000〜 |
| 中規模本番 | 非推奨 | ¥10,000〜 | ¥15,000〜 |
| Azure本番 | 非推奨 | - | ¥8,000〜（Flexible） |

---

## zlothにおける推奨構成

### ユースケース別推奨

```mermaid
flowchart TD
    Start[開始] --> Q1{利用環境は?}
    Q1 -->|ローカル開発| SQLite
    Q1 -->|本番| Q2{Worker数は?}
    Q2 -->|1台| Q3{将来スケール予定?}
    Q2 -->|2台以上| PostgreSQL
    Q3 -->|なし| SQLite
    Q3 -->|あり| PostgreSQL
```

| 環境 | 推奨DB | 理由 |
|------|--------|------|
| **ローカル開発** | SQLite | セットアップ不要、依存なし |
| **CI/テスト** | SQLite | 高速起動、分離容易 |
| **小規模本番（個人）** | SQLite | 運用コストゼロ |
| **小規模本番（チーム）** | PostgreSQL | 同時アクセス対応 |
| **Azure本番** | PostgreSQL | マネージドサービス活用 |
| **スケールアウト構成** | PostgreSQL | 必須要件 |

### zloth v2アーキテクチャとの関係

architecture-v2.mdで定義されたUI-API-Queue-Workerパターンでは:

```mermaid
flowchart TB
    subgraph Development["開発環境"]
        API_Dev[API Server] --> SQLite_Dev[(SQLite)]
        Worker_Dev[Worker] --> SQLite_Dev
    end

    subgraph Production["本番環境"]
        API1[API Server 1] --> PG[(PostgreSQL)]
        API2[API Server 2] --> PG
        W1[Worker 1] --> PG
        W2[Worker 2] --> PG
        WN[Worker N] --> PG
    end
```

**開発環境**: SQLiteで迅速に開発
**本番環境**: PostgreSQLで信頼性とスケーラビリティを確保

---

## 移行に関する考慮事項

### SQLite → PostgreSQL 移行時の変更点

| カテゴリ | 変更内容 |
|---------|---------|
| **接続設定** | `sqlite:///path` → `postgresql://user:pass@host/db` |
| **非同期ドライバ** | `aiosqlite` → `asyncpg` |
| **型の違い** | `INTEGER PRIMARY KEY` → `SERIAL` or `BIGSERIAL` |
| **日時型** | 文字列 → `TIMESTAMP WITH TIME ZONE` |
| **Boolean** | 0/1 → `TRUE`/`FALSE` |
| **自動インクリメント** | `AUTOINCREMENT` → `SERIAL` |

### 互換性を保つための設計指針

1. **DAO層の抽象化**: データアクセスをDAO経由に統一
2. **SQLAlchemy Core使用**: 方言の違いを吸収
3. **型変換の明示**: アプリケーション層で型を正規化
4. **環境変数での切り替え**: `ZLOTH_DATABASE_URL` で接続先を制御

### コード例

```python
# 現在のSQLite接続
ZLOTH_DATABASE_URL=sqlite+aiosqlite:///data/zloth.db

# PostgreSQL接続
ZLOTH_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/zloth
```

---

## まとめ

| 評価軸 | SQLite優位 | PostgreSQL優位 |
|--------|-----------|---------------|
| シンプルさ | ✅ | |
| 開発速度 | ✅ | |
| ゼロ依存 | ✅ | |
| 同時実行 | | ✅ |
| スケーラビリティ | | ✅ |
| 本番運用 | | ✅ |
| 高度な機能 | | ✅ |

**結論**: zlothでは、開発・テスト環境ではSQLiteを使用し、本番環境（特に複数WorkerやAzureデプロイ）ではPostgreSQLを使用するハイブリッドアプローチを推奨。これはarchitecture-v2.mdの移行パスと一致している。
