# Contributing to zloth

Thank you for your interest in zloth!

## How to Contribute

### Bug Reports & Feature Requests (Welcome!)

We actively welcome bug reports and feature requests via [GitHub Issues](https://github.com/hampen2929/zloth/issues).

#### Bug Reports

Please include:
- Summary of the issue
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, Node.js version, Docker version)
- Relevant logs or error messages

#### Feature Requests

Please include:
- Summary of the feature
- Motivation / use case
- Proposed solution (if any)

### Pull Requests

> **Note**: This project is primarily developed using AI-assisted coding. Pull requests may not be reviewed or merged in a timely manner (or at all).

If you still wish to submit a PR:
- There is no guarantee of review or merge
- Consider opening an Issue first to discuss your idea
- PRs for typo fixes or documentation improvements are more likely to be reviewed

## Development Reference

If you want to run zloth locally for testing or personal use:

### Setup

```bash
# Clone
git clone https://github.com/hampen2929/zloth.git
cd zloth

# Backend
cd apps/api
uv sync --extra dev

# Frontend
cd apps/web
npm install

# Configure
cp .env.example .env
# Edit .env
```

### Running Tests

```bash
# Backend
cd apps/api
uv run pytest
uv run ruff check src/
uv run mypy src/

# Frontend
cd apps/web
npm run lint
npm run build
```

## License

This project is licensed under the [Apache License 2.0](LICENSE).

## Questions

For questions and discussions, please use [GitHub Issues](https://github.com/hampen2929/zloth/issues).
