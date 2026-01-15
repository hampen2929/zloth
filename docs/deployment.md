# Production Deployment Guide

This guide covers deploying dursor in a production environment.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Security Considerations](#security-considerations)
- [Docker Deployment](#docker-deployment)
- [Manual Deployment](#manual-deployment)
- [Reverse Proxy Setup](#reverse-proxy-setup)
- [SSL/TLS Configuration](#ssltls-configuration)
- [Environment Configuration](#environment-configuration)
- [Monitoring and Logging](#monitoring-and-logging)
- [Backup and Recovery](#backup-and-recovery)

## Prerequisites

- Docker 20.10+ and Docker Compose v2
- Or: Python 3.13+, Node.js 20+, and a process manager (systemd, PM2)
- A domain name (for HTTPS)
- SSL certificate (Let's Encrypt or commercial)
- GitHub App configured with appropriate permissions

## Security Considerations

Before deploying to production, address these security requirements:

### 1. Encryption Key

Generate a strong encryption key for API key storage:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Store this key securely. **Never commit it to version control.**

### 2. Network Security

- Deploy behind a reverse proxy (nginx, Caddy, Traefik)
- Use HTTPS for all connections
- Restrict direct access to API and database ports
- Consider using a firewall (ufw, iptables)

### 3. GitHub App Security

- Use a GitHub App instead of Personal Access Tokens
- Grant minimum required permissions (Contents, Pull requests)
- Store the private key securely
- Rotate keys periodically

### 4. Database Security

- SQLite file should not be exposed to the network
- Set appropriate file permissions (600 or 640)
- Regular backups with encryption

## Docker Deployment

### Basic Docker Compose Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/hampen2929/dursor.git
   cd dursor
   ```

2. **Create production environment file**:
   ```bash
   cp .env.example .env.production
   ```

3. **Configure environment variables**:
   ```bash
   # .env.production
   DURSOR_ENCRYPTION_KEY=your_generated_key
   DURSOR_GITHUB_APP_ID=your_app_id
   DURSOR_GITHUB_APP_PRIVATE_KEY=base64_encoded_private_key
   DURSOR_GITHUB_APP_INSTALLATION_ID=your_installation_id
   DURSOR_DEBUG=false
   DURSOR_LOG_LEVEL=INFO
   ```

4. **Create production Docker Compose override**:
   ```yaml
   # docker-compose.prod.yml
   version: '3.8'

   services:
     api:
       restart: always
       environment:
         - DURSOR_DEBUG=false
         - DURSOR_LOG_LEVEL=INFO
       volumes:
         - ./data:/app/data
         - ./workspaces:/app/workspaces
       healthcheck:
         test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
         interval: 30s
         timeout: 10s
         retries: 3

     web:
       restart: always
       environment:
         - NODE_ENV=production
   ```

5. **Start the services**:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d
   ```

### Docker Compose with Traefik

For automatic HTTPS with Let's Encrypt:

```yaml
# docker-compose.traefik.yml
version: '3.8'

services:
  traefik:
    image: traefik:v2.10
    command:
      - "--api.insecure=false"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
      - "--certificatesresolvers.letsencrypt.acme.email=your-email@example.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./letsencrypt:/letsencrypt
    restart: always

  api:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.api.rule=Host(`api.yourdomain.com`)"
      - "traefik.http.routers.api.entrypoints=websecure"
      - "traefik.http.routers.api.tls.certresolver=letsencrypt"
      - "traefik.http.services.api.loadbalancer.server.port=8000"

  web:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.web.rule=Host(`yourdomain.com`)"
      - "traefik.http.routers.web.entrypoints=websecure"
      - "traefik.http.routers.web.tls.certresolver=letsencrypt"
      - "traefik.http.services.web.loadbalancer.server.port=3000"
```

## Manual Deployment

### API Server (systemd)

1. **Create a systemd service file**:
   ```ini
   # /etc/systemd/system/dursor-api.service
   [Unit]
   Description=dursor API Server
   After=network.target

   [Service]
   Type=simple
   User=dursor
   Group=dursor
   WorkingDirectory=/opt/dursor/apps/api
   EnvironmentFile=/opt/dursor/.env
   ExecStart=/home/dursor/.local/bin/uv run python -m dursor_api.main
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

2. **Enable and start the service**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable dursor-api
   sudo systemctl start dursor-api
   ```

### Frontend (PM2 or systemd)

Using PM2:
```bash
cd /opt/dursor/apps/web
npm run build
pm2 start npm --name "dursor-web" -- start
pm2 save
pm2 startup
```

Using systemd:
```ini
# /etc/systemd/system/dursor-web.service
[Unit]
Description=dursor Web Frontend
After=network.target

[Service]
Type=simple
User=dursor
Group=dursor
WorkingDirectory=/opt/dursor/apps/web
Environment=NODE_ENV=production
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Reverse Proxy Setup

### nginx Configuration

```nginx
# /etc/nginx/sites-available/dursor
upstream dursor_api {
    server 127.0.0.1:8000;
}

upstream dursor_web {
    server 127.0.0.1:3000;
}

server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";

    # API proxy
    location /v1/ {
        proxy_pass http://dursor_api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (if needed)
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Frontend proxy
    location / {
        proxy_pass http://dursor_web;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Caddy Configuration

```caddyfile
# Caddyfile
yourdomain.com {
    # API
    handle /v1/* {
        reverse_proxy localhost:8000
    }

    # Frontend
    handle {
        reverse_proxy localhost:3000
    }
}
```

## SSL/TLS Configuration

### Using Let's Encrypt with Certbot

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d yourdomain.com -d api.yourdomain.com

# Auto-renewal is configured automatically
# Test renewal
sudo certbot renew --dry-run
```

### Certificate Renewal

Add to crontab:
```bash
0 12 * * * /usr/bin/certbot renew --quiet
```

## Environment Configuration

### Production Environment Variables

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| `DURSOR_ENCRYPTION_KEY` | Fernet key for API key encryption | Yes | Generated key |
| `DURSOR_GITHUB_APP_ID` | GitHub App ID | Yes | `123456` |
| `DURSOR_GITHUB_APP_PRIVATE_KEY` | Base64-encoded private key | Yes | `LS0tLS...` |
| `DURSOR_GITHUB_APP_INSTALLATION_ID` | Installation ID | Yes | `12345678` |
| `DURSOR_DEBUG` | Enable debug mode | No | `false` |
| `DURSOR_LOG_LEVEL` | Log verbosity | No | `INFO` |
| `DURSOR_CLAUDE_CLI_PATH` | Path to Claude CLI | No | `/usr/local/bin/claude` |
| `DURSOR_CODEX_CLI_PATH` | Path to Codex CLI | No | `/usr/local/bin/codex` |
| `DURSOR_GEMINI_CLI_PATH` | Path to Gemini CLI | No | `/usr/local/bin/gemini` |

### Encoding the GitHub App Private Key

```bash
# Encode the private key to base64
cat your-github-app.private-key.pem | base64 -w 0 > private-key-base64.txt

# Use this value for DURSOR_GITHUB_APP_PRIVATE_KEY
```

## Monitoring and Logging

### Log Configuration

Set log level via environment variable:
```bash
DURSOR_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

### Log Aggregation

For Docker deployments, use a logging driver:
```yaml
services:
  api:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

Or use a centralized logging solution (ELK, Loki, etc.):
```yaml
services:
  api:
    logging:
      driver: "fluentd"
      options:
        fluentd-address: "localhost:24224"
        tag: "dursor.api"
```

### Health Checks

The API provides a health endpoint:
```bash
curl http://localhost:8000/health
```

Use this for monitoring:
- Uptime monitoring (e.g., UptimeRobot, Pingdom)
- Container orchestration health checks
- Load balancer health probes

## Backup and Recovery

### Database Backup

SQLite database backup script:
```bash
#!/bin/bash
# backup.sh
BACKUP_DIR=/backups/dursor
DATE=$(date +%Y%m%d_%H%M%S)
DB_FILE=/opt/dursor/data/dursor.db

mkdir -p $BACKUP_DIR

# Create backup using SQLite online backup
sqlite3 $DB_FILE ".backup '$BACKUP_DIR/dursor_$DATE.db'"

# Compress
gzip $BACKUP_DIR/dursor_$DATE.db

# Remove backups older than 30 days
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete
```

Add to crontab for daily backups:
```bash
0 2 * * * /opt/dursor/scripts/backup.sh
```

### Workspace Backup

Workspaces contain git clones and can be regenerated. For disaster recovery:
```bash
# Backup workspaces
tar -czf workspaces_backup.tar.gz /opt/dursor/workspaces/
```

### Recovery Procedure

1. Stop services:
   ```bash
   docker compose down
   # or
   sudo systemctl stop dursor-api dursor-web
   ```

2. Restore database:
   ```bash
   gunzip -c /backups/dursor/dursor_YYYYMMDD_HHMMSS.db.gz > /opt/dursor/data/dursor.db
   ```

3. Restore workspaces (if backed up):
   ```bash
   tar -xzf workspaces_backup.tar.gz -C /
   ```

4. Start services:
   ```bash
   docker compose up -d
   # or
   sudo systemctl start dursor-api dursor-web
   ```

## Scaling Considerations

### Current Limitations (v0.1)

- Single SQLite database (not suitable for multi-instance deployment)
- File-based workspace storage (requires shared filesystem for scaling)
- In-memory task queuing

### Future Scaling Options (v0.2+)

- PostgreSQL for multi-instance database
- Shared workspace storage (NFS, S3)
- Redis for task queue and caching
- Horizontal API scaling with load balancer

## Checklist

Before going live, verify:

- [ ] Encryption key generated and stored securely
- [ ] GitHub App configured with minimum permissions
- [ ] HTTPS enabled with valid certificate
- [ ] Reverse proxy configured
- [ ] Firewall rules restrict direct access to services
- [ ] Automated backups configured
- [ ] Log aggregation set up
- [ ] Health monitoring enabled
- [ ] Environment variables secured (not in version control)
- [ ] Services configured to restart on failure
