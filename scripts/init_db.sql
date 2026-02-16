-- ForensicValue AI — Database Schema
-- PostgreSQL 16 with pgvector extension

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ============================================================
-- Stock Analyses — Top-level analysis records
-- ============================================================
CREATE TABLE stock_analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_ticker VARCHAR(20) NOT NULL,
    company_name VARCHAR(200),
    sector VARCHAR(100),
    analysis_depth VARCHAR(20) DEFAULT 'full',  -- 'quick' or 'full'
    status VARCHAR(30) DEFAULT 'pending',
    -- Status: pending, running, awaiting_review, escalated, complete, failed
    risk_score DECIMAL(5,2),  -- Overall 0-100
    findings_count INTEGER DEFAULT 0,
    hitl_mode VARCHAR(20) DEFAULT 'interactive',
    user_id VARCHAR(100),
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sa_ticker ON stock_analyses(company_ticker);
CREATE INDEX idx_sa_status ON stock_analyses(status);
CREATE INDEX idx_sa_user ON stock_analyses(user_id);

-- ============================================================
-- Agent Findings — Individual findings from each agent
-- ============================================================
CREATE TABLE agent_findings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    analysis_id UUID NOT NULL REFERENCES stock_analyses(id) ON DELETE CASCADE,
    agent_name VARCHAR(50) NOT NULL,
    -- Agents: forensic, management, rpt, red_flag, auditor, critic
    finding_type VARCHAR(80) NOT NULL,
    title VARCHAR(300) NOT NULL,
    description TEXT,
    severity VARCHAR(20) NOT NULL DEFAULT 'medium',
    -- Severity: critical, high, medium, low
    confidence DECIMAL(5,2) NOT NULL DEFAULT 50.0,
    adjusted_confidence DECIMAL(5,2),
    evidence JSONB DEFAULT '[]'::jsonb,
    industry_benchmark JSONB,
    requires_human_review BOOLEAN DEFAULT FALSE,
    user_validation VARCHAR(20),
    -- Validation: approved, rejected, needs_more_info, NULL
    iteration INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_af_analysis ON agent_findings(analysis_id);
CREATE INDEX idx_af_agent ON agent_findings(agent_name);
CREATE INDEX idx_af_severity ON agent_findings(severity);
CREATE INDEX idx_af_validation ON agent_findings(user_validation);

-- ============================================================
-- User Feedback — HITL feedback entries
-- ============================================================
CREATE TABLE user_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    finding_id UUID REFERENCES agent_findings(id) ON DELETE SET NULL,
    analysis_id UUID REFERENCES stock_analyses(id) ON DELETE SET NULL,
    user_id VARCHAR(100),
    feedback_type VARCHAR(30) NOT NULL,
    -- Types: correction, pattern, validation, priority_adjustment
    company_ticker VARCHAR(20),
    sector VARCHAR(100),
    agent_name VARCHAR(50),
    finding_type VARCHAR(80),
    status VARCHAR(20),
    -- Status: approved, rejected, needs_more_info
    content TEXT NOT NULL,
    reasoning TEXT,
    confidence_adjustment DECIMAL(5,2) DEFAULT 0.0,
    apply_to_future BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_uf_finding ON user_feedback(finding_id);
CREATE INDEX idx_uf_company ON user_feedback(company_ticker);
CREATE INDEX idx_uf_type ON user_feedback(feedback_type);
CREATE INDEX idx_uf_sector ON user_feedback(sector);

-- ============================================================
-- Analysis Sessions — Workflow state tracking
-- ============================================================
CREATE TABLE analysis_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    analysis_id UUID NOT NULL REFERENCES stock_analyses(id) ON DELETE CASCADE,
    current_step VARCHAR(50),
    workflow_state JSONB DEFAULT '{}'::jsonb,
    agent_outputs JSONB DEFAULT '{}'::jsonb,
    iteration_count INTEGER DEFAULT 0,
    max_iterations INTEGER DEFAULT 3,
    paused_at TIMESTAMP,
    resumed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_as_analysis ON analysis_sessions(analysis_id);
