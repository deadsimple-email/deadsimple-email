# Containerised stdio MCP server, for hosts that install MCP servers as images
# (Docker MCP Catalog / MCP Toolkit).
#
# Most users want the hosted remote endpoint instead — see README.md — which
# needs no container at all.
FROM python:3.11-slim

# mcp 2.0 removed mcp.server.fastmcp; the SDK extra pins <2 but be explicit here
# too so an image rebuild can never silently drift.
ARG DSE_VERSION=0.2.2
RUN pip install --no-cache-dir "deadsimple-email[mcp]==${DSE_VERSION}"

# Required by the MCP Registry to verify OCI image ownership.
LABEL io.modelcontextprotocol.server.name="email.deadsimple/dead-simple-email"
LABEL org.opencontainers.image.source="https://github.com/deadsimple-email/deadsimple-email"
LABEL org.opencontainers.image.description="Email for AI agents — real inboxes in one call"
LABEL org.opencontainers.image.licenses="MIT"

# DSE_API_KEY is supplied by the host at run time (docker run -e / MCP host config).
# Deliberately not declared as ENV — that trips the Docker "secrets in ENV" lint
# and would bake an empty value that masks a genuinely missing key.

ENTRYPOINT ["python", "-m", "deadsimple.mcp"]
