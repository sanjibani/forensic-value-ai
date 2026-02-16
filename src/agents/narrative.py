"""
Narrative Agent — Synthesizes findings into a cohesive story.
"""
from loguru import logger

from src.agents.base import BaseAgent
from src.llm.prompts import NARRATIVE_SYSTEM, NARRATIVE_USER


class NarrativeAgent(BaseAgent):
    """Synthesizes valid findings into a final narrative."""

    agent_name = "narrative"

    def analyze(self, state: dict) -> dict:
        """
        Run narrative generation.

        Expected state keys:
            - company_data
            - forensic_findings, management_findings, etc.
            - critic_summary
        """
        company = state.get("company_data", {})
        ticker = company.get("ticker", "UNKNOWN")
        company_name = company.get("company_name", ticker)

        logger.info(f"[narrative] Generating story for {ticker}")

        # Gather summaries and risks
        forensic_summary = state.get("forensic_summary", "N/A")
        forensic_risk = state.get("forensic_risk_score", 0)
        
        management_summary = state.get("management_summary", "N/A")
        management_risk = state.get("management_risk_score", 0)
        
        rpt_summary = state.get("rpt_summary", "N/A")
        rpt_risk = state.get("rpt_risk_score", 0)
        
        market_intel_summary = state.get("market_intel_summary", "N/A")
        market_intel_risk = state.get("market_intel_risk_score", 0)
        
        critic_summary = state.get("critic_summary", "N/A")

        # Gather all findings
        all_findings = state.get("all_findings", [])
        # Format findings for prompt
        findings_text = ""
        for f in all_findings:
            findings_text += f"- [{f.get('severity', 'medium').upper()}] {f.get('finding_type', 'Issue')}: {f.get('title', 'Untitled')}\n"

        # Format prompt
        user_prompt = NARRATIVE_USER.format(
            company_name=company_name,
            ticker=ticker,
            forensic_summary=forensic_summary,
            forensic_risk=forensic_risk,
            management_summary=management_summary,
            management_risk=management_risk,
            rpt_summary=rpt_summary,
            rpt_risk=rpt_risk,
            market_intel_summary=market_intel_summary,
            market_intel_risk=market_intel_risk,
            critic_summary=critic_summary,
            all_findings=findings_text,
        )

        try:
            # We don't ask for JSON here, just text.
            # But BaseAgent._call_llm_json expects JSON.
            # So we use self.llm.call directly.
            response = self.llm.call(
                prompt=user_prompt,
                system_prompt=NARRATIVE_SYSTEM,
                json_mode=False,
                max_tokens=2000,
                temperature=0.7 # Higher temperature for creative writing
            )
            narrative = response.content

            logger.info(f"[narrative] Story generated ({len(narrative)} chars)")

            # Update state
            state["narrative_report"] = narrative

        except Exception as e:
            logger.error(f"[narrative] Generation failed: {e}")
            state["narrative_report"] = f"Narrative generation failed: {str(e)}"
            state["errors"] = state.get("errors", []) + [f"Narrative error: {str(e)}"]

        return state
