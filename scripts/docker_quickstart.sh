#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-up}"

if [ "$ACTION" = "up" ]; then
  docker compose run --rm crabclaw-cli onboard
  docker compose up -d crabclaw-gateway crabclaw-dashboard
  exit 0
fi

if [ "$ACTION" = "down" ]; then
  docker compose down
  exit 0
fi

if [ "$ACTION" = "logs" ]; then
  docker compose logs -f crabclaw-gateway crabclaw-dashboard
  exit 0
fi

if [ "$ACTION" = "status" ]; then
  docker compose ps
  exit 0
fi

echo "Usage: $0 [up|down|logs|status]"
exit 1
