#!/usr/bin/env bash
# Anukriti PGx — one-shot EC2 bootstrap.
#
# Target deployment:
#   domain : mcp-pgx.anukritiai.com
#   email  : abhimanyurbsa@gmail.com
#
# Run on a fresh Amazon Linux 2023 EC2 instance after cloning the
# repo. Assumes the repo is already at ~/anukriti-swarm on the
# ``hackathon/agents-assemble-2026`` branch.
#
# Usage (defaults baked in):
#     cd ~/anukriti-swarm
#     bash hackathon/deploy/ec2-bootstrap.sh
#
# Override for a different target:
#     DOMAIN=other.example.com EMAIL=you@example.com \
#         bash hackathon/deploy/ec2-bootstrap.sh

set -euo pipefail

# ------------------------------------------------------------------
# Defaults for this deploy
# ------------------------------------------------------------------
# These are baked in so you can just run `bash ec2-bootstrap.sh`
# on the box without exporting env vars. Override by exporting
# DOMAIN= / EMAIL= / REPO_DIR= before invocation if needed.
REPO_DIR="${REPO_DIR:-$HOME/anukriti-swarm}"
DOMAIN="${DOMAIN:-mcp-pgx.anukritiai.com}"
EMAIL="${EMAIL:-abhimanyurbsa@gmail.com}"

log() { printf '\n\033[1;36m[bootstrap]\033[0m %s\n' "$*"; }

log "deploy target: $DOMAIN"
log "certbot contact: $EMAIL"

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
# If DOMAIN differs from the baked-in default, rewrite it. When DOMAIN
# matches the default, this is a no-op.
sudo sed -i "s/mcp-pgx.anukritiai.com/$DOMAIN/g" \
    /etc/nginx/conf.d/anukriti-pgx.conf

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
    # Pre-flight: check that DOMAIN actually resolves to this box's
    # public IP. certbot will fail otherwise and the error is cryptic.
    log "checking that $DOMAIN resolves to this EC2 instance"
    this_ip="$(curl -s -4 ifconfig.me || true)"
    resolved_ip="$(getent hosts "$DOMAIN" 2>/dev/null | awk '{print $1}' | head -1 || true)"

    if [[ -z "$resolved_ip" ]]; then
        log "WARNING: $DOMAIN does not resolve yet. Set an A record:"
        log "    $DOMAIN  A  $this_ip"
        log "Then re-run this script. Skipping TLS for now."
    elif [[ "$resolved_ip" != "$this_ip" ]]; then
        log "WARNING: $DOMAIN resolves to $resolved_ip but this box is $this_ip."
        log "Fix the A record and re-run. Skipping TLS for now."
    else
        log "DNS OK ($DOMAIN -> $this_ip). Installing certbot and issuing cert."
        sudo dnf install -y certbot python3-certbot-nginx >/dev/null
        sudo certbot --nginx \
            -d "$DOMAIN" \
            --non-interactive \
            --agree-tos \
            -m "$EMAIL" \
            --redirect
        log "TLS enabled. Test: curl -sSI https://$DOMAIN/mcp"
        log "Register this in Prompt Opinion: https://$DOMAIN/mcp"
    fi
else
    log "skipping TLS — set DOMAIN + EMAIL env vars and re-run to enable"
    log "HTTP test: curl -sSI http://$(curl -s ifconfig.me)/"
fi

log "bootstrap complete"
log "next: register the endpoint at https://app.promptopinion.ai"
