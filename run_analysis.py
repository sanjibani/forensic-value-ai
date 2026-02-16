"""
CLI runner for ForensicValue AI.

Usage:
    python run_analysis.py INFY
    python run_analysis.py RELIANCE --sector "Energy" --depth quick
"""
import argparse
import json
import sys

from loguru import logger
from src.config import settings
from src.llm.provider import LLMProvider
from src.storage.postgres import PostgresManager
from src.storage.redis_cache import RedisCache
from src.graph.workflow import ForensicWorkflow
from src.data.fetcher import DataFetcher


def main():
    parser = argparse.ArgumentParser(
        description="ForensicValue AI — Forensic Accounting Analysis"
    )
    parser.add_argument("ticker", help="NSE stock ticker (e.g., INFY)")
    parser.add_argument("--name", default="", help="Company name")
    parser.add_argument("--sector", default="", help="Sector")
    parser.add_argument(
        "--depth", choices=["full", "quick"], default="full",
        help="Analysis depth"
    )
    parser.add_argument(
        "--sample-data", action="store_true",
        help="Use sample data instead of scraping"
    )
    parser.add_argument(
        "--output", default="",
        help="Output JSON file path"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        logger.enable("src")
    else:
        logger.disable("src")
        logger.enable("src.graph.workflow")

    print(f"\n🔍 ForensicValue AI — Analyzing {args.ticker}")
    print("=" * 50)

    # Initialize services
    print("⚡ Initializing services...")
    llm = LLMProvider()
    postgres = PostgresManager()

    try:
        redis = RedisCache()
    except Exception:
        print("⚠️  Redis not available, continuing without cache")
        redis = None

    workflow = ForensicWorkflow(
        llm=llm,
        postgres=postgres,
        redis=redis,
    )

    # If sample data requested, inject it
    if args.sample_data:
        fetcher = DataFetcher()
        sample = fetcher.build_sample_data(args.ticker)
        print(f"📄 Using sample data for {args.ticker}")
        # We'll still use the workflow, it will merge sample data

    print(f"🚀 Starting {'full' if args.depth == 'full' else 'quick'} analysis...")
    print()

    report = workflow.analyze(
        ticker=args.ticker,
        company_name=args.name,
        sector=args.sector,
        analysis_depth=args.depth,
    )

    # Print results
    if report.get("status") == "failed":
        print(f"\n❌ Analysis failed: {report.get('error', 'Unknown')}")
        sys.exit(1)

    print(f"\n✅ Analysis Complete: {report.get('ticker', args.ticker)}")
    print(f"   Company: {report.get('company_name', 'N/A')}")
    print(f"   Sector:  {report.get('sector', 'N/A')}")
    print(f"   Risk Score: {report.get('overall_risk_score', 0):.1f} ({report.get('risk_level', 'N/A')})")
    print(f"   Total Findings: {report.get('findings_count', 0)}")
    print(f"   Critical: {report.get('critical_findings', 0)}")
    print(f"   High: {report.get('high_findings', 0)}")
    print()

    # Print summaries
    summaries = report.get("summary", {})
    for agent, text in summaries.items():
        if text:
            print(f"📊 {agent.title()}: {text}")

    # Print top findings
    findings = report.get("findings", [])
    if findings:
        print(f"\n🔍 Top Findings:")
        for f in findings[:5]:
            sev = f.get("severity", "medium").upper()
            emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(sev, "⚪")
            print(f"  {emoji} [{sev}] {f.get('title', '')} (confidence: {f.get('confidence', 0):.0f}%)")

    # Save to file
    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\n💾 Report saved to {args.output}")

    if report.get("errors"):
        print(f"\n⚠️  Warnings: {', '.join(report['errors'])}")


if __name__ == "__main__":
    main()
