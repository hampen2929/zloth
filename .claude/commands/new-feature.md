# New Feature Scaffolding

Create boilerplate code for new features in the dursor project.

## Instructions

### New API Endpoint

Files to create/modify:

1. **Domain model** (if needed)
   - `apps/api/src/dursor_api/domain/models.py`

2. **Database schema** (if needed)
   - `apps/api/src/dursor_api/storage/schema.sql`

3. **DAO** (Data Access Object)
   - `apps/api/src/dursor_api/storage/dao.py`

4. **Service** (Business logic)
   - `apps/api/src/dursor_api/services/{feature}_service.py`

5. **Route** (API endpoints)
   - `apps/api/src/dursor_api/routes/{feature}.py`

6. **Register router**
   - `apps/api/src/dursor_api/main.py`

7. **Dependency injection**
   - `apps/api/src/dursor_api/dependencies.py`

### New Frontend Page

Files to create/modify:

1. **Page component**
   - `apps/web/src/app/{feature}/page.tsx`

2. **Components**
   - `apps/web/src/components/{Feature}Component.tsx`

3. **Types**
   - `apps/web/src/types.ts`

4. **API client**
   - `apps/web/src/lib/api.ts`

### New LLM Provider

Files to modify:

1. **Add to Provider enum**
   - `apps/api/src/dursor_api/domain/enums.py`

2. **Implement in LLMClient**
   - `apps/api/src/dursor_api/agents/llm_router.py`

## User Request

$ARGUMENTS

## Task

1. Understand what type of feature the user wants to create
2. Ask clarifying questions if needed (feature name, endpoints, etc.)
3. Create the necessary files with proper boilerplate
4. Follow existing code patterns and conventions
5. Add appropriate type annotations
6. Suggest next steps for implementing the feature
