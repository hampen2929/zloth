# Language Settings Design Document

This document describes the design for adding fine-grained language settings to dursor's Settings page.

## Overview

Users need the ability to configure output language for different contexts:

1. **PR-related text** - PR title, PR description, commit message
2. **Task breakdown** - Language for broken-down task titles and descriptions
3. **Run summaries** - Language for task execution summaries

## Current State Analysis

### Existing Language Infrastructure

#### Frontend Terminology (`apps/web/src/lib/terminology.ts`)
- Contains translations for UI elements in English and Japanese
- Currently not dynamically switchable - translations exist but no selection mechanism
- Location: `apps/web/src/lib/terminology.ts:1-263`

#### Current UserPreferences Model
- Backend model: `apps/api/src/dursor_api/domain/models.py:479-496`
- Database schema: `apps/api/src/dursor_api/storage/schema.sql:109-119`
- Frontend types: `apps/web/src/types.ts:241-256`
- DAO: `apps/api/src/dursor_api/storage/dao.py:811-910`
- API routes: `apps/api/src/dursor_api/routes/preferences.py:1-38`
- Settings UI: `apps/web/src/components/SettingsModal.tsx` (DefaultsTab function at line 510+)

### Text Generation Locations

#### 1. PR Title & Description Generation
- Location: `apps/api/src/dursor_api/services/pr_service.py:583-710`
- Method: `_generate_title_and_description()`
- Uses LLM executors (Claude Code, Codex, Gemini) to generate content
- Current prompts are in English with no language configuration

#### 2. Commit Message Generation
- Location: `apps/api/src/dursor_api/services/commit_message.py:1-110`
- Method: `ensure_english_commit_message()`
- **Current policy**: Commit messages MUST be in English (line 5-6)
- Auto-translates CJK characters to English using LLM

#### 3. Task Breakdown
- Location: `apps/api/src/dursor_api/services/breakdown_service.py:1-168`
- Templates: `BREAKDOWN_INSTRUCTION_TEMPLATE` (v1) and `BREAKDOWN_INSTRUCTION_TEMPLATE_V2` (v2)
- Currently outputs in English
- Produces: Task titles, descriptions, implementation hints, subtasks

#### 4. Run Summary
- Location: `apps/api/src/dursor_api/services/run_service.py:650-760`
- Summary priority (line 657-659):
  1. Agent-generated file (`.dursor-summary.md`)
  2. CLI output summary
  3. Auto-generated from file changes
- Currently no language preference applied

## Proposed Design

### Language Options

```typescript
type OutputLanguage = 'en' | 'ja' | 'zh' | 'auto';
```

- `en`: English
- `ja`: Japanese
- `zh`: Chinese
- `auto`: Follow user's instruction language (detect from input)

### New Preference Fields

#### Backend Model Changes

**File: `apps/api/src/dursor_api/domain/models.py`**

```python
class UserPreferences(BaseModel):
    """User preferences for default settings."""

    default_repo_owner: str | None = None
    default_repo_name: str | None = None
    default_branch: str | None = None
    default_branch_prefix: str | None = None
    default_pr_creation_mode: PRCreationMode = PRCreationMode.CREATE

    # New language settings
    lang_pr: str | None = None           # PR title, description, commit message
    lang_breakdown: str | None = None    # Task breakdown output
    lang_summary: str | None = None      # Run summaries
```

**File: `apps/api/src/dursor_api/domain/enums.py`**

```python
class OutputLanguage(str, Enum):
    """Output language options."""
    ENGLISH = "en"
    JAPANESE = "ja"
    CHINESE = "zh"
    AUTO = "auto"
```

#### Database Schema Changes

**File: `apps/api/src/dursor_api/storage/schema.sql`**

```sql
-- Add to user_preferences table
ALTER TABLE user_preferences ADD COLUMN lang_pr TEXT;          -- 'en' | 'ja' | 'zh' | 'auto'
ALTER TABLE user_preferences ADD COLUMN lang_breakdown TEXT;   -- 'en' | 'ja' | 'zh' | 'auto'
ALTER TABLE user_preferences ADD COLUMN lang_summary TEXT;     -- 'en' | 'ja' | 'zh' | 'auto'
```

