# Anukriti PGx — AWS Deployment Guide

This document walks through deploying the MCP Superpower to AWS
and registering it with Prompt Opinion. Optimised for the
hackathon-timeline case: **one EC2 instance, Docker, HTTPS via
nginx + certbot, under 30 minutes end-to-end**.

---

## Why EC2 (not App Runner, not ECS)

- **App Runner** auto-scales and handles TLS for you, but the FastMCP
  transport is a long-lived HTTP connection that doesn't play
  perfectly with App Runner's request-scoped model. Not a dealbreaker
  but risk we don't need today.
- **ECS Fargate** is overkill for a single-container workload on
  hackathon timelines.
- **EC2 t3.small**: $15/month, boots in 60s, `docker-compose up -d`,
  point nginx at it, done. Exactly what we need for judging.

---

## Deployment prerequisites

On your AWS side (one-time):

1. An AWS account (obvious)
2. A key pair you can SSH with
3. A subdomain you can point at the EC2 public IP
   (e.g. `anukriti-pgx.yourdomain.com`) — optional but recommended
   for a clean Prompt Opinion marketplace listing
4. AWS CLI configured locally: `aws configure`

On your local side:

1. This repo checked out on `hackathon/agents-assemble-2026`
2. `.env` file populated with any LLM API keys the swarm expects
   (Gemini is optional — the MCP server runs purely deterministic
   unless `GOOGLE_API_KEY` is set)

---

## Step 1 — Launch the EC2 instance

**Region:** whatever is closest to you (us-east-1 default, ap-south-1
for India).

**AMI:** Ubuntu 22.04 LTS **or** Amazon Linux 2023. The bootstrap
script auto-detects and handles both (different package managers).

**Instance type:** `t3.small` (2 vCPU, 2 GiB) — the swarm is CPU-
bound during KG build (~40ms first call, then reused).

**Storage:** 20 GiB gp3 (comfortable headroom). 30 GiB if you want
to keep multiple Docker image tags for rollback. Don't go below
16 GiB; the Docker image + deps take ~5 GiB and you want room for
logs.

**Security group:** inbound rules
  - 22/tcp from your IP (SSH)
  - 80/tcp from 0.0.0.0/0 (HTTP, for certbot challenge)
  - 443/tcp from 0.0.0.0/0 (HTTPS, where the MCP lives)
  - (optional) 9000/tcp from 0.0.0.0/0 while you're debugging;
    close this before final demo.

Using the AWS CLI:

```bash
# One-liner launch (replace placeholders)
aws ec2 run-instances \
  --region ap-south-1 \
  --image-id ami-XXXXXX \
  --instance-type t3.small \
  --key-name YOUR_KEY_PAIR \
  --security-group-ids sg-XXXXXX \
  --tag-specifications \
      'ResourceType=instance,Tags=[{Key=Name,Value=anukriti-pgx-hackathon}]'
```

Note the public IPv4 address that comes back; you will need it.

## Step 2 — Bootstrap the instance

SSH in and run the all-in-one bootstrap script:

```bash
# On Ubuntu:
ssh -i ~/.ssh/your-key.pem ubuntu@<EC2_PUBLIC_IP>

# On Amazon Linux 2023:
ssh -i ~/.ssh/your-key.pem ec2-user@<EC2_PUBLIC_IP>

# Then on the box:
git clone --branch hackathon/agents-assemble-2026 \
    https://github.com/AnukritiAi-hq/anukriti-swarm.git
cd anukriti-swarm
bash hackathon/deploy/ec2-bootstrap.sh
```

The script auto-detects Ubuntu vs Amazon Linux, installs Docker,
nginx, certbot, builds the container, runs a DNS pre-flight check
against the baked-in domain (`mcp-pgx.anukritiai.com`), and issues
a Let's Encrypt cert.

If you need to SSH in and the git clone fails with "repository not
found", the hackathon branch hasn't been pushed yet — see the root
README for push instructions.

## Step 3 — Get the code on the box

```bash
cd ~
git clone --branch hackathon/agents-assemble-2026 \
  https://github.com/AnukritiAi-hq/anukriti-swarm.git
cd anukriti-swarm
```

