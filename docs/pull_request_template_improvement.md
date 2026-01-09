# Pull Request Template処理の改善

## 1. 調査結果

### 1.1 現状のアーキテクチャ

PR Description生成に関連する主要なコードは `apps/api/src/dursor_api/services/pr_service.py` に集約されている。

#### テンプレート検索パス

現在、以下の順序でテンプレートファイルを検索している：

1. `.github/pull_request_template.md`
2. `.github/PULL_REQUEST_TEMPLATE.md`
3. `pull_request_template.md`
4. `PULL_REQUEST_TEMPLATE.md`
5. `.github/PULL_REQUEST_TEMPLATE/default.md`

#### 主要な処理フロー

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PR Description生成                            │
├─────────────────────────────────────────────────────────────────────┤
│  1. テンプレート読み込み (_load_pr_template)                          │
│     ↓                                                               │
│  2. 経路分岐                                                         │
│     ├── create() → _render_pr_body_from_template (手動タイトル/説明)  │
│     ├── create_auto() → LLM生成 (_generate_description_for_new_pr)   │
│     └── regenerate_description() → LLM再生成 (_generate_description)  │
│     ↓                                                               │
│  3. フォールバック処理 (LLM失敗時)                                    │
│     ├── _generate_fallback_description_for_new_pr                    │
│     └── _generate_fallback_description                               │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 発見された課題

#### 課題1: テンプレート解析の硬直性

**問題点:**
- `_render_pr_body_from_template`: `Summary` または `Description` セクションのみを認識
- `_fill_template_sections`: 固定的なセクション名（summary/description, changes, review notes/test plan）のみに対応
- 任意のセクション名（例: `## Motivation`, `## Breaking Changes`, `## Related Issues`）に対応できない

**該当コード:**
```python
# _render_pr_body_from_template (L997-1037)
heading_re = re.compile(
    r"^(#{1,6})\s+(summary|description)\s*$",  # ← 固定パターン
    re.IGNORECASE | re.MULTILINE,
)

# _fill_template_sections (L669-703)
section_mappings = [
    (r"(#{1,6}\s+(?:summary|description)\s*\n)", summary),
    (r"(#{1,6}\s+changes\s*\n)", changes),
    (r"(#{1,6}\s+(?:review\s*notes?|test\s*plan)\s*\n)", "N/A"),  # ← 固定パターン
]
```

#### 課題2: HTMLコメント（指示）の活用不足

**問題点:**
- テンプレート内のHTMLコメント（`<!-- 説明文を入力 -->`）を単純に削除
- コメント内の指示内容をLLMに渡さず、重要なコンテキストが失われる

**該当コード:**
```python
# _fill_template_sections (L685-686)
result = re.sub(r"<!--.*?-->", "", result, flags=re.DOTALL)  # ← 単純削除
```

**一般的なテンプレート例（未対応パターン）:**
```markdown
## Summary
<!-- Briefly describe what this PR does -->

## Motivation
<!-- Why is this change necessary? -->

## Breaking Changes
<!-- List any breaking changes, or write "None" -->
- [ ] This PR introduces breaking changes
```

#### 課題3: LLMプロンプトの曖昧さ

**問題点:**
- 「MUST FOLLOW EXACTLY」と指示しているが、具体性に欠ける
- テンプレート内のコメント指示の扱いが明確でない
- LLMの出力形式が厳密に規定されていない

**該当コード:**
```python
# _build_description_prompt_for_new_pr (L581-597)
prompt_parts.extend([
    "",
    "## Template (MUST FOLLOW EXACTLY)",
    "You MUST create the Description following this exact template structure.",
    "- Keep ALL section headings from the template.",
    "- Fill in each section with content based on the diff and context.",
    "- Do NOT add sections that are not in the template.",
    "- Do NOT remove or rename any sections from the template.",
    "- Replace HTML comments (<!-- ... -->) with actual content.",
    # ← コメント内の指示をどう解釈するかが不明確
])
```

#### 課題4: チェックボックス処理の未対応

