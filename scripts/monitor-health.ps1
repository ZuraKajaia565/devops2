param(
    [int]$Count = 12,
    [int]$IntervalSeconds = 10,
    [string]$Url = "http://localhost:5000/health",
    [string]$OutputPath = "logs/health-check.log"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutputPath) | Out-Null

for ($i = 1; $i -le $Count; $i++) {
    $timestamp = (Get-Date).ToString("o")
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 10
        $line = "$timestamp status=UP code=$($response.StatusCode) url=$Url"
    }
    catch {
        $line = "$timestamp status=DOWN error=$($_.Exception.Message) url=$Url"
    }

    Add-Content -Path $OutputPath -Value $line
    Write-Host $line

    if ($i -lt $Count) {
        Start-Sleep -Seconds $IntervalSeconds
    }
}
