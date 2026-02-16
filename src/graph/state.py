"""
LangGraph state definition for the forensic analysis workflow.
"""
from typing import TypedDict, List, Dict, Optional, Annotated
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage


class ForensicState(TypedDict):
    """State passed between agents in the forensic analysis workflow."""

    # ---- Input ----
    company_data: Dict
    # {ticker, company_name, sector, financials, shareholding,
    #  governance, related_parties, ...}

    analysis_id: str
    analysis_depth: str  # "quick" or "full"
    hitl_mode: str  # "interactive" or "automatic"
    user_id: str

    # ---- Memory Context ----
    memory_context: str  # Formatted text from past feedback
    feedback_history: str  # For critic agent

    # ---- Forensic Accounting Agent ----
    forensic_findings: List[Dict]
    forensic_summary: str
    forensic_risk_score: float

    # ---- Management Integrity Agent ----
    management_findings: List[Dict]
    management_summary: str
    management_quality_score: float
    management_key_concerns: List[str]

    # ---- RPT Agent ----
    rpt_findings: List[Dict]
    rpt_summary: str
    rpt_risk_score: float
    rpt_total_amount: str
    rpt_pct_revenue: str

    # ---- Market Intelligence Agent (Phase 2) ----
    market_intel_findings: List[Dict]
    market_intel_summary: str
    market_sentiment_score: float

    # ---- Red Flag Scanner Agent (Phase 3) ----
    red_flag_findings: List[Dict]
    red_flag_summary: str

    # ---- Auditor Analysis Agent (Phase 3) ----
    auditor_findings: List[Dict]
    auditor_summary: str

    # ---- Critic/Validator Agent ----
    all_findings: List[Dict]  # Aggregated for critic
    critic_result: Dict
    needs_reinvestigation: bool
    human_escalation_queue: List[str]

    # ---- HITL State ----
    status: str
    # pending, running, awaiting_review, escalated, complete, failed
    user_feedback: List[Dict]
    hitl_paused: bool

    # ---- Report ----
    overall_risk_score: float
    report: Dict

    # ---- Metadata ----
    research_path: List[str]
    errors: List[str]
    iteration_count: int
    max_iterations: int

    # ---- LangGraph messages ----
    messages: Annotated[List[BaseMessage], add_messages]