**問題点:**
- テンプレート内のチェックボックス（`- [ ]`, `- [x]`）の扱いが定義されていない
- 状況に応じてチェック/アンチェックすべきかの判断ロジックがない

**一般的なテンプレート例:**
```markdown
## Checklist
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Breaking changes documented
```

#### 課題5: フォールバック処理の限定性

**問題点:**
- LLM失敗時のフォールバックが限定的なセクションのみに対応
- テンプレートの元の構造を保持できない
- 情報の欠損が発生する

**該当コード:**
```python
# _fill_template_sections で対応しているセクション
section_mappings = [
    (r"(#{1,6}\s+(?:summary|description)\s*\n)", summary),      # Summary/Description のみ
    (r"(#{1,6}\s+changes\s*\n)", changes),                      # Changes のみ
    (r"(#{1,6}\s+(?:review\s*notes?|test\s*plan)\s*\n)", "N/A"), # Review/Test のみ
]
# その他のセクション（Motivation, Related Issues等）は処理されない
```

#### 課題6: 複数テンプレートディレクトリの未対応

**問題点:**
- `.github/PULL_REQUEST_TEMPLATE/` ディレクトリ内に複数のテンプレートがある場合、`default.md` のみを検索
- テンプレート選択機能がない

**GitHubが対応しているパターン:**
```
.github/
└── PULL_REQUEST_TEMPLATE/
    ├── bug_fix.md
    ├── feature.md
    └── documentation.md  # ← これらは検出されない
```

#### 課題7: テストの不足

**問題点:**
- PRサービスに対するユニットテストが存在しない
- 様々なテンプレートパターンに対する検証が行われていない

---

## 2. 対応すべきテンプレートパターン

### 2.1 シンプルなテンプレート

```markdown
## Summary
<!-- Brief description of changes -->

## Changes
<!-- List of changes -->

## Test Plan
<!-- How was this tested? -->
```

### 2.2 詳細なテンプレート（多セクション）

```markdown
## Summary
<!-- One-line summary of the PR -->

## Motivation
<!-- Why is this change necessary? What problem does it solve? -->

## Changes
<!-- Detailed list of changes -->

## Screenshots
<!-- If applicable, add screenshots -->

## Related Issues
<!-- Link to related issues: Fixes #123 -->

## Breaking Changes
<!-- List breaking changes or write "None" -->

## Checklist
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Changelog updated
```

### 2.3 条件分岐を含むテンプレート

```markdown
## Type of Change
<!-- Check the relevant option -->
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Description
<!-- Describe your changes -->

## If Bug Fix
<!-- Skip if not applicable -->
### Root Cause
### Solution

## If New Feature
<!-- Skip if not applicable -->
### Use Case
### Implementation Details
```

### 2.4 ネストされたセクションを含むテンプレート

```markdown
# PR Summary

## Overview
Brief overview here.

## Details
### Backend Changes
- Change 1
- Change 2

### Frontend Changes
- Change A
- Change B

## Testing
### Unit Tests
### Integration Tests
### Manual Testing Steps
```

### 2.5 テーブルを含むテンプレート

```markdown
## Summary

## Impact Analysis

| Area | Impact | Notes |
|------|--------|-------|
| API  |        |       |
| UI   |        |       |
| DB   |        |       |

## Changes
```

---

## 3. 改善計画

### 3.1 フェーズ1: テンプレート解析の改善

#### 目標
任意のセクション構造を持つテンプレートを動的に解析し、構造を保持する。

#### 実装内容

**新規クラス: `TemplateParser`**

```python
@dataclass
class TemplateSection:
    """テンプレートのセクションを表すデータクラス"""
    heading: str          # 見出しテキスト（例: "## Summary"）
    heading_level: int    # 見出しレベル（1-6）
    name: str             # セクション名（例: "Summary"）
    content: str          # セクションの内容
    instructions: list[str]  # HTMLコメント内の指示
    has_checkboxes: bool  # チェックボックスを含むか
    checkboxes: list[dict]   # チェックボックスのリスト

class TemplateParser:
    """テンプレートを動的に解析するクラス"""
    
    def parse(self, template: str) -> list[TemplateSection]:
        """テンプレートをセクションに分解"""
        pass
    
    def extract_instructions(self, content: str) -> list[str]:
        """HTMLコメントから指示を抽出"""
        pass
    
    def extract_checkboxes(self, content: str) -> list[dict]:
        """チェックボックスを抽出"""
        pass
```

