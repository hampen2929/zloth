# Contributing to dursor

Thank you for your interest in contributing to dursor! Please follow this guide to participate in development.

## Development Environment Setup

1. Fork & clone the repository

```bash
git clone https://github.com/hampen2929/dursor.git
cd dursor
```

2. Set up environment (see [Development Guide](docs/development.md))

```bash
# Backend
cd apps/api
uv sync --extra dev

# Frontend
cd apps/web
npm install
```

3. Configure environment variables

```bash
cp .env.example .env
# Edit .env
```

## Coding Conventions

### Python

- **Formatter**: ruff
- **Linter**: ruff
- **Type checker**: mypy (strict)
- **Line length**: 100 characters
- **Docstring**: Google style

```bash
# Run before submitting
uv run ruff check --fix src/
uv run ruff format src/
uv run mypy src/
```

### TypeScript

- **Linter**: ESLint
- **Formatter**: Prettier (Next.js default)

```bash
# Run before submitting
npm run lint
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/).

```
feat: Add new feature
fix: Bug fix
docs: Documentation changes
style: Formatting changes (no code behavior change)
refactor: Code refactoring
test: Add or fix tests
chore: Build/tooling changes
```

Examples:
```
feat: Add support for Gemini 2.0 Flash
fix: Handle empty patch response from LLM
docs: Update API documentation for runs endpoint
```

## Pull Request Workflow

### 1. Check Issues

- Check if an existing issue exists
- If not, create a new issue for discussion

### 2. Create Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-fix-name
```

### 3. Develop

- Make small commits
- Write tests
- Update documentation

### 4. Test

```bash
# Backend
cd apps/api
uv run pytest
uv run ruff check src/
uv run mypy src/

# Frontend
cd apps/web
npm run lint
```

### 5. Create Pull Request

- Use Conventional Commits format for title
- Describe changes and reasoning
- Link related issues

### PR Template

```markdown
## Summary
Brief description of the change

## Changes
- Change 1
- Change 2

## How to Test
1. Step 1
2. Step 2

## Checklist
- [ ] Added/updated tests
- [ ] Updated documentation
- [ ] Passed lint and type checks
```

## Development Priorities

### v0.1 Scope
- Bug fixes
- Documentation improvements
- Existing feature enhancements

### v0.2 Planned
- Docker sandbox
- GitHub App authentication
- Review/Meta agent

## Issue Reporting

### Bug Reports

```markdown
## Summary
Brief description

## Steps to Reproduce
1. Step 1
2. Step 2

## Expected Behavior
What should happen

## Actual Behavior
What happened

## Environment
- OS:
- Python:
- Node.js:
- Docker:
```

### Feature Requests

```markdown
## Summary
What feature you want

## Motivation
Why you need this feature

## Proposed Solution
How it should be implemented (if known)
```

## Code Review

Reviewers will check:

- [ ] Feature works correctly
- [ ] Sufficient test coverage
- [ ] Follows coding conventions
- [ ] No security issues
- [ ] No performance issues
- [ ] Documentation updated

## License

Contributed code is released under the [MIT License](LICENSE).

## Questions & Discussions

- GitHub Issues: Bug reports & feature requests
- GitHub Discussions: Questions & discussions

Thank you for your contribution!
