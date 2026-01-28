# Code Review

Perform code review on changes in the dursor project.

## Instructions

Review the specified code changes and provide feedback on:

1. **Code Quality**
   - Follows project conventions (ruff for Python, ESLint for TypeScript)
   - Proper error handling
   - No security vulnerabilities

2. **Architecture**
   - Follows the layered architecture (routes -> services -> dao)
   - Proper separation of concerns
   - Consistent with existing patterns

3. **Types and Models**
   - Proper type annotations (Python: mypy strict, TypeScript: strict)
   - Pydantic models for API contracts
   - Proper use of domain enums

4. **Testing**
   - Test coverage for new functionality
   - Edge cases handled

5. **Security**
   - No hardcoded secrets
   - Proper input validation
   - Forbidden paths respected (.git, .env, etc.)

## User Request

$ARGUMENTS

## Task

1. Get the changes to review:
   - If a PR number is provided, fetch PR details
   - If a file path is provided, read the file
   - If nothing specified, use `git diff` for uncommitted changes
2. Analyze the code against the criteria above
3. Provide specific, actionable feedback
4. Highlight both issues and good practices
