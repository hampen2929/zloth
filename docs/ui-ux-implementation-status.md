# UI/UX 改善 実装ステータス

このドキュメントは、UI/UX改善計画の実装状況を追跡するためのものです。

**最終更新**: 2026-01-31
**関連ドキュメント**: [UI/UX 改善 実装計画書](./ui-ux-implementation-plan.md)

---

## 概要

| Phase | 計画項目数 | 完了 | 未完了 | 進捗率 |
|-------|-----------|------|--------|--------|
| Phase 1: 基盤整備 | 8 | 6 | 2 | 75% |
| Phase 2: コアUX改善 | 6 | 5 | 1 | 83% |
| Phase 3: アクセシビリティ & i18n | 7 | 3 | 4 | 43% |
| Phase 4: 高度な機能 | 3 | 3 | 0 | 100% |
| **統合作業** | 8 | 1 | 7 | 13% |
| **合計** | 32 | 18 | 14 | 56% |

---

## Phase 1: 基盤整備

### 完了項目 ✅

#### 1.1.1 CSS変数の拡張
- **ファイル**: `apps/web/src/app/globals.css`
- **内容**: ダーク/ライトテーマ用のセマンティックカラー変数を追加
- **コミット**: `f06f311`

```css
:root, [data-theme='dark'] {
  --bg-primary: #030712;
  --text-primary: #f9fafb;
  /* ... */
}

[data-theme='light'] {
  --bg-primary: #ffffff;
  --text-primary: #111827;
  /* ... */
}
```

#### 1.1.2 Tailwind設定の拡張
- **ファイル**: `apps/web/tailwind.config.js`
- **内容**: CSS変数をTailwindカラーにマッピング

```javascript
colors: {
  'bg-primary': 'var(--bg-primary)',
  'text-primary': 'var(--text-primary)',
  // ...
}
```

#### 1.1.3 テーマプロバイダーの作成
- **ファイル**: `apps/web/src/context/ThemeContext.tsx`
- **内容**:
  - light/dark/system モード対応
  - localStorage 永続化
  - システム設定の自動検出
  - `useSyncExternalStore` によるハイドレーション対応

#### 1.2.1 プリファレンスコンテキストの作成
- **ファイル**: `apps/web/src/context/PreferencesContext.tsx`
- **内容**:
  - SWR による API データ取得
  - localStorage キャッシュ（高速表示）
  - 楽観的更新とロールバック

#### 1.3.2 バリデーションスキーマの作成
- **ファイル**: `apps/web/src/lib/schemas.ts`
- **内容**: Zod スキーマ定義
  - `addModelSchema`
  - `githubAppSchema`
  - `createTaskSchema`
  - `messageSchema`

#### 1.4.1 EmptyState コンポーネントの作成
- **ファイル**: `apps/web/src/components/ui/EmptyState.tsx`
- **内容**:
  - 汎用空状態コンポーネント
  - プリセットバリアント（no-tasks, no-repos, no-models, etc.）
  - サイズ対応（sm, md, lg）

### 未完了項目 ❌

#### 1.1.4 コンポーネントのテーマ対応
- **対象ファイル**:
  - `apps/web/src/components/ui/Button.tsx`
  - `apps/web/src/components/ui/Card.tsx`
  - `apps/web/src/components/ui/Input.tsx`
  - `apps/web/src/components/ui/Modal.tsx`
  - `apps/web/src/components/Sidebar.tsx`
- **作業内容**: ハードコードされた色 (`bg-gray-900` など) をセマンティックカラー (`bg-bg-primary` など) に置換
- **優先度**: 高

#### 1.3.3 フォームコンポーネントのリファクタリング
- **対象ファイル**:
  - `apps/web/src/components/SettingsModal.tsx` (AddModelForm)
  - `apps/web/src/app/page.tsx` (タスク作成フォーム)
- **作業内容**: react-hook-form + zodResolver による書き換え
- **優先度**: 中

---

## Phase 2: コアUX改善

### 完了項目 ✅

#### 2.1.1 セットアップ状態の検出
- **ファイル**: `apps/web/src/hooks/useSetupStatus.ts`
- **内容**:
  - GitHub App 設定状態の検出
  - モデル登録状態の検出
  - 次のステップの提示

