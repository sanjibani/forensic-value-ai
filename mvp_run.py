"""
MVP Runner — Forensic analysis without Docker.

Usage:
    python mvp_run.py HOMESFY
    python mvp_run.py HOMESFY --fetch-only       # Just fetch data
    python mvp_run.py HOMESFY --analyze           # Run analysis on cached data
    python mvp_run.py --batch HOMESFY,TCS,INFY    # Multiple tickers
"""
import argparse
import json
import sys
import os
from pathlib import Path
from datetime import datetime

from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.data.enhanced_fetcher import EnhancedFetcher
from src.storage.json_store import JSONStorage
from src.llm.provider import LLMProvider


def setup_logging(verbose: bool = False):
    """Configure logging."""
    logger.remove()
    if verbose:
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.add(sys.stderr, level="INFO", format="{message}")


def fetch_data(ticker: str, fetcher: EnhancedFetcher) -> dict:
    """Fetch and cache company data."""
    print(f"\n📊 Fetching data for {ticker}...")
    print("=" * 50)

    data = fetcher.fetch_all(ticker)

    # Print summary
    print(f"\n📋 Data Summary for {data.get('company_name', ticker)}:")
    print(f"   Sector: {data.get('sector', 'N/A')}")
    print(f"   Market Cap: {data.get('market_cap', 'N/A')}")
    print(f"   Sources: {', '.join(data.get('data_sources', []))}")
    print(f"   Financial rows: {len(data.get('financials', {}))}")
    print(f"   Ratios: {len(data.get('ratios', {}))}")
    print(f"   Shareholding rows: {len(data.get('shareholding', {}))}")
    print(f"   Corporate announcements: {len(data.get('corporate_announcements', []))}")
    print(f"   Annual reports: {len(data.get('annual_report_urls', []))}")
    print(f"   Concalls: {len(data.get('concall_data', []))}")

    if data.get("pros"):
        print(f"\n   ✅ Pros:")
        for p in data["pros"]:
            print(f"      + {p}")

    if data.get("cons"):
        print(f"\n   ⚠️  Cons:")
        for c in data["cons"]:
            print(f"      - {c}")

    if data.get("ratios"):
        print(f"\n   📈 Key Ratios:")
        for k, v in list(data["ratios"].items())[:10]:
            print(f"      {k}: {v}")

    return data


