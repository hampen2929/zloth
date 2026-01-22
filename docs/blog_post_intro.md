# 寝ている間にAIがコードを書く。「Zloth」というOSSを作りました

こんにちは。今回は私が開発しているオープンソースのAIコーディングエージェント「**Zloth**（ゾロス）」を紹介します。

## Zloth とは？

Zloth は、セルフホスト可能なマルチモデル並列コーディングエージェントです。

簡単に言うと、**「自分のAPIキーを使って、複数のAIモデルに同時に同じタスクを依頼し、その結果を見比べて良いとこ取りができるWebアプリ」**です。

リポジトリはこちら: [hampen2929/zloth](https://github.com/hampen2929/zloth)

![Zloth Screenshot](https://raw.githubusercontent.com/hampen2929/zloth/main/docs/images/screenshot.png) *(※スクリーンショットはイメージです)*

## 名前の由来

「Zloth」という少し変わった名前には、こんな由来があります。

**Zloth = Zzz (眠り) + Sloth (ナマケモノ)**

ユーザーが寝ている間に、ナマケモノ（Sloth）のようにエージェントが働いてくれる、というコンセプトです。また、単なる「Sloth」ではなく綴りを変えることで、検索しやすくしつつ、どことなくハッカーっぽい響きを持たせています。

## なぜ作ったのか？

最近は Claude Code や Cursor など、優れたAIコーディングツールがたくさんあります。しかし、使っているうちにいくつか「もっとこうだったらいいのに」と思う点が出てきました。

1. **モデルの比較がしたい**: 「このタスク、GPT-4oとClaude 3.5 Sonnetどっちが得意だろう？」と思ったとき、同時に試して結果を見比べたい。
2. **自分のAPIキーを使いたい**: サブスクリプション型のサービスも良いですが、従量課金で自分のAPIキー（OpenAI, Anthropic, Google）を使ってコストをコントロールしたい。
3. **CLIもいいけどGUIも欲しい**: ターミナルでの対話も良いですが、コードの差分（Diff）を見たり、過去の履歴を追ったりするには、リッチなWeb UIが便利です。
4. **データは手元に置きたい**: セルフホストで動かすことで、コードや会話データを自分の管理下に置きたい。

これらを解決するために Zloth を開発しました。

## 主な機能

### 1. マルチモデル並列実行 (Multi-model Parallel Execution)
一つのタスクに対して、複数のモデル（例: GPT-4o, Claude 3.5 Sonnet, Gemini 1.5 Pro）を同時に走らせることができます。それぞれのモデルが生成したパッチ（修正案）を横並びで比較し、最も良いものを採用できます。

### 2. BYO API Key (Bring Your Own API Key)
OpenAI、Anthropic、Google のAPIキーを登録して利用します。キーはローカルのデータベースに暗号化されて保存されるため安心です。

### 3. 会話主導のPR開発
チャットインターフェースで指示を出し、エージェントと対話しながらコードを修正していきます。納得いくコードができたら、ボタン一つでGitHubのPull Requestを作成できます。

## 技術スタック

Zloth は以下の技術で構築されています。

- **Backend**: Python 3.13+, FastAPI, uv
- **Frontend**: Next.js 14 (React, TypeScript, Tailwind CSS)
- **Database**: SQLite (aiosqlite)
- **Git Operations**: GitHub App / CLI Integration

## 今後の展望

現在は v0.1 ですが、今後は以下の機能を予定しています。

- **Docker Sandbox**: コードの実行やテストを安全なサンドボックス環境で行う機能。
- **Review Agent**: 複数のモデルが出したコードを、別の「レビュー担当」AIが評価・ランク付けする機能。
- **コスト管理**: API利用料の可視化と予算設定。

## さいごに

Zloth はオープンソース（Apache 2.0 License）で公開しています。もし興味を持っていただけたら、ぜひ GitHub でスターをお願いします！

[https://github.com/hampen2929/zloth](https://github.com/hampen2929/zloth)

バグ報告や機能要望も Issue でお待ちしています。
