# Multi-stage build for optimized production image
FROM python:3.11-slim AS builder

# Build arguments
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION=4.0.0

# Labels
LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.url="https://github.com/yourusername/pfsense-mcp-server" \
      org.opencontainers.image.source="https://github.com/yourusername/pfsense-mcp-server" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.vendor="pfSense MCP" \
      org.opencontainers.image.title="pfSense MCP Server" \
      org.opencontainers.image.description="Production-grade pfSense management via Model Context Protocol" \
      org.opencontainers.image.licenses="MIT"

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    python3-dev \
    libffi-dev \
    libssl-dev \
    cargo \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements first for better caching
COPY requirements.txt /tmp/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies and security updates
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    tini \
    libssl3 \
    libffi8 \
    openssh-client \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r mcp && useradd -r -g mcp -u 1000 -m -s /bin/bash mcp

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    MCP_HOME=/app \
    MCP_DATA=/data \
    MCP_LOGS=/logs \
    MCP_CONFIG=/config

# Create required directories
RUN mkdir -p ${MCP_HOME} ${MCP_DATA} ${MCP_LOGS} ${MCP_CONFIG} && \
    chown -R mcp:mcp ${MCP_HOME} ${MCP_DATA} ${MCP_LOGS} ${MCP_CONFIG}

# Copy application files
WORKDIR ${MCP_HOME}
COPY --chown=mcp:mcp src/ ./src/
COPY --chown=mcp:mcp scripts/ ./scripts/
COPY --chown=mcp:mcp config/ ./config/

# Create health check script
RUN echo '#!/bin/bash\ncurl -f http://localhost:${MCP_PORT:-8000}/health || exit 1' > /usr/local/bin/healthcheck && \
    chmod +x /usr/local/bin/healthcheck

# Set up entrypoint script
COPY --chown=mcp:mcp docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Security: Set proper permissions
RUN chmod -R 750 ${MCP_HOME} && \
    chmod -R 770 ${MCP_DATA} ${MCP_LOGS} && \
    chmod -R 750 ${MCP_CONFIG}

# Switch to non-root user
USER mcp

# Expose ports
EXPOSE 8000 9090

# Volume mounts for persistence
VOLUME ["${MCP_DATA}", "${MCP_LOGS}", "${MCP_CONFIG}"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD ["/usr/local/bin/healthcheck"]

# Use tini as PID 1
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command
CMD ["/usr/local/bin/docker-entrypoint.sh"]
