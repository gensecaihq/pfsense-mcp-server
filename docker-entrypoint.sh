#!/bin/bash
set -e

# Production-grade Docker entrypoint script
# Handles initialization, configuration, and graceful shutdown

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Banner
echo "============================================"
echo "       pfSense MCP Server v${VERSION:-4.0.0}"
echo "          FastMCP Implementation"
echo "============================================"
echo ""

# Environment validation
validate_environment() {
    log_info "Validating environment configuration..."
    
    # Required variables
    REQUIRED_VARS=(
        "PFSENSE_URL"
        "PFSENSE_CONNECTION_METHOD"
    )
    
    for var in "${REQUIRED_VARS[@]}"; do
        if [ -z "${!var}" ]; then
            log_error "Required environment variable $var is not set!"
            exit 1
        fi
    done
    
    # Connection method specific validation
    case "${PFSENSE_CONNECTION_METHOD}" in
        "rest")
            if [ -z "$PFSENSE_API_KEY" ] || [ -z "$PFSENSE_API_SECRET" ]; then
                log_error "REST API requires PFSENSE_API_KEY and PFSENSE_API_SECRET"
                exit 1
            fi
            ;;
        "xmlrpc")
            if [ -z "$PFSENSE_USERNAME" ] || [ -z "$PFSENSE_PASSWORD" ]; then
                log_error "XML-RPC requires PFSENSE_USERNAME and PFSENSE_PASSWORD"
                exit 1
            fi
            ;;
        "ssh")
            if [ -z "$PFSENSE_SSH_HOST" ] || [ -z "$PFSENSE_SSH_USERNAME" ]; then
                log_error "SSH requires PFSENSE_SSH_HOST and PFSENSE_SSH_USERNAME"
                exit 1
            fi
            ;;
        *)
            log_error "Invalid PFSENSE_CONNECTION_METHOD: ${PFSENSE_CONNECTION_METHOD}"
            exit 1
            ;;
    esac
    
    log_info "Environment validation passed"
}

# Initialize configuration
initialize_config() {
    log_info "Initializing configuration..."
    
    # Create config directory structure
    mkdir -p ${MCP_CONFIG}/ssl ${MCP_CONFIG}/rules ${MCP_CONFIG}/backups
    
    # Generate self-signed certificate if needed
    if [ ! -f "${MCP_CONFIG}/ssl/cert.pem" ] && [ "${ENABLE_TLS:-false}" = "true" ]; then
        log_info "Generating self-signed certificate..."
        openssl req -x509 -newkey rsa:4096 -keyout ${MCP_CONFIG}/ssl/key.pem \
            -out ${MCP_CONFIG}/ssl/cert.pem -days 365 -nodes \
            -subj "/C=US/ST=State/L=City/O=Organization/CN=pfsense-mcp"
    fi
    
    # Load custom configuration if exists
    if [ -f "${MCP_CONFIG}/custom.env" ]; then
        log_info "Loading custom configuration..."
        set -a
        source ${MCP_CONFIG}/custom.env
        set +a
    fi
}

# Database migrations (if using SQL for audit logs)
run_migrations() {
    if [ "${ENABLE_AUDIT_DB:-false}" = "true" ]; then
        log_info "Running database migrations..."
        alembic upgrade head || {
            log_warn "Database migrations failed, continuing without audit DB"
            export ENABLE_AUDIT_DB=false
        }
    fi
}

# Setup monitoring
setup_monitoring() {
    if [ "${OTEL_ENABLED:-false}" = "true" ]; then
        log_info "OpenTelemetry enabled, configuring exporters..."
        export OTEL_SERVICE_NAME="${OTEL_SERVICE_NAME:-pfsense-mcp-server}"
        export OTEL_TRACES_EXPORTER="${OTEL_TRACES_EXPORTER:-otlp}"
        export OTEL_METRICS_EXPORTER="${OTEL_METRICS_EXPORTER:-otlp}"
        export OTEL_LOGS_EXPORTER="${OTEL_LOGS_EXPORTER:-otlp}"
    fi
}

# Health check wait
wait_for_pfsense() {
    log_info "Waiting for pfSense connection..."
    
    MAX_ATTEMPTS=30
    ATTEMPT=1
    
    while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
        if python -c "import asyncio; from src.main import get_api_client; client = get_api_client(); asyncio.run(client.test_connection())" 2>/dev/null; then
            log_info "Successfully connected to pfSense"
            return 0
        fi
        
        log_warn "Connection attempt $ATTEMPT/$MAX_ATTEMPTS failed, retrying..."
        sleep 2
        ATTEMPT=$((ATTEMPT + 1))
    done
    
    log_error "Failed to connect to pfSense after $MAX_ATTEMPTS attempts"
    return 1
}

# Graceful shutdown handler
shutdown_handler() {
    log_info "Received shutdown signal, gracefully stopping..."
    
    # Signal the application to shutdown
    kill -TERM "$APP_PID" 2>/dev/null || true
    
    # Wait for graceful shutdown
    WAIT_TIME=30
    while [ $WAIT_TIME -gt 0 ]; do
        if ! kill -0 "$APP_PID" 2>/dev/null; then
            log_info "Application stopped gracefully"
            exit 0
        fi
        sleep 1
        WAIT_TIME=$((WAIT_TIME - 1))
    done
    
    # Force kill if still running
    log_warn "Force stopping application..."
    kill -KILL "$APP_PID" 2>/dev/null || true
    exit 0
}

# Trap signals for graceful shutdown
trap shutdown_handler SIGTERM SIGINT

# Main execution
main() {
    # Validate environment
    validate_environment
    
    # Initialize
    initialize_config
    setup_monitoring
    run_migrations
    
    # Determine run mode
    RUN_MODE="${MCP_MODE:-http}"
    log_info "Starting in $RUN_MODE mode..."
    
    # Export common settings
    export LOG_LEVEL="${LOG_LEVEL:-INFO}"
    export LOG_FILE="${MCP_LOGS}/pfsense-mcp.log"
    
    # Create log directory
    mkdir -p $(dirname "$LOG_FILE")
    
    # Start the application based on mode
    case "$RUN_MODE" in
        "stdio")
            log_info "Starting Enhanced MCP server in stdio mode for Claude Desktop..."
            exec python -m src.main --stdio
            ;;
        "http")
            log_info "Starting FastMCP server in HTTP mode..."
            
            # Determine server settings
            HOST="${MCP_HOST:-0.0.0.0}"
            PORT="${MCP_PORT:-8000}"
            WORKERS="${MCP_WORKERS:-4}"
            
            if [ "${PRODUCTION:-false}" = "true" ]; then
                # Production mode with gunicorn
                log_info "Running in production mode with gunicorn..."
                exec gunicorn src.main:mcp.asgi \
                    --bind "${HOST}:${PORT}" \
                    --workers "${WORKERS}" \
                    --worker-class uvicorn.workers.UvicornWorker \
                    --access-logfile "${MCP_LOGS}/access.log" \
                    --error-logfile "${MCP_LOGS}/error.log" \
                    --log-level "${LOG_LEVEL}" \
                    --timeout 120 \
                    --keep-alive 5 \
                    --max-requests 10000 \
                    --max-requests-jitter 1000
            else
                # Development mode with uvicorn
                log_info "Running in development mode with uvicorn..."
                exec python -m src.main \
                    --host "${HOST}" \
                    --port "${PORT}" \
                    --reload
            fi
            ;;
        *)
            log_error "Invalid MCP_MODE: $RUN_MODE"
            exit 1
            ;;
    esac
}

# Run main function
main "$@" &
APP_PID=$!

# Wait for the application
wait $APP_PID