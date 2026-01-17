# tazuna Next Gen: Concept & Roadmap

このドキュメントは、tazunaを「AI時代の究極の開発パートナー」へと進化させるためのコンセプト、現状分析、そして具体的なロードマップをまとめたものです。

## 1. コンセプトの再定義

従来の「AIにコードを書かせるツール」から、「**複数のAIエンジニアを指揮・管理し、開発を加速させる司令塔（オーケストレーター）**」へと役割を再定義します。

### コアコンセプト
1.  **Human as Manager, AI as Workers**: 人間は「実装」から解放され、「意思決定」「レビュー」「方向付け」という人間ならではの高度な業務に集中する。
2.  **Orchestration over Generation**: コード生成能力自体の向上はClaude CodeやCursorなどの専門ツールに任せ、tazunaはそれらを「誰に・どう働かせるか」を管理し、成果を最大化することに注力する。
3.  **Radical Observability**: AIが「今何をしているか」「なぜそうしたか」をブラックボックス化せず、完全に可視化する。
4.  **Native Developer Experience**: Webブラウザの中に閉じ込めず、ローカルのファイルシステム、ターミナル、エディタとシームレスに統合された「最高のパソコン体験」を提供する。

---

## 2. 現状と課題 (Gap Analysis)

| 領域 | 現状 (As-Is) | 課題 (Gap) | あるべき姿 (To-Be) |
| :--- | :--- | :--- | :--- |
| **役割** | 自前のLLMプロンプトでパッチ生成 | AIモデルの進化速度に追従コストがかかる。<br>複雑なリファクタリング等は苦手。 | **外部の強力なAIツール(Claude Code等)をAPI/CLI経由で統御する**。 |
| **人間の作業** | プロンプト記述、モデル選択、PR作成 | 試行錯誤の指示出しが必要。<br>「AIのお守り」をしている感覚。 | **ゴール設定と承認のみ**。<br>AIが自律的にプラン提示→実行→報告を行う。 |
| **可視性** | 完了後のDiffのみ | 実行中の思考プロセスが見えない。<br>長時間待機中の不安。 | **思考・操作のリアルタイム中継**。<br>AIの作業画面を覗き込むような体験。 |
| **UX** | ブラウザ上のWeb UI | ローカルエディタとの行ったり来たり。<br>ファイルアクセスの制限。 | **Desktop App / IDE Extension**。<br>ローカル環境と一体化した体験。 |
| **比較** | 生成結果の並列表示 | 結局どれが良いか人間が詳細レビュー必要。<br>差分がわかりにくい。 | **構造的な比較と自動評価**。<br>「A案は安全、B案は高速」のような洞察提示。 |

---

## 3. 次世代アーキテクチャの柱

### A. The "Cockpit" UI (コックピット)
AIの作業を「待つ」のではなく「監視・指揮する」ためのインターフェース。
- **Multi-Agent Live View**: 複数のAIエージェント（例: Claude Code, Custom Agent）が並列で動いているターミナルや思考ログを1画面でモニタリング。
- **Intervention (介入)**: 暴走しかけたエージェントを一時停止、方向修正の指示を割り込ませる機能。

### B. Executor Plugin System (外部脳の活用)
tazuna自身がLLMを叩くコードを減らし、外部の優秀なCLI/APIをプラグインとして扱う。
- **Claude Code Executor**: AnthropicのClaude Code CLIをサブプロセスとして制御。
- **OpenAI Operator (将来)**: OpenAIのOperator機能が出たら即座に取り込む。
- **Local LLM Executor**: 機密性の高いコード向けのローカルモデル実行。

### C. Native Desktop Integration
Web技術(Next.js)をベースにしつつ、Electron/Tauri等を用いてデスクトップアプリ化。
- **Local Worktree Management**: ユーザーのローカルディスク上で `git worktree` を駆使し、メインブランチを汚さずにAIに並列作業させる。
- **System Notification**: 作業完了や確認依頼をネイティブ通知。

---

## 4. 優先度付きロードマップ

### Phase 1: The Orchestrator (基盤刷新) - Priority: High
「AIの進歩はAI coding toolに任せる」を体現するため、自前生成から外部ツール利用へシフトする。

- **[P0] Claude Code Integration**: `PatchAgent` に代わる主力Executorとして `ClaudeCodeExecutor` を実装。`git worktree` 上で隔離実行させる。
    - *既に `support-claude-code.md` で計画済みだが、最優先で進める。*
- **[P1] Stream & Log Visualization**: CLIツールの出力をリアルタイムでWeb UIにストリーミングし、ANSIカラー等を保持して表示する。
- **[P2] Task-based Worktree**: 1タスク1ワークツリーの原則を確立し、ファイルシステムレベルでの安全な並列実行を実現する。

### Phase 2: The Cockpit (可視化とUI刷新) - Priority: High
「AIが何をやっていることを一目瞭然で確認できるようにする」を実現する。

- **[P0] Real-time Agent Dashboard**: 進行中のRunのステータス、現在実行中のコマンド、最新の思考ログをタイル状に表示するダッシュボード。
- **[P1] Smart Diff Viewer**: 単なるテキスト差分ではなく、ファイルツリー構造、シンタックスハイライト、AIによる変更理由の解説が付いたDiffビューア。
- **[P2] Timeline View**: 時系列で「いつ、どのファイルに、何をしたか」を可視化するタイムラインUI。

### Phase 3: Desktop Experience (体験向上) - Priority: Medium
「パソコンでの開発体験を最高にする」を実現する。

- **[P1] Desktop App Prototype**: Electron または Tauri を用いて、既存のWebフロントエンドをラップしたデスクトップアプリを作成。
- **[P2] Local File System Access**: Dockerコンテナ内ではなく、ホストマシンのディレクトリを直接扱えるモード（Local Mode）の整備。
- **[P3] Notification & Menu Bar**: 常駐アプリとしての利便性向上。

### Phase 4: Autonomous Manager (自律化) - Priority: Low (Long-term)
「人間がやることを最小限にする」を突き詰める。

- **[P2] Auto-Reviewer**: AIが生成したコードを、別のAI（Reviewer Agent）が自動レビューし、簡単な修正なら人間に見せる前に直させる。
- **[P3] Semantic Search & Context**: ユーザーの指示が曖昧でも、RAGや過去のPR履歴からコンテキストを補完して自律的に動く機能。

---

## 5. 直近のアクションアイテム (Next Steps)

1. **`ClaudeCodeExecutor` の実装開始**:
   - `apps/api/src/tazuna_api/executors/claude_code.py` の作成。
   - `RunService` の改修。

2. **Web UIの「実行ログ」表示のりリッチ化**:
   - 現在のテキストログから、ターミナルエミュレータ風のUIコンポーネントへの置き換え。

3. **ドキュメント整備**:
   - 本ドキュメントの内容をチーム（ユーザー）と合意し、開発ブランチでの実装フェーズへ移行。
