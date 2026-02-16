FROM python:3.11-slim AS builder

ARG VERSION=4.0.0

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

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    libssl3 \
    libffi8 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r mcp && useradd -r -g mcp -u 1000 -m -s /bin/bash mcp

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

# Copy application files
WORKDIR ${MCP_HOME}
COPY --chown=mcp:mcp src/ ./src/

# Switch to non-root user
USER mcp

EXPOSE 3000

VOLUME ["${MCP_LOGS}"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:${MCP_PORT:-3000}/mcp || exit 1

ENTRYPOINT ["python", "src/main.py"]
CMD ["-t", "stdio"]
