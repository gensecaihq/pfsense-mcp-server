#!/bin/bash
set -e

# Docker entrypoint script for pfSense MCP Server
# Note: The Dockerfile uses ENTRYPOINT ["python", "-m", "src.main"] directly.
# This script is provided as an alternative entrypoint for environments
# that need pre-flight checks before starting the server.

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo "============================================"
echo "       pfSense MCP Server v5.0.0"
echo "============================================"
echo ""

# Environment validation
validate_environment() {
    log_info "Validating environment configuration..."

    if [ -z "$PFSENSE_URL" ]; then
        log_error "PFSENSE_URL is not set"
        exit 1
    fi

    AUTH="${AUTH_METHOD:-api_key}"

    case "$AUTH" in
        "basic"|"jwt")
            if [ -z "$PFSENSE_USERNAME" ] || [ -z "$PFSENSE_PASSWORD" ]; then
                log_error "$AUTH auth requires PFSENSE_USERNAME and PFSENSE_PASSWORD"
                exit 1
            fi
            ;;
        "api_key")
            if [ -z "$PFSENSE_API_KEY" ]; then
                log_error "api_key auth requires PFSENSE_API_KEY (generate at System > REST API > Keys)"
                exit 1
            fi
            ;;
        *)
            log_error "Invalid AUTH_METHOD: $AUTH (must be basic, api_key, or jwt)"
            exit 1
            ;;
    esac

    # HTTP transport requires MCP_API_KEY for bearer auth
    TRANSPORT="${MCP_TRANSPORT:-stdio}"
    if [ "$TRANSPORT" = "streamable-http" ] && [ -z "$MCP_API_KEY" ]; then
        log_error "MCP_API_KEY must be set for streamable-http transport"
        exit 1
    fi

    log_info "Environment validation passed (auth: $AUTH, transport: $TRANSPORT)"
}

# Graceful shutdown handler
shutdown_handler() {
    log_info "Received shutdown signal, stopping..."
    kill -TERM "$APP_PID" 2>/dev/null || true
    wait "$APP_PID" 2>/dev/null
    exit 0
}

trap shutdown_handler SIGTERM SIGINT

# Main execution
validate_environment

log_info "Starting pfSense MCP Server..."
exec python -m src.main "$@"
