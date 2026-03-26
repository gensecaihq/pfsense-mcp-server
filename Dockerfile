FROM python:3.11-slim AS builder

ARG VERSION=1.0.0

LABEL org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.title="pfSense MCP Server" \
      org.opencontainers.image.description="pfSense management via Model Context Protocol" \
      org.opencontainers.image.licenses="MIT"

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    python3-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt /tmp/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies (minimal — no shell tools beyond curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    libssl3 \
    libffi8 \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* /var/tmp/*

# Create non-root user with no login shell
RUN groupadd -r mcp && useradd -r -g mcp -u 1000 -m -s /usr/sbin/nologin mcp

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MCP_HOME=/app \
    MCP_LOGS=/logs

# Create required directories
RUN mkdir -p ${MCP_HOME} ${MCP_LOGS} && \
    chown -R mcp:mcp ${MCP_HOME} ${MCP_LOGS}

# Copy application files (read-only — app never writes to its own directory)
WORKDIR ${MCP_HOME}
COPY --chown=mcp:mcp src/ ./src/

# Make application directory read-only (only /logs is writable)
RUN chmod -R a-w ${MCP_HOME}/src/

# Switch to non-root user
USER mcp

EXPOSE 3000

VOLUME ["${MCP_LOGS}"]

# HEALTHCHECK only applies when running in HTTP transport mode.
# In stdio mode (the default), there is no HTTP endpoint to probe.
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD if [ "${MCP_TRANSPORT:-stdio}" = "stdio" ]; then exit 0; else curl -sf http://localhost:${MCP_PORT:-3000}/mcp || exit 1; fi

ENTRYPOINT ["python3", "-m", "src.main"]
CMD ["-t", "stdio"]
