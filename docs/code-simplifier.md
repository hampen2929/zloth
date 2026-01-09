# Code-Simplifier Plugin Integration Proposal

## Overview

This document outlines how to integrate the Claude Code `code-simplifier` plugin into Dursor for UI-based usage during Claude Code sessions.

## What is Code-Simplifier?

The `code-simplifier` is an official Anthropic plugin that simplifies and refines code for clarity, consistency, and maintainability while preserving exact functionality. It was developed internally by the Claude Code team and recently open-sourced.

### Core Principles

1. **Preserve Functionality** - Never changes what code does, only how it does it
2. **Apply Project Standards** - Follows coding conventions from CLAUDE.md
3. **Enhance Clarity** - Reduces complexity, eliminates redundancy, improves naming
4. **Maintain Balance** - Avoids over-simplification that reduces readability
5. **Focus Scope** - Operates on recently modified code unless instructed otherwise

### Key Capabilities

- Simplifying complex functions with nested conditionals
- Eliminating code duplication (DRY principle)
- Improving variable and function naming conventions
- Converting nested ternary operators to switch/if-else
- Operating autonomously after code modifications

## Installation

```bash
# Direct installation
claude plugin install code-simplifier

# From within Claude Code session
/plugin marketplace update claude-plugins-official
/plugin install code-simplifier
```

## Integration Proposals for Dursor

### Proposal 1: Session Start Hook (Recommended)

Automatically enable code-simplifier for all Claude Code sessions by configuring a session start hook.

#### Implementation

1. **Create a Claude settings template in workspaces**

Create `.claude/settings.json` in each workspace or repository:

```json
{
  "plugins": ["code-simplifier"],
  "hooks": {
    "SessionStart": [
      {
        "command": "echo 'Code-simplifier plugin enabled'"
      }
    ]
  }
}
```

2. **Modify ClaudeCodeExecutor to set up plugins**

Add plugin configuration to `apps/api/src/dursor_api/executors/claude_code_executor.py`:

```python
# Before execution, ensure plugin is installed
async def _ensure_plugins(self, worktree_path: Path) -> None:
    claude_dir = worktree_path / ".claude"
    claude_dir.mkdir(exist_ok=True)

    settings_file = claude_dir / "settings.json"
    settings = {
        "plugins": ["code-simplifier"]
    }
    settings_file.write_text(json.dumps(settings, indent=2))
```

#### Pros
- Zero UI changes required
- Automatic for all sessions
- Consistent experience

#### Cons
- No per-session control
- Modifies workspace files

---

### Proposal 2: Executor Configuration Option

Add plugin configuration as an executor option in the UI.

#### Implementation

1. **Add new config field**

`apps/api/src/dursor_api/config.py`:
```python
class Settings(BaseSettings):
    # ...existing fields...
    claude_plugins: list[str] = Field(
        default=["code-simplifier"],
        description="Plugins to enable for Claude Code sessions"
    )
```

2. **Update ClaudeCodeExecutor**

`apps/api/src/dursor_api/executors/claude_code_executor.py`:
```python
@dataclass
class ClaudeCodeOptions:
    claude_cli_path: str = "claude"
    plugins: list[str] = field(default_factory=list)

# In execute():
if self.options.plugins:
    for plugin in self.options.plugins:
        cmd.extend(["--plugin", plugin])
```

3. **Add UI toggle in Settings**

`apps/web/src/app/settings/page.tsx`:
```tsx
<div className="space-y-2">
  <label>Claude Code Plugins</label>
  <MultiSelect
    options={["code-simplifier", "code-review", "commit-commands"]}
    value={settings.claudePlugins}
    onChange={(plugins) => updateSettings({ claudePlugins: plugins })}
  />
</div>
```

#### Pros
- User control over plugins
- Persistent settings
- Easy to add more plugins

#### Cons
- Requires settings UI changes
- Global setting (not per-task)

---

### Proposal 3: Per-Run Plugin Selection (Most Flexible)

Allow users to select plugins for each run from the ChatPanel.

#### Implementation

1. **Extend Run model**

`apps/api/src/dursor_api/domain/models.py`:
```python
class RunCreate(BaseModel):
    instruction: str
    model_ids: list[str] | None = None
    executor_type: ExecutorType = ExecutorType.PATCH_AGENT
    message_id: str | None = None
    plugins: list[str] | None = None  # NEW: Plugin selection
```

2. **Update runs route**

`apps/api/src/dursor_api/routes/runs.py`:
```python
@router.post("/tasks/{task_id}/runs")
async def create_runs(
    task_id: str,
    body: RunCreate,
    # ...
):
    # Pass plugins to run_service
    runs = await run_service.create_runs(
        task_id=task_id,
        # ...
        plugins=body.plugins,
    )
```

3. **Add plugin selector to ChatPanel**

`apps/web/src/components/ChatPanel.tsx`:
```tsx
const [selectedPlugins, setSelectedPlugins] = useState<string[]>([]);

// Plugin chip selector
<div className="flex gap-2 mt-2">
  <Chip
    label="code-simplifier"
    selected={selectedPlugins.includes('code-simplifier')}
    onClick={() => togglePlugin('code-simplifier')}
  />
  <Chip
    label="code-review"
    selected={selectedPlugins.includes('code-review')}
    onClick={() => togglePlugin('code-review')}
  />
</div>

// Include in run creation
const handleSubmit = async () => {
  await runsApi.create(taskId, {
    instruction: message,
    executor_type: selectedExecutor,
    plugins: selectedPlugins,
  });
};
```