#### 2.1.2 ウェルカムカードの作成
- **ファイル**: `apps/web/src/components/WelcomeCard.tsx`
- **内容**:
  - セットアップ進捗表示
  - 各ステップへのナビゲーション
  - 完了時は非表示

#### 2.2.1 進捗表示コンポーネント
- **ファイル**: `apps/web/src/components/RunProgress.tsx`
- **内容**:
  - 実行ステップの可視化
  - 経過時間表示
  - ログからのステップ推定
  - Executor タイプ別のステップ定義

#### 2.3.1 ネットワーク状態フック
- **ファイル**: `apps/web/src/hooks/useNetworkStatus.ts`
- **内容**:
  - オンライン/オフライン検出
  - API 到達性チェック
  - レイテンシ計測

#### 2.3.2 ステータスインジケーター
- **ファイル**: `apps/web/src/components/NetworkStatusIndicator.tsx`
- **内容**:
  - オフライン時のバナー表示
  - API 接続エラー時のバナー表示

### 未完了項目 ❌

#### 2.4 Diff ビューアの改善
- **対象ファイル**: `apps/web/src/components/DiffViewer.tsx`
- **作業内容**:
  - ファイル一覧サイドバーの追加
  - Unified/Split 表示切替
- **優先度**: 低

---

## Phase 3: アクセシビリティ & i18n

### 完了項目 ✅

#### 3.1.1 アクセシブルなドロップダウン
- **ファイル**: `apps/web/src/components/ui/Menu.tsx`
- **内容**:
  - キーボードナビゲーション（Arrow, Home, End, Escape, Tab）
  - ARIA 属性（role="menu", aria-expanded, aria-haspopup）
  - フォーカス管理

#### 3.4.2 メッセージファイルの作成
- **ファイル**: `apps/web/messages/en.json`
- **内容**: 英語メッセージ定義
  - common, navigation, task, run, settings, errors, empty

#### 3.4.3 i18n コンテキストの作成
- **ファイル**: `apps/web/src/context/I18nContext.tsx`
- **内容**:
  - カスタム i18n 実装（next-intl は Next.js 16 非対応のため）
  - ネストキー対応
  - 変数補間対応

### 未完了項目 ❌

#### 3.1.2 既存ドロップダウンの置き換え
- **対象ファイル**:
  - `apps/web/src/components/Sidebar.tsx` (ソートメニュー)
  - `apps/web/src/components/RunDetailPanel.tsx` (更新ドロップダウン)
  - `apps/web/src/components/RunsPanel.tsx` (フィルターメニュー)
- **優先度**: 中

#### 3.2.1 LiveAnnouncer の拡充
- **対象ファイル**: `apps/web/src/components/ui/LiveAnnouncer.tsx`
- **作業内容**: イベントタイプの追加（run_started, run_completed, etc.）
- **優先度**: 低

#### 3.2.2 アイコンボタンのラベル追加
- **対象ファイル**: 複数
- **作業内容**: `aria-label` 属性の追加
- **優先度**: 低

#### 3.4.4 コンポーネントでの i18n 使用
- **対象ファイル**: すべてのコンポーネント
- **作業内容**: ハードコード文字列を `useTranslations` で置換
- **優先度**: 低

---

## Phase 4: 高度な機能

### 完了項目 ✅

#### 4.1.1 テンプレート管理
- **ファイル**: `apps/web/src/components/InstructionTemplates.tsx`
- **内容**:
  - デフォルトテンプレート（Bug fix, Add tests, Refactor, etc.）
  - localStorage によるカスタムテンプレート保存

#### 4.2.1 比較パネル
- **ファイル**: `apps/web/src/components/RunComparisonPanel.tsx`
- **内容**:
  - 成功した実行結果の比較
  - ファイル数、変更行数の表示
  - 各実行への詳細リンク

#### 4.3.1 コマンドパレット
- **ファイル**: `apps/web/src/components/CommandPalette.tsx`
- **内容**:
  - Cmd/Ctrl + K で起動
  - コマンド検索
  - キーボードナビゲーション
  - ナビゲーション、アクション、設定カテゴリ

---

## 統合作業

### 完了項目 ✅

#### ClientLayout への統合
- **ファイル**: `apps/web/src/components/ClientLayout.tsx`
- **内容**:
  - ThemeProvider の追加
  - PreferencesProvider の追加
  - NetworkStatusIndicator の追加
  - CommandPalette の追加

### 未完了項目 ❌

