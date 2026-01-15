# Troubleshooting Guide

This guide covers common issues and their solutions when using dursor.

## Table of Contents

- [Installation Issues](#installation-issues)
- [API Server Issues](#api-server-issues)
- [Frontend Issues](#frontend-issues)
- [Docker Issues](#docker-issues)
- [GitHub Integration Issues](#github-integration-issues)
- [LLM Provider Issues](#llm-provider-issues)
- [Database Issues](#database-issues)

## Installation Issues

### Python version mismatch

**Symptom**: `uv sync` fails with Python version error.

**Solution**: dursor requires Python 3.13+. Check your version:
```bash
python --version
# or
python3 --version
```

Install Python 3.13+ if needed. Consider using [pyenv](https://github.com/pyenv/pyenv) to manage Python versions.

### Node.js version mismatch

**Symptom**: `npm install` fails or frontend build errors.

**Solution**: dursor requires Node.js 20+. Check your version:
```bash
node --version
```

Use [nvm](https://github.com/nvm-sh/nvm) to install and manage Node.js versions:
```bash
nvm install 20
nvm use 20
```

### uv not found

**Symptom**: `uv: command not found`

**Solution**: Install uv (Python package manager):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then restart your terminal or run:
```bash
source ~/.bashrc  # or ~/.zshrc
```

## API Server Issues

### Server fails to start

**Symptom**: API server crashes on startup.

**Possible causes and solutions**:

1. **Missing environment variables**
   ```bash
   # Check .env file exists and has required variables
   cat .env | grep DURSOR_ENCRYPTION_KEY
   ```

   Generate an encryption key if missing:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

2. **Port already in use**
   ```bash
   # Check if port 8000 is in use
   lsof -i :8000

   # Kill the process or use a different port
   DURSOR_API_PORT=8001 uv run python -m dursor_api.main
   ```

3. **Database file permissions**
   ```bash
   # Check data directory permissions
   ls -la data/

   # Create directory if missing
   mkdir -p data
   chmod 755 data
   ```

### API returns 500 Internal Server Error

**Symptom**: API calls fail with 500 errors.

**Solution**: Check API logs for detailed error messages:
```bash
# If running with uvicorn
uv run python -m dursor_api.main

# Enable debug mode for more details
DURSOR_DEBUG=true DURSOR_LOG_LEVEL=DEBUG uv run python -m dursor_api.main
```

### CORS errors

**Symptom**: Browser shows CORS policy errors.

**Solution**: The API server is configured to allow requests from `localhost:3000`. If using a different frontend URL, update the CORS settings in `apps/api/src/dursor_api/main.py`.

## Frontend Issues

### Build fails

**Symptom**: `npm run build` fails with errors.

**Solution**:
```bash
cd apps/web

# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install

# Clear Next.js cache
rm -rf .next

# Try building again
npm run build
```

### Page shows "Failed to fetch"

**Symptom**: Frontend shows network errors when trying to communicate with the API.

**Solution**:
1. Verify the API server is running on port 8000
2. Check browser console for detailed error messages
3. Verify `NEXT_PUBLIC_API_URL` environment variable if customized

### Styles not loading

**Symptom**: Page appears unstyled or broken.

**Solution**:
```bash
cd apps/web
rm -rf .next
npm run dev
```

## Docker Issues

### Build fails

**Symptom**: `docker compose build` fails.

**Solution**:
```bash
# Clean Docker cache and rebuild
docker compose down
docker system prune -f
docker compose build --no-cache
```

### Container exits immediately

**Symptom**: Container starts but exits right away.

**Solution**: Check container logs:
```bash
docker compose logs api
docker compose logs web
```

Common issues:
- Missing environment variables in `.env`
- Volume mount permission issues

### Volume permission issues

**Symptom**: Errors about file permissions inside containers.

**Solution**:
```bash
# Fix permissions on data and workspaces directories
sudo chown -R $USER:$USER data/ workspaces/
chmod -R 755 data/ workspaces/
```

### Network connectivity issues

**Symptom**: Containers can't communicate with each other.

**Solution**:
```bash
# Recreate the Docker network
docker compose down
docker network prune -f
docker compose up -d
```

## GitHub Integration Issues

### Cannot clone repository

**Symptom**: Repository cloning fails.

**Possible causes**:

1. **Repository doesn't exist or is private**
   - Verify the repository URL is correct
   - For private repos, ensure GitHub App or PAT has access

2. **Git not installed in container**
   ```bash
   docker compose exec api git --version
   ```

3. **Network issues**
   - Check internet connectivity
   - Verify firewall settings

### Cannot create Pull Request

**Symptom**: PR creation fails with authentication error.

**Solution**:

1. **Configure GitHub App** (recommended):
   - Go to Settings in the dursor UI
   - Enter GitHub App ID, Private Key, and Installation ID
   - Ensure the app has `Contents` and `Pull requests` permissions

2. **Using environment variables**:
   ```bash
   # Set in .env file
   DURSOR_GITHUB_APP_ID=your_app_id
   DURSOR_GITHUB_APP_PRIVATE_KEY=base64_encoded_private_key
   DURSOR_GITHUB_APP_INSTALLATION_ID=your_installation_id
   ```

### PR update fails

**Symptom**: Updating an existing PR fails.

**Solution**:
- Verify the branch still exists
- Check that the GitHub App installation has write access to the repository
- Look at the API logs for detailed error messages

## LLM Provider Issues

### API key invalid

**Symptom**: Runs fail with authentication errors.

**Solution**:
1. Verify the API key is correct in Settings
2. Check if the API key has expired or been revoked
3. Ensure the API key has the necessary permissions/scope

### Rate limiting

**Symptom**: Runs fail intermittently with rate limit errors.

**Solution**:
- Reduce the number of parallel runs
- Add delays between runs
- Upgrade your API plan for higher rate limits

### Model not available

**Symptom**: Run fails with "model not found" error.

**Solution**:
- Verify the model name is correct
- Check if you have access to the specified model
- For newer models, ensure your API account has been granted access

### CLI executors not working

**Symptom**: Claude Code, Codex, or Gemini CLI executor fails.

**Solution**:
1. Verify the CLI is installed:
   ```bash
   which claude  # or codex, gemini
   ```

2. Set the correct path in environment:
   ```bash
   DURSOR_CLAUDE_CLI_PATH=/path/to/claude
   DURSOR_CODEX_CLI_PATH=/path/to/codex
   DURSOR_GEMINI_CLI_PATH=/path/to/gemini
   ```

3. Verify the CLI is authenticated:
   ```bash
   claude --version
   codex --version
   gemini --version
   ```

## Database Issues

### Database locked

**Symptom**: "database is locked" error.

**Solution**:
```bash
# Stop all dursor processes
pkill -f dursor

# If using Docker
docker compose down

# Restart
docker compose up -d
```

### Database corruption

**Symptom**: SQLite errors about malformed database.

**Solution**:
```bash
# Backup current database
cp data/dursor.db data/dursor.db.backup

# Try to recover
sqlite3 data/dursor.db ".recover" | sqlite3 data/dursor_recovered.db

# If recovery fails, you may need to start fresh
rm data/dursor.db
# Database will be recreated on next startup
```

### Missing tables

**Symptom**: "no such table" error.

**Solution**: The database schema is automatically created on startup. If tables are missing:
```bash
# Remove the database file
rm data/dursor.db

# Restart the API server
uv run python -m dursor_api.main
```

## Getting More Help

If your issue isn't covered here:

1. **Enable debug logging**:
   ```bash
   DURSOR_DEBUG=true DURSOR_LOG_LEVEL=DEBUG
   ```

2. **Check the logs**:
   - API logs: Output from the API server
   - Docker logs: `docker compose logs -f`
   - Browser console: Press F12 in your browser

3. **Search existing issues**: [GitHub Issues](https://github.com/hampen2929/dursor/issues)

4. **Open a new issue**: Include:
   - Steps to reproduce
   - Expected vs actual behavior
   - Logs and error messages
   - Environment details (OS, Python version, Node.js version)
