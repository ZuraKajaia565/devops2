param(
    [ValidateSet("blue", "green")]
    [string]$Target = "green"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$activeFile = "logs/production-active.txt"
$inactive = if ($Target -eq "blue") { "green" } else { "blue" }
$port = if ($Target -eq "blue") { "5101" } else { "5102" }

New-Item -ItemType Directory -Force -Path "logs/app", "logs/production" | Out-Null

docker build -t "devops2-app:$Target" ./app
$existingContainer = docker ps -a --filter "name=devops2-app-$Target" --format "{{.Names}}"
if ($existingContainer -eq "devops2-app-$Target") {
    docker rm -f "devops2-app-$Target" | Out-Null
}
docker run -d `
    --name "devops2-app-$Target" `
    --restart unless-stopped `
    -p "${port}:5000" `
    -e PORT=5000 `
    -e LOG_DIR=/var/log/app `
    -v "${PWD}/logs/app:/var/log/app" `
    "devops2-app:$Target" | Out-Null

for ($i = 1; $i -le 30; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$port/health" -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            Set-Content -Path $activeFile -Value $Target
            "active=$Target port=$port deployed_at=$((Get-Date).ToString("o"))" | Add-Content -Path "logs/production/deployments.log"
            Write-Host "Blue-green deployment complete. Active slot: $Target on http://localhost:$port"
            Write-Host "Previous slot remains available for rollback: $inactive"
            exit 0
        }
    }
    catch {
        Start-Sleep -Seconds 2
    }
}

throw "Target slot $Target did not become healthy on port $port"
