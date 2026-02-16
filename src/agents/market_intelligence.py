"""
Market Intelligence Agent — Qualitative risk analysis via web search.

Searches for:
- Legal/Regulatory actions (raids, lawsuits, SEBI orders)
- Management integrity (past scams, political exposure)
- Employee/Customer sentiment (fake work culture, product issues)
"""
import json
from typing import List, Dict, Any

from loguru import logger
try:
    from duckduckgo_search import DDGS
except ImportError:
    logger.warning("duckduckgo-search not installed. Market Intelligence Agent will be disabled.")
    DDGS = None

from src.agents.base import BaseAgent
from src.llm.prompts import MARKET_INTELLIGENCE_SYSTEM, MARKET_INTELLIGENCE_USER


class MarketIntelligenceAgent(BaseAgent):
    """
    Gather qualitative data from the web to catch 'soft' risks
    that financial statements miss.
    """

    agent_name = "market_intel"

    def analyze(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform web searches and analyze results for qualitative red flags.
        """
        logger.info(f"[{self.agent_name}] Starting market intelligence analysis")

        company_data = state.get("company_data", {})
        ticker = company_data.get("ticker", "Unknown")
        company_name = company_data.get("company_name", ticker)
        
        # Get promoters if available
        shareholding = company_data.get("shareholding", {})
        promoters = [] # TODO: Extract promoter names from shareholding if detailed data available
        
        # Context from memory
        memory_context = state.get("memory_context", "No prior context.")

        # 1. Gather Data via Web Search
        if DDGS:
            search_results = self._perform_searches(company_name, promoters)
        else:
            search_results = "Web search unavailable (duckduckgo-search missing)."
            logger.error("Skipping web search: duckduckgo-search library not found")

        # 2. Format Prompt
        user_prompt = MARKET_INTELLIGENCE_USER.format(
            company_name=company_name,
            ticker=ticker,
            search_results=search_results,
            memory_context=memory_context
        )

        # 3. Call LLM
        try:
            response = self._call_llm_json(
                system_prompt=MARKET_INTELLIGENCE_SYSTEM,
                user_prompt=user_prompt
            )
        except Exception as e:
            logger.error(f"[{self.agent_name}] Analysis failed: {e}")
            return state

        # 4. Update State
        findings = self._extract_findings(response)
        summary = response.get("summary", "Analysis failed.")
        sentiment = float(response.get("sentiment_score", 50))

        logger.info(f"[{self.agent_name}] Analysis complete: {len(findings)} findings, Sentiment: {sentiment}")

        return {
            "market_intel_findings": findings,
            "market_intel_summary": summary,
            "market_sentiment_score": sentiment
        }

    def _perform_searches(self, company_name: str, promoters: List[str]) -> str:
        """Run multiple targeted search queries and aggregate results."""
        results_text = ""
        ddgs = DDGS()
        
        queries = [
            f'"{company_name}" fraud lawsuit raid SEBI investigation',
            f'"{company_name}" employee reviews fake work culture scam',
            f'"{company_name}" customer complaints consumer forum',
            f'"{company_name}" promoter political connection',
        ]
        
        # Add promoter-specific queries if names available
        for p in promoters[:2]: # Limit to top 2 to avoid spam
            queries.append(f'"{p}" scam fraud history')

        for q in queries:
            try:
                # Use rate limit handling if needed, but DDGS is usually lenient for low volume
                logger.info(f"[{self.agent_name}] Searching: {q}")
                results = list(ddgs.text(q, max_results=4))
                
                if results:
                    results_text += f"\n### Query: {q}\n"
                    for r in results:
                        title = r.get("title", "")
                        link = r.get("href", "")
                        body = r.get("body", "")
                        results_text += f"- **{title}**: {body} ({link})\n"
                else:
                    results_text += f"\n### Query: {q}\nNo relevant results found.\n"
                    
            except Exception as e:
                logger.error(f"[{self.agent_name}] Search failed for '{q}': {e}")
                results_text += f"\nError searching for '{q}'\n"

        return results_text
