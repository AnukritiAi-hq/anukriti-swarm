#!/usr/bin/env bash
# setup.sh — First-time setup and deployment on a fresh instance.
#
# Usage:
#   ./scripts/setup.sh              # default setup
#   ./scripts/setup.sh --mongo      # include MongoDB
#
set -euo pipefail

cd "$(dirname "$0")/.."

PROFILE=""
for arg in "$@"; do
  case "$arg" in
    --mongo) PROFILE="--profile mongo" ;;
  esac
done

# 1. Check prerequisites
echo "🔍 Checking prerequisites..."
for cmd in docker curl git; do
  if ! command -v "$cmd" &> /dev/null; then
    echo "❌ $cmd not found. Install it first."
    exit 1
  fi
done

if ! docker compose version &> /dev/null; then
  echo "❌ docker compose not available. Install Docker Compose v2."
  exit 1
fi

# 2. Create .env if missing
if [ ! -f .env ]; then
  echo "📝 Creating .env from .env.example..."
  cp .env.example .env
  echo "   ⚠️  Edit .env to add your API keys (GEMINI_API_KEY, etc.)"
fi

# 3. Build and start
echo "🏗️  Building Docker images..."
docker compose $PROFILE build

echo "🚀 Starting services..."
docker compose $PROFILE up -d

# 4. Health check
echo "⏳ Waiting for backend..."
for i in $(seq 1 20); do
  if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
    echo ""
    echo "✅ Setup complete!"
    echo "   Backend:  http://localhost:8000/api/health"
    echo "   Frontend: http://localhost:3000/pages/index.html"
    echo ""
    echo "To redeploy after code changes:"
    echo "   ./scripts/deploy.sh"
    exit 0
  fi
  printf "."
  sleep 2
done

echo ""
echo "⚠️  Backend not healthy after 40s. Check:"
echo "   docker compose logs swarm-backend"
exit 1
