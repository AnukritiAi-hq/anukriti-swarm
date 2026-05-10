# Anukriti PGx — MCP Superpower Dockerfile
#
# Single-stage build optimised for hackathon deploy speed:
# - python:3.12-slim base (matches the venv we tested on)
# - install top-level + hackathon requirements
# - copy repo
# - run the FastMCP server on 0.0.0.0:9000

FROM python:3.12-slim

# System deps — only what fhir.resources / httpx / fastmcp actually
# need. curl is kept for the health-check CMD.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only requirements first for Docker layer caching.
COPY requirements.txt ./
COPY hackathon/requirements.txt ./hackathon/requirements.txt

# The hackathon requirements re-pin fastmcp + fhir.resources which
# upgrade pydantic > starlette. Install both files in order:
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r hackathon/requirements.txt \
    && pip install --no-cache-dir 'pytest-asyncio>=0.23'

# Copy the rest of the repo.
COPY . .

# Sanity check — the server imports must succeed at build time.
RUN python -c "from hackathon.mcp_server import build_server; build_server()"

# Runtime config.
ENV ANUKRITI_MCP_HOST=0.0.0.0
ENV ANUKRITI_MCP_PORT=9000
ENV PYTHONUNBUFFERED=1

EXPOSE 9000

# Health check — the MCP endpoint returns 200 on GET (SSE upgrade).
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD curl -fsS -H "Accept: application/json, text/event-stream" \
        http://localhost:9000/mcp -o /dev/null \
        -w "%{http_code}" | grep -qE "^(200|400|406)$" || exit 1

# Run as a non-root user.
RUN useradd -m -u 1000 anukriti \
    && chown -R anukriti:anukriti /app
USER anukriti

CMD ["python", "-m", "hackathon.mcp_server"]
