#!/usr/bin/env bash
# Anukriti PGx — one-shot EC2 bootstrap.
#
# Target deployment:
#   domain : mcp-pgx.anukritiai.com
#   email  : abhimanyurbsa@gmail.com
#
# Supports both:
#   - Ubuntu 22.04 LTS / 24.04 LTS  (apt, ssh user = ubuntu)
#   - Amazon Linux 2023             (dnf, ssh user = ec2-user)
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
REPO_DIR="${REPO_DIR:-$HOME/anukriti-swarm}"
DOMAIN="${DOMAIN:-mcp-pgx.anukritiai.com}"
EMAIL="${EMAIL:-abhimanyurbsa@gmail.com}"

log() { printf '\n\033[1;36m[bootstrap]\033[0m %s\n' "$*"; }
warn() { printf '\n\033[1;33m[bootstrap WARN]\033[0m %s\n' "$*"; }

# ------------------------------------------------------------------
# Distro detection — populates DISTRO + CURRENT_USER
# ------------------------------------------------------------------
if [[ -f /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    case "${ID:-}" in
        ubuntu|debian)
            DISTRO="ubuntu"
            ;;
        amzn|amazon)
            DISTRO="amazon"
            ;;
        *)
            DISTRO="unknown-$ID"
            ;;
    esac
else
    DISTRO="unknown"
fi
CURRENT_USER="$(id -un)"

log "deploy target : $DOMAIN"
log "certbot email : $EMAIL"
log "detected OS   : $DISTRO (${PRETTY_NAME:-unknown})"
log "current user  : $CURRENT_USER"

if [[ "$DISTRO" != "ubuntu" && "$DISTRO" != "amazon" ]]; then
    warn "unsupported distro. This script handles Ubuntu and Amazon Linux."
    warn "Aborting. Install docker + nginx + certbot manually then re-run."
    exit 1
fi

# ------------------------------------------------------------------
# Sanity — repo layout
# ------------------------------------------------------------------
if [[ ! -d "$REPO_DIR" ]]; then
    echo "expected repo at $REPO_DIR — clone it first:" >&2
    echo "  git clone --branch hackathon/agents-assemble-2026 \\" >&2
    echo "      https://github.com/AnukritiAi-hq/anukriti-swarm.git \$HOME/anukriti-swarm" >&2
    exit 1
fi

cd "$REPO_DIR"

if [[ ! -f "hackathon/deploy/docker-compose.yml" ]]; then
    echo "not on the hackathon branch — run:" >&2
    echo "  git checkout hackathon/agents-assemble-2026" >&2
    exit 1
fi

# ==================================================================
# 1. OS packages — docker + nginx + git + curl
# ==================================================================

log "installing docker + nginx + git"

if [[ "$DISTRO" == "ubuntu" ]]; then
    sudo apt-get update -qq
    # Prerequisites for the official Docker apt repo
    sudo apt-get install -y -qq \
        ca-certificates curl gnupg lsb-release git nginx >/dev/null

    # Set up Docker's official apt repo (cleaner than Ubuntu's docker.io)
    if ! command -v docker >/dev/null 2>&1; then
        sudo install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
            | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        sudo chmod a+r /etc/apt/keyrings/docker.gpg

        echo \
          "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
          https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
          | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

        sudo apt-get update -qq
        sudo apt-get install -y -qq \
            docker-ce docker-ce-cli containerd.io \
            docker-buildx-plugin docker-compose-plugin >/dev/null
    fi

elif [[ "$DISTRO" == "amazon" ]]; then
    sudo dnf install -y docker git nginx curl >/dev/null
fi

sudo systemctl enable --now docker

# Add the current user to the docker group so they can run compose
# without sudo. A fresh shell is required to pick it up — we work
# around that below with ``sg docker``.
if ! groups "$CURRENT_USER" | grep -qE '(^| )docker( |$)'; then
    sudo usermod -aG docker "$CURRENT_USER"
    log "added $CURRENT_USER to docker group"
fi

# ==================================================================
# 2. docker compose — skip if already available (Ubuntu repo ships it)
# ==================================================================

