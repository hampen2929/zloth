# Coding Agent Best Practices

This document summarizes best practices for the three major coding agent CLIs: **Claude Code**, **OpenAI Codex CLI**, and **Google Gemini CLI**.

## Overview

| Feature | Claude Code | Codex CLI | Gemini CLI |
|---------|-------------|-----------|------------|
| Config File | `CLAUDE.md` | `AGENTS.md` | `GEMINI.md` |
| Settings Location | `~/.claude/settings.json` | `~/.codex/` | `~/.gemini/settings.json` |
| Custom Commands | `.claude/commands/` | Skills (`SKILL.md`) | MCP Servers |
| Context Injection | Hierarchical CLAUDE.md | Cascading AGENTS.md | `@file` syntax |

---

## Claude Code

### Configuration with CLAUDE.md

CLAUDE.md files provide context and instructions to Claude at the start of each session. They are hierarchical and can be placed at multiple levels:

- **Global**: `~/.claude/CLAUDE.md` (applies to all projects)
- **Project Root**: `./CLAUDE.md` (shared with team)
- **Subdirectories**: More specific instructions for components

#### What to Include

```markdown
# Project Context

## Tech Stack
- Backend: FastAPI (Python 3.13+)
- Frontend: Next.js 14 (TypeScript)
- Database: PostgreSQL

## Coding Standards
- Use TypeScript for all new code
- Follow existing ESLint configuration
- Write tests for all new functions

## Common Commands
- `uv run pytest` - Run tests
- `npm run build` - Build frontend
```

#### Best Practices

1. **Keep it concise** - Aim for < 300 lines; shorter is better
2. **Focus on WHAT, WHY, HOW** - Describe the tech stack, purpose, and workflows
3. **Iterate and refine** - Treat CLAUDE.md like any frequently used prompt
4. **Use `/init`** - Run `/init` to auto-generate an initial CLAUDE.md

### Prompting Best Practices

1. **Be specific and detailed**
   ```bash
   # Good
   claude "Review UserAuth.js for security vulnerabilities, focusing on JWT handling"

   # Bad
   claude "check my code"
   ```

2. **Scope conversations to one feature** - Use `/clear` when switching tasks

3. **Use planning mode for complex changes** - Align on a plan before implementation

4. **Break large tasks into steps** - Ask Claude to create a project plan in a markdown file

### Custom Commands

Store prompt templates in `.claude/commands/` directory:

```
.claude/commands/
├── review-security.md
├── add-tests.md
└── debug-loop.md
```

Access via `/` menu in the CLI.

### CLI Tips

- Use `-p` flag for headless mode (direct output)
- Pipe output: `cat data.csv | claude -p "Analyze this data"`
- Press `Escape` to stop (not `Ctrl+C`)
- Use `--mcp-debug` when debugging MCP server connections

### Context Management

- Use `/clear` to clear context when starting new tasks
- Check `/cost` to monitor token usage
- Create draft PRs for low-risk review before marking ready

---

## OpenAI Codex CLI

### Configuration with AGENTS.md

AGENTS.md is an open format for guiding coding agents, now stewarded by the Linux Foundation. Think of it as a README for agents.

#### File Discovery Hierarchy

1. **Global scope**: `~/.codex/AGENTS.md` or `AGENTS.override.md`
2. **Project scope**: Walks from project root to current directory
3. **Nearest wins**: The closest AGENTS.md to the file being edited takes precedence

#### What to Include

```markdown
# Project Structure
- `/src` - Main application code
- `/tests` - Test files
- `/docs` - Documentation

# Development Commands
- Type check: `npm run typecheck`
- Lint: `npm run lint`
- Test: `npm test`
- Build: `npm run build`

# Coding Standards
- Use TypeScript strict mode
- Prefer functional components with hooks
- Write unit tests for business logic
```

#### Best Practices

1. **Keep root file for repo-wide conventions** - Add area-specific files in subdirectories

2. **Use overrides for special cases** - Create `AGENTS.override.md` for temporary rules (e.g., release freeze)

3. **Mind the size limits** - Default limit is 32 KiB combined; split large files if needed

4. **Treat AGENTS.md like code** - Update when build steps change via PR reviews

5. **Link, don't duplicate** - Reference READMEs and design docs instead of copying

### Prompting Best Practices

1. **Less is more** - GPT-5-Codex has coding best practices built in; over-prompting reduces quality

2. **Maximize parallelism** - Never read files one-by-one unless logically unavoidable
   ```bash
   # The model should batch operations like:
   # cat, rg, sed, ls, git show, etc.
   ```

3. **Assign well-scoped tasks** - Use multiple agents simultaneously for different tasks

### Skills System

Create reusable capabilities with `SKILL.md` files:

```
skills/
└── api-testing/
    ├── SKILL.md
    ├── test-template.ts
    └── fixtures/
```

### Environment Setup

- Configure dev environments properly
- Ensure reliable testing setups
- Maintain clear documentation
- Codex agents perform best with well-configured environments