#### Frontend Type Changes

**File: `apps/web/src/types.ts`**

```typescript
export type OutputLanguage = 'en' | 'ja' | 'zh' | 'auto';

export interface UserPreferences {
  default_repo_owner: string | null;
  default_repo_name: string | null;
  default_branch: string | null;
  default_branch_prefix: string | null;
  default_pr_creation_mode: PRCreationMode;
  // New language settings
  lang_pr: OutputLanguage | null;
  lang_breakdown: OutputLanguage | null;
  lang_summary: OutputLanguage | null;
}
```

### UI Changes

#### Settings Modal - New "Language" Tab or Section

**File: `apps/web/src/components/SettingsModal.tsx`**

Add a new "Language" tab (or section within Defaults tab) with three dropdowns:

```
+---------------------------------------------+
| Language Settings                           |
+---------------------------------------------+
|                                             |
| PR & Commit Language:                       |
| [English ▼]                                 |
| For PR titles, descriptions, commit msgs    |
|                                             |
| Task Breakdown Language:                    |
| [Follow Input ▼]                            |
| For broken-down task titles & descriptions  |
|                                             |
| Summary Language:                           |
| [Follow Input ▼]                            |
| For run execution summaries                 |
|                                             |
+---------------------------------------------+
```

Options per dropdown:
- English (default for PR/Commit)
- Japanese
- Chinese
- Follow Input (auto-detect from user instruction)

### Service Layer Changes

#### 1. PR Service Updates

**File: `apps/api/src/dursor_api/services/pr_service.py`**

Modify `_generate_title_and_description()` to accept language preference:

```python
async def _generate_title_and_description(
    self,
    run: Run,
    worktree_path: Path,
    diff: str,
    template: str | None,
    lang: str = "en",  # New parameter
) -> tuple[str, str]:
    # Add language instruction to prompt
    lang_instruction = self._get_language_instruction(lang)
    prompt_parts.append(lang_instruction)
```

Add helper method:

```python
def _get_language_instruction(self, lang: str) -> str:
    """Generate language instruction for prompts."""
    lang_map = {
        "en": "Write the output in English.",
        "ja": "Write the output in Japanese (日本語で出力してください).",
        "zh": "Write the output in Chinese (请用中文输出).",
        "auto": "Write the output in the same language as the user instruction.",
    }
    return f"\n## Language\n{lang_map.get(lang, lang_map['en'])}"
```

#### 2. Commit Message Service Updates

**File: `apps/api/src/dursor_api/services/commit_message.py`**

Option A: Keep English-only (recommended for Git convention):
- Commit messages stay in English regardless of setting
- This is a common convention for international teams

Option B: Make configurable:
- Skip `ensure_english_commit_message()` if user prefers non-English
- Add warning in UI about potential compatibility issues

**Recommendation**: Keep commit messages English by default but allow override with a warning.

#### 3. Breakdown Service Updates

**File: `apps/api/src/dursor_api/services/breakdown_service.py`**

Modify prompt templates to include language instruction:

```python
BREAKDOWN_INSTRUCTION_TEMPLATE_V2 = """
You are a software development requirements analysis expert.
...

## Output Language
{lang_instruction}

## Requirements
{content}
...
"""
```

#### 4. Run Service Updates

**File: `apps/api/src/dursor_api/services/run_service.py`**

For agent-generated summaries (`.dursor-summary.md`), the language is controlled by the instruction sent to the agent. Update the system prompt:

```python
# In _build_system_prompt or equivalent
summary_lang_instruction = self._get_summary_language_instruction(lang_summary)
```

### DAO Updates

**File: `apps/api/src/dursor_api/storage/dao.py`**

Update `UserPreferencesDAO`:

```python
async def save(
    self,
    default_repo_owner: str | None = None,
    default_repo_name: str | None = None,
    default_branch: str | None = None,
    default_branch_prefix: str | None = None,
    default_pr_creation_mode: str | None = None,
    lang_pr: str | None = None,          # New
    lang_breakdown: str | None = None,   # New
    lang_summary: str | None = None,     # New
) -> UserPreferences:
    ...
```

### API Route Updates

**File: `apps/api/src/dursor_api/routes/preferences.py`**

Update to handle new fields:

```python
@router.post("", response_model=UserPreferences)
async def save_preferences(
    data: UserPreferencesSave,
    dao: UserPreferencesDAO = Depends(get_user_preferences_dao),
) -> UserPreferences:
    return await dao.save(
        ...
        lang_pr=data.lang_pr,
        lang_breakdown=data.lang_breakdown,
        lang_summary=data.lang_summary,
    )
```

## Implementation Plan

### Phase 1: Backend Infrastructure

1. Add `OutputLanguage` enum to `domain/enums.py`
2. Update `UserPreferences` and `UserPreferencesSave` models in `domain/models.py`
3. Create database migration for new columns in `user_preferences` table
4. Update `UserPreferencesDAO` in `storage/dao.py`
5. Update preferences routes in `routes/preferences.py`

### Phase 2: Service Layer Integration

1. Add language instruction helper methods to services
2. Update `pr_service.py` - pass language to title/description generation
3. Update `breakdown_service.py` - inject language into prompt templates
4. Update `run_service.py` - include language preference in agent instructions
5. Decide on commit message policy (keep English or make configurable)

### Phase 3: Frontend Implementation

1. Update TypeScript types in `types.ts`
2. Add API client methods in `lib/api.ts`
3. Create language settings UI in `SettingsModal.tsx`
4. Add new "Language" tab or section in Defaults tab
5. Implement save/load for language preferences

### Phase 4: Testing & Documentation

1. Add unit tests for new preference fields
2. Add integration tests for language-aware generation
3. Update API documentation
4. Update user documentation

## Files to Modify

| File | Changes |
|------|---------|
| `apps/api/src/dursor_api/domain/enums.py` | Add `OutputLanguage` enum |
| `apps/api/src/dursor_api/domain/models.py` | Add language fields to `UserPreferences` |
| `apps/api/src/dursor_api/storage/schema.sql` | Add columns to `user_preferences` |
| `apps/api/src/dursor_api/storage/dao.py` | Update `UserPreferencesDAO` |
| `apps/api/src/dursor_api/routes/preferences.py` | Handle new fields |
| `apps/api/src/dursor_api/services/pr_service.py` | Add language support |
| `apps/api/src/dursor_api/services/breakdown_service.py` | Add language support |
| `apps/api/src/dursor_api/services/run_service.py` | Add language support |
| `apps/api/src/dursor_api/services/commit_message.py` | Optional: make configurable |
| `apps/web/src/types.ts` | Add `OutputLanguage` type and update interfaces |
| `apps/web/src/lib/api.ts` | Update API client if needed |
| `apps/web/src/components/SettingsModal.tsx` | Add Language settings UI |

## Considerations

### Commit Message Language

**Current behavior**: Commit messages are always translated to English (enforced in `commit_message.py`).

**Recommendation**: Keep this as the default but allow users to disable auto-translation:
- Add `lang_commit_translate: bool = True` preference
- If `False`, skip the `ensure_english_commit_message()` call
- Show warning: "Non-English commit messages may cause issues with some Git tools"

### Auto-Detection ("Follow Input")

For `auto` language mode:
- Detect primary language from the user's instruction
- Use simple heuristics (CJK character detection) or LLM-based detection
- Cache detected language per task to ensure consistency across outputs

### Fallback Behavior

If language preference is not set:
- PR/Commit: Default to English (`en`)
- Breakdown: Default to Auto (`auto`)
- Summary: Default to Auto (`auto`)

## Security Considerations

- Language preferences are user settings, not secrets
- No encryption needed for language values
- Standard input validation applies (enum validation)

## Migration Notes

- New columns should be nullable with no default in SQL
- Application defaults applied in model layer
- No data migration needed - existing users get defaults
