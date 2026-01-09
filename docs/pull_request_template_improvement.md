# pull_request_template 改善調査と実装計画

## 背景 / 問題

対象リポジトリに `pull_request_template` が存在するにもかかわらず、dursor で作成される PR 本文（PR Desc）がうまく生成・反映されないことがある。

本ドキュメントでは、現状実装を調査して課題を洗い出し、「どのような pull_request_template にも対応」できるようにするための設計・実装計画をまとめる。

---

## 現状の実装（調査結果）

### PR本文生成のフロー

バックエンド `apps/api/src/dursor_api/services/pr_service.py` では、主に以下の3パスで PR 本文を作る。

- **手動作成（`create`）**
  - `PRCreate.body` があればそれをベースにし、なければ `run.summary` を使う
  - リポジトリ内にテンプレが見つかった場合は `_render_pr_body_from_template()` で「テンプレに注入」して PR 本文を作る

- **自動作成（`create_auto`）**
  - diff / task / run を入力に LLM で title と body を生成する
  - テンプレがある場合は、テンプレ全文をプロンプトに含めて「テンプレに厳密に従え」と指示して生成する（`_build_description_prompt_for_new_pr()`）
  - LLM失敗時は `_generate_fallback_description_for_new_pr()` にフォールバックし、テンプレがあれば `_fill_template_sections()` で穴埋めを試みる

- **既存PRの本文再生成（`regenerate_description`）**
  - diff を作り直し、テンプレがあれば同様に LLM へ渡して生成
  - 失敗時は `_generate_fallback_description()` → `_fill_template_sections()` を利用

### テンプレ探索（現状）

`_load_pr_template()` は、クローン済みワークスペース上で以下の固定パスのみ探索している（優先順）。

1. `.github/pull_request_template.md`
2. `.github/PULL_REQUEST_TEMPLATE.md`
3. `pull_request_template.md`
4. `PULL_REQUEST_TEMPLATE.md`
5. `.github/PULL_REQUEST_TEMPLATE/default.md`

### テンプレ注入（現状）

#### `create` パス（手動作成時）

`_render_pr_body_from_template()` の戦略は以下。

- テンプレ内に `Summary` または `Description` 見出し（`#`〜`######`）があれば、その見出し「配下の本文」を生成文に差し替える
- 見出しが無ければ、`## Summary` を先頭に付けて生成文を置き、テンプレ全文を後ろに連結する

#### フォールバック穴埋め

`_fill_template_sections()` は以下の動作。

- HTML コメント `<!-- ... -->` を **全削除**（`re.DOTALL`）
- 見出し名が英語の特定語（summary/description/changes/review notes/test plan）に当たるものだけを正規表現で探し、各セクション「配下の本文」を置換する

---

## 課題（うまく生成できない原因の洗い出し）

### 1) テンプレ探索パスが GitHub の実運用に対して不十分

GitHub ではテンプレ配置・運用が多様で、以下が一般的に存在する。

- `docs/pull_request_template.md`（GitHub公式の探索パスに含まれる運用がある）
- `.github/PULL_REQUEST_TEMPLATE/*.md`（複数テンプレ運用）
  - `default.md` 固定ではない（`bugfix.md` や `feature.md` など）
  - PR作成時に `?template=feature.md` のような指定で選ぶ運用が多い

現状は `docs/` を見ず、複数テンプレも `default.md` しか見ないため「テンプレがあるのに見つからない」ケースが発生する。

### 2) 「見出し配下を丸ごと置換」がテンプレ構造を破壊し得る（重大）

現状の置換ロジックは「次の同レベル以上の見出し（`#`〜現在のレベル）まで」を本文範囲とみなし置換する。

このとき、テンプレが以下のように **`## Description` の下に `###` だけが続く**スタイルだと、次の `##` が現れないため **テンプレ末尾まで丸ごと削除**され得る。

- 例: `## Description` の後に `### Type of change` / `### Checklist` が続くテンプレ

この破壊は `create` の `_render_pr_body_from_template()` でも、フォールバックの `_replace_section_content()` でも起こり得るため、テンプレによっては「生成文は入ったがチェックリスト等が消える」「結果的に本文が不自然/不足」といった不具合に繋がる。

### 3) 見出し名・言語依存（英語前提）が強すぎる

置換対象の見出し判定が実質的に以下へ偏っている。

- `Summary` / `Description`
- `Changes`
- `Review Notes` / `Test Plan`

実運用では以下が頻出する。

- 日本語見出し（例: `概要`, `変更内容`, `テスト`, `確認項目`）
- 絵文字付き見出し（例: `## ✅ Checklist`）
- 「What/Why/How」「Background」「Risk」「Screenshots」「Breaking changes」など多様なセクション名

