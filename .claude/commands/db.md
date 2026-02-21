# Database Management

Manage the SQLite database for the dursor project.

## Instructions

### Database Location

- Default: `data/dursor.db`
- Schema: `apps/api/src/dursor_api/storage/schema.sql`

### Common Operations

**Reset database (development):**
```bash
rm data/dursor.db
# Database is auto-created on next API start
```

**View schema:**
```bash
sqlite3 data/dursor.db ".schema"
```

**Query data:**
```bash
sqlite3 data/dursor.db "SELECT * FROM table_name LIMIT 10;"
```

**Backup:**
```bash
cp data/dursor.db data/dursor.db.backup
```

### Manual Migration Example

```sql
-- Add new column
ALTER TABLE runs ADD COLUMN new_column TEXT;
```

### Available Tables

- `model_profiles` - LLM provider configurations
- `repos` - Cloned repositories
- `tasks` - Conversation units
- `messages` - Chat messages
- `runs` - Model execution units
- `prs` - Created pull requests

## User Request

$ARGUMENTS

## Task

1. Understand what database operation is needed
2. For destructive operations, confirm with the user first
3. Execute the operation safely
4. Report the result
