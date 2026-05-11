#!/usr/bin/env bash
# deploy.sh — Rebuild and redeploy Anukriti Swarm with latest changes.
#
# Usage:
#   ./scripts/deploy.sh              # default: rebuild backend + frontend
#   ./scripts/deploy.sh --mongo      # include MongoDB profile
#   ./scripts/deploy.sh --full       # full rebuild (no cache)
#
set -euo pipefail

cd "$(dirname "$0")/.."

PROFILE=""
BUILD_ARGS=""

for arg in "$@"; do
  case "$arg" in
    --mongo) PROFILE="--profile mongo" ;;
    --full)  BUILD_ARGS="--no-cache" ;;
  esac
done

echo "⏳ Rebuilding containers..."
docker compose $PROFILE build $BUILD_ARGS

echo "🔄 Restarting services..."
docker compose $PROFILE up -d --force-recreate

echo "⏳ Waiting for backend health..."
for i in $(seq 1 15); do
  if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "✅ Deployed. Backend healthy at http://localhost:8000"
    echo "   Frontend: http://localhost:3000/pages/index.html"
    exit 0
  fi
  sleep 2
done

echo "⚠️  Backend not healthy after 30s. Check logs:"
echo "   docker compose logs swarm-backend"
exit 1
