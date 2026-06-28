$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Invoke-CheckedCommand {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath failed with exit code $LASTEXITCODE"
    }
}

New-Item -ItemType Directory -Force -Path "reports" | Out-Null

Write-Host "Building application image for security scanning..."
Invoke-CheckedCommand "docker" @("compose", "build", "app")

Write-Host "Running dependency vulnerability scan with pip-audit..."
Invoke-CheckedCommand "docker" @(
    "run", "--rm",
    "-v", "${PWD}/app:/app",
    "-w", "/app",
    "python:3.12-slim",
    "sh", "-c", "pip install --no-cache-dir pip-audit && pip-audit -r requirements.txt"
)

Write-Host "Running container image scan with Trivy..."
Invoke-CheckedCommand "docker" @("save", "devops2-app:latest", "-o", "reports/app-image.tar")
Invoke-CheckedCommand "docker" @(
    "run", "--rm",
    "-v", "${PWD}/reports:/reports",
    "aquasec/trivy:0.52.2", "image",
    "--input", "/reports/app-image.tar",
    "--exit-code", "1",
    "--severity", "HIGH,CRITICAL",
    "--format", "table",
    "-o", "/reports/trivy-report.txt"
)

Write-Host "Running secret scan with Gitleaks..."
Invoke-CheckedCommand "docker" @(
    "run", "--rm",
    "-v", "${PWD}:/repo",
    "zricethezav/gitleaks:v8.18.4", "detect",
    "--source", "/repo",
    "--no-git",
    "--redact",
    "--report-path", "/repo/reports/gitleaks-report.json"
)

Write-Host "Security scans completed successfully. Reports are in ./reports."
