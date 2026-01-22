# zloth - BYOキーで動く、マルチモデル並列AIコーディングエージェント

AIコーディングツールを日常的に使っている開発者の皆さん、こんな悩みはありませんか？

- 会社でSaaSツールを契約できず、自前のAPIキーで動くツールを探している
- Claude Code、Codex、Gemini CLI...複数のターミナルを行き来して並列実行を管理するのに疲れた
- IDEやCLIではなく、シンプルなWebチャット形式でAIと開発したい
- 複数モデルの出力を比較して、最適な実装を選びたい

そんな方に向けて、OSSのセルフホスト型AIコーディングエージェント「**zloth**」を紹介します。

## zlothとは

**zloth**は、自分のAPIキーを使って複数のAIモデルを並列実行できる、セルフホスト型のコーディングエージェントです。

主な特徴：

- **BYO API Key**: OpenAI、Anthropic、GoogleのAPIキーを持ち込んで利用
- **マルチモデル並列実行**: GPT-4、Claude、Geminiなど複数モデルで同時にタスクを実行
- **Webチャット形式**: ブラウザ上でチャットしながらコードを生成・修正
- **結果比較**: 各モデルの出力をサイドバイサイドで比較し、最適なものを選択
- **PR連携**: 選んだ実装からGitHub PRを直接作成

## どんな人に向いている？

### 向いている人

**1. 会社でSaaSを契約できず、BYOなプロダクトを探している人**

多くのAIコーディングツールはサブスクリプション型のSaaSですが、セキュリティポリシーや予算の都合で契約できないケースもあります。zlothは完全にセルフホストで動作し、自分のAPIキーを使うため、データは自社ネットワーク内に留まります。

**2. CLIでの並列管理に疲れた人**

Claude Code、Codex CLI、Gemini CLIなど、優秀なCLIツールは増えていますが、複数を並列で動かして結果を比較するのは手間がかかります。zlothは裏側でこれらのCLIを実行し、Web UI上で一元管理できます。

**3. Webチャット形式で開発したい人**

IDEの拡張機能やCLIではなく、ChatGPTやClaudeのようなシンプルなチャットUIで開発したい方に。指示を入力して、複数モデルの結果を見比べて、良い方を採用するというワークフローが実現できます。

**4. 開発による認知負荷を下げたい人**

どのモデルが最適かを毎回考えるのは疲れます。zlothでは複数モデルを一度に試して比較できるため、「このタスクにはどのモデルが向いているか」を都度検証しながら開発を進められます。

### 向いていないかもしれない人

**CLIでカスタマイズしまくって並列実装して極限まで生産性を高めたい人**

zlothはWebベースのUIで「手軽に」マルチモデル実行できることを重視しています。Claude Codeなどのカスタムフック、シェルスクリプトとの連携、複雑なワークフロー自動化など、CLIならではの柔軟性を最大限活かしたい方には、各CLIツールを直接使う方が適しているかもしれません。

## 技術スタック

- **バックエンド**: FastAPI（Python 3.13+）
- **フロントエンド**: Next.js 14（React, TypeScript, Tailwind CSS）
- **データベース**: SQLite
- **LLM連携**: OpenAI / Anthropic / Google API + Claude Code / Codex / Gemini CLI

## 使い方の流れ

1. **APIキーを登録**: Settings画面でOpenAI、Anthropic、GoogleのAPIキーを登録
2. **リポジトリを選択**: GitHub Appを連携して、対象リポジトリを選択
3. **モデルを選択**: 並列実行したいモデルを複数選択
4. **指示を入力**: 「このフォームにバリデーションを追加して」などの指示を入力
5. **結果を比較**: 各モデルが生成したパッチを比較
6. **PRを作成**: 気に入った実装を選んでPRを作成

## 他ツールとの比較

|  | zloth | Cursor (Cloud) | Cursor (IDE) | AI Coding CLIs | AI Coding Cloud |
|---|:---:|:---:|:---:|:---:|:---:|
| Webベースチャット | o | o | x | x | o |
| オンプレ/ローカルホスト | o | x | o | o | x |
| 複数AIモデル対応 | o | o | o | x | x |
| BYO API Key | o | x | o | o | x |
| OSS | o | x | x | o | x |
| CLI連携 | o* | x | x | o | x |

*zlothは裏側でAI Coding CLIを実行

## セットアップ

### Docker（推奨）

```bash
git clone https://github.com/hampen2929/zloth.git
cd zloth
cp .env.example .env
# .envを編集してZLOTH_ENCRYPTION_KEYを設定
docker-compose up -d
```

http://localhost:3000 でアクセスできます。

### ローカル開発

```bash
# バックエンド
cd apps/api
uv sync --extra dev
uv run python -m zloth_api.main

# フロントエンド（別ターミナル）
cd apps/web
npm install
npm run dev
```

## セキュリティ

- APIキーはFernet（AES-128）で暗号化して保存
- ワークスペースはタスクごとに隔離
- `.git`、`.env`などの機密パスへのアクセスはブロック

## ロードマップ

- **v0.2**: Dockerサンドボックスによるコマンド実行、レビューエージェント
- **v0.3**: マルチユーザー対応、コスト管理、ポリシー設定

## まとめ

zlothは「自分のAPIキーで、複数モデルを並列実行して、Webチャットで開発する」というニッチだけど確実なニーズに応えるツールです。

- SaaSを契約できない環境でもAIコーディングを活用したい
- 複数モデルの出力を簡単に比較したい
- CLIを行き来する手間を省きたい

そんな方はぜひ試してみてください。

**GitHub**: https://github.com/hampen2929/zloth
**ライセンス**: Apache License 2.0

---

質問やフィードバックは[GitHub Issues](https://github.com/hampen2929/zloth/issues)へどうぞ。
