# Docker Deployment Guide for BunTool

## Overview

This guide provides step-by-step instructions for building, deploying, and maintaining BunTool using Docker in various environments.

## Prerequisites

- Docker 20.10 or higher
- Docker Compose 1.29 or higher (for compose deployments)
- 2GB minimum disk space for the image
- 4GB RAM minimum for the container

## Quick Start

### 1. Using Docker Compose (Easiest)

```bash
cd /path/to/buntool
docker-compose up -d
```

Access the application at: http://localhost:7001

### 2. Using Docker CLI

```bash
# Build the image
docker build -t buntool:latest .

# Run the container
docker run -d \
  --name buntool \
  -p 7001:7001 \
  -v buntool_tempfiles:/app/tempfiles \
  -v buntool_logs:/app/logs \
  buntool:latest
```

## Docker File Contents

### Dockerfile
- **Base Image**: `python:3.11-slim` (minimalist, ~150MB)
- **System Dependencies**:
  - `pdftk-java`: PDF manipulation tool
  - `ghostscript`: PostScript/PDF rendering
  - `texlive-latex-*`: LaTeX for page numbering
  - Build tools for Python packages
- **Python Dependencies**: All packages from requirements.txt
- **Port**: 7001 (Flask development server via waitress)
- **Health Check**: HTTP endpoint validation every 30 seconds

### docker-compose.yml
- Service: `buntool`
- Port mapping: `7001:7001`
- Volumes for persistent data
- Restart policy: `unless-stopped`
- Health check enabled

## Environment-Specific Deployment

### Development Environment

```bash
# Build with caching disabled (fresh build)
docker build --no-cache -t buntool:dev .

# Run with interactive logging
docker-compose up  # (without -d)

# Stop with Ctrl+C
```

### Staging Environment

```bash
# Tag the image for staging
docker build -t buntool:staging .

# Run with resource limits
docker run -d \
  --name buntool-staging \
  -p 7001:7001 \
  -m 2g \
  --cpus="1" \
  -v buntool_tempfiles:/app/tempfiles \
  -v buntool_logs:/app/logs \
  buntool:staging
```

### Production Environment

#### Using Docker Swarm

```bash
# Initialize swarm
docker swarm init

# Create a production compose file (docker-compose-prod.yml)
version: '3.8'
services:
  buntool:
    image: buntool:v1.0
    ports:
      - "7001:7001"
    volumes:
      - buntool_tempfiles:/app/tempfiles
      - buntool_logs:/app/logs
    environment:
      - FLASK_ENV=production
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 1G
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      update_config:
        parallelism: 1
        delay: 10s
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7001/bookmark_tool"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

# Deploy to swarm
docker stack deploy -c docker-compose-prod.yml buntool
```

#### Using Kubernetes

Create `k8s-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: buntool
spec:
  replicas: 2
  selector:
    matchLabels:
      app: buntool
  template:
    metadata:
      labels:
        app: buntool
    spec:
      containers:
      - name: buntool
        image: buntool:latest
        ports:
        - containerPort: 7001
        resources:
          limits:
            memory: "2Gi"
            cpu: "1000m"
          requests:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /bookmark_tool
            port: 7001
          initialDelaySeconds: 40
          periodSeconds: 30
          timeoutSeconds: 10
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /bookmark_tool
            port: 7001
          initialDelaySeconds: 20
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: buntool-service
spec:
  selector:
    app: buntool
  ports:
  - port: 7001
    targetPort: 7001
  type: LoadBalancer
```

Deploy to Kubernetes:
```bash
kubectl apply -f k8s-deployment.yaml
```

## Volume Management

### Temporary Files Volume
- **Path in container**: `/app/tempfiles`
- **Purpose**: Stores PDFs during processing
- **Auto-cleanup**: Yes (automatic after processing)
- **Persistence**: Optional (recreated on container restart)

### Logs Volume
- **Path in container**: `/app/logs`
- **Purpose**: Application and system logs
- **Retention**: Until volume is pruned
- **Inspection**: `docker exec buntool tail -f /app/logs/*.log`

### Manual Volume Management

```bash
# List volumes
docker volume ls

# Inspect volume
docker volume inspect buntool_tempfiles

# Clean up unused volumes
docker volume prune

# Backup logs
docker run --rm -v buntool_logs:/app/logs \
  -v $(pwd):/backup alpine \
  tar czf /backup/logs-backup.tar.gz -C /app logs

# Remove specific volume
docker volume rm buntool_logs
```

## Monitoring and Debugging

### View Container Logs

