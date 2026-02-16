"""
Critic / Validator Agent — Cross-validates findings, reduces false positives.

Challenges findings from all other agents, forces deeper investigation
for low-confidence findings, and integrates user feedback patterns.
"""
from loguru import logger

from src.agents.base import BaseAgent
from src.llm.prompts import CRITIC_SYSTEM, CRITIC_USER


class CriticAgent(BaseAgent):
    """Validates and challenges findings across all agents."""

    agent_name = "critic"

    def analyze(self, state: dict) -> dict:
        """
        Validate all agent findings and request re-investigation if needed.

        Expected state keys:
            - all_findings: Aggregated findings from all agents
            - feedback_history: Formatted feedback history text
            - company_data: Basic company info
        """
        company = state.get("company_data", {})
        ticker = company.get("ticker", "UNKNOWN")
        company_name = company.get("company_name", ticker)
        sector = company.get("sector", "Unknown")

        logger.info(f"[critic] Starting validation for {ticker}")

        # Aggregate all findings
        all_findings = state.get("all_findings", [])
        if not all_findings:
            # Collect from individual agent outputs
            all_findings = (
                state.get("forensic_findings", [])
                + state.get("management_findings", [])
                + state.get("rpt_findings", [])
                + state.get("red_flag_findings", [])
                + state.get("auditor_findings", [])
            )

        if not all_findings:
            logger.warning(f"[critic] No findings to validate for {ticker}")
            state["critic_result"] = {
                "validated_findings": [],
                "reinvestigation_requests": [],
                "human_escalation_queue": [],
                "summary": "No findings to validate.",
            }
            state["needs_reinvestigation"] = False
            return state

        findings_json = self._format_data_for_prompt(
            {"findings": all_findings}, max_chars=10000
        )
        feedback_history = state.get(
            "feedback_history", "No prior feedback available."
        )

        user_prompt = CRITIC_USER.format(
            company_name=company_name,
            ticker=ticker,
            sector=sector,
            findings_json=findings_json,
            feedback_history=feedback_history,
        )

        try:
            result = self._call_llm_json(
                system_prompt=CRITIC_SYSTEM,
                user_prompt=user_prompt,
                max_tokens=4096,
            )

            validated = result.get("validated_findings", [])
            reinvestigations = result.get("reinvestigation_requests", [])
            escalations = result.get("human_escalation_queue", [])
            summary = result.get("summary", "Validation complete.")

            logger.info(
                f"[critic] {ticker}: {len(validated)} validated, "
                f"{len(reinvestigations)} reinvestigations, "
                f"{len(escalations)} escalations"
            )

            state["critic_result"] = result
            state["needs_reinvestigation"] = len(reinvestigations) > 0
            state["human_escalation_queue"] = escalations
            state["research_path"] = state.get("research_path", []) + ["critic"]

        except Exception as e:
            logger.error(f"[critic] Validation failed for {ticker}: {e}")
            state["critic_result"] = {
                "validated_findings": [],
                "summary": f"Validation failed: {str(e)}",
            }
            state["needs_reinvestigation"] = False
            state["errors"] = state.get("errors", []) + [
                f"Critic agent error: {str(e)}"
            ]

        return state