### 3.2 フェーズ2: LLMプロンプトの改善

#### 目標
テンプレートの構造と指示をLLMに正確に伝え、高品質な出力を得る。

#### 実装内容

**改善されたプロンプト構造:**

```python
def _build_enhanced_description_prompt(
    self,
    diff: str,
    sections: list[TemplateSection],
    task: Task,
    run: Run,
) -> str:
    """改善されたプロンプトを構築"""
    prompt_parts = [
        "Generate a Pull Request description following the EXACT template structure below.",
        "",
        "## Context",
        f"Task: {task.title or '(None)'}",
        f"Run Summary: {run.summary or '(None)'}",
        "",
        "## Diff",
        f"```diff\n{diff[:10000]}\n```",
        "",
        "## Template Sections (MUST FOLLOW EXACTLY)",
        "Fill in each section according to its instructions.",
        "Keep ALL section headings exactly as shown.",
        "Do NOT add or remove sections.",
        "",
    ]
    
    for section in sections:
        prompt_parts.append(f"### {section.heading}")
        if section.instructions:
            prompt_parts.append(f"Instructions: {'; '.join(section.instructions)}")
        if section.has_checkboxes:
            prompt_parts.append("Note: Check appropriate boxes based on the changes.")
        prompt_parts.append("")
    
    prompt_parts.extend([
        "## Output Format",
        "Output ONLY the filled template, starting with the first section heading.",
        "Do NOT include any preamble or explanation.",
    ])
    
    return "\n".join(prompt_parts)
```

### 3.3 フェーズ3: フォールバック処理の改善

#### 目標
LLM失敗時でもテンプレート構造を保持し、最低限の情報を提供する。

#### 実装内容

```python
def _generate_enhanced_fallback_description(
    self,
    diff: str,
    sections: list[TemplateSection],
    task: Task,
    run: Run,
) -> str:
    """テンプレート構造を保持したフォールバック"""
    result_parts = []
    
    # Diff分析結果を準備
    analysis = self._analyze_diff(diff)
    
    for section in sections:
        result_parts.append(section.heading)
        
        # セクション名に応じたデフォルト内容を生成
        content = self._get_default_content_for_section(
            section_name=section.name.lower(),
            analysis=analysis,
            task=task,
            run=run,
        )
        result_parts.append(content)
        result_parts.append("")
    
    return "\n".join(result_parts)

def _get_default_content_for_section(
    self,
    section_name: str,
    analysis: DiffAnalysis,
    task: Task,
    run: Run,
) -> str:
    """セクション名に応じたデフォルト内容を返す"""
    defaults = {
        "summary": run.summary or task.title or "Code changes",
        "description": run.summary or task.title or "Code changes",
        "changes": analysis.files_summary,
        "motivation": task.title or "Improvement",
        "test": "- [ ] Manual testing\n- [ ] Unit tests",
        "test plan": "- [ ] Manual testing\n- [ ] Unit tests",
        "checklist": "- [ ] Verified locally",
        "breaking": "None",
        "breaking changes": "None",
        "related": "N/A",
        "screenshots": "N/A",
    }
    
    # 部分一致で検索
    for key, value in defaults.items():
        if key in section_name:
            return value
    
    return "N/A"
```

### 3.4 フェーズ4: チェックボックス処理の追加

#### 目標
テンプレート内のチェックボックスを状況に応じて適切に処理する。

#### 実装内容

