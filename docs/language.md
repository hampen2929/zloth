# 言語・コーディング規約

このドキュメントでは、dursor プロジェクトで使用されているプログラミング言語とコーディング規約について説明します。

## 使用言語

### バックエンド (apps/api)

| 項目 | 詳細 |
|------|------|
| 言語 | Python 3.13+ |
| フレームワーク | FastAPI |
| パッケージマネージャー | uv |
| データベース | SQLite (aiosqlite) |
| 型チェッカー | mypy (strict モード) |
| フォーマッター/リンター | ruff |

### フロントエンド (apps/web)

| 項目 | 詳細 |
|------|------|
| 言語 | TypeScript |
| フレームワーク | Next.js 14 (React) |
| スタイリング | Tailwind CSS |
| パッケージマネージャー | npm |
| リンター | ESLint |
| フォーマッター | Prettier |

## Python コーディング規約

### 基本ルール

- **行の長さ**: 最大100文字
- **インデント**: スペース4つ
- **docstring**: Google スタイル
- **型ヒント**: 必須（mypy strict モードで検証）

### ファイル構成

```
apps/api/src/dursor_api/
├── main.py         # アプリケーションエントリーポイント
├── config.py       # 設定（環境変数）
├── dependencies.py # 依存性注入
├── agents/         # エージェント実装
├── domain/         # ドメインモデル
├── routes/         # APIルート
├── services/       # ビジネスロジック
└── storage/        # データ永続化
```

### 命名規則

| 種類 | 規則 | 例 |
|------|------|-----|
| クラス | PascalCase | `RunService`, `ModelProfile` |
| 関数/メソッド | snake_case | `create_runs`, `get_by_id` |
| 変数 | snake_case | `run_id`, `workspace_path` |
| 定数 | UPPER_SNAKE_CASE | `DEFAULT_TIMEOUT`, `MAX_RETRIES` |
| プライベート | 先頭に `_` | `_execute_run`, `_connection` |

### 型ヒントのベストプラクティス

```python
# DAO の戻り値は T | None を処理する
pr = await self.pr_dao.get(pr_id)
if not pr:
    raise ValueError(f"PR not found: {pr_id}")
return pr

# ラムダ式ではなく型付きヘルパー関数を使用
def make_coro(r: Run) -> Callable[[], Coroutine[Any, Any, None]]:
    return lambda: self._execute(r)

# Union 型を持つ dict には明示的な型注釈を追加
executor_map: dict[ExecutorType, tuple[ClaudeExecutor | CodexExecutor, str]] = {
    ExecutorType.CLAUDE: (self.claude_executor, "Claude"),
}
```

### import 順序

1. 標準ライブラリ
2. サードパーティライブラリ
3. ローカルモジュール

```python
import asyncio
from pathlib import Path

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from dursor_api.services.run_service import RunService
from dursor_api.domain.models import Run
```

## TypeScript コーディング規約

### 基本ルール

- **strict モード**: 有効
- **インデント**: スペース2つ
- **セミコロン**: あり
- **クォート**: シングルクォート優先

### ファイル構成

```
apps/web/src/
├── app/            # App Router (ページ)
├── components/     # React コンポーネント
├── lib/           # ユーティリティ
└── types.ts       # 型定義
```

### 命名規則

| 種類 | 規則 | 例 |
|------|------|-----|
| コンポーネント | PascalCase | `ChatPanel`, `DiffViewer` |
| 関数 | camelCase | `createRun`, `fetchTask` |
| 変数 | camelCase | `taskId`, `isLoading` |
| 型/インターフェース | PascalCase | `Task`, `RunStatus` |
| 定数 | UPPER_SNAKE_CASE または camelCase | `API_BASE_URL` |
| ファイル名 | PascalCase（コンポーネント）、camelCase（その他） | `ChatPanel.tsx`, `api.ts` |

### React コンポーネントの規則

```typescript
// 関数コンポーネントを使用
export function ChatPanel({ taskId }: ChatPanelProps) {
  // hooks は先頭に
  const [messages, setMessages] = useState<Message[]>([]);
  const { data, isLoading } = useSWR(`/tasks/${taskId}`);

  // イベントハンドラ
  const handleSubmit = useCallback(() => {
    // ...
  }, []);

  // レンダリング
  return <div>...</div>;
}
```

## コードフォーマット

### Python

```bash
# フォーマット
uv run ruff format src/

# リントチェック
uv run ruff check src/

# 型チェック
uv run mypy src/
```

### TypeScript

```bash
# リントチェック
npm run lint

# ビルド（型チェックを含む）
npm run build
```

## ドキュメント言語

- **コードコメント**: 英語
- **docstring**: 英語
- **README/docs**: 英語（一部日本語ドキュメントあり）
- **コミットメッセージ**: 英語

## 依存関係管理

### Python (uv)

```bash
# 依存関係のインストール
uv sync --extra dev

# 新しい依存関係の追加
uv add <package>

# 開発用依存関係の追加
uv add --dev <package>
```

### TypeScript (npm)

```bash
# 依存関係のインストール
npm ci

# 新しい依存関係の追加
npm install <package>

# 開発用依存関係の追加
npm install --save-dev <package>
```

## セキュリティ

### 禁止されるファイルパターン

以下のファイルはコミットしてはいけません：

- `.env`, `.env.*`
- `*.key`, `*.pem`
- `*.secret`
- `credentials.*`

### API キーの取り扱い

- API キーは `CryptoService` を使用して暗号化して保存
- 環境変数で管理し、コードにハードコードしない
- `DURSOR_ENCRYPTION_KEY` 環境変数が必須
