# Language Settings Design Document

## Overview

Settings画面から言語設定を細かく設定できるようにする機能の設計ドキュメント。

## 対象となる言語設定

| 設定項目 | 説明 | 生成元 |
|---------|------|-------|
| PR関連言語 | PR title, PR description, commit message | `pr_service.py`, `run_service.py` |
| Taskの言語 | Breakdown後のTask/Backlog itemの説明 | `breakdown_service.py` |
| Summaryの言語 | Run実行後のSummary | Agent (`.dursor-summary.md`) |

## 現状分析

### 現在のアーキテクチャ

#### 1. Settings画面構造

**フロントエンド**
- `apps/web/src/components/SettingsModal.tsx` - モーダルベースのUI
- 3タブ構成: Models, GitHub App, Defaults
- 既存の用語翻訳: `apps/web/src/lib/terminology.ts` (日英対応あり)

**バックエンド**
- `apps/api/src/dursor_api/routes/preferences.py` - 設定API
- `apps/api/src/dursor_api/storage/dao.py` - UserPreferencesDAO
- `apps/api/src/dursor_api/storage/schema.sql` - user_preferencesテーブル

#### 2. 現在のテキスト生成箇所

| テキスト種別 | ファイル | メソッド | 行番号 |
|------------|---------|---------|--------|
| PR Title | `pr_service.py` | `_generate_title_and_description()` | 583 |
| PR Description | `pr_service.py` | `_generate_title_and_description()` | 583 |
| Commit Message | `run_service.py` | `_generate_commit_message()` | 775 |
| Task Breakdown | `breakdown_service.py` | `_execute_breakdown()` | 319 |
| Run Summary | Agent creates | `.dursor-summary.md` | - |

#### 3. 現在のプロンプトテンプレート

**PR Title/Description生成 (`pr_service.py`)**
```python
# Lines 663-687 - ハードコードされた英語プロンプト
TITLE_GENERATION_PROMPT = """..."""
DESCRIPTION_GENERATION_PROMPT = """..."""
```

**Task Breakdown (`breakdown_service.py`)**
```python
# Lines 96-168 - BREAKDOWN_INSTRUCTION_TEMPLATE_V2
# ハードコードされた英語プロンプト
```

**Commit Message (`commit_message.py`)**
```python
# ensure_english_commit_message() - 英語強制
# CJK文字検出時にLLMで英語に書き換え
```

## 設計方針

### 1. データベーススキーマ変更

`user_preferences`テーブルに言語設定カラムを追加:

```sql
ALTER TABLE user_preferences ADD COLUMN language_pr TEXT DEFAULT 'en';
ALTER TABLE user_preferences ADD COLUMN language_breakdown TEXT DEFAULT 'en';
ALTER TABLE user_preferences ADD COLUMN language_summary TEXT DEFAULT 'en';
```

**カラム定義:**
| カラム名 | 説明 | デフォルト | 許可値 |
|---------|------|----------|--------|
| `language_pr` | PR title, description, commit message | `'en'` | `'en'`, `'ja'` |
| `language_breakdown` | Task/Backlog itemの説明 | `'en'` | `'en'`, `'ja'` |
| `language_summary` | Run Summary | `'en'` | `'en'`, `'ja'` |

### 2. バックエンド変更

#### 2.1 Domain Models

**`apps/api/src/dursor_api/domain/models.py`**
```python
class LanguageSettings(BaseModel):
    language_pr: str = "en"
    language_breakdown: str = "en"
    language_summary: str = "en"

class UserPreferences(BaseModel):
    # 既存フィールド...
    language_pr: str = "en"
    language_breakdown: str = "en"
    language_summary: str = "en"
```

#### 2.2 DAO更新

**`apps/api/src/dursor_api/storage/dao.py`**
- `UserPreferencesDAO.get()` - 新カラム読み込み
- `UserPreferencesDAO.upsert()` - 新カラム保存

#### 2.3 Routes更新

**`apps/api/src/dursor_api/routes/preferences.py`**
- Request/Responseスキーマに言語設定追加

#### 2.4 Service更新

**`apps/api/src/dursor_api/services/pr_service.py`**
- `_generate_title_and_description()` - 言語パラメータ追加
- プロンプトテンプレートの多言語化

**`apps/api/src/dursor_api/services/breakdown_service.py`**
- `_execute_breakdown()` - 言語パラメータ追加
- プロンプトテンプレートの多言語化

**`apps/api/src/dursor_api/services/run_service.py`**
- Summary生成プロンプトに言語指定追加
- `ensure_english_commit_message()` の条件付き呼び出し

### 3. フロントエンド変更

#### 3.1 Settings Modal更新

**`apps/web/src/components/SettingsModal.tsx`**

Defaultsタブに言語設定セクションを追加:

```tsx
// Language Settings Section
<div className="space-y-4">
  <h3>Language Settings</h3>

  {/* PR関連言語 */}
  <Select
    label="PR Language (title, description, commit)"
    options={[
      { value: 'en', label: 'English' },
      { value: 'ja', label: '日本語' }
    ]}
    value={languagePr}
    onChange={setLanguagePr}
  />

  {/* Breakdown言語 */}
  <Select
    label="Task Breakdown Language"
    options={[...]}
    value={languageBreakdown}
    onChange={setLanguageBreakdown}
  />

  {/* Summary言語 */}
  <Select
    label="Summary Language"
    options={[...]}
    value={languageSummary}
    onChange={setLanguageSummary}
  />
</div>
```

