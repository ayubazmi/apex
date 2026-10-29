#!/usr/bin/env bash
# Usage: bash scripts/rollback.sh [version]   (bina version = last known good)
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${1:-$(cat .deploy/previous 2>/dev/null || true)}"
[ -z "$VERSION" ] && { echo "Usage: bash scripts/rollback.sh <version>"; exit 1; }

FROM=$(cat .deploy/current 2>/dev/null || true)
export APP_VERSION="$VERSION"
echo ">> Rolling back ${FROM:-?} -> $VERSION"
docker compose up -d --no-build || { docker compose pull app && docker compose up -d --no-build; }

for i in $(seq 1 30); do
  if curl -fs localhost:8000/ready >/dev/null; then
    mkdir -p .deploy
    [ -n "$FROM" ] && [ "$FROM" != "$VERSION" ] && echo "$FROM" > .deploy/previous
    echo "$VERSION" > .deploy/current
    echo ">> ROLLBACK OK: $VERSION is live"
    curl -s localhost:8000/health; echo
    exit 0
  fi
  sleep 2
done
echo ">> ROLLBACK FAILED"; docker compose logs app --tail 30; exit 1
