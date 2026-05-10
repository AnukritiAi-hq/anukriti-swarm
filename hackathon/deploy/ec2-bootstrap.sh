#!/usr/bin/env bash
# Anukriti PGx — one-shot EC2 bootstrap.
#
# Run on a fresh Amazon Linux 2023 EC2 instance after cloning the
# repo. Assumes the repo is already at ~/anukriti-swarm on the
# ``hackathon/agents-assemble-2026`` branch.
#
# Usage:
#     cd ~/anukriti-swarm
#     bash hackathon/deploy/ec2-bootstrap.sh

set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/anukriti-swarm}"
DOMAIN="${DOMAIN:-}"         # e.g. anukriti-pgx.yourdomain.com
EMAIL="${EMAIL:-}"           # for certbot

log() { printf '\n\033[1;36m[bootstrap]\033[0m %s\n' "$*"; }

# ------------------------------------------------------------------
# Sanity checks
# ------------------------------------------------------------------

if [[ ! -d "$REPO_DIR" ]]; then
    echo "expected repo at $REPO_DIR — clone it first." >&2
    exit 1
fi

cd "$REPO_DIR"

if [[ ! -f "hackathon/deploy/docker-compose.yml" ]]; then
    echo "not on the hackathon branch — run:"
    echo "  git checkout hackathon/agents-assemble-2026"
    exit 1
fi

# ------------------------------------------------------------------
# 1. OS packages
# ------------------------------------------------------------------

log "installing docker + nginx + git"
sudo dnf install -y docker git nginx curl >/dev/null
sudo systemctl enable --now docker
if ! groups ec2-user | grep -q docker; then
    sudo usermod -aG docker ec2-user
    log "added ec2-user to docker group — relogin to activate"
fi

# ------------------------------------------------------------------
# 2. docker compose plugin
# ------------------------------------------------------------------

if ! docker compose version >/dev/null 2>&1; then
    log "installing docker compose plugin"
    mkdir -p ~/.docker/cli-plugins
    curl -sSL \
      https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
      -o ~/.docker/cli-plugins/docker-compose
    chmod +x ~/.docker/cli-plugins/docker-compose
fi

# ------------------------------------------------------------------
# 3. .env guard
# ------------------------------------------------------------------

if [[ ! -f ".env" ]]; then
    log "no .env found — creating a minimal placeholder"
    cat > .env <<'EOF'
# Populate if you want generative narrative synthesis. The MCP
# server runs fully deterministic without these.
GOOGLE_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
EOF
fi

# ------------------------------------------------------------------
# 4. Build + start the container
# ------------------------------------------------------------------

log "building + starting the MCP server container"
docker compose -f hackathon/deploy/docker-compose.yml up -d --build

log "waiting for health check"
for i in {1..30}; do
    if curl -fsS http://127.0.0.1:9000/mcp >/dev/null 2>&1; then
        log "server is up on http://127.0.0.1:9000/mcp"
        break
    fi
    sleep 2
done

docker compose -f hackathon/deploy/docker-compose.yml ps

# ------------------------------------------------------------------
# 5. nginx (HTTP-only for now; certbot adds TLS below if DOMAIN set)
# ------------------------------------------------------------------

log "configuring nginx"
sudo cp hackathon/deploy/nginx.conf /etc/nginx/conf.d/anukriti-pgx.conf
if [[ -n "$DOMAIN" ]]; then
    sudo sed -i "s/anukriti-pgx.example.com/$DOMAIN/g" \
        /etc/nginx/conf.d/anukriti-pgx.conf
fi

# Remove default welcome server block if present (Amazon Linux 2023
# ships one that claims port 80).
sudo rm -f /etc/nginx/conf.d/default.conf 2>/dev/null || true

sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx

# ------------------------------------------------------------------
# 6. Optional — TLS via certbot if DOMAIN + EMAIL are set
# ------------------------------------------------------------------

if [[ -n "$DOMAIN" && -n "$EMAIL" ]]; then
    log "installing certbot and requesting cert for $DOMAIN"
    sudo dnf install -y certbot python3-certbot-nginx >/dev/null
    sudo certbot --nginx \
        -d "$DOMAIN" \
        --non-interactive \
        --agree-tos \
        -m "$EMAIL" \
        --redirect
    log "TLS enabled. Test: curl -sSI https://$DOMAIN/mcp"
else
    log "skipping TLS — set DOMAIN + EMAIL env vars and re-run to enable"
    log "HTTP test: curl -sSI http://$(curl -s ifconfig.me)/"
fi

log "bootstrap complete"
log "next: register the endpoint at https://app.promptopinion.ai"
