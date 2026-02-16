"""
LangGraph workflow orchestrator for forensic analysis.

Coordinates the multi-agent pipeline:
  Data Fetch → Memory Load → Agents (parallel) → Aggregate → Critic → Report
"""
import json
from datetime import datetime
from typing import Dict, Optional

from langgraph.graph import StateGraph, END
from loguru import logger

from src.graph.state import ForensicState
from src.llm.provider import LLMProvider
from src.agents.forensic import ForensicAccountingAgent
from src.agents.management import ManagementIntegrityAgent
from src.agents.rpt import RPTAgent
from src.agents.critic import CriticAgent
from src.agents.market_intelligence import MarketIntelligenceAgent
from src.data.fetcher import DataFetcher
from src.storage.postgres import PostgresManager
from src.storage.redis_cache import RedisCache


class ForensicWorkflow:
    """
    LangGraph workflow orchestrating the forensic analysis pipeline.

    Flow:
      fetch_data → load_memory → [forensic, management, rpt] →
      aggregate_findings → critic_validation → generate_report
    """

    def __init__(
        self,
        llm: LLMProvider,
        postgres: PostgresManager,
        redis: Optional[RedisCache] = None,
        feedback_memory=None,
    ):
        self.llm = llm
        self.postgres = postgres
        self.redis = redis
        self.feedback_memory = feedback_memory
        self.data_fetcher = DataFetcher()

        # Initialize agents
        self.forensic_agent = ForensicAccountingAgent(llm)
        self.management_agent = ManagementIntegrityAgent(llm)
        self.rpt_agent = RPTAgent(llm)
        self.market_intel_agent = MarketIntelligenceAgent(llm)
        self.critic_agent = CriticAgent(llm)

        # Build graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(ForensicState)

        # Add nodes
        workflow.add_node("fetch_data", self._fetch_data)
        workflow.add_node("load_memory", self._load_memory)
        workflow.add_node("forensic", self.forensic_agent)
        workflow.add_node("management", self.management_agent)
        workflow.add_node("rpt", self.rpt_agent)
        workflow.add_node("market_intel", self.market_intel_agent)
        workflow.add_node("aggregate", self._aggregate_findings)
        workflow.add_node("critic", self.critic_agent)
        workflow.add_node("report", self._generate_report)

        # Define flow
        workflow.set_entry_point("fetch_data")
        workflow.add_edge("fetch_data", "load_memory")

        # Fan-out: memory → parallel agents
        workflow.add_edge("load_memory", "forensic")
        workflow.add_edge("load_memory", "management")
        workflow.add_edge("load_memory", "rpt")
        workflow.add_edge("load_memory", "market_intel")

        # Fan-in: agents → aggregate
        workflow.add_edge("forensic", "aggregate")
        workflow.add_edge("management", "aggregate")
        workflow.add_edge("rpt", "aggregate")
        workflow.add_edge("market_intel", "aggregate")

        # Aggregate → Critic → Conditional
        workflow.add_edge("aggregate", "critic")

        # After critic: check if reinvestigation needed
        workflow.add_conditional_edges(
            "critic",
            self._should_reinvestigate,
            {"reinvestigate": "forensic", "proceed": "report"},
        )

        workflow.add_edge("report", END)

        return workflow.compile()

    # ---- Workflow Nodes ----

    def _fetch_data(self, state: ForensicState) -> dict:
        """Fetch company data from various sources."""
        ticker = state.get("company_data", {}).get("ticker", "")
        logger.info(f"[workflow] Fetching data for {ticker}")

        # Check Redis cache first
        if self.redis:
            cached = self.redis.get_cached_company_data(ticker)
            if cached:
                logger.info(f"[workflow] Using cached data for {ticker}")
                state["company_data"] = cached
                return state

        # Fetch fresh data
        try:
            company_data = self.data_fetcher.fetch_company_data(ticker)
            # Merge with any existing data in state
            existing = state.get("company_data", {})
            existing.update(company_data)
            state["company_data"] = existing

            # Cache in Redis
            if self.redis:
                self.redis.cache_company_data(ticker, existing)

        except Exception as e:
            logger.warning(f"[workflow] Data fetch failed for {ticker}: {e}")
            state["errors"] = state.get("errors", []) + [
                f"Data fetch warning: {str(e)}"
            ]

        return state

    def _load_memory(self, state: ForensicState) -> dict:
        """Load relevant user feedback from memory."""
        company = state.get("company_data", {})
        ticker = company.get("ticker", "")
        sector = company.get("sector", "")

        if self.feedback_memory:
            try:
                memory_data = self.feedback_memory.retrieve_relevant_feedback(
                    company=ticker, sector=sector
                )
                state["memory_context"] = (
                    self.feedback_memory.format_memory_context(memory_data)
                )
                state["feedback_history"] = state["memory_context"]
            except Exception as e:
                logger.warning(f"[workflow] Memory load failed: {e}")
                state["memory_context"] = "No prior feedback available."
                state["feedback_history"] = "No prior feedback available."
        else:
            state["memory_context"] = "No prior feedback available."
            state["feedback_history"] = "No prior feedback available."

        return state

    def _aggregate_findings(self, state: ForensicState) -> dict:
        """Aggregate findings from all agents into a single list."""
        all_findings = (
            state.get("forensic_findings", [])
            + state.get("management_findings", [])
            + state.get("rpt_findings", [])
            + state.get("market_intel_findings", [])
        )
        state["all_findings"] = all_findings

        logger.info(
            f"[workflow] Aggregated {len(all_findings)} total findings"
        )
        return state

    def _generate_report(self, state: ForensicState) -> dict:
        """Generate the final analysis report."""
        company = state.get("company_data", {})
        ticker = company.get("ticker", "UNKNOWN")

        # Calculate overall risk score as weighted average
        scores = []
        if state.get("forensic_risk_score"):
            scores.append(("forensic", state["forensic_risk_score"], 0.35))
        if state.get("management_quality_score"):
            # Invert: low quality = high risk
            mgmt_risk = 100 - state["management_quality_score"]
            scores.append(("management", mgmt_risk, 0.30))
        if state.get("rpt_risk_score"):
            scores.append(("rpt", state["rpt_risk_score"], 0.35))
        if state.get("market_sentiment_score"):
            # Invert: low sentiment = high risk
            intel_risk = 100 - state["market_sentiment_score"]
            scores.append(("market_intel", intel_risk, 0.20))

        if scores:
            total_weight = sum(w for _, _, w in scores)
            overall_risk = sum(s * w for _, s, w in scores) / total_weight
        else:
            overall_risk = 50.0

        state["overall_risk_score"] = round(overall_risk, 1)

        # Build report
        all_findings = state.get("all_findings", [])
        critical = [f for f in all_findings if f.get("severity") == "critical"]
        high = [f for f in all_findings if f.get("severity") == "high"]

        state["report"] = {
            "ticker": ticker,
            "company_name": company.get("company_name", ticker),
            "sector": company.get("sector", "Unknown"),
            "analysis_date": datetime.utcnow().isoformat(),
            "overall_risk_score": state["overall_risk_score"],
            "risk_level": self._risk_level(state["overall_risk_score"]),
            "summary": {
                "forensic": state.get("forensic_summary", ""),
                "management": state.get("management_summary", ""),
                "rpt": state.get("rpt_summary", ""),
                "market_intel": state.get("market_intel_summary", ""),
            },
            "scores": {
                "forensic_risk": state.get("forensic_risk_score", 0),
                "management_quality": state.get("management_quality_score", 0),
                "rpt_risk": state.get("rpt_risk_score", 0),
                "market_sentiment": state.get("market_sentiment_score", 0),
            },
            "findings_count": len(all_findings),
            "critical_findings": len(critical),
            "high_findings": len(high),
            "findings": all_findings,
            "management_key_concerns": state.get("management_key_concerns", []),
            "critic_summary": state.get("critic_result", {}).get("summary", ""),
            "errors": state.get("errors", []),
        }

        state["status"] = "complete"

        logger.info(
            f"[workflow] Report generated for {ticker}: "
            f"risk={state['overall_risk_score']}, "
            f"findings={len(all_findings)}"
        )

        return state

    def _should_reinvestigate(self, state: ForensicState) -> str:
        """Decide if reinvestigation is needed based on critic output."""
        iteration = state.get("iteration_count", 0)
        max_iter = state.get("max_iterations", 3)

        if (
            state.get("needs_reinvestigation", False)
            and iteration < max_iter
        ):
            state["iteration_count"] = iteration + 1
            logger.info(
                f"[workflow] Reinvestigation triggered "
                f"(iteration {iteration + 1}/{max_iter})"
            )
            return "reinvestigate"

        return "proceed"

    @staticmethod
    def _risk_level(score: float) -> str:
        if score >= 75:
            return "CRITICAL"
        elif score >= 55:
            return "HIGH"
        elif score >= 35:
            return "MODERATE"
        else:
            return "LOW"

    # ---- Public API ----

    def analyze(
        self,
        ticker: str,
        company_name: str = "",
        sector: str = "",
        analysis_depth: str = "full",
        hitl_mode: str = "automatic",
        user_id: str = "default",
    ) -> dict:
        """
        Run the full forensic analysis workflow.

        Args:
            ticker: Stock ticker (e.g. "INFY")
            company_name: Full company name
            sector: Industry sector
            analysis_depth: "quick" or "full"
            hitl_mode: "interactive" or "automatic"
            user_id: User identifier

        Returns:
            Final report dict
        """
        # Create analysis record in PostgreSQL
        analysis_id = self.postgres.create_analysis(
            ticker=ticker,
            company_name=company_name or ticker,
            sector=sector,
            analysis_depth=analysis_depth,
            hitl_mode=hitl_mode,
            user_id=user_id,
        )

        # Build initial state
        initial_state = {
            "company_data": {
                "ticker": ticker,
                "company_name": company_name or ticker,
                "sector": sector,
            },
            "analysis_id": analysis_id,
            "analysis_depth": analysis_depth,
            "hitl_mode": hitl_mode,
            "user_id": user_id,
            "memory_context": "",
            "feedback_history": "",
            "forensic_findings": [],
            "forensic_summary": "",
            "forensic_risk_score": 0.0,
            "management_findings": [],
            "management_summary": "",
            "management_quality_score": 0.0,
            "management_key_concerns": [],
            "rpt_findings": [],
            "rpt_summary": "",
            "rpt_risk_score": 0.0,
            "rpt_total_amount": "",
            "rpt_pct_revenue": "",
            "market_intel_findings": [],
            "market_intel_summary": "",
            "market_sentiment_score": 50.0,
            "red_flag_findings": [],
            "red_flag_summary": "",
            "auditor_findings": [],
            "auditor_summary": "",
            "all_findings": [],
            "critic_result": {},
            "needs_reinvestigation": False,
            "human_escalation_queue": [],
            "status": "running",
            "user_feedback": [],
            "hitl_paused": False,
            "overall_risk_score": 0.0,
            "report": {},
            "research_path": [],
            "errors": [],
            "iteration_count": 0,
            "max_iterations": 3,
            "messages": [],
        }

        # Update status
        self.postgres.update_analysis_status(analysis_id, "running")

        if self.redis:
            self.redis.set_analysis_progress(
                analysis_id,
                {"status": "running", "step": "starting", "progress": 0},
            )

        try:
            # Run the graph
            final_state = self.graph.invoke(initial_state)

            # Store findings in PostgreSQL
            report = final_state.get("report", {})
            findings = report.get("findings", [])

            for f in findings:
                self.postgres.store_finding(
                    analysis_id=analysis_id,
                    agent_name=f.get("agent_name", "unknown"),
                    finding_type=f.get("finding_type", "unknown"),
                    title=f.get("title", ""),
                    description=f.get("description", ""),
                    severity=f.get("severity", "medium"),
                    confidence=f.get("confidence", 50.0),
                    evidence=f.get("evidence", []),
                    industry_benchmark=f.get("industry_benchmark", {}),
                    requires_human_review=f.get("requires_human_review", False),
                )

            # Update analysis with results
            self.postgres.update_analysis_status(
                analysis_id,
                "complete",
                risk_score=report.get("overall_risk_score", 0),
                findings_count=len(findings),
            )

            return report

        except Exception as e:
            logger.error(f"[workflow] Analysis failed for {ticker}: {e}")
            self.postgres.update_analysis_status(analysis_id, "failed")
            return {
                "ticker": ticker,
                "error": str(e),
                "status": "failed",
                "analysis_id": analysis_id,
            }
