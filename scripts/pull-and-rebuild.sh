#!/bin/bash
set -Eeuo pipefail

echo "Pulling latest changes from GitHub and rebuilding containers..."

PROJECT_DIR="/var/www/airco-fintech"
cd "$PROJECT_DIR"

# Pull latest changes
echo "Pulling latest changes from main branch..."
git pull origin main

# Set compose project name
export COMPOSE_PROJECT_NAME=airco-fintech

# Determine compose command
if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose -f docker-compose.prod.yml"
elif docker compose version >/dev/null 2>&1; then
    COMPOSE="docker compose -f docker-compose.prod.yml"
else
    echo "docker-compose / docker compose not found"
    exit 1
fi

# Stop containers
echo "Stopping current containers..."
$COMPOSE down --remove-orphans || true

# Rebuild images with latest code
echo "Rebuilding Docker images..."
$COMPOSE build --no-cache backend frontend

# Start containers
echo "Starting containers..."
$COMPOSE up -d --remove-orphans backend frontend

# Wait for health checks
echo "Waiting for services to become healthy..."
backend_health=missing
frontend_health=missing
for i in 1 2 3 4 5 6 7 8 9 10; do
    backend_health=$(docker inspect -f '{{.State.Health.Status}}' fintech_backend 2>/dev/null || echo missing)
    frontend_health=$(docker inspect -f '{{.State.Health.Status}}' fintech_frontend 2>/dev/null || echo missing)

    echo "Backend health: $backend_health"
    echo "Frontend health: $frontend_health"

    if [ "$backend_health" = "healthy" ] && [ "$frontend_health" = "healthy" ]; then
        break
    fi

    sleep 6
done

# Show container status
echo "Container status:"
$COMPOSE ps

# Reload nginx if present
if docker ps --format '{{.Names}}' | grep -qx 'nginx-gateway'; then
    echo "Reloading shared nginx gateway..."
    docker exec nginx-gateway nginx -s reload
else
    echo "Shared nginx gateway not found; skipping reload."
fi

# Final health check
if [ "$backend_health" != "healthy" ]; then
    echo "Backend failed health check"
    exit 1
fi

if [ "$frontend_health" != "healthy" ] && [ "$frontend_health" != "starting" ]; then
    echo "Frontend failed health check"
    exit 1
fi

echo "Deployment completed successfully!"
