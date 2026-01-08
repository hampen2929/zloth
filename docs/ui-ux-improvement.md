# UI/UX 改善提案（dursor）

対象: Webフロントエンド（apps/web）／日付: 2026-01-08

本ドキュメントは、実リポジトリのコードを確認した上で、dursor のUI/UX改善点を優先度付きで整理したものです。短期での不具合修正から、中期的な体験向上・運用改善までを包括します。

## 概要

良い点（現状）
- レスポンシブ対応（モバイル: タブ切替、サイドバー: オーバーレイ表示）。
- 共有UI（`Button`/`Input`/`Modal`/`Toast`/`Skeleton`/`ConfirmDialog`）が整備され、フォーカスリングやARIA属性など基礎的なアクセシビリティ配慮あり。
- ローディング、空状態、エラー表示が各所にあり、ユーザーフィードバックが明確。
- 設定モーダルのフォーカストラップ・Escapeクローズ、チャット/実行/PR作成の主要フローが一本化。

主な課題（要対応）
- 一部Tailwindクラスの誤記、キーボード操作未対応のドロップダウン、色コントラストのばらつき。
- Diff表示の可読性/パフォーマンス（大規模パッチ時）と、実行状況の更新方式（ポーリング依存）。
- ページ単位で共有コンポーネント未適用箇所が残り、UIの一貫性が崩れる部分がある。

---

## 優先度付き改善リスト

### P0（即時修正／不具合）

1) Tailwindクラス誤記の修正
- 影響: ホバー時の視覚フィードバックが機能しない。
- 対象: `apps/web/src/components/RunsPanel.tsx`（`hover:bg-gray-750` は存在しない）
- 対応: `hover:bg-gray-700` に修正。

2) ドロップダウンのキーボード操作対応（Listboxパターン）
- 影響: キーボードのみのユーザーがモデル/リポジトリ/ブランチ選択を操作できない。
- 対象: `apps/web/src/app/page.tsx`（モデル/リポジトリ/ブランチ各ドロップダウン）、`apps/web/src/components/SettingsModal.tsx`（モデル追加フォームの`select`）。
- 対応: `role="listbox"/role="option"`、`aria-activedescendant`、上下矢印/Enter/Escapeのハンドリング、初期フォーカス移動、Tab/Shift+Tabの流れを実装。

3) 色コントラストの標準化（WCAG 2.1 AA）
- 影響: 小サイズテキストの可読性が画面によりばらつく。
- 対象: `text-gray-500` など補助文言の多用箇所。
- 対応: 本文: `text-gray-300`、補助: `text-gray-400` を原則に統一。既存の設計トークン（`apps/web/src/lib/design-tokens.ts`）に揃える。

4) 共有UIコンポーネント未適用箇所の是正（Home）
- 影響: ページごとにボタン/入力の見た目・フォーカス挙動が揺れる。
- 対象: `apps/web/src/app/page.tsx` の送信ボタン/入力類。
- 対応: `Button`/`Textarea` を使用して統一し、`title` だけでなく `aria-describedby` 等も活用。

### P1（体験の質を大きく底上げ）

5) DiffViewer の可読性・性能強化
- 課題: 全行描画で大規模パッチが重い。行番号/シンタックスハイライトなし。
- 対応: 行仮想化（例: `react-virtuoso`）、行番号/左右カラム/ハイライト追加、ファイル折り畳み・目次・ファイル間ナビゲーション、コピー操作の追加。
- 対象: `apps/web/src/components/DiffViewer.tsx`

6) 実行状態更新のリアルタイム化
- 課題: SWRの`refreshInterval`に依存し更新遅延・負荷がある。
- 対応: SSE/WebSocketでラン状態/ログ/パッチのプッシュ配信。非表示タブでは購読停止、復帰時に再同期。

7) 動きの低減（アクセシビリティ）
- 対応: `@media (prefers-reduced-motion: reduce)` を `apps/web/src/app/globals.css` に追加し、アニメーション/トランジションを低減。

8) UI状態の永続化/ディープリンク
- 対応: 選択モデル、直近のリポジトリ/ブランチ、タスク詳細のアクティブタブ等を `localStorage` とURLクエリで復元。

9) line-clamp の安定化
- 課題: コード内で `line-clamp-2` を使用（`RunsPanel`）しているが、Tailwind設定にプラグイン未登録。
- 対応: `@tailwindcss/line-clamp` を導入、もしくはCSSでの2行省略スタイルに置換。
- 対象: `apps/web/tailwind.config.js`, `apps/web/src/components/RunsPanel.tsx`

