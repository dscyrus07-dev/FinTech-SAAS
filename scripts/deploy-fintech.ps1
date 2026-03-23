# FinTech Deploy to Utho Server - PowerShell Script
# Usage: .\scripts\deploy-fintech.ps1 [branch]

param(
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"

Write-Host "FinTech Deploy to Utho Server" -ForegroundColor Green
Write-Host "==============================" -ForegroundColor Green

$Server = "root@134.195.138.56"
$ProjectDir = "/var/www/airco-fintech"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$TempArchive = Join-Path ([System.IO.Path]::GetTempPath()) "fintech-deploy-$Timestamp.tar.gz"
$TempScript = Join-Path ([System.IO.Path]::GetTempPath()) "fintech-remote-$Timestamp.sh"
$SshKey = "$env:USERPROFILE\.ssh\id_ed25519"

Write-Host "Server: $Server" -ForegroundColor Cyan
Write-Host "Project: $ProjectDir" -ForegroundColor Cyan
Write-Host "Branch: $Branch" -ForegroundColor Cyan
Write-Host ""

Write-Host "Testing SSH connection..." -ForegroundColor Yellow
$sshCheck = ssh -i $SshKey -o ConnectTimeout=10 $Server "echo Connection_OK" 2>$null
if ($sshCheck -notmatch "Connection_OK") {
    throw "SSH connection failed"
}
Write-Host "SSH connection OK" -ForegroundColor Green
Write-Host ""

Write-Host "Creating deployment archive..." -ForegroundColor Yellow
tar -czf $TempArchive `
    --exclude=.git `
    --exclude=.github `
    --exclude=frontend/.next `
    --exclude=frontend/node_modules `
    --exclude=backend/__pycache__ `
    --exclude=backend/.venv `
    -C $ProjectRoot .

$RemoteScript = @'
set -Eeuo pipefail

PROJECT_DIR="__PROJECT_DIR__"
ARCHIVE="__ARCHIVE__"
BRANCH="__BRANCH__"

export COMPOSE_PROJECT_NAME=airco-fintech

mkdir -p "$PROJECT_DIR"
rm -rf "$PROJECT_DIR/backend" "$PROJECT_DIR/frontend" "$PROJECT_DIR/nginx" "$PROJECT_DIR/docker-compose.prod.yml"
tar -xzf "$ARCHIVE" -C "$PROJECT_DIR"

cd "$PROJECT_DIR"

if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose -f docker-compose.prod.yml"
elif docker compose version >/dev/null 2>&1; then
    COMPOSE="docker compose -f docker-compose.prod.yml"
else
    echo "docker-compose / docker compose not found"
    exit 1
fi

echo "Stopping current FinTech services..."
$COMPOSE down --remove-orphans || true

echo "Building only FinTech services..."
$COMPOSE build backend frontend

echo "Starting only FinTech services..."
$COMPOSE up -d --remove-orphans --force-recreate backend frontend

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

echo "Container status:"
$COMPOSE ps

if docker ps --format '{{.Names}}' | grep -qx 'nginx-gateway'; then
    echo "Reloading shared nginx gateway..."
    docker exec nginx-gateway nginx -s reload
else
    echo "Shared nginx gateway not found; skipping reload."
fi

if [ "$backend_health" != "healthy" ]; then
    echo "Backend failed health check"
    exit 1
fi

if [ "$frontend_health" != "healthy" ] && [ "$frontend_health" != "starting" ]; then
    echo "Frontend failed health check"
    exit 1
fi

echo "Deployment completed!"
'@

$RemoteScript = $RemoteScript.Replace('__PROJECT_DIR__', $ProjectDir)
$RemoteScript = $RemoteScript.Replace('__ARCHIVE__', '/tmp/fintech-deploy.tar.gz')
$RemoteScript = $RemoteScript.Replace('__BRANCH__', $Branch)

[System.IO.File]::WriteAllText($TempScript, $RemoteScript)

Write-Host "Starting deployment..." -ForegroundColor Yellow
try {
    scp -i $SshKey -o ConnectTimeout=10 $TempArchive "${Server}:/tmp/fintech-deploy.tar.gz"
    scp -i $SshKey -o ConnectTimeout=10 $TempScript "${Server}:/tmp/deploy-fintech.sh"
    ssh -i $SshKey -o ConnectTimeout=10 $Server "chmod +x /tmp/deploy-fintech.sh && /tmp/deploy-fintech.sh"

    if ($LASTEXITCODE -eq 0) {
        Write-Host "" 
        Write-Host "Deployment successful!" -ForegroundColor Green
        Write-Host "Check: https://insights.theairco.ai/health" -ForegroundColor Cyan
    } else {
        throw "Deployment failed"
    }
} finally {
    if (Test-Path $TempArchive) {
        Remove-Item $TempArchive -Force
    }
    if (Test-Path $TempScript) {
        Remove-Item $TempScript -Force
    }
}

Write-Host "Script completed!" -ForegroundColor Green