if ! docker compose version >/dev/null 2>&1; then
    # Amazon Linux only — Ubuntu's docker-ce bundle includes the
    # plugin.
    log "installing docker compose plugin"
    mkdir -p ~/.docker/cli-plugins
    curl -sSL \
      https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
      -o ~/.docker/cli-plugins/docker-compose
    chmod +x ~/.docker/cli-plugins/docker-compose
fi

# docker compose version (via sg so the group change is live)
sg docker -c 'docker compose version' | head -1 | while read -r line; do
    log "compose: $line"
done

# ==================================================================
# 3. .env guard
# ==================================================================

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

# ==================================================================
# 4. Build + start the container
# ==================================================================

log "building + starting the MCP server container (this takes ~3-5 min)"
sg docker -c 'docker compose -f hackathon/deploy/docker-compose.yml up -d --build'

log "waiting for health check (up to 60s for first build)"
for i in {1..30}; do
    if curl -fsS -H "Accept: text/event-stream" \
        http://127.0.0.1:9000/mcp -o /dev/null \
        -w "%{http_code}" 2>/dev/null | grep -qE "^(200|400|406)$"; then
        log "server is up on http://127.0.0.1:9000/mcp"
        break
    fi
    sleep 2
done

sg docker -c 'docker compose -f hackathon/deploy/docker-compose.yml ps'

# ==================================================================
# 5. nginx — reverse proxy
# ==================================================================

log "configuring nginx"
sudo cp hackathon/deploy/nginx.conf /etc/nginx/conf.d/anukriti-pgx.conf

# If DOMAIN differs from the baked-in default, rewrite it.
sudo sed -i "s/mcp-pgx.anukritiai.com/$DOMAIN/g" \
    /etc/nginx/conf.d/anukriti-pgx.conf

# Distro-specific cleanup of default server blocks that claim port 80.
if [[ "$DISTRO" == "ubuntu" ]]; then
    # Ubuntu's default welcome page is at /etc/nginx/sites-enabled/default
    sudo rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
elif [[ "$DISTRO" == "amazon" ]]; then
    # AL2023 ships a default.conf in conf.d
    sudo rm -f /etc/nginx/conf.d/default.conf 2>/dev/null || true
fi

sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx

# ==================================================================
# 6. TLS via certbot
# ==================================================================

log "checking that $DOMAIN resolves to this EC2 instance"
this_ip="$(curl -s -4 ifconfig.me || true)"
resolved_ip="$(getent hosts "$DOMAIN" 2>/dev/null | awk '{print $1}' | head -1 || true)"

log "this instance public IP : $this_ip"
log "$DOMAIN resolves to      : ${resolved_ip:-<not yet>}"

if [[ -z "$resolved_ip" ]]; then
    warn "$DOMAIN does not resolve yet."
    warn "Add an A record in your DNS provider:"
    warn "    $DOMAIN  A  $this_ip   (TTL 60-300s)"
    warn "Wait 1-2 min for propagation, then re-run:"
    warn "    bash hackathon/deploy/ec2-bootstrap.sh"
    warn "Skipping TLS for now."
elif [[ "$resolved_ip" != "$this_ip" ]]; then
    warn "$DOMAIN resolves to $resolved_ip but this instance is $this_ip."
    warn "Fix the A record and re-run. Skipping TLS for now."
else
    log "DNS OK — issuing Let's Encrypt certificate for $DOMAIN"
    if [[ "$DISTRO" == "ubuntu" ]]; then
        sudo apt-get install -y -qq certbot python3-certbot-nginx >/dev/null
    else
        sudo dnf install -y certbot python3-certbot-nginx >/dev/null
    fi

    sudo certbot --nginx \
        -d "$DOMAIN" \
        --non-interactive \
        --agree-tos \
        -m "$EMAIL" \
        --redirect

    log "TLS enabled. Test: curl -sSI https://$DOMAIN/mcp"
    log ""
    log "═══════════════════════════════════════════════════════════"
    log "  Paste this URL into Prompt Opinion:"
    log "  https://$DOMAIN/mcp"
    log "═══════════════════════════════════════════════════════════"
fi

log "bootstrap complete"
log "next steps:"
log "  1. Register your MCP at https://app.promptopinion.ai"
log "  2. Publish to the marketplace"
log "  3. Record the 3-min demo video (hackathon/VIDEO_SCRIPT.md)"
log "  4. Submit on Devpost (hackathon/SUBMISSION.md)"
