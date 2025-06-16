#!/bin/bash
# Backup script for pfSense MCP Server

set -e

BACKUP_DIR="${BACKUP_DIR:-./backups}"
DATE=$(date +%Y%m%d_%H%M%S)

echo "Starting backup..."

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup configuration
cp .env "$BACKUP_DIR/.env.$DATE" 2>/dev/null || echo "No .env file"

# Backup logs
if [ -d "logs" ]; then
    tar -czf "$BACKUP_DIR/logs_$DATE.tar.gz" logs/
fi

# Create manifest
cat > "$BACKUP_DIR/manifest_$DATE.txt" << MANIFEST
Backup Date: $DATE
Version: $(grep VERSION main.py | head -1 | cut -d'"' -f2)
Files:
- .env.$DATE
- logs_$DATE.tar.gz
MANIFEST

echo "Backup completed: $BACKUP_DIR/manifest_$DATE.txt"
