"""
Management Integrity Agent — Promoter behavior and governance assessment.

Evaluates promoter pledging, shareholding patterns, board composition,
executive compensation, and management track record.
"""
from loguru import logger

from src.agents.base import BaseAgent
from src.llm.prompts import MANAGEMENT_SYSTEM, MANAGEMENT_USER


class ManagementIntegrityAgent(BaseAgent):
    """Assesses management quality and governance integrity."""

    agent_name = "management"

    def analyze(self, state: dict) -> dict:
        """
        Run management integrity analysis.

        Expected state keys:
            - company_data: {ticker, company_name, sector, governance, shareholding}
            - memory_context: Formatted memory text
        """
        company = state.get("company_data", {})
        ticker = company.get("ticker", "UNKNOWN")
        company_name = company.get("company_name", ticker)
        sector = company.get("sector", "Unknown")

        logger.info(f"[management] Starting analysis for {ticker}")

        # Compile governance data
        governance_data = {
            "shareholding": company.get("shareholding", {}),
            "governance": company.get("governance", {}),
            "board": company.get("board_composition", {}),
            "compensation": company.get("compensation", {}),
            "promoter_entities": company.get("promoter_entities", []),
            "pledging": company.get("pledging", {}),
        }
        governance_text = self._format_data_for_prompt(governance_data)

        memory_context = state.get("memory_context", "No prior feedback available.")

        user_prompt = MANAGEMENT_USER.format(
            company_name=company_name,
            ticker=ticker,
            sector=sector,
            governance_data=governance_text,
            memory_context=memory_context,
        )

        try:
            result = self._call_llm_json(
                system_prompt=MANAGEMENT_SYSTEM,
                user_prompt=user_prompt,
                max_tokens=4096,
            )

            findings = self._extract_findings(result)
            mgmt_score = float(result.get("management_quality_score", 50))
            summary = result.get("summary", "Analysis complete.")
            key_concerns = result.get("key_concerns", [])

            logger.info(
                f"[management] {ticker}: {len(findings)} findings, "
                f"mgmt_score={mgmt_score}"
            )

            state["management_findings"] = findings
            state["management_summary"] = summary
            state["management_quality_score"] = mgmt_score
            state["management_key_concerns"] = key_concerns
            state["research_path"] = state.get("research_path", []) + ["management"]

        except Exception as e:
            logger.error(f"[management] Analysis failed for {ticker}: {e}")
            state["management_findings"] = []
            state["management_summary"] = f"Analysis failed: {str(e)}"
            state["management_quality_score"] = 0.0
            state["management_key_concerns"] = []
            state["errors"] = state.get("errors", []) + [
                f"Management agent error: {str(e)}"
            ]

        return state
