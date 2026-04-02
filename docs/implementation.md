# Implementation Gap Analysis: ドキュメント計画 vs 現状実装

本ドキュメントは、`docs/` 配下の設計ドキュメントで計画された機能と、現在の実装状況とのギャップを整理したものです。

---

## 凡例

| アイコン | 意味 |
|---------|------|
| ✅ | 実装済み |
| 🔶 | 部分的に実装済み |
| ❌ | 未実装 |

---

## 1. Gen2: Decision Visibility & Governance（zloth_gen2.md / zloth_gen2_implementation_roadmap.md）

zloth の中核戦略。Phase 1〜4 の段階的な責任移譲モデル。

### P0: Phase 1 完成 — Decision Visibility の強化

| ID | タスク | 状態 | 詳細 |
|----|--------|------|------|
| P0-1 | Decision データモデル（SelectionDecision, PromotionDecision, MergeDecision） | ❌ | `decisions` テーブル、`DecisionType`/`DeciderType`/`RiskLevel` enum が未作成 |
| P0-2 | Evidence 自動収集（CI結果・差分規模・レビュー情報の構造化） | ❌ | `evidence_service.py`, `risk_service.py` が未作成 |
| P0-3 | 判断記録 API・UI（採用/却下/修正の記録） | ❌ | `routes/decisions.py` が未作成、フロントエンドの理由入力モーダルなし |
| P0-4 | 比較体験の向上（複数Run横並び差分表示） | ❌ | `RunComparisonView.tsx` が未作成 |
| P0-5 | 判断説明画面（Decision Dashboard） | ❌ | `decisions/page.tsx`, `DecisionCard.tsx`, `EvidenceDisplay.tsx` が未作成 |

### P1: Phase 2 前半 — Decision Reuse & Automation

| ID | タスク | 状態 | 詳細 |
|----|--------|------|------|
| P1-1 | 判断テンプレート機能 | ❌ | `template_service.py`, `DecisionTemplate` モデルなし |
| P1-2 | リトライ戦略の標準化（エラーパターン→対処マッピング） | ❌ | `retry_service.py` なし |
| P1-3 | 類似ケース検索（Embedding） | ❌ | `embedding_service.py`, `vector_store.py` なし |
| P1-4 | change_type 自動分類 | ❌ | `change_classifier.py` なし |

### P2: Phase 3 — Delegated Responsibility

| ID | タスク | 状態 | 詳細 |
|----|--------|------|------|
| P2-1 | ポリシー言語の設計（YAML） | ❌ | `policy_service.py` なし |
| P2-2 | ポリシー管理UI | ❌ | `PolicyEditor.tsx` なし |
| P2-3 | ポリシーに基づく自律実行ワークフロー拡張 | ❌ | `AgenticOrchestrator` にポリシー評価なし |

### P3: Phase 4 — Autonomous Development

| ID | タスク | 状態 | 詳細 |
|----|--------|------|------|
| P3-1 | 課題発見エージェント | ❌ | R&Dフェーズ、未着手 |

---

## 2. スケーラビリティ（scalability_issues.md）

| ID | タスク | 状態 | 詳細 |
|----|--------|------|------|
| S-P0-1 | 抽象キューIF + Redis実装 | ❌ | `QueueBackend` IF未定義。現状 SQLite ポーリング型のみ |
| S-P0-2 | PostgreSQL対応 | ❌ | SQLite のみ。`asyncpg`, Alembic 未導入 |
| S-P0-3 | 冪等性の導入 | ❌ | `create_runs()` に冪等キーなし |
| S-P0-4 | 観測可能性の整備（Prometheus, structlog, OpenTelemetry） | ❌ | `prometheus-client` 未導入、構造化ログなし |
| S-P1-1 | ワークスペース最適化（ベアミラー + `--reference`） | ❌ | 毎回 `git clone --depth=1` |
| S-P1-2 | API と Worker の分離 | ❌ | 同一プロセスで起動 |
| S-P1-3 | 外部APIレート制限・リトライ（tenacity, セマフォ） | ❌ | プロバイダー別制限なし |
| S-P1-4 | LLM出力キャッシュ | ❌ | キャッシュ機構なし |
| S-P2-1 | 実行環境のコンテナ隔離 | ❌ | サブプロセス直接実行 |
| S-P2-2 | リアルタイム配信方式の確定 | 🔶 | SSE ストリーミング実装済みだが、スケール設計未確定 |
| S-P2-3 | バックプレッシャ / サーキットブレーカ | ❌ | 未実装 |
| S-P3-1 | CI を Webhook 駆動へ | 🔶 | Webhook エンドポイントあり、だがポーリングが主 |
| S-P3-2 | マルチテナント / クォータ | ❌ | シングルユーザー前提 |

---

## 3. UI/UX 改善（ui-ux-improvement.md / ui-ux-improvement-v2.md）

### v1: 基盤的な改善

