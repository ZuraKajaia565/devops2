param(
    [switch]$SkipValidation
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example. Update GRAFANA_ADMIN_PASSWORD before production use."
}

New-Item -ItemType Directory -Force -Path "logs/app" | Out-Null
docker compose up --build -d

if (-not $SkipValidation) {
    & "$PSScriptRoot\validate.ps1"
}
