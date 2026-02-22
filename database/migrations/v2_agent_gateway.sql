-- WebReaper v2.0 — Agent Gateway and new feature tables
-- Run against existing WebReaper database

-- Agent sessions table
CREATE TABLE IF NOT EXISTS agent_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL,
    connected_at TIMESTAMPTZ DEFAULT NOW(),
    disconnected_at TIMESTAMPTZ,
    messages_sent INTEGER DEFAULT 0,
    tools_executed INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active'
);

-- Agent audit log
CREATE TABLE IF NOT EXISTS agent_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES agent_sessions(id),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    tool_name TEXT NOT NULL,
    parameters JSONB,
    result_status TEXT,
    execution_time_ms INTEGER
);

-- Missions table
CREATE TABLE IF NOT EXISTS missions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL,
    brief TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    steps JSONB DEFAULT '[]',
    results JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Alert rules
CREATE TABLE IF NOT EXISTS alert_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    condition JSONB NOT NULL,
    delivery JSONB NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    last_triggered TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Workstation pins (research canvas)
CREATE TABLE IF NOT EXISTS workstation_pins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category TEXT,
    content JSONB NOT NULL,
    position_x FLOAT DEFAULT 0,
    position_y FLOAT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Infrastructure cache
CREATE TABLE IF NOT EXISTS infrastructure_cache (
    domain TEXT PRIMARY KEY,
    dns_records JSONB,
    ssl_info JSONB,
    cdn_info JSONB,
    whois_info JSONB,
    subdomains JSONB,
    scanned_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_session ON agent_audit_log(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON agent_audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(status);
CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules(enabled);