```bash
# Real-time logs
docker logs -f buntool

# Last 100 lines
docker logs --tail 100 buntool

# With timestamps
docker logs -f --timestamps buntool

# Since specific time
docker logs -f --since 2026-01-22 buntool
```

### Execute Commands in Container

```bash
# Interactive shell
docker exec -it buntool bash

# Run single command
docker exec buntool ls -la /app/tempfiles

# Check Python version
docker exec buntool python3 --version

# Test pdftk
docker exec buntool pdftk --version
```

### Health Check

```bash
# Check health status
docker ps | grep buntool

# Manual health test
docker exec buntool curl -f http://localhost:7001/bookmark_tool

# Get container inspect data
docker inspect buntool | grep -A 10 "Health"
```

## Performance Optimization

### Reduce Image Size

Use multi-stage build (edit Dockerfile):

```dockerfile
# Stage 1: Builder
FROM python:3.11-slim as builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
RUN mkdir -p /app/tempfiles /app/logs
EXPOSE 7001
CMD ["python3", "app.py"]
```

Build: `docker build -f Dockerfile.multistage -t buntool:slim .`

### Resource Limits

```bash
docker run -d \
  --name buntool \
  -p 7001:7001 \
  -m 2g \
  --cpus="2" \
  --memory-swap 3g \
  --pids-limit 1000 \
  buntool:latest
```

### Network Optimization

```bash
# Create custom network
docker network create buntool-net

# Run container on network
docker run -d \
  --name buntool \
  --network buntool-net \
  -p 7001:7001 \
  buntool:latest
```

## Backup and Restore

### Backup Data

```bash
# Backup volumes
docker run --rm \
  -v buntool_logs:/app/logs \
  -v buntool_tempfiles:/app/tempfiles \
  -v $(pwd):/backup \
  alpine \
  tar czf /backup/buntool-backup.tar.gz -C /app logs tempfiles
```

### Restore Data

```bash
# Extract backup
tar xzf buntool-backup.tar.gz

# Restore to volumes
docker run --rm \
  -v buntool_logs:/app/logs \
  -v buntool_tempfiles:/app/tempfiles \
  -v $(pwd):/backup \
  alpine \
  tar xzf /backup/buntool-backup.tar.gz -C /app
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker logs buntool

# Validate image
docker run -it buntool:latest /bin/bash

# Check dependencies
docker exec buntool pdftk --version
docker exec buntool python3 -c "import pikepdf; print('OK')"
```

### Port already in use

```bash
# Find process using port 7001
lsof -i :7001

# Use different port
docker run -d -p 8080:7001 buntool:latest
```

### Out of disk space

```bash
# Check Docker disk usage
docker system df

# Clean up
docker system prune -a  # WARNING: Removes all unused images/containers
docker volume prune     # Remove unused volumes
```

### Memory issues

```bash
# Monitor resource usage
docker stats buntool

# Increase memory limit
docker update -m 4g buntool
docker restart buntool
```

## Security Best Practices

### 1. Run as Non-Root User

Edit Dockerfile:

```dockerfile
RUN useradd -m -u 1000 appuser
USER appuser
```

### 2. Use Read-Only Filesystem

```bash
docker run -d \
  --read-only \
  --tmpfs /app/tempfiles \
  --tmpfs /app/logs \
  buntool:latest
```

### 3. Network Security

```bash
# Disable host network access
docker run -d \
  --network buntool-net \
  -p 7001:7001 \
  --cap-drop=ALL \
  --cap-add=NET_BIND_SERVICE \
  buntool:latest
```

### 4. Image Scanning

```bash
# Scan for vulnerabilities (requires Snyk)
snyk container test buntool:latest

# Build with security scanning
docker build --scan -t buntool:latest .
```

## Maintenance

### Regular Updates

```bash
# Check for updates
docker pull python:3.11-slim

# Rebuild image
docker build --no-cache -t buntool:latest .

# Rolling restart
docker-compose up -d
```

### Log Rotation

Add to docker-compose.yml:

```yaml
services:
  buntool:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Scheduled Cleanup

```bash
# Create cron job
0 2 * * * docker system prune -af

# Or use Docker's built-in pruning
docker system prune --all --volumes --force
```

## Summary

| Task | Command |
|------|---------|
| Build | `docker build -t buntool:latest .` |
| Start | `docker-compose up -d` |
| Stop | `docker-compose down` |
| Logs | `docker logs -f buntool` |
| Restart | `docker restart buntool` |
| Status | `docker ps` |
| Remove | `docker-compose down -v` |

For more information, visit: [Docker Documentation](https://docs.docker.com/)
