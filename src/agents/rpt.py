"""
Related Party Transaction (RPT) Agent — Forensic RPT analysis.

Detects fund siphoning, non-arm's-length pricing, circular transactions,
and undisclosed promoter benefits through related party disclosures.
"""
from loguru import logger

from src.agents.base import BaseAgent
from src.llm.prompts import RPT_SYSTEM, RPT_USER


class RPTAgent(BaseAgent):
    """Deep forensic analysis of related party transactions."""

    agent_name = "rpt"

    def analyze(self, state: dict) -> dict:
        """
        Run related party transaction analysis.

        Expected state keys:
            - company_data: {ticker, company_name, sector, related_parties, ...}
            - memory_context: Formatted memory text
        """
        company = state.get("company_data", {})
        ticker = company.get("ticker", "UNKNOWN")
        company_name = company.get("company_name", ticker)
        sector = company.get("sector", "Unknown")

        logger.info(f"[rpt] Starting analysis for {ticker}")

        rpt_data = {
            "related_parties": company.get("related_parties", {}),
            "rpt_transactions": company.get("rpt_transactions", []),
            "loans_advances": company.get("loans_advances", {}),
            "guarantees": company.get("guarantees", {}),
            "corporate_structure": company.get("corporate_structure", {}),
            "financials_summary": {
                "revenue": company.get("financials", {}).get("revenue", "N/A"),
                "net_worth": company.get("financials", {}).get("net_worth", "N/A"),
            },
        }
        rpt_text = self._format_data_for_prompt(rpt_data)

        memory_context = state.get("memory_context", "No prior feedback available.")

        # Search for RPT data + promoter entities if missing
        search_results = ""
        try:
            from duckduckgo_search import DDGS
            search_results = self._perform_rpt_searches(company_name, ticker, DDGS)
        except ImportError:
            logger.warning("duckduckgo-search not found, skipping RPT web search")
        except Exception as e:
            logger.warning(f"RPT web search failed: {e}")

        user_prompt = RPT_USER.format(
            company_name=company_name,
            ticker=ticker,
            sector=sector,
            rpt_data=rpt_text,
            search_results=search_results,
            memory_context=memory_context,
        )

        try:
            result = self._call_llm_json(
                system_prompt=RPT_SYSTEM,
                user_prompt=user_prompt,
                max_tokens=4096,
            )

            findings = self._extract_findings(result)
            rpt_risk = float(result.get("rpt_risk_score", 50))
            summary = result.get("summary", "Analysis complete.")

            logger.info(
                f"[rpt] {ticker}: {len(findings)} findings, "
                f"rpt_risk={rpt_risk}"
            )

            state["rpt_findings"] = findings
            state["rpt_summary"] = summary
            state["rpt_risk_score"] = rpt_risk
            state["rpt_total_amount"] = result.get("total_rpt_amount", "N/A")
            state["rpt_pct_revenue"] = result.get("rpt_as_pct_revenue", "N/A")
            state["research_path"] = state.get("research_path", []) + ["rpt"]

        except Exception as e:
            logger.error(f"[rpt] Analysis failed for {ticker}: {e}")
            state["rpt_findings"] = []
            state["rpt_summary"] = f"Analysis failed: {str(e)}"
            state["rpt_risk_score"] = 0.0
            state["errors"] = state.get("errors", []) + [
                f"RPT agent error: {str(e)}"
            ]

        return state

    def _perform_rpt_searches(self, company_name: str, ticker: str, ddgs_cls) -> str:
        """Search for related party transactions and promoter entities."""
        results_text = "\n### Web Search Results for RPTs & Promoter Entities:\n"
        ddgs = ddgs_cls()
        
        queries = [
            f'"{company_name}" related party transactions annual report 2024',
            f'"{company_name}" promoter group private entities list',
            f'"{company_name}" money transfer to promoter entities',
            f'"{company_name}" undisclosed related party transactions SEBI',
            f'"{company_name}" loans to related parties',
        ]

        for q in queries:
            try:
                # logger.info(f"[rpt] Searching: {q}")
                results = list(ddgs.text(q, max_results=3))
                if results:
                    results_text += f"\n**Query:** {q}\n"
                    for r in results:
                        title = r.get("title", "")
                        body = r.get("body", "")
                        link = r.get("href", "")
                        results_text += f"- {title}: {body} ({link})\n"
            except Exception as e:
                logger.warning(f"[rpt] Search error for '{q}': {e}")
        
        return results_text