これにより、テンプレは見つかっても「狙った位置に生成文が入らない」ケースが発生する。

### 4) HTMLコメントの扱いが乱暴（全削除）で、テンプレ意図を壊す

多くのテンプレは、各セクションのプレースホルダとして HTMLコメントを多用する。

現状フォールバックは `<!-- ... -->` を全削除するため、

- セクションの入力ガイドが消える
- コメントで囲まれたブロックが想定通りに置換されず、空欄が増える

など、出力品質が下がりやすい。

### 5) 複数テンプレ運用（テンプレ選択）に対応できない

テンプレが複数ある場合、どれを使うべきかはユーザの意図（feature/bugfix等）に依存するが、現状は選択UI/APIが無く、実質的に対応不能。

### 6) 「再生成」時にユーザ手修正を保護する仕組みがない

`regenerate_description` は PR body 全体を上書きするため、ユーザが GitHub 上で本文を手編集していても消える。

テンプレ適用の改善とは別だが、テンプレ運用では「チェックリストだけ手で更新」などが多いため、手修正保護は実用上重要。

---

## 目標（あるべき仕様）

- **探索**: GitHub のテンプレ探索/運用パターンを広くカバーする
- **選択**: 複数テンプレがある場合に「どれを使うか」を指定できる（デフォルトも決められる）
- **合成**: テンプレ構造（見出し、チェックリスト、注意書き、フロントマター等）を壊さずに生成文を差し込む
- **再生成**: PR本文の「dursor生成ブロック」だけを更新し、ユーザの手修正やテンプレ固定部は保持する
- **後方互換**: 既存API/既存UIは動作を保ちつつ、任意指定ができるよう拡張する

---

## 改善方針（設計）

### A. テンプレ探索を「列挙 + 選択」へ分離する

現状は「見つかった1つを返す」関数だが、複数テンプレ運用を前提に以下へ変更する。

- **Template Locator（新規）**
  - リポジトリ内の候補テンプレを列挙して返す
  - 例: `PRTemplate { id, path, filename, content, source, is_default_candidate }`

探索対象（優先度付きの推奨セット）:

- 単一テンプレ系
  - `.github/pull_request_template.md`
  - `.github/PULL_REQUEST_TEMPLATE.md`
  - `pull_request_template.md`
  - `PULL_REQUEST_TEMPLATE.md`
  - `docs/pull_request_template.md`
- 複数テンプレ系
  - `.github/PULL_REQUEST_TEMPLATE/*.md`（`default.md` 以外も含む）

※ 実装では「大文字小文字違い」を吸収する（Linuxでも実運用では大小が揺れる）。

### B. テンプレ選択を API で明示可能にする（複数テンプレ対応の本丸）

以下を追加/拡張する。

- **新規API（案）**: `GET /repos/{repo_id}/pull-request-templates`
  - 返却: テンプレ一覧（`name/path` とプレビュー用の先頭N文字など）
- **PR作成API拡張（案）**
  - `PRCreate` / `PRCreateAuto` / `create_link` 系に `template_path`（または `template_id`）を追加（optional）
  - 未指定の場合は「推奨デフォルト」を自動選択

推奨デフォルト選択規則（案）:

1. 単一テンプレ（`.github/pull_request_template.md` 等）があればそれを優先
2. `.github/PULL_REQUEST_TEMPLATE/default.md` があればそれ
3. `.github/PULL_REQUEST_TEMPLATE/*.md` が1つだけならそれ
4. 複数ある場合は `default`/`pull_request_template` に近い名前を優先し、最後は辞書順（または「最短ファイル名」）で決める

ただし最終的には UI から明示選択できるようにするのが望ましい。

### C. 「非破壊の差し込み」へ変更する（テンプレ互換性の本丸）

現状の「見出し配下を丸ごと置換」は破壊的なので廃止し、以下のどちらか（または併用）へ移行する。

#### 方針C-1: dursor管理ブロック（マーカー）方式（推奨）

テンプレ本文は一切削らず、本文の先頭（または適切な位置）に dursor 管理ブロックを挿入する。

例:

- `<!-- dursor:begin -->`
- `<!-- dursor:end -->`

再生成時は **このブロックだけ**を更新する。

挿入位置（案）:

- YAML front matter (`--- ... ---`) がある場合は **front matter の直後**
- それ以外は **先頭**（または先頭の導入コメント直後）

メリット:

- テンプレ構造を破壊しない
- どんなテンプレにも対応できる（最悪でも「テンプレ + 生成サマリ」は成立）
- 再生成で手修正を守れる（ブロック外は触らない）