Copy your `.env` up (or create a minimal one — the MCP tools run
without LLM keys, they just don't do generative narrative synthesis):

```bash
# From your local machine
scp -i ~/.ssh/your-key.pem .env ec2-user@<EC2_PUBLIC_IP>:~/anukriti-swarm/.env
```

## Step 4 — Build + run the container

```bash
cd ~/anukriti-swarm
docker compose -f hackathon/deploy/docker-compose.yml up -d --build
```

This:
- builds the Docker image from `hackathon/deploy/Dockerfile`
- starts the FastMCP server on `:9000`
- auto-restarts on failure
- binds `127.0.0.1:9000` only (nginx fronts it)

Confirm it's healthy:

```bash
docker compose -f hackathon/deploy/docker-compose.yml ps
docker compose -f hackathon/deploy/docker-compose.yml logs --tail 40
curl -sS http://127.0.0.1:9000/mcp | head -5
```

You should see the MCP server's initial SSE handshake.

## Step 5 — nginx + TLS (HTTPS is required by Prompt Opinion)

Copy the nginx config:

```bash
sudo cp hackathon/deploy/nginx.conf /etc/nginx/conf.d/anukriti-pgx.conf
# Edit the server_name to match your subdomain
sudo vi /etc/nginx/conf.d/anukriti-pgx.conf
sudo nginx -t
sudo systemctl restart nginx
```

Install certbot and get the cert:

```bash
sudo dnf install -y certbot python3-certbot-nginx
sudo certbot --nginx \
  -d anukriti-pgx.yourdomain.com \
  --non-interactive --agree-tos -m you@yourdomain.com
```

certbot rewrites the nginx config to serve HTTPS and sets up auto-
renewal. Confirm:

```bash
curl -sSI https://anukriti-pgx.yourdomain.com/mcp | head -5
```

## Step 6 — Register with Prompt Opinion

1. Log into `https://app.promptopinion.ai`
2. Go to **MCP Tools & Servers** → **Add a new server**
3. Paste the URL: `https://anukriti-pgx.yourdomain.com/mcp`
4. The platform will introspect the server, discover the 5 tools,
   and show the SHARP capability extension.
5. Publish to the marketplace.

## Step 7 — Verify end-to-end

In a new Prompt Opinion workspace:

1. Add a FHIR data source (any SMART-on-FHIR test server works;
   the SMART Bulk Data reference server is a good default).
2. Compose a prescriber agent + our Anukriti PGx Superpower into a
   workspace.
3. Select a test patient with CYP2C19 genotype data.
4. Ask: *"Should this patient take clopidogrel?"*
5. The prescriber agent will call `pgx_analyze_patient` — you'll see
   the DetectedIssue returned in the workspace trace.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `nginx: bind() to 0.0.0.0:443 failed` | ACM/certbot conflict, run `sudo certbot certificates` to inspect |
| `unhealthy` in `docker compose ps` | check `docker compose logs` for Python tracebacks — most likely missing env var |
| MCP handshake 500 | check that fastmcp is 3.2.4+ in the container: `docker compose exec anukriti-pgx pip show fastmcp` |
| Prompt Opinion says "no tools discovered" | confirm the capability extension: `curl -sS https://<host>/mcp/capabilities` (in dev) |
| High first-call latency (> 1s) | expected: KG+indexer builds on first run (~40 ms). After that, sub-30 ms. |

---

## Rollback

```bash
# On the EC2 box
cd ~/anukriti-swarm
docker compose -f hackathon/deploy/docker-compose.yml down
git checkout <previous-commit-sha>
docker compose -f hackathon/deploy/docker-compose.yml up -d --build
```

---

## Cost sketch

| Resource | Monthly cost (approx) |
|---|---|
| t3.small, 24/7 | ~ $15 |
| 20 GiB gp3 | ~ $2 |
| Data egress (light) | ~ $1 |
| Route 53 subdomain | $0.50 |
| **Total** | **~ $18/month** |

Shutdown commands (stop the instance when not demoing to save
~90% of the cost):

```bash
aws ec2 stop-instances --instance-ids i-XXXXXX
# and later
aws ec2 start-instances --instance-ids i-XXXXXX
# IP will change unless you allocate an Elastic IP.
```