```python
def _process_checkboxes(
    self,
    checkboxes: list[dict],
    diff: str,
    run: Run,
) -> list[dict]:
    """チェックボックスの状態を推定"""
    processed = []
    
    for cb in checkboxes:
        text = cb["text"].lower()
        checked = False
        
        # テスト関連
        if "test" in text:
            checked = self._has_test_changes(diff)
        # ドキュメント関連
        elif "doc" in text:
            checked = self._has_doc_changes(diff)
        # 破壊的変更関連
        elif "breaking" in text:
            checked = False  # デフォルトはunchecked
        
        processed.append({
            "text": cb["text"],
            "checked": checked,
        })
    
    return processed
```

### 3.5 フェーズ5: 複数テンプレート対応（オプション）

#### 目標
テンプレートディレクトリ内の複数テンプレートを検出し、選択可能にする。

#### 実装内容

```python
async def _load_pr_templates(self, repo: Repo) -> dict[str, str]:
    """利用可能な全テンプレートを読み込む"""
    templates = {}
    workspace_path = Path(repo.workspace_path)
    
    # 単一テンプレートのパス
    single_paths = [
        (".github/pull_request_template.md", "default"),
        (".github/PULL_REQUEST_TEMPLATE.md", "default"),
        ("pull_request_template.md", "default"),
        ("PULL_REQUEST_TEMPLATE.md", "default"),
    ]
    
    for path, name in single_paths:
        full_path = workspace_path / path
        if full_path.exists():
            templates[name] = full_path.read_text()
            break
    
    # 複数テンプレートディレクトリ
    template_dir = workspace_path / ".github" / "PULL_REQUEST_TEMPLATE"
    if template_dir.is_dir():
        for file in template_dir.glob("*.md"):
            name = file.stem  # 例: "bug_fix"
            templates[name] = file.read_text()
    
    return templates
```

---

## 4. 実装優先順位

| 優先度 | フェーズ | 内容 | 工数目安 |
|--------|----------|------|----------|
| **高** | 3.1 | テンプレート解析の改善 | 2-3日 |
| **高** | 3.2 | LLMプロンプトの改善 | 1-2日 |
| **中** | 3.3 | フォールバック処理の改善 | 1-2日 |
| **中** | 3.4 | チェックボックス処理 | 1日 |
| **低** | 3.5 | 複数テンプレート対応 | 1日 |

**合計: 6-9日**

---

## 5. テスト計画

### 5.1 ユニットテスト

```python
# tests/test_pr_service_template.py

class TestTemplateParser:
    def test_parse_simple_template(self):
        """シンプルなテンプレートの解析"""
        
    def test_parse_nested_sections(self):
        """ネストされたセクションの解析"""
        
    def test_extract_html_comments(self):
        """HTMLコメント内の指示抽出"""
        
    def test_extract_checkboxes(self):
        """チェックボックスの抽出"""

class TestPRDescriptionGeneration:
    def test_generate_with_simple_template(self):
        """シンプルなテンプレートでの生成"""
        
    def test_generate_with_complex_template(self):
        """複雑なテンプレートでの生成"""
        
    def test_fallback_preserves_structure(self):
        """フォールバック時の構造保持"""
        
    def test_checkbox_processing(self):
        """チェックボックス処理"""
```

### 5.2 統合テスト

```python
class TestPRServiceIntegration:
    def test_create_pr_auto_with_template(self):
        """自動生成PRでテンプレートが適用される"""
        
    def test_regenerate_description_with_template(self):
        """Description再生成でテンプレートが適用される"""
```

---

## 6. 関連ファイル

| ファイル | 役割 |
|----------|------|
| `apps/api/src/dursor_api/services/pr_service.py` | PR生成ロジック（主要な変更対象） |
| `apps/api/src/dursor_api/routes/prs.py` | PRルート定義 |
| `docs/git_operation_design.md` | 設計ドキュメント |

---

## 7. 備考

### 今後の拡張可能性

1. **テンプレート変数対応**: `{{author}}`, `{{branch}}` などのプレースホルダー
2. **条件付きセクション**: 変更内容に応じたセクションの表示/非表示
3. **多言語対応**: 日本語テンプレートの指示解釈
4. **カスタムプロンプト**: ユーザー定義のLLMプロンプトテンプレート