| タスク | 状態 | 詳細 |
|--------|------|------|
| モバイルレスポンシブ対応 | 🔶 | 一部のみ対応、完全なレスポンシブではない |
| コンポーネント一貫性（ボタン、フォーム、スペーシング） | 🔶 | `components/ui/` に共通パーツあり、一貫性に課題 |
| Skeleton ローダー | ✅ | 実装済み |
| Toast 通知 | ✅ | 実装済み |
| アクセシビリティ（コントラスト、キーボードナビ） | 🔶 | `LiveAnnouncer` 等あるが網羅的ではない |

### v2: ユーザー中心の改善

| タスク | 状態 | 詳細 |
|--------|------|------|
| オンボーディング（初回設定ガイダンス） | ❌ | ウィザード/ガイドなし |
| 情報階層の整理 | 🔶 | ページ構造あるが情報設計は最適化されていない |
| マルチモデル比較体験 | ❌ | 横並び比較UI なし（Gen2 P0-4 と関連） |
| エラー復旧パスの明確化 | 🔶 | エラー表示はあるが復旧導線が弱い |
| 認知負荷の軽減（選択肢の最適化） | 🔶 | デフォルト設定あるが推奨表示が不足 |

---

## 4. AI Role リファクタリング（refactoring-ai-role.md）

| タスク | 状態 | 詳細 |
|--------|------|------|
| 共通 `BaseRoleService` 基底クラス | ✅ | `BaseRoleService` 実装済み、Run/Review/Breakdown が継承 |
| `RoleExecutionStatus` 共通ステータス | ✅ | enum 実装済み |
| `RoleResultCard` 共通コンポーネント | ✅ | フロントエンド実装済み |
| `OutputManager` 共通ログストリーミング | ✅ | 実装済み |
| 新 Role の追加容易性 | ✅ | 共通インターフェースで拡張可能 |

---

## 5. 開発メトリクス（dev-metrics.md）

| タスク | 状態 | 詳細 |
|--------|------|------|
| North Star（週あたりマージPR数） | ✅ | `MetricsService` で算出 |
| Core KPI（Merge Rate, Cycle Time, Run Success Rate 等） | ✅ | 実装済み |
| Diagnostic KPI（CI Success Rate, Avg Run Duration 等） | ✅ | 実装済み |
| メトリクスダッシュボード UI | ✅ | `metrics/page.tsx` 実装済み |
| リアルタイムメトリクス | ✅ | `/metrics/realtime` エンドポイントあり |
| トレンド表示 | ✅ | `/metrics/trends` エンドポイントあり |

---

## 6. ユーザープロンプト分析（user_prompt_analysis.md）

| タスク | 状態 | 詳細 |
|--------|------|------|
| プロンプト品質分析 | ✅ | `AnalysisService` 実装済み |
| エグゼキューター成功率分析 | ✅ | `/analysis` エンドポイントあり |
| エラーパターン検出 | ✅ | 実装済み |
| レコメンデーション | ✅ | `/analysis/recommendations` エンドポイントあり |

---

## 7. Agentic 実行 / コーディングモード（coding-mode.md / agentic-dursor.md）

| タスク | 状態 | 詳細 |
|--------|------|------|
| Interactive モード | ✅ | 手動実行フロー |
| Semi-Auto モード | ✅ | `AgenticOrchestrator` で実装 |
| Full-Auto モード | ✅ | イテレーション制限付きで実装 |
| フェーズ管理（coding → CI → review → merge） | ✅ | `AgenticPhase` enum + オーケストレータ |
| CI 失敗時の自動修正 | ✅ | `fixing_ci` フェーズ |
| レビュー指摘の自動修正 | ✅ | `fixing_review` フェーズ |
| マージゲート | ✅ | `MergeGateService` 実装済み |
| 人間承認の待機 | ✅ | `awaiting_human` フェーズ |

---

## 8. CI 連携 / Gating（ci_check.md / gating_status.md / check_ci_behavior.md）

| タスク | 状態 | 詳細 |
|--------|------|------|
| CI ステータスポーリング | ✅ | `CIPollingService` 実装済み |
| CI チェック結果の保存・表示 | ✅ | `ci_checks` テーブル + UI |
| Gating ステータス（CI + Review 複合条件） | ✅ | `MergeGateService` で条件チェック |
| GitHub Webhook 受信 | ✅ | `/webhooks/github` エンドポイント |
| CI 失敗時の Kanban ステータス反映 | ✅ | Kanban の動的ステータス算出で反映 |

---

## 9. Kanban ボード（kanban.md）

| タスク | 状態 | 詳細 |
|--------|------|------|
| ハイブリッドステータス管理（手動 + 動的算出） | ✅ | `KanbanService` 実装済み |
| カラム: backlog / todo / in_progress / in_review / gating / done / archived | ✅ | 全ステータス実装済み |
| タスク移動（backlog ↔ todo, archive/unarchive） | ✅ | API + UI 実装済み |
| リポジトリフィルタリング | ✅ | `/kanban/repos` + UI フィルタ |

---

## 10. コードレビュー（review.md）

