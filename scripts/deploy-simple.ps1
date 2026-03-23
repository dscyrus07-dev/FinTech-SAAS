# FinTech Deploy to Utho Server - Simple Wrapper
# Usage: .\scripts\deploy-simple.ps1 [branch]

param(
    [string]$Branch = "main"
)

$ScriptPath = Join-Path $PSScriptRoot "deploy-fintech.ps1"

if (-not (Test-Path $ScriptPath)) {
    Write-Host "deploy-fintech.ps1 not found at $ScriptPath" -ForegroundColor Red
    exit 1
}

Write-Host "Forwarding to deploy-fintech.ps1 with branch '$Branch'..." -ForegroundColor Cyan
& $ScriptPath -Branch $Branch
