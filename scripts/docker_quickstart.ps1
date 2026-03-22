$Action = if ($args.Count -gt 0) { $args[0] } else { "up" }

if ($Action -eq "up") {
    docker compose run --rm crabclaw-cli onboard
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    docker compose up -d crabclaw-gateway crabclaw-dashboard
    exit $LASTEXITCODE
}

if ($Action -eq "down") {
    docker compose down
    exit $LASTEXITCODE
}

if ($Action -eq "logs") {
    docker compose logs -f crabclaw-gateway crabclaw-dashboard
    exit $LASTEXITCODE
}

if ($Action -eq "status") {
    docker compose ps
    exit $LASTEXITCODE
}

Write-Host "Usage: .\scripts\docker_quickstart.ps1 [up|down|logs|status]"
exit 1