4. **Update executor to use plugins**

`apps/api/src/dursor_api/executors/claude_code_executor.py`:
```python
async def execute(
    self,
    worktree_path: Path,
    instruction: str,
    constraints: AgentConstraints | None = None,
    on_output: Callable[[str], Awaitable[None]] | None = None,
    resume_session_id: str | None = None,
    plugins: list[str] | None = None,  # NEW
) -> ExecutorResult:
    cmd = [self.options.claude_cli_path, "-p", instruction, ...]

    # Add plugins to command
    if plugins:
        for plugin in plugins:
            cmd.extend(["--plugin", plugin])
```

#### Pros
- Maximum flexibility
- Per-run customization
- Clear UI visibility

#### Cons
- Most implementation effort
- May add UI complexity

---

### Proposal 4: Agent-Based Approach (Alternative)

Create a dedicated "Code Simplifier" agent in Dursor that wraps the plugin functionality.

#### Implementation

1. **Create new executor type**

`apps/api/src/dursor_api/domain/enums.py`:
```python
class ExecutorType(str, Enum):
    PATCH_AGENT = "patch_agent"
    CLAUDE_CODE = "claude_code"
    CLAUDE_CODE_SIMPLIFIER = "claude_code_simplifier"  # NEW
    CODEX_CLI = "codex_cli"
    GEMINI_CLI = "gemini_cli"
```

2. **Create dedicated executor**

`apps/api/src/dursor_api/executors/simplifier_executor.py`:
```python
class CodeSimplifierExecutor(BaseExecutor):
    """Executor that runs Claude Code with code-simplifier plugin."""

    async def execute(self, ...) -> ExecutorResult:
        cmd = [
            self.options.claude_cli_path,
            "-p", instruction,
            "--plugin", "code-simplifier",
            "--dangerously-skip-permissions",
            "--verbose",
            "--output-format", "stream-json",
        ]
        # ... execution logic
```

3. **Add button to ChatPanel**

Add a "Simplify" executor option alongside existing buttons.

#### Pros
- Clear separation of concerns
- Easy to understand
- One-click access

#### Cons
- Duplicates executor code
- Less flexible than plugin selection

---

## Recommended Approach

**Proposal 2 + Proposal 3 Hybrid**:

1. **Phase 1**: Implement Proposal 2 (Settings-based default plugins)
   - Add `claudePlugins` to Settings
   - Auto-enable code-simplifier by default
   - Simple to implement

2. **Phase 2**: Implement Proposal 3 (Per-run plugin selection)
   - Add plugin selector chips to ChatPanel
   - Override defaults per-run
   - Maximum flexibility

### Implementation Priority

| Phase | Feature | Effort | Impact |
|-------|---------|--------|--------|
| 1 | Settings-based default plugins | Low | High |
| 2 | ChatPanel plugin selector | Medium | High |
| 3 | Pre-installed plugin marketplace | High | Medium |

---

## UI Mockup

### ChatPanel with Plugin Selector

```
┌─────────────────────────────────────────────────────────────┐
│                        Chat Panel                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [Message history...]                                       │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Please add error handling to the API routes         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Executor: [Patch Agent] [Claude Code ✓] [Codex] [Gemini]  │
│                                                             │
│  Plugins: [code-simplifier ✓] [code-review] [+ More...]    │
│                                                             │
│                                            [Send Message]   │
└─────────────────────────────────────────────────────────────┘
```

### Settings Page

```
┌─────────────────────────────────────────────────────────────┐
│                    Claude Code Settings                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Claude CLI Path: [claude________________]                  │
│                                                             │
│  Default Plugins:                                           │
│  ☑ code-simplifier - Code clarity and maintainability      │
│  ☐ code-review     - Automated PR code review              │
│  ☐ commit-commands - Git workflow automation               │
│                                                             │
│  [Save Settings]                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Technical Considerations

### Plugin Installation

Claude Code plugins need to be installed in the environment where the CLI runs:

```bash
# Pre-install required plugins
claude plugin install code-simplifier
claude plugin install code-review
```

For Docker deployments, add to Dockerfile:
```dockerfile
RUN claude plugin install code-simplifier
```

### Plugin Persistence

Plugins are stored in `~/.claude/plugins/` by default. Ensure this directory is persisted across container restarts.

### CLI Flag Support

Verify Claude Code CLI supports `--plugin` flag:
```bash
claude --help | grep plugin
```

If not supported, use workspace `.claude/settings.json` approach instead.

---

## References

- [Claude Code Plugins Documentation](https://code.claude.com/docs/en/plugins)
- [code-simplifier Agent](https://github.com/anthropics/claude-plugins-official/blob/main/plugins/code-simplifier/agents/code-simplifier.md)
- [Official Plugins Repository](https://github.com/anthropics/claude-plugins-official)
- [Boris Cherny's Announcement](https://x.com/bcherny/status/2009450715081789767)
