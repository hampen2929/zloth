# アーキテクチャレビュー: 問題点と改善提案

このドキュメントは、`docs/architecture.md` および実装コードの分析に基づいて、現状のアーキテクチャの問題点を洗い出し、改善点を優先度付きで提示します。

## 前提条件

- **ローカルホスト運用**: 単一マシンでの実行を想定
- **シングルユーザー**: 認証・認可は現時点で不要
- **セルフホスト**: ユーザーが自身の環境で運用

## 分析対象

- `docs/architecture.md` - アーキテクチャ設計書
- `apps/api/src/zloth_api/` - バックエンド実装

---

## 問題点一覧

### 🔴 高優先度（Critical）

#### 1. サービス層の肥大化（God Class 問題）

**現状**: `RunService` が 1360行以上

```
run_service.py: 1360+ lines
- create_runs
- _create_cli_run
- _execute_cli_run
- _execute_patch_agent_run
- ワークスペース管理
- Git操作
- コミットメッセージ生成
- 差分解析
...
```

**問題点**:
- 単一責任原則（SRP）違反
- テストが困難
- 変更の影響範囲が広い
- 依存関係が複雑（13以上のコンストラクタ引数）

**改善案**:
1. **責務の分離**:
   - `RunExecutionService` - 実行ロジック
   - `WorkspaceManager` - ワークスペース管理
   - `DiffParser` - 差分解析
   - `CommitService` - コミット・プッシュ
2. **Facade パターン**の導入

---

### 🟡 中優先度（Important）

#### 2. DAO層の重複コード

**現状**: 各DAOに類似した `_row_to_model` メソッドが存在

```python
# 各DAOに同様のパターン
def _row_to_model(self, row: Any) -> Model:
    return Model(
        id=row["id"],
        field1=row["field1"],
        ...
    )
```

**問題点**:
- DRY原則違反
- SQLiteの `row` 型に依存した脆弱なコード
- 新規フィールド追加時の修正漏れリスク

**改善案**:
1. **Generic DAO パターン**の導入
2. Pydantic の `model_validate` を活用
3. ORM (SQLAlchemy + async) の検討（将来的に）

---

#### 3. エラーハンドリングの非一貫性

**現状**: 例外処理パターンが統一されていない

```python
# パターン1: ValueError
if not task:
    raise ValueError(f"Task not found: {task_id}")

# パターン2: None返却
async def get(self, id: str) -> Run | None:
    ...
    return None

# パターン3: ログのみ
except Exception as e:
    logger.warning(f"Failed: {e}")
```

**問題点**:
- API呼び出し元でのエラーハンドリングが困難
- 一貫した HTTP ステータスコード返却が難しい

**改善案**:
1. **カスタム例外階層**の定義
```python
class ZlothError(Exception): ...
class NotFoundError(ZlothError): ...
class ValidationError(ZlothError): ...
class ExecutionError(ZlothError): ...
```
2. FastAPI の例外ハンドラーで統一処理

---

#### 4. 設定管理の二重化

**現状**: 環境変数とDBの両方で設定を管理

```python
# config.py - 環境変数
settings.worktrees_dir

# user_preferences テーブル - DB
prefs.worktrees_dir
```

**問題点**:
- どちらが優先されるか不明瞭
- 設定変更のための再起動要否が不明
- テスト時のモック化が複雑

**改善案**:
1. **設定の優先順位を明文化**:
   - 環境変数 > DB設定 > デフォルト値
2. 設定の種類を分類:
   - システム設定 → 環境変数のみ
   - ユーザー設定 → DBのみ

---

### 🟢 低優先度（Nice to Have）

#### 5. ドキュメントと実装の乖離

**現状**: `CLAUDE.md` と `architecture.md` で内容が異なる

| 項目 | CLAUDE.md | architecture.md |
|------|-----------|-----------------|
| ロードマップ | Review/Meta agent: 未完了 | Review統合: 完了 ✓ |
| ディレクトリ構造 | 古い構造（executors/, roles/ 未記載） | 新しい構造 |
| サービス一覧 | 基本的なもののみ | 詳細リスト |

**改善案**:
1. `CLAUDE.md` を Single Source of Truth (SSOT) として統一
2. `architecture.md` は詳細設計ドキュメントとして位置づけ

---

#### 6. ロギングの標準化不足

**現状**:
```python
# 異なるフォーマット
logger.info(f"[{run.id[:8]}] Starting run")
logger.warning(f"Push failed: {error}")
await self._log_output(run_id, "Starting execution...")
```

**改善案**:
1. 構造化ロギング（JSON形式）の導入
2. トレース ID の一貫した付与
3. ログレベルガイドラインの策定

---

#### 7. テストカバレッジの可視性

**現状**: テストカバレッジが不明

**改善案**:
1. `pytest-cov` による カバレッジ計測
2. CI での最低カバレッジ閾値設定（例: 80%）
3. カバレッジレポートの PR コメント自動投稿

---

## 改善ロードマップ（推奨順序）

```mermaid
gantt
    title アーキテクチャ改善ロードマップ
    dateFormat YYYY-MM
    section フェーズ1（保守性向上）
    RunService 分割       :crit, p1-1, 2026-02, 3w
    カスタム例外階層      :p1-2, after p1-1, 2w
    section フェーズ2（信頼性向上）
    DAO リファクタリング  :p2-1, after p1-2, 2w
    設定管理整理          :p2-2, after p2-1, 1w
    section フェーズ3（品質向上）
    ドキュメント整備      :p3-1, after p2-2, 1w
    ロギング標準化        :p3-2, after p3-1, 1w
    テストカバレッジ向上  :p3-3, after p3-2, 2w
```

---

## 優先度サマリー

| 優先度 | # | 問題 | 影響 | 工数見積 |
|--------|---|------|------|----------|
| 🔴 高 | 1 | RunService肥大化 | 保守性・テスト困難 | 中 |
| 🟡 中 | 2 | DAO重複コード | 保守性 | 小 |
| 🟡 中 | 3 | エラーハンドリング | 信頼性 | 小 |
| 🟡 中 | 4 | 設定管理二重化 | 運用性 | 小 |
| 🟢 低 | 5 | ドキュメント乖離 | 開発効率 | 小 |
| 🟢 低 | 6 | ロギング標準化 | 運用性 | 小 |
| 🟢 低 | 7 | テストカバレッジ | 品質 | 中 |

---

## 付録: アーキテクチャ品質属性評価

| 品質属性 | 現状スコア | 目標スコア | 備考 |
|----------|------------|------------|------|
| **可用性** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | SQLiteバックドジョブキューで改善済み |
| **保守性** | ⭐⭐ | ⭐⭐⭐⭐ | リファクタリングで改善 |
| **拡張性** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | プラグイン構造は良好 |
| **テスト容易性** | ⭐⭐ | ⭐⭐⭐⭐ | DI改善・責務分離で対応 |
| **シンプルさ** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Clone モード統一で改善済み |

---

## 将来検討事項（マルチユーザー対応時）

以下はシングルユーザー前提では不要だが、将来的に検討が必要な項目:

- **認証・認可**: JWT/OAuth2.0, RBAC
- **データベース移行**: PostgreSQL への移行
- **分散キュー**: Redis + Celery
- **水平スケーリング**: 複数サーバー対応