#### WelcomeCard のホームページへの統合
- **対象ファイル**: `apps/web/src/app/page.tsx`
- **優先度**: 高

#### InstructionTemplates のホームページへの統合
- **対象ファイル**: `apps/web/src/app/page.tsx`
- **優先度**: 高

#### RunProgress の RunDetailPanel への統合
- **対象ファイル**: `apps/web/src/components/RunDetailPanel.tsx`
- **優先度**: 高

#### RunComparisonPanel のタスク詳細ページへの統合
- **対象ファイル**: `apps/web/src/app/tasks/[taskId]/page.tsx` または関連コンポーネント
- **優先度**: 中

#### EmptyState の既存コンポーネントへの適用
- **対象ファイル**:
  - `apps/web/src/components/Sidebar.tsx`
  - `apps/web/src/app/kanban/components/KanbanColumn.tsx`
  - `apps/web/src/components/RunsPanel.tsx`
  - `apps/web/src/components/SettingsModal.tsx`
- **優先度**: 中

---

## 作成されたファイル一覧

| ファイル | 種類 | 説明 |
|---------|------|------|
| `src/context/ThemeContext.tsx` | Context | テーマ管理 |
| `src/context/PreferencesContext.tsx` | Context | プリファレンス管理 |
| `src/context/I18nContext.tsx` | Context | 国際化 |
| `src/lib/schemas.ts` | Utility | Zod バリデーションスキーマ |
| `src/components/ui/EmptyState.tsx` | Component | 汎用空状態 |
| `src/components/ui/Menu.tsx` | Component | アクセシブルメニュー |
| `src/hooks/useSetupStatus.ts` | Hook | セットアップ状態 |
| `src/hooks/useNetworkStatus.ts` | Hook | ネットワーク状態 |
| `src/components/WelcomeCard.tsx` | Component | オンボーディング |
| `src/components/RunProgress.tsx` | Component | 実行進捗 |
| `src/components/NetworkStatusIndicator.tsx` | Component | ネットワーク状態表示 |
| `src/components/InstructionTemplates.tsx` | Component | 指示テンプレート |
| `src/components/RunComparisonPanel.tsx` | Component | 結果比較 |
| `src/components/CommandPalette.tsx` | Component | コマンドパレット |
| `messages/en.json` | Data | 英語メッセージ |

---

## 変更されたファイル一覧

| ファイル | 変更内容 |
|---------|----------|
| `package.json` | zod, react-hook-form, @hookform/resolvers 追加 |
| `src/app/globals.css` | テーマ用 CSS 変数追加 |
| `tailwind.config.js` | セマンティックカラーマッピング |
| `src/app/layout.tsx` | セマンティックカラークラス適用 |
| `src/components/ClientLayout.tsx` | Provider、グローバルコンポーネント追加 |
| `src/components/SettingsModal.tsx` | Appearance タブ追加 |
| `src/hooks/index.ts` | 新規 hook のエクスポート追加 |

---

## 次のステップ（推奨順序）

### 優先度: 高
1. **WelcomeCard のホームページ統合** - 初回ユーザー体験の改善
2. **RunProgress の RunDetailPanel 統合** - 実行中のフィードバック改善
3. **InstructionTemplates のホームページ統合** - タスク作成の効率化

### 優先度: 中
4. **コンポーネントのテーマ対応** - ライトモードの完全サポート
5. **EmptyState の適用** - 一貫性のある空状態表示
6. **既存ドロップダウンの Menu 置換** - アクセシビリティ向上

### 優先度: 低
7. **フォームの react-hook-form 化** - バリデーション体験の改善
8. **i18n の適用** - 多言語対応の基盤完成
9. **その他のアクセシビリティ改善** - WCAG 2.1 AA 準拠

---

## 技術的な注意事項

### React 19 対応
- `useEffect` 内での `setState` 呼び出しは ESLint エラーになる
- 対策:
  - 遅延初期化（`useState(() => initialValue)`）
  - `useSyncExternalStore` の使用
  - `eslint-disable-next-line react-hooks/set-state-in-effect` コメント

### Next.js 16 対応
- `next-intl` は Next.js 16 非対応
- 対策: カスタム `I18nContext` を実装

### 型安全性
- `UserPreferencesSave` と `UserPreferences` の型の違いに注意
- `null` 許容フィールドのマージ時は型アサーションが必要
