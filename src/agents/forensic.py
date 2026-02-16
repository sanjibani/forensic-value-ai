"""
Forensic Accounting Agent — Deep financial statement analysis.

Detects accounting irregularities, revenue manipulation,
working capital manipulation, and cash flow discrepancies.
"""
from loguru import logger

from src.agents.base import BaseAgent
from src.llm.prompts import FORENSIC_SYSTEM, FORENSIC_USER


class ForensicAccountingAgent(BaseAgent):
    """Analyzes financial statements for accounting irregularities."""

    agent_name = "forensic"

    def analyze(self, state: dict) -> dict:
        """
        Run forensic accounting analysis.

        Expected state keys:
            - company_data: {ticker, company_name, sector, financials}
            - memory_context: Formatted memory text
        """
        company = state.get("company_data", {})
        ticker = company.get("ticker", "UNKNOWN")
        company_name = company.get("company_name", ticker)
        sector = company.get("sector", "Unknown")

        logger.info(f"[forensic] Starting analysis for {ticker}")

        # Extract financial data for the prompt
        financial_data = company.get("financials", {})
        financial_text = self._format_data_for_prompt(financial_data)

        memory_context = state.get("memory_context", "No prior feedback available.")

        # Search for accounting irregularities context
        search_results = ""
        try:
            from duckduckgo_search import DDGS
            search_results = self._perform_forensic_searches(company_name, ticker, DDGS)
        except ImportError:
            logger.warning("duckduckgo-search not found, skipping forensic web search")
        except Exception as e:
            logger.warning(f"Forensic web search failed: {e}")

        # Format prompt
        user_prompt = FORENSIC_USER.format(
            company_name=company_name,
            ticker=ticker,
            sector=sector,
            financial_data=financial_text,
            annual_report_text=company.get("annual_report_text", "")[:50000], # Safely truncate
            concall_text=company.get("concall_text", "")[:30000],
            search_results=search_results,
            memory_context=memory_context,
        )

        try:
            result = self._call_llm_json(
                system_prompt=FORENSIC_SYSTEM,
                user_prompt=user_prompt,
                max_tokens=4096,
            )

            findings = self._extract_findings(result)
            summary = result.get("summary", "Analysis complete.")
            risk_score = float(result.get("overall_risk_score", 50))

            logger.info(
                f"[forensic] {ticker}: {len(findings)} findings, "
                f"risk_score={risk_score}"
            )

            # Update state
            state["forensic_findings"] = findings
            state["forensic_summary"] = summary
            state["forensic_risk_score"] = risk_score
            state["research_path"] = state.get("research_path", []) + ["forensic"]

        except Exception as e:
            logger.error(f"[forensic] Analysis failed for {ticker}: {e}")
            state["forensic_findings"] = []
            state["forensic_summary"] = f"Analysis failed: {str(e)}"
            state["forensic_risk_score"] = 0.0
            state["errors"] = state.get("errors", []) + [
                f"Forensic agent error: {str(e)}"
            ]

        return state

    def _perform_forensic_searches(self, company_name: str, ticker: str, ddgs_cls) -> str:
        """Search for accounting irregularities and fraud indicators."""
        results_text = "\n### Web Search Results for Accounting & Fraud:\n"
        ddgs = ddgs_cls()
        
        queries = [
            f'"{company_name}" accounting fraud investigation',
            f'"{company_name}" auditor resignation reasons',
            f'"{company_name}" SEBI order financial misstatement',
            f'"{company_name}" tax evasion raid',
            f'"{company_name}" inflated revenue recognition',
        ]

        for q in queries:
            try:
                # logger.info(f"[forensic] Searching: {q}")
                results = list(ddgs.text(q, max_results=3))
                if results:
                    results_text += f"\n**Query:** {q}\n"
                    for r in results:
                        title = r.get("title", "")
                        body = r.get("body", "")
                        link = r.get("href", "")
                        results_text += f"- {title}: {body} ({link})\n"
            except Exception as e:
                logger.warning(f"[forensic] Search error for '{q}': {e}")
        
        return results_text