10) ラン状態の音声出力（スクリーンリーダー通知）
- 対応: `aria-live="polite"` のライブリージョンで「完了/失敗」等を通知。トーストと併用。
- 対象: `RunDetailPanel`/`TaskPage` いずれかに実装。

### P2（操作性/理解促進の強化）

11) Runs/Tasks のフィルタ・ソート・検索
- 対応: ステータス/モデル/期間などで絞り込み、結果リストは仮想化。
- 対象: `apps/web/src/components/RunsPanel.tsx`、サイドバーのタスクリスト。

12) キーボードショートカットのヘルプ
- 対応: `?` で開くヘルプモーダル。`Cmd/Ctrl+Enter` 等を一覧表示し学習コストを低減。

13) エラーバウンダリ
- 対応: パネル単位でエラーバウンダリを導入し、予期せぬ例外時でもアプリ全体を保護。

14) コピー操作の明示
- 対応: PR URL/ログ/パッチにコピーアイコンを付与し、トーストで結果通知。

### P3（テーマ/ビジュアルの拡張・運用）

15) ライトテーマ追加とトグル
- 対応: 設計トークンをCSS変数化し、テーマ切替を容易に。ユーザー設定保持。

16) ビジュアルリグレッション/アクセシビリティ自動検査
- 対応: Chromatic/Percy と axe-core のCI導入で退行検知を自動化。

17) パフォーマンス予算とLighthouse計測の運用
- 対応: Web Vitals/Lighthouse目標を設定し、PRごとに計測・アラート連携。

---

## 実装ガイド（要所の変更方針）

- 誤記修正（P0）
  - `apps/web/src/components/RunsPanel.tsx` の `hover:bg-gray-750` → `hover:bg-gray-700`

- キーボード操作対応（P0）
  - ドロップダウンを Listboxパターンに統一（`role`/`aria-*`/`onKeyDown` を追加）。
  - フォーカス管理（開時に最初の項目へ、Escで閉じ、Tab移動の自然化）。

- コントラスト標準化（P0）
  - 小サイズ本文: `text-gray-300`、補助: `text-gray-400` を原則化。設計トークンに合わせる。

- Homeの共有UI適用（P0）
  - 送信ボタン/入力域を `Button`/`Textarea` に置換。ローディング/無効/フォーカス状態を統一。

- DiffViewer強化（P1）
  - 仮想化・行番号・ハイライト・ファイル折り畳み・目次・コピーなどを追加。

- プッシュ更新（P1）
  - クライアントにSSE/WebSocketクライアントを追加し、SWRの `mutate` と連携。非表示時は購読停止。

- 動きの低減（P1）
  - `globals.css` に `prefers-reduced-motion` を追加し、`.animate-in` を低減/無効化。

- i18n 導入準備（P1→P2）
  - 文言キー化と辞書分離（例: `next-intl`）。`<html lang>` をユーザー設定やブラウザに同期。

- line-clamp 安定化（P1）
  - Tailwindプラグイン追加 or CSS代替（`display: -webkit-box; -webkit-line-clamp: 2;`）。

---

## 監査エビデンス（抜粋）

- レスポンシブ/スケルトン: `apps/web/src/app/tasks/[taskId]/page.tsx`
- 共有UI: `apps/web/src/components/ui/`（Button/Input/Modal/Toast/Skeleton/ConfirmDialog）
- 誤記クラス: `apps/web/src/components/RunsPanel.tsx:134`（`hover:bg-gray-750`）
- 設計トークン: `apps/web/src/lib/design-tokens.ts`
- Tailwind設定: `apps/web/tailwind.config.js`（プラグイン未登録）

---

## 成功指標（例）

- Accessibility（Lighthouse）: 90点以上。
- キーボードのみ操作での主要フロー完遂率: 100%。
- 大型パッチ（>5,000行）でもDiff描画の体感スムーズさ確保（仮想化でフレーム落ち低減）。
- エラー回復性: パネル単位の例外でアプリ継続（エラーバウンダリ導入）。

---

## 付録: 主な関連ファイル

- `apps/web/src/app/page.tsx`
- `apps/web/src/app/tasks/[taskId]/page.tsx`
- `apps/web/src/components/ChatPanel.tsx`
- `apps/web/src/components/RunsPanel.tsx`
- `apps/web/src/components/RunDetailPanel.tsx`
- `apps/web/src/components/Sidebar.tsx`
- `apps/web/src/components/SettingsModal.tsx`
- `apps/web/src/components/ui/*`
- `apps/web/src/components/DiffViewer.tsx`
- `apps/web/src/lib/design-tokens.ts`
- `apps/web/src/app/globals.css`

