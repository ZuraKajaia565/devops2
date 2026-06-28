$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Invoke-HealthCheck {
    param(
        [string]$Name,
        [string]$Url,
        [string]$ExpectedText = "",
        [int]$Retries = 12,
        [int]$DelaySeconds = 5
    )

    Write-Host "Checking $Name at $Url"
    for ($attempt = 1; $attempt -le $Retries; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 10
            if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 400) {
                throw "$Name returned HTTP $($response.StatusCode)"
            }
            if ($ExpectedText -and ($response.Content -notmatch [regex]::Escape($ExpectedText))) {
                throw "$Name response did not contain expected text: $ExpectedText"
            }
            return
        }
        catch {
            if ($attempt -eq $Retries) {
                throw
            }
            Write-Host "$Name is not ready yet; retrying in $DelaySeconds seconds..."
            Start-Sleep -Seconds $DelaySeconds
        }
    }
}

$envFile = ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]+)=(.*)$") {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

$appPort = if ($env:APP_PORT) { $env:APP_PORT } else { "5000" }
$prometheusPort = if ($env:PROMETHEUS_PORT) { $env:PROMETHEUS_PORT } else { "9090" }
$grafanaPort = if ($env:GRAFANA_PORT) { $env:GRAFANA_PORT } else { "3000" }
$lokiPort = if ($env:LOKI_PORT) { $env:LOKI_PORT } else { "3100" }

Invoke-HealthCheck "Application health" "http://localhost:$appPort/health" "healthy"
Invoke-HealthCheck "Application root endpoint" "http://localhost:$appPort/" "OK"
Invoke-HealthCheck "Application UI" "http://localhost:$appPort/ui" "DevOps Observability App"
Invoke-HealthCheck "Application dynamic route" "http://localhost:$appPort/hello/student" "Hello"
Invoke-HealthCheck "Application input form" "http://localhost:$appPort/feedback" "Feedback"
Invoke-HealthCheck "Application metrics" "http://localhost:$appPort/metrics" "app_requests_total"
Invoke-HealthCheck "Prometheus readiness" "http://localhost:$prometheusPort/-/ready" "Prometheus"
Invoke-HealthCheck "Grafana health" "http://localhost:$grafanaPort/api/health" "ok"
Invoke-HealthCheck "Loki readiness" "http://localhost:$lokiPort/ready" "ready"

$composeStatus = docker compose ps --format json
if (-not $composeStatus) {
    throw "docker compose ps returned no services"
}

Write-Host "Environment validation completed successfully."
