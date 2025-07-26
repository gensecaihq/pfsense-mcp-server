-- Initialize MCP Audit Database

-- Create schema
CREATE SCHEMA IF NOT EXISTS audit;

-- Audit logs table
CREATE TABLE IF NOT EXISTS audit.logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id VARCHAR(255) NOT NULL,
    access_level VARCHAR(50) NOT NULL,
    session_id VARCHAR(255),
    ip_address INET,
    method VARCHAR(255) NOT NULL,
    tool VARCHAR(255),
    parameters JSONB,
    result JSONB,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    duration_ms INTEGER,
    metadata JSONB
);

-- Indexes for performance
CREATE INDEX idx_audit_logs_timestamp ON audit.logs(timestamp DESC);
CREATE INDEX idx_audit_logs_user_id ON audit.logs(user_id);
CREATE INDEX idx_audit_logs_method ON audit.logs(method);
CREATE INDEX idx_audit_logs_tool ON audit.logs(tool);
CREATE INDEX idx_audit_logs_success ON audit.logs(success);

-- Security events table
CREATE TABLE IF NOT EXISTS audit.security_events (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    user_id VARCHAR(255),
    ip_address INET,
    details JSONB NOT NULL,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(255),
    notes TEXT
);

-- Indexes for security events
CREATE INDEX idx_security_events_timestamp ON audit.security_events(timestamp DESC);
CREATE INDEX idx_security_events_type ON audit.security_events(event_type);
CREATE INDEX idx_security_events_severity ON audit.security_events(severity);
CREATE INDEX idx_security_events_resolved ON audit.security_events(resolved);

-- Compliance scans table
CREATE TABLE IF NOT EXISTS audit.compliance_scans (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    framework VARCHAR(50) NOT NULL,
    version VARCHAR(20),
    score DECIMAL(5,2),
    status VARCHAR(20) NOT NULL,
    findings JSONB NOT NULL,
    scanned_by VARCHAR(255) NOT NULL,
    next_scan_due TIMESTAMPTZ,
    report_url TEXT
);

-- Indexes for compliance scans
CREATE INDEX idx_compliance_scans_timestamp ON audit.compliance_scans(timestamp DESC);
CREATE INDEX idx_compliance_scans_framework ON audit.compliance_scans(framework);
CREATE INDEX idx_compliance_scans_status ON audit.compliance_scans(status);

-- Create read-only user for reporting
CREATE USER mcp_reader WITH PASSWORD 'readonly_password';
GRANT USAGE ON SCHEMA audit TO mcp_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA audit TO mcp_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA audit GRANT SELECT ON TABLES TO mcp_reader;

-- Create views for common queries
CREATE OR REPLACE VIEW audit.recent_activity AS
SELECT 
    timestamp,
    user_id,
    access_level,
    method,
    tool,
    success,
    duration_ms
FROM audit.logs
WHERE timestamp > NOW() - INTERVAL '24 hours'
ORDER BY timestamp DESC;

CREATE OR REPLACE VIEW audit.user_activity_summary AS
SELECT 
    user_id,
    COUNT(*) as total_actions,
    COUNT(DISTINCT DATE(timestamp)) as active_days,
    COUNT(CASE WHEN success THEN 1 END) as successful_actions,
    COUNT(CASE WHEN NOT success THEN 1 END) as failed_actions,
    AVG(duration_ms) as avg_duration_ms,
    MAX(timestamp) as last_activity
FROM audit.logs
WHERE timestamp > NOW() - INTERVAL '30 days'
GROUP BY user_id;

-- Function to archive old logs
CREATE OR REPLACE FUNCTION audit.archive_old_logs() RETURNS void AS $$
BEGIN
    -- Move logs older than 90 days to archive table
    INSERT INTO audit.logs_archive 
    SELECT * FROM audit.logs 
    WHERE timestamp < NOW() - INTERVAL '90 days';
    
    DELETE FROM audit.logs 
    WHERE timestamp < NOW() - INTERVAL '90 days';
END;
$$ LANGUAGE plpgsql;

-- Create archive table
CREATE TABLE IF NOT EXISTS audit.logs_archive (LIKE audit.logs INCLUDING ALL);

-- Schedule periodic cleanup (requires pg_cron extension)
-- SELECT cron.schedule('archive-old-logs', '0 2 * * *', 'SELECT audit.archive_old_logs();');