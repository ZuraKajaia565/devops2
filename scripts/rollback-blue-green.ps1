$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$activeFile = "logs/production-active.txt"
if (-not (Test-Path $activeFile)) {
    throw "No active production slot file found. Run scripts/deploy-blue-green.ps1 first."
}

$current = (Get-Content $activeFile -Raw).Trim()
$rollback = if ($current -eq "blue") { "green" } else { "blue" }
$port = if ($rollback -eq "blue") { "5101" } else { "5102" }
$containerName = "devops2-app-$rollback"

$container = docker ps --filter "name=$containerName" --filter "status=running" --format "{{.Names}}"
if ($container -ne $containerName) {
    throw "Rollback slot $rollback is not running. Deploy it before rolling back."
}

$response = Invoke-WebRequest -Uri "http://localhost:$port/health" -UseBasicParsing -TimeoutSec 10
if ($response.StatusCode -ne 200) {
    throw "Rollback slot $rollback is not healthy."
}

Set-Content -Path $activeFile -Value $rollback
"rollback_to=$rollback port=$port rolled_back_at=$((Get-Date).ToString("o"))" | Add-Content -Path "logs/production/deployments.log"
Write-Host "Rollback complete. Active slot: $rollback on http://localhost:$port"