#### 3.2 API Client更新

**`apps/web/src/lib/api.ts`**
- `UserPreferences`型に言語設定追加

#### 3.3 Types更新

**`apps/web/src/types.ts`**
```typescript
interface UserPreferences {
  // 既存フィールド...
  language_pr: string;
  language_breakdown: string;
  language_summary: string;
}
```

### 4. プロンプトテンプレート多言語化

#### 4.1 PR Title/Description

```python
PR_LANGUAGE_INSTRUCTIONS = {
    "en": "Write in English.",
    "ja": "日本語で記述してください。"
}

def _get_title_prompt(language: str) -> str:
    return f"""
Generate a concise PR title for the following changes.
{PR_LANGUAGE_INSTRUCTIONS[language]}
...
"""
```

#### 4.2 Task Breakdown

```python
BREAKDOWN_LANGUAGE_INSTRUCTIONS = {
    "en": "Write all task descriptions in English.",
    "ja": "全てのタスク説明を日本語で記述してください。"
}
```

#### 4.3 Summary

```python
SUMMARY_LANGUAGE_INSTRUCTIONS = {
    "en": "Write the summary in English.",
    "ja": "サマリーを日本語で記述してください。"
}
```

## 実装計画

### Phase 1: バックエンド基盤

1. **スキーマ更新**
   - `schema.sql`に新カラム追加
   - マイグレーション対応

2. **Domain Models更新**
   - `models.py`に言語設定追加

3. **DAO更新**
   - `UserPreferencesDAO`更新

4. **Routes更新**
   - API Request/Response更新

### Phase 2: プロンプト多言語化

1. **言語定義ファイル作成**
   - `apps/api/src/dursor_api/prompts/languages.py`

2. **PR Service更新**
   - プロンプトテンプレート多言語化
   - 言語パラメータ追加

3. **Breakdown Service更新**
   - プロンプトテンプレート多言語化
   - 言語パラメータ追加

4. **Run Service更新**
   - Summary生成の言語対応
   - Commit message言語対応

### Phase 3: フロントエンド

1. **Types更新**
   - `types.ts`更新

2. **API Client更新**
   - `api.ts`更新

3. **Settings Modal更新**
   - 言語選択UI追加

### Phase 4: テストとドキュメント

1. **テスト追加**
   - Service単体テスト
   - API統合テスト

2. **ドキュメント更新**
   - CLAUDE.md更新

## ファイル変更一覧

| ファイル | 変更種別 | 説明 |
|---------|---------|------|
| `apps/api/src/dursor_api/storage/schema.sql` | 更新 | 言語設定カラム追加 |
| `apps/api/src/dursor_api/domain/models.py` | 更新 | UserPreferencesに言語設定追加 |
| `apps/api/src/dursor_api/storage/dao.py` | 更新 | UserPreferencesDAO更新 |
| `apps/api/src/dursor_api/routes/preferences.py` | 更新 | API更新 |
| `apps/api/src/dursor_api/prompts/languages.py` | 新規 | 言語定義 |
| `apps/api/src/dursor_api/services/pr_service.py` | 更新 | 言語対応 |
| `apps/api/src/dursor_api/services/breakdown_service.py` | 更新 | 言語対応 |
| `apps/api/src/dursor_api/services/run_service.py` | 更新 | 言語対応 |
| `apps/web/src/types.ts` | 更新 | 型定義追加 |
| `apps/web/src/lib/api.ts` | 更新 | API型更新 |
| `apps/web/src/components/SettingsModal.tsx` | 更新 | UI追加 |

## UI設計

### Settings Modal - Language Settings

```
┌─────────────────────────────────────────────────────────┐
│  Settings                                          [×]  │
├─────────────────────────────────────────────────────────┤
│  [Models]  [GitHub App]  [Defaults]                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Repository Settings                                    │
│  ├─ Default Repository: [owner/repo        ▼]          │
│  ├─ Default Branch:     [main              ▼]          │
│  └─ Branch Prefix:      [feature/          ▼]          │
│                                                         │
│  PR Settings                                            │
│  └─ Default PR Mode:    [○ Create  ● Link]             │
│                                                         │
│  ─────────────────────────────────────────────────────  │
│                                                         │
│  Language Settings                                      │
│  ├─ PR Language:        [English           ▼]          │
│  │   (title, description, commit message)              │
│  │                                                      │
│  ├─ Task Language:      [English           ▼]          │
│  │   (breakdown task descriptions)                     │
│  │                                                      │
│  └─ Summary Language:   [English           ▼]          │
│      (run execution summary)                           │
│                                                         │
│                                      [Cancel] [Save]    │
└─────────────────────────────────────────────────────────┘
```

## 注意事項

### 後方互換性
- 既存のデータベースは`ALTER TABLE`で対応
- デフォルト値は`'en'`（現在の動作を維持）

### 拡張性
- 言語コードは`'en'`, `'ja'`から開始
- 将来的に他言語追加可能な設計

### 制限事項
- コミットメッセージの言語を日本語にした場合、Git履歴で文字化けする環境がある可能性
- LLMの言語能力に依存するため、出力品質は言語によって異なる可能性