---

## Gemini CLI

### Configuration with GEMINI.md

GEMINI.md files provide instructional context to Gemini. The CLI uses a hierarchical system combining files from multiple locations.

#### Loading Order

1. **Global**: `~/.gemini/GEMINI.md`
2. **Project/Ancestor**: Searches from current directory up to project root
3. **Sub-directory**: Component-specific instructions

#### What to Include

```markdown
# Project Overview
An e-commerce platform built with Python and React.

# Coding Guidelines
- Follow PEP 8 for Python code
- Use React hooks, avoid class components
- All functions must have type hints

# Testing
- Run `pytest` for backend tests
- Run `npm test` for frontend tests
```

#### Best Practices

1. **Navigate to project folder first** - Helps Gemini load the correct GEMINI.md

2. **Use modular imports** - Break large files into components
   ```markdown
   @coding-standards.md
   @testing-guidelines.md
   ```

3. **Use `/memory refresh`** - Force reload of all GEMINI.md files after changes

4. **Use `/memory add`** - Add persistent memories on the fly

### Prompting Best Practices

1. **Be specific and contextual**
   ```bash
   # Good
   "Refactor the authentication module to use JWT tokens.
    Wait for my confirmation before editing files."

   # Bad
   "fix auth"
   ```

2. **Use @ for explicit context injection**
   ```bash
   "Compare @old-api.ts with @new-api.ts and list breaking changes"
   ```

3. **Create step-by-step checklists** - Ask for confirmation before major edits

### Checkpointing

Enable checkpointing for safety during multi-step edits:

- Use `/restore` to view saved snapshots
- Roll back to previous working versions
- Recommended for non-trivial tasks
- Still use git as primary safety net

### Built-in Tools

Gemini CLI includes powerful built-in tools:

- **Codebase Investigator Agent** - Analyze codebase structure
- **Edit** - Replace content in files
- **FindFiles** - Glob-based file search
- **GoogleSearch** - Web search integration
- **ReadFile/ReadFolder** - Read file contents
- **Shell** - Execute shell commands
- **WebFetch** - Fetch web content
- **WriteTodos** - Task management

### MCP Extension

Configure MCP servers in `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "github": {
      "command": "mcp-server-github",
      "args": ["--token", "ghp_xxx"]
    }
  }
}
```

### System Prompt Override

For advanced customization, use `GEMINI_SYSTEM_MD=true`:

- Place `system.md` in `.gemini/` at project root
- Full replacement of default system prompt
- Indicated by `|⌐■_■|` in the UI

---

## Cross-Tool Comparison

### Configuration File Strategy

| Aspect | Claude Code | Codex CLI | Gemini CLI |
|--------|-------------|-----------|------------|
| Recommended Length | < 300 lines | < 32 KiB total | Modular with imports |
| Override Mechanism | Nested directories | `AGENTS.override.md` | `GEMINI_SYSTEM_MD` |
| Team Sharing | Check into git | Check into git | Check into git |
| Personal Settings | `.local.json` files | N/A | Global `~/.gemini/` |

### Prompting Philosophy

| Agent | Philosophy | Key Insight |
|-------|------------|-------------|
| Claude Code | Be specific | Specificity leads to better first-attempt alignment |
| Codex CLI | Less is more | Coding best practices are built-in; avoid over-prompting |
| Gemini CLI | Be contextual | Use @ references for explicit context injection |

### Common Best Practices (All Tools)

1. **Scope conversations** - One feature or task per session
2. **Clear context regularly** - Avoid stale context consuming tokens
3. **Use version control** - Git is your safety net for agent-generated changes
4. **Break down large tasks** - Create plans in markdown before implementation
5. **Iterate on configuration** - Treat config files like frequently-used prompts
6. **Document environment setup** - Agents perform better with clear dev environments

---

## References

### Claude Code
- [Best practices for agentic coding](https://www.anthropic.com/engineering/claude-code-best-practices)
- [Using CLAUDE.MD files](https://claude.com/blog/using-claude-md-files)
- [Writing a good CLAUDE.md](https://www.humanlayer.dev/blog/writing-a-good-claude-md)
- [CLI Reference](https://code.claude.com/docs/en/cli-reference)

### OpenAI Codex CLI
- [Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md/)
- [Codex CLI Features](https://developers.openai.com/codex/cli/features/)
- [Agent Skills](https://developers.openai.com/codex/skills/)
- [GPT-5-Codex Prompting Guide](https://cookbook.openai.com/examples/gpt-5-codex_prompting_guide)

### Gemini CLI
- [Gemini CLI Documentation](https://developers.google.com/gemini-code-assist/docs/gemini-cli)
- [Configuration Guide](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/configuration.md)
- [GEMINI.md Context Files](https://google-gemini.github.io/gemini-cli/docs/cli/gemini-md.html)
- [GitHub Repository](https://github.com/google-gemini/gemini-cli)
