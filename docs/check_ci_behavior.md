# Check CI 挙動調査メモ

## 目的 / 期待される挙動（ユーザー要件）
- PR が作成されていない場合は `Check CI` を実行しない
- PR が作成済みの場合は Implementation 実行後に `Check CI` を実行
- PR の CI が実行になったら Task の `Check CI` もそれを追従して実行する
- Task に紐づく実行中の `Check CI` は 1 つ
- `Pending` が長時間継続しない
- `Check CI` 更新ごとに強制スクロールしない
- 同一 SHA の `Check CI` は新規作成ではなく更新する

## 現状の実装フロー（主要箇所）

### Backend
- **手動 Check CI**
  - `POST /tasks/{task_id}/prs/{pr_id}/check-ci` → `CICheckService.check_ci`
  - 参照: `apps/api/src/zloth_api/routes/prs.py`, `services/ci_check_service.py`
- **自動 Check CI（gating 有効時のみ）**
  - PR 作成 / 更新 / 手動同期時に `_trigger_ci_check_if_enabled` が実行
  - `enable_gating_status` が OFF の場合は動かない
  - 参照: `apps/api/src/zloth_api/routes/prs.py`
- **CI 状態取得**
  - `CICheckService.check_ci` が GitHub API を叩き、`ci_checks` を作成/更新
  - 重複抑止は「PR+SHA の既存レコード探索 + in-memory cooldown」
  - 参照: `apps/api/src/zloth_api/services/ci_check_service.py`
- **Agentic の CI ポーリング**
  - `CIPollingService` は Agentic の状態遷移のみ更新（`ci_checks` 未更新）
  - 参照: `apps/api/src/zloth_api/services/ci_polling_service.py`,
    `services/agentic_orchestrator.py`
- **Metrics の Pending CI**
  - `ci_checks` の `status='pending'` を単純集計
  - 参照: `apps/api/src/zloth_api/storage/dao.py#get_realtime_metrics`

### Frontend
- **CI チェック表示**
  - `ciChecksApi.list()` で Task 全体の `ci_checks` を取得
  - 参照: `apps/web/src/components/ChatCodeView.tsx`
- **Pending の自動チェック**
  - `pending` を検知すると 1 回だけ `check-ci` を叩く（再ポーリングしない）
  - `lastTriggeredCICheckRef` が同一 SHA の再実行を抑止
- **自動スクロール**
  - `messages / runs / reviews` 変化で常に `scrollIntoView`
  - 参照: `apps/web/src/components/ChatCodeView.tsx`

## 問題点（観測された不安定さの原因候補）

1. **Implementation 後の自動 Check CI が必ず走らない**
   - 自動 Check CI は `enable_gating_status` が ON の場合のみ
   - PR 作成/更新タイミングに依存し、Run 完了そのものには反応しない
   - `runs` が実行中の場合は `defer` されるが再実行の仕組みが無い
   - 参照: `routes/prs.py::_trigger_ci_check_if_enabled`

2. **Pending の追従が「1 回だけ」で止まりやすい**
   - Frontend の pending 自動チェックは 1 回実行後に抑止される
   - CI がまだ始まっていない / 終了していない場合、そのまま Pending が残りやすい
   - 参照: `ChatCodeView.tsx` の `lastTriggeredCICheckRef`

3. **`ci_checks` の重複・並行実行が起きやすい**
   - DB に一意制約が無く、同一 PR+SHA の並行 `check_ci` で複数行が作られる可能性
   - cooldown が in-memory のためマルチプロセス/多台構成で抑止が効かない
   - 参照: `CICheckService` / `CICheckDAO`

4. **Pending が Metrics に累積しやすい**
   - `pending_ci_checks` は `ci_checks` の全 pending を単純カウント
   - 古い pending が残ると「稼働中タスク数」以上に膨らむ
   - 参照: `MetricsDAO.get_realtime_metrics`

5. **Task の `latest_ci_status` が古い/誤った状態になり得る**
   - 集計は `created_at` の最新を参照（更新の競合や重複があるとズレる）
   - 参照: `TaskDAO.list_with_aggregates` 内サブクエリ

6. **Check CI 更新で強制スクロールされやすい**
   - `runs` のポーリング更新（2s）だけで `scrollIntoView` が発火
   - CI 更新時に画面が動いたように感じやすい
   - 参照: `ChatCodeView.tsx` の auto-scroll

7. **PR の CI と Task の CI 記録が連動していない**
   - Webhook / Polling は agentic 状態のみ更新し `ci_checks` を更新しない
   - 参照: `routes/webhooks.py`, `CIPollingService`

## 解決に向けた計画（段階案）

### 1) トリガーの統一と再試行
- **Run 完了時に PR が存在すれば自動 Check CI を起動**
  - `RunService` 成功時に PR を検出して `check_ci` を起動
  - `enable_gating_status` とは別の「auto_ci_check」設定に切り分け検討
- **実行中で defer した CI の再実行キュー**
  - `runs` 完了イベントで遅延トリガーを再評価

### 2) CI 追従の実装（サーバ側）
- **pending の間はサーバ側でポーリング**
  - `ci_checks` に `next_check_at` 等を持たせ定期ジョブで更新
  - 一定時間で `timed_out` / `error` に遷移
- **GitHub Webhook 連携**
  - `workflow_run` / `check_run` のイベントで `ci_checks` を更新
  - `/webhooks/ci` も `ci_checks` 更新に対応

### 3) 重複防止と「1 つだけ」の保証
- **DB に一意制約 or upsert**
  - `(pr_id, sha)` を一意にし `INSERT ... ON CONFLICT DO UPDATE`
  - `sha` 未確定時は `pending_sha` を持つなど一意化方針を明確化
- **古い pending を `superseded` へ遷移**
  - 新しい SHA を検出したら古い pending を無効化

### 4) Metrics と UI の整合
- **pending 計上の基準を「最新・有効な CI のみ」に限定**
  - `is_latest` フラグ、もしくは `updated_at` の最新 1 件だけ集計
- **UI の自動チェックは “継続ポーリング” か “サーバ追従” に統一**
  - `hasPendingCIChecks` は「現在の PR の pending のみ」に限定

### 5) スクロール制御の改善
- **ユーザーが下端付近の時のみ auto-scroll**
  - `isAtBottom` 判定を追加し、CI 更新ではスクロールしない
- **`runs` 更新によるスクロール抑制**
  - 新規メッセージ/新規 run 完了時のみスクロールするよう条件化

## まとめ
現在は「PR 作成/更新時に 1 回だけ Check CI」が主流で、
その後の CI 進行に追従する仕組みが薄く、Pending が残留しやすい。
トリガーの統一・サーバ側追従・重複排除・スクロール制御の改善が必要。
