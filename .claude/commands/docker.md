# Docker Management

Manage Docker containers for the dursor project.

## Instructions

### Common Commands

**Start services:**
```bash
docker compose up -d --build
```

**View logs:**
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api
docker compose logs -f web
```

**Stop services:**
```bash
docker compose down
```

**Rebuild without cache:**
```bash
docker compose build --no-cache
```

**Check status:**
```bash
docker compose ps
```

**Clean up:**
```bash
docker compose down -v  # Remove volumes too
docker system prune -f  # Clean unused resources
```

## User Request

$ARGUMENTS

## Task

1. Determine the Docker operation needed
2. Execute the appropriate command(s)
3. Report the result and status of services
4. For logs, show relevant output