def run_analysis(
    ticker: str,
    company_data: dict,
    storage: JSONStorage,
    llm: LLMProvider,
) -> dict:
    """Run forensic analysis using agents."""
    from src.agents.forensic import ForensicAccountingAgent
    from src.agents.management import ManagementIntegrityAgent
    from src.agents.rpt import RPTAgent
    from src.agents.critic import CriticAgent
    from src.agents.market_intelligence import MarketIntelligenceAgent

    analysis_id = storage.create_analysis(
        ticker=ticker,
        company_name=company_data.get("company_name", ""),
        sector=company_data.get("sector", ""),
    )

    # Save raw data
    storage.save_raw_data(analysis_id, company_data)

    print(f"\n🔬 Running forensic analysis (ID: {analysis_id})...")
    print("=" * 50)

    # Build state dict for agents
    state = {
        "company_data": company_data,
        "memory_context": "No prior feedback available (first analysis).",
    }

    results = {}
    all_findings = []

    # Run each agent
    agents = [
        ("Forensic Accounting", ForensicAccountingAgent(llm)),
        ("Management Integrity", ManagementIntegrityAgent(llm)),
        ("RPT Analysis", RPTAgent(llm)),
        ("Market Intelligence", MarketIntelligenceAgent(llm)),
    ]

    for name, agent in agents:
        print(f"\n  🕵️  {name} Agent analyzing...")
        try:
            agent_result = agent.analyze(state)
            results[agent.agent_name] = agent_result

            # Extract findings
            findings_key = f"{agent.agent_name}_findings"
            agent_findings = agent_result.get(findings_key, [])
            all_findings.extend(agent_findings)

            risk_key = f"{agent.agent_name}_risk_score"
            if agent.agent_name == "market_intel":
                 # Market intel returns sentiment score (0-100, where 100 is good)
                 # We need risk score (100 is bad)
                 sentiment = agent_result.get("market_sentiment_score", 50)
                 risk_score = 100 - sentiment
                 results[agent.agent_name]["market_intel_risk_score"] = risk_score
            elif agent.agent_name == "management":
                 # Management returns quality score (100 is good)
                 # We need risk score (100 is bad)
                 quality = agent_result.get("management_quality_score", 50)
                 risk_score = 100 - quality
                 results[agent.agent_name]["management_risk_score"] = risk_score
            else:
                 risk_score = agent_result.get(risk_key, 0)

            print(f"     → {len(agent_findings)} findings, risk score: {risk_score}")

            for f in agent_findings:
                sev = f.get("severity", "medium").upper()
                emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(sev, "⚪")
                print(f"     {emoji} [{sev}] {f.get('title', '')} (conf: {f.get('confidence', 0):.0f}%)")

                # Store in JSON
                storage.store_finding(
                    analysis_id=analysis_id,
                    agent_name=agent.agent_name,
                    finding_type=f.get("finding_type", ""),
                    title=f.get("title", ""),
                    description=f.get("description", ""),
                    severity=f.get("severity", "medium"),
                    confidence=f.get("confidence", 50.0),
                    evidence=f.get("evidence", []),
                )

        except Exception as e:
            print(f"     ❌ Agent failed: {e}")
            logger.exception(f"Agent {name} failed")

    # Run Critic
    print(f"\n  🧪 Critic Agent validating findings...")
    try:
        critic = CriticAgent(llm)
        critic_state = {
            "company_data": company_data,
            "all_findings": all_findings,
            "forensic_findings": results.get("forensic", {}).get("forensic_findings", []),
            "management_findings": results.get("management", {}).get("management_findings", []),
            "rpt_findings": results.get("rpt", {}).get("rpt_findings", []),
            "market_intel_findings": results.get("market_intel", {}).get("market_intel_findings", []),
            "memory_context": "First analysis.",
            # Pass summaries for context
            "forensic_summary": results.get("forensic", {}).get("forensic_summary", ""),
            "management_summary": results.get("management", {}).get("management_summary", ""),
            "rpt_summary": results.get("rpt", {}).get("rpt_summary", ""),
            "market_intel_summary": results.get("market_intel", {}).get("market_intel_summary", ""),
            "forensic_risk_score": results.get("forensic", {}).get("forensic_risk_score", 0),
            "management_risk_score": results.get("management", {}).get("management_risk_score", 0),
            "rpt_risk_score": results.get("rpt", {}).get("rpt_risk_score", 0),
            "market_intel_risk_score": results.get("market_intel", {}).get("market_intel_risk_score", 0),
        }
        critic_result = critic.analyze(critic_state)
        results["critic"] = critic_result
        print(f"     → Critic summary: {critic_result.get('critic_summary', 'N/A')[:100]}")
    except Exception as e:
        print(f"     ❌ Critic failed: {e}")
        # Ensure results["critic"] exists even if failed
        results["critic"] = {"critic_summary": f"Critic failed: {str(e)}"}

    # Run Narrative Agent
    print(f"\n  📖 Narrative Agent writing story...")
    narrative_report = ""
    try:
        from src.agents.narrative import NarrativeAgent
        narrative_agent = NarrativeAgent(llm)
        
        # Prepare state with everything needed
        narrative_state = critic_state.copy()
        narrative_state["critic_summary"] = results.get("critic", {}).get("critic_summary", "")
        # Validated findings? For now use all_findings
        narrative_state["all_findings"] = all_findings

        narrative_result = narrative_agent.analyze(narrative_state)
        narrative_report = narrative_result.get("narrative_report", "Story generation failed.")
        print(f"     → Story generated ({len(narrative_report)} chars)")
    except Exception as e:
        print(f"     ❌ Narrative failed: {e}")
        narrative_report = f"Narrative failed: {str(e)}"

    # Calculate overall risk
    risk_scores = []
    weights = {"forensic": 0.35, "management": 0.25, "rpt": 0.25, "market_intel": 0.15}
    for agent_name, weight in weights.items():
        key = f"{agent_name}_risk_score"
        for r in results.values():
            if key in r:
                risk_scores.append((r[key], weight))

    overall_risk = sum(s * w for s, w in risk_scores) / max(sum(w for _, w in risk_scores), 0.01)

    risk_level = (
        "CRITICAL" if overall_risk >= 75
        else "HIGH" if overall_risk >= 55
        else "MODERATE" if overall_risk >= 35
        else "LOW"
    )

    # Build final report
    report = {
        "ticker": ticker,
        "company_name": company_data.get("company_name", ""),
        "sector": company_data.get("sector", ""),
        "market_cap": company_data.get("market_cap", ""),
        "overall_risk_score": round(overall_risk, 1),
        "risk_level": risk_level,
        "findings_count": len(all_findings),
        "critical_findings": len([f for f in all_findings if f.get("severity") == "critical"]),
        "high_findings": len([f for f in all_findings if f.get("severity") == "high"]),
        "findings": all_findings,
        "scores": {
            "forensic_risk": results.get("forensic", {}).get("forensic_risk_score", 0),
            "management_risk": results.get("management", {}).get("management_risk_score", 0),
            "rpt_risk": results.get("rpt", {}).get("rpt_risk_score", 0),
        },
        "summary": {
            "forensic": results.get("forensic", {}).get("forensic_summary", ""),
            "management": results.get("management", {}).get("management_summary", ""),
            "rpt": results.get("rpt", {}).get("rpt_summary", ""),
        },
        "critic_summary": results.get("critic", {}).get("critic_summary", ""),
        "narrative_report": narrative_report,
        "pros": company_data.get("pros", []),
        "cons": company_data.get("cons", []),
        "data_sources": company_data.get("data_sources", []),
        "data_depth": {
            "financial_years": len(company_data.get("financials", {})),
            "shareholding_quarters": len(company_data.get("shareholding", {})),
            "annual_reports": len(company_data.get("annual_report_urls", [])),
            "concalls": len(company_data.get("concall_data", [])),
            "announcements": len(company_data.get("corporate_announcements", [])),
        },
        "analyzed_at": datetime.utcnow().isoformat(),
    }

    # Update storage
    storage.update_analysis_status(
        analysis_id, "complete",
        risk_score=overall_risk,
        findings_count=len(all_findings),
    )
    storage.save_report(analysis_id, report)

    # Print final report
    print(f"\n{'='*50}")
    print(f"📋 FORENSIC REPORT: {report['company_name']}")
    print(f"{'='*50}")
    print(f"  Overall Risk: {report['overall_risk_score']:.1f} ({report['risk_level']})")
    print(f"  Forensic Risk: {report['scores']['forensic_risk']}")
    print(f"  Management Risk: {report['scores']['management_risk']}")
    print(f"  RPT Risk: {report['scores']['rpt_risk']}")
    print(f"  Total Findings: {report['findings_count']}")
    print(f"  Critical: {report['critical_findings']} | High: {report['high_findings']}")
    print()

    print(f"📖 DETECTIVE STORY:\n{report['narrative_report']}\n")

    for agent, summary in report["summary"].items():
        if summary:
            print(f"  📝 {agent.title()}: {summary[:200]}")

    # Save report JSON
    report_file = Path("data") / "reports" / f"{ticker}_report.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n  💾 Report saved: {report_file}")
    print(f"  💾 Analysis file: data/analyses/{analysis_id}.json")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="ForensicValue AI MVP — Micro-cap forensic analysis"
    )
    parser.add_argument("ticker", nargs="?", help="NSE ticker symbol")
    parser.add_argument("--fetch-only", action="store_true", help="Only fetch data, don't analyze")
    parser.add_argument("--analyze", action="store_true", help="Analyze cached data")
    parser.add_argument("--batch", type=str, help="Comma-separated tickers for batch analysis")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if not args.ticker and not args.batch:
        parser.print_help()
        sys.exit(1)

    fetcher = EnhancedFetcher()
    storage = JSONStorage()

    tickers = args.batch.split(",") if args.batch else [args.ticker]

    for ticker in tickers:
        ticker = ticker.strip().upper()

        if args.fetch_only:
            fetch_data(ticker, fetcher)
            continue

        # Check for cached data
        if args.analyze:
            data = fetcher.load_cached(ticker)
            if not data:
                print(f"❌ No cached data for {ticker}. Run with --fetch-only first.")
                continue
        else:
            data = fetch_data(ticker, fetcher)

        # Run analysis
        if not args.fetch_only:
            try:
                llm = LLMProvider()
                run_analysis(ticker, data, storage, llm)
            except Exception as e:
                print(f"\n❌ Analysis failed: {e}")
                if args.verbose:
                    logger.exception("Analysis error")


if __name__ == "__main__":
    main()
