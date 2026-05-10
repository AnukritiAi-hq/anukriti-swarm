# syntax=docker/dockerfile:1.7
# ------------------------------------------------------------------
# Anukriti Swarm — Dockerfile
#
# Multi-stage build. Produces a minimal runtime image with the full
# backend (FastAPI + WebSocket) and all demo entry points available.
#
# Build:
#   docker build -t anukriti-swarm:local .
#
# Run the live backend:
#   docker run --rm -p 8000:8000 anukriti-swarm:local
#
# Run a one-shot demo:
#   docker run --rm anukriti-swarm:local python -m demos.unified_demo
#
# With MongoDB persistence:
#   docker run --rm -p 8000:8000 \
#     -e MONGODB_URI=mongodb://host.docker.internal:27017 \
#     anukriti-swarm:local
# ------------------------------------------------------------------

# ---------- Stage 1: builder ----------
# Install dependencies in a separate stage so the runtime image
# doesn't carry build toolchain.
FROM python:3.12-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Install build deps only for the builder stage. Pymongo wheels are
# available for 3.12, so no gcc/openssl-dev needed.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create a venv in a known location; the runtime stage copies it out.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only requirements first to maximize cache hits.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH"

# Non-root user for runtime. UID 10001 is arbitrary but stable for
# volume-mount compatibility.
RUN groupadd --gid 10001 swarm \
    && useradd --uid 10001 --gid swarm --shell /bin/bash --create-home swarm

# Bring in the venv from the builder. No build toolchain in the
# runtime image.
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Copy application sources. .dockerignore keeps tests, docs, venv,
# and local artifacts out of the image.
COPY --chown=swarm:swarm . /app

USER swarm

# Healthcheck pings the FastAPI /api/health endpoint. This only
# makes sense when the container is running the backend (the default
# CMD); a one-shot demo run will exit before the healthcheck fires.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; \
import json; \
r = urllib.request.urlopen('http://localhost:8000/api/health', timeout=3); \
sys.exit(0 if r.status == 200 else 1)" || exit 1

EXPOSE 8000

# Default: run the live backend. Override for demo runs:
#   docker run ... python -m demos.unified_demo
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
