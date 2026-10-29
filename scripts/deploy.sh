#!/usr/bin/env bash
# Usage: bash scripts/deploy.sh <version>   e.g. bash scripts/deploy.sh 1.0.6
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${1:?Usage: bash scripts/deploy.sh <version>}"
mkdir -p .deploy

export APP_VERSION="$VERSION"
echo ">> Deploying $VERSION"
docker compose pull app
docker compose up -d --no-build

for i in $(seq 1 30); do
  if curl -fs localhost:8000/ready >/dev/null; then
    CURRENT=$(cat .deploy/current 2>/dev/null || true)
    [ -n "$CURRENT" ] && [ "$CURRENT" != "$VERSION" ] && echo "$CURRENT" > .deploy/previous
    echo "$VERSION" > .deploy/current
    echo ">> SUCCESS: $VERSION is live"
    curl -s localhost:8000/health; echo
    exit 0
  fi
  sleep 2
done

echo ">> FAILED: app ready nahi hui. Rollback karo: bash scripts/rollback.sh"
docker compose logs app --tail 30
exit 1