#### 方針C-2: 既存テンプレのプレースホルダ（HTMLコメント）を安全に置換

テンプレの典型として `<!-- Please describe ... -->` のようなコメントがあるため、

- 「コメント1個」を置換する
- 「コメントの中身だけ」を置換する

などの **局所的な置換**を行う。

この場合も「見出し配下を丸ごと置換」はしない（`###` を巻き込んで消えるため）。

推奨の置換ルール（案）:

- `Summary/Description` 相当のセクション直下の最初の HTMLコメントを「生成サマリ」に置換
- それ以外のコメントは基本保持（または “N/A” を入れる）し、チェックリスト等の非コメント行は保持

### D. LLMの出力を「テンプレ全文生成」から「差し込みブロック生成」へ寄せる

テンプレ全文を LLM に再生成させると、微妙なズレで構造が変わりやすい（チェックボックスの欠落、見出し名変更など）。

そのため、LLM には以下だけを生成させる設計へ寄せる。

- **dursor管理ブロックの中身のみ**（Summary/Changes/Test Plan など）

そしてテンプレ合成はアプリ側で deterministic（決定的）に行う。

メリット:

- “どんなテンプレにも対応” の実現可能性が上がる
- 出力差分が小さく、再生成も安全

---

## 実装計画（ステップ）

### Step 0: 回帰防止のためのテスト追加

テンプレの代表パターンを fixtures として用意し、以下をテストする。

- **探索**
  - `docs/pull_request_template.md` が見つかる
  - `.github/PULL_REQUEST_TEMPLATE/*.md` が列挙される
- **合成（非破壊）**
  - `## Description` の下に `###` が続くテンプレでも、`###` セクションが消えない
  - チェックボックス (`- [ ]`) が保持される
  - YAML front matter が保持される
- **再生成**
  - dursorブロックだけが更新され、ブロック外の手修正が残る

### Step 1: テンプレ列挙ロジックの導入

- `PRService._load_pr_template()` を置き換え/内包し、テンプレの「列挙」を実装
- 返却は `list[Template]` にし、既存呼び出し箇所は「デフォルト1件を選ぶ」ヘルパーで後方互換を保つ

### Step 2: テンプレ選択のAPI拡張

- `PRCreate` / `PRCreateAuto` に `template_path`（or `template_id`）を追加（optional）
- `create_link*` にも同様の指定を追加（compare URL に `template=` を付与する設計も検討）
- 新規でテンプレ一覧取得 API を追加し、Web UI 側で選択できるようにする（段階導入可）

### Step 3: 非破壊合成（dursorブロック方式）へ切り替え

- `_render_pr_body_from_template()` と `_fill_template_sections()` を「テンプレ破壊しない」方式に置換
- 生成文は `<!-- dursor:begin --> ... <!-- dursor:end -->` に閉じ込め、テンプレ本文は保持
- `regenerate_description` も同様に、dursorブロックのみ更新する

### Step 4: LLMプロンプトの変更（ブロック生成に寄せる）

- LLMにはテンプレ全文の再生成をさせず、dursorブロックに入れる内容だけを生成させる
- 可能なら「出力はMarkdownで、以下の見出しのみ」と制約を強める（例: Summary / Changes / Test Plan）

### Step 5: 既存動作の互換・段階導入

- テンプレ未指定でも今まで通り PR が作れる（デフォルト選択）
- 既存の PR 本文に dursorブロックが無い場合は、初回再生成時に挿入して以後は更新する

---

## 追加で検討すべき点（設計上の論点）

- **テンプレ選択の永続化**
  - Repo単位/ユーザ単位で「既定テンプレ」を保存するか
- **手動作成（compare link）時のテンプレ**
  - GitHub UI はテンプレ自動挿入を行うが、`body` クエリを付けると挙動が変わる可能性がある
  - link生成APIは `template=` パラメータ付与（複数テンプレ運用に合う）を検討
- **セキュリティ/禁止パス**
  - ワークスペースのテンプレ読み取りは `.github/` `docs/` 等の読み取りになるため問題は小さいが、
    将来「Contents APIで取得」へ切替える場合は権限/レート制限考慮が必要

---

## 結論

現状の不安定さは、主に以下が原因。

- テンプレ探索の不足（`docs/`、複数テンプレ）
- 見出し配下の丸ごと置換がテンプレ構造を破壊する（`###` を巻き込んで消す）
- 英語見出し前提/コメント全削除により、多様なテンプレで穴埋めできない
- 再生成が全上書きで、手修正を守れない

対策として、テンプレを **列挙して選択可能**にし、本文は **非破壊な dursorブロック方式**で合成・再生成する方針が、最も「どのような pull_request_template にも対応」しやすい。