| タスク | 状態 | 詳細 |
|--------|------|------|
| AI レビュー実行 | ✅ | `ReviewService` 実装済み |
| フィードバック分類（severity × category） | ✅ | `ReviewSeverity`, `ReviewCategory` enum |
| 修正指示の自動生成 | ✅ | `/reviews/{id}/generate-fix` |
| レビュー結果のチャット反映 | ✅ | `/reviews/{id}/to-message` |

---

## 11. タスク分解（task-split.md / task-split-v2.md）

| タスク | 状態 | 詳細 |
|--------|------|------|
| AI によるタスク分解 | ✅ | `BreakdownService` 実装済み |
| Backlog 管理（v2 で追加） | ✅ | `backlog_items` テーブル + CRUD API |
| サブタスクからのタスク一括作成 | ✅ | `POST /tasks/bulk` |

---

## 12. マルチツール並列実行（ai-coding-tool-multiple.md）

| タスク | 状態 | 詳細 |
|--------|------|------|
| 複数 ExecutorType の並列実行 | ✅ | `ExecutorType` 配列で複数選択可 |
| Claude Code / Codex / Gemini CLI 対応 | ✅ | 各 Executor 実装済み |
| PatchAgent（LLM API 直接呼び出し） | ✅ | 実装済み |

---

## 未実装サマリー（実装が必要な項目一覧）

### 最優先（Gen2 P0）— Decision Visibility の完成

> Phase 1 を完成させ、Trust Ladder L2 を達成するために必須。

| # | タスク | 新規ファイル | 工数 |
|---|--------|-------------|------|
| 1 | Decision データモデル + DB スキーマ | `schema.sql` 追記, `models.py` 追記, `enums.py` 追記, `dao.py` 追記 | 中 |
| 2 | Evidence 自動収集サービス | `services/evidence_service.py`, `services/risk_service.py` | 中 |
| 3 | 判断記録 API | `routes/decisions.py` | 中 |
| 4 | 判断記録 UI（理由入力モーダル等） | フロントエンド複数コンポーネント | 大 |
| 5 | Run 比較ビュー | `components/RunComparisonView.tsx` | 中 |
| 6 | Decision Dashboard | `app/tasks/[taskId]/decisions/page.tsx`, `DecisionCard.tsx`, `EvidenceDisplay.tsx` | 大 |

### 高優先（Gen2 P1）— Decision Reuse

| # | タスク | 新規ファイル | 工数 |
|---|--------|-------------|------|
| 7 | 判断テンプレート機能 | `services/template_service.py`, `TemplateManager.tsx` | 大 |
| 8 | リトライ戦略の標準化 | `services/retry_service.py` | 中 |
| 9 | 類似ケース検索（Embedding） | `services/embedding_service.py`, `storage/vector_store.py` | 大 |
| 10 | change_type 自動分類 | `services/change_classifier.py` | 小 |

### 高優先（スケーラビリティ P0）

| # | タスク | 新規ファイル | 工数 |
|---|--------|-------------|------|
| 11 | 抽象キュー IF + Redis 実装 | `services/queue_backend.py`, `services/redis_queue.py` | 中 |
| 12 | 冪等性の導入 | `storage/idempotency_dao.py` | 小 |
| 13 | 観測可能性（Prometheus メトリクス, structlog） | `services/observability.py` | 中 |
| 14 | PostgreSQL 対応 | `storage/db.py` 改修, Alembic 導入 | 中 |

### 中優先（Gen2 P2 / スケーラビリティ P1）

| # | タスク | 工数 |
|---|--------|------|
| 15 | ポリシー言語設計 + サービス | 大 |
| 16 | ポリシー管理 UI | 大 |
| 17 | ポリシーベース自律実行拡張 | 中 |
| 18 | ワークスペース最適化（ベアミラー） | 中 |
| 19 | API / Worker 分離 | 小 |
| 20 | 外部 API レート制限 / リトライ | 小 |
| 21 | LLM 出力キャッシュ | 中 |

### 低優先（UI/UX / スケーラビリティ P2-P3）

| # | タスク | 工数 |
|---|--------|------|
| 22 | オンボーディングウィザード | 中 |
| 23 | モバイルレスポンシブ完全対応 | 中 |
| 24 | 実行環境コンテナ隔離 | 高 |
| 25 | マルチテナント / クォータ | 高 |
| 26 | 課題発見エージェント（R&D） | 研究 |

---

## 実装済み機能の完成度

```
██████████████████████████████████░░░░░░░░░░  ~75% (基盤機能)
```

**実装済み（21項目）**: リポジトリ管理, タスク管理, 並列実行, PR管理, コードレビュー, Agentic実行, CI連携, Kanban, メトリクス, 分析, タスク分解, Backlog, マルチツール, AI Role共通化, マージゲート, Webhook, ストリーミングログ, 設定管理, 暗号化, Git操作, ブランチ/Worktree管理

**未実装（26項目）**: 上記テーブル参照。Gen2 の判断記録・ガバナンス基盤とスケーラビリティインフラが主な残課題。
