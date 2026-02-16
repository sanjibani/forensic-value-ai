"""
ForensicValue AI — Research Dashboard

Displays forensic analysis results with agent work,
risk scores, findings, and deep-dive research.

Run: streamlit run dashboard.py
"""
import json
import math
from pathlib import Path

import streamlit as st
import subprocess
import os

# ---- Page Config ----
st.set_page_config(
    page_title="ForensicValue AI — Research Dashboard",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- Styles ----
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg-primary: #f8f9fa;
    --bg-secondary: #ffffff;
    --bg-card: #ffffff;
    --text-primary: #0f172a;
    --text-secondary: #64748b;
    --accent-blue: #3b82f6;
    --accent-purple: #8b5cf6;
    --border: #e2e8f0;
    --shadow-sm: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
    --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    --critical: #ef4444;
    --high: #f97316;
    --medium: #f59e0b;
    --low: #10b981;
}

.stApp {
    font-family: 'Inter', sans-serif;
    background-color: var(--bg-primary);
    color: var(--text-primary);
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: var(--bg-secondary);
    border-right: 1px solid var(--border);
}

/* Metric cards */
div[data-testid="stMetric"] {
    background-color: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    box-shadow: var(--shadow-sm);
    color: var(--text-primary);
}
div[data-testid="stMetric"] label {
    color: var(--text-secondary);
    font-weight: 500;
}

/* Agent cards */
.agent-card {
    background-color: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    margin: 16px 0;
    box-shadow: var(--shadow-sm);
    transition: box-shadow 0.2s;
}
.agent-card:hover {
    box-shadow: var(--shadow-md);
}

/* Risk meter */
.risk-meter {
    background: linear-gradient(90deg, #10b981 0%, #f59e0b 50%, #ef4444 100%);
    height: 8px;
    border-radius: 4px;
    position: relative;
    margin: 16px 0;
}
.risk-needle {
    position: absolute;
    top: -6px;
    width: 12px;
    height: 20px;
    background: white;
    border: 2px solid #64748b;
    border-radius: 4px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

/* Findings Badges */
.badge-critical {
    background-color: #fef2f2;
    color: #ef4444;
    border: 1px solid #fee2e2;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.badge-high {
    background-color: #fff7ed;
    color: #f97316;
    border: 1px solid #ffedd5;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.badge-medium {
    background-color: #fffbeb;
    color: #f59e0b;
    border: 1px solid #fef3c7;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.badge-low {
    background-color: #eff6ff; #ecfdf5;
    color: #10b981;
    border: 1px solid #d1fae5;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Score Circle */
.score-circle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 110px;
    height: 110px;
    border-radius: 50%;
    font-size: 36px;
    font-weight: 700;
    margin: 8px auto;
    font-family: 'Inter', sans-serif;
    background: white;
}
.score-critical {
    border: 8px solid #ef4444;
    color: #ef4444;
}
.score-high {
    border: 8px solid #f97316;
    color: #f97316;
}
.score-moderate {
    border: 8px solid #f59e0b;
    color: #f59e0b;
}
.score-low {
    border: 8px solid #10b981;
    color: #10b981;
}

/* Headers */
.section-header {
    font-size: 20px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 40px 0 20px 0;
    display: flex;
    align-items: center;
    gap: 12px;
}
.section-header:after {
    content: "";
    flex: 1;
    height: 1px;
    background: var(--border);
}

/* Source badge */
.source-badge {
    background-color: #eff6ff;
    color: #3b82f6;
    border: 1px solid #dbeafe;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 500;
    margin-right: 8px;
    display: inline-block;
}

/* Depth badge */
.depth-badge {
    background-color: #f1f5f9;
    color: #475569;
    border: 1px solid #e2e8f0;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 500;
    display: inline-block;
}

/* Confidence */
.conf-bar-bg {
    background-color: #f1f5f9;
    height: 6px;
    border-radius: 3px;
    overflow: hidden;
    margin-top: 8px;
}
.conf-bar-fill {
    height: 100%;
    border-radius: 3px;
}

/* Expander */
div[data-testid="stExpander"] {
    background-color: white;
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
div[data-testid="stExpander"] p {
    color: var(--text-primary);
}

.divider {
    height: 1px;
    background-color: var(--border);
    margin: 24px 0;
}
</style>
""", unsafe_allow_html=True)


# ---- Data Loading ----

REPORTS_DIR = Path(__file__).parent / "data" / "reports"
ANALYSES_DIR = Path(__file__).parent / "data" / "analyses"
TICKERS_FILE = Path(__file__).parent / "data" / "tickers.json"


def load_tickers() -> list[dict]:
    """Load NSE Microcap 250 ticker list."""
    if TICKERS_FILE.exists():
        with open(TICKERS_FILE) as f:
            return json.load(f)
    return []


def load_reports() -> list[dict]:
    """Load all report JSON files."""
    reports = []
    if REPORTS_DIR.exists():
        for f in sorted(REPORTS_DIR.glob("*_report.json"), reverse=True):
            try:
                with open(f) as fh:
                    reports.append(json.load(fh))
            except Exception:
                continue
    return reports


def load_analysis_detail(analysis_id: str) -> dict | None:
    """Load a full analysis file."""
    if ANALYSES_DIR.exists():
        f = ANALYSES_DIR / f"{analysis_id}.json"
        if f.exists():
            with open(f) as fh:
                return json.load(fh)
    return None


def risk_color(score: float) -> str:
    if score >= 75:
        return "critical"
    elif score >= 55:
        return "high"
    elif score >= 35:
        return "moderate"
    return "low"


def risk_emoji(score: float) -> str:
    if score >= 75:
        return "🔴"
    elif score >= 55:
        return "🟠"
    elif score >= 35:
        return "🟡"
    return "🟢"


def severity_emoji(s: str) -> str:
    return {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(s, "⚪")


def severity_color(s: str) -> str:
    return {
        "critical": "#ef4444",
        "high": "#f97316",
        "medium": "#f59e0b",
        "low": "#10b981",
    }.get(s, "#94a3b8")


# ---- Sidebar ----

def render_sidebar(reports):
    with st.sidebar:
        st.markdown("""
        <div style="padding: 20px 0;">
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 24px;">
                <div style="font-size: 28px;">🔬</div>
                <div>
                    <h1 style="font-size: 18px; font-weight: 700; margin: 0; color: #0f172a;">
                        ForensicValue AI
                    </h1>
                    <p style="color: #64748b; font-size: 12px; margin: 0;">
                        v0.1.0 (MVP)
                    </p>
                </div>
            </div>
            <div style="margin-bottom: 24px;">
                <p style="font-size: 12px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">
                    Analyses
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

        page = st.radio(
            "Navigation", 
            ["Analysis Dashboard", "Batch Runner", "System Architecture"], 
            label_visibility="collapsed"
        )

        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

        selected = None
        if page == "Analysis Dashboard":
            if reports:
                # Add dropdown at the top of the main area or sidebar? 
                # User asked for "in the analysis page keep a dropwn".
                # The sidebar already has buttons.
                # Let's add a dropdown in the main area if no specific company is selected yet, 
                # OR just sync the sidebar selection.
                # Actually, user wants "change companies to see individual analysis".
                # The sidebar buttons do this.
                # But maybe they want a dropdown at the top of the report view?
                # I'll add a dropdown in the sidebar REPLACING the buttons if there are many, 
                # OR add a dropdown in the main area to switch.
                pass
            else:
                st.info("No analyses yet. Use Batch Runner to start.")

        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

        with st.expander("🚀 New Analysis"):
            st.code("python mvp_run.py TICKER", language="bash")

        # Initialize session state for selection if not exists
        if "selected_ticker" not in st.session_state and reports:
            st.session_state["selected_ticker"] = reports[0]["ticker"]

        selected_ticker = st.session_state.get("selected_ticker")
        selected_report = next((r for r in reports if r["ticker"] == selected_ticker), None)
        
        return page, selected_report


# ---- Main Report View ----

def render_report_header(report):
    """Hero section with company name and risk score."""
    score = report.get("overall_risk_score", 0)
    level = report.get("risk_level", "UNKNOWN")
    color_class = risk_color(score)

    col_info, col_score = st.columns([3, 1])

    with col_info:
        st.markdown(f"""
        <h1 style="font-size: 32px; font-weight: 700; margin: 0; color: #0f172a;">
            {report.get('company_name', report['ticker'])}
        </h1>
        <div style="display: flex; gap: 16px; margin: 8px 0 24px; color: #64748b; font-size: 14px;">
            <span><strong>NSE:</strong> {report['ticker']}</span>
            <span><strong>Sector:</strong> {report.get('sector', 'N/A')}</span>
            <span><strong>Market Cap:</strong> ₹{report.get('market_cap', 'N/A')} Cr</span>
        </div>
        """, unsafe_allow_html=True)

        # Data source badges
        sources_html = ""
        for src in report.get("data_sources", []):
            sources_html += f'<span class="source-badge">{src}</span>'
        
        # Data depth badges
        depth = report.get("data_depth", {})
        if depth:
            if depth.get("financial_years"):
                sources_html += f'<span class="depth-badge">📅 {depth["financial_years"]} Years Financials</span>'
            if depth.get("shareholding_quarters"):
                sources_html += f'<span class="depth-badge">👥 {depth["shareholding_quarters"]} Qtrs Shareholding</span>'
            if depth.get("annual_reports"):
                sources_html += f'<span class="depth-badge">📄 {depth["annual_reports"]} Annual Reports</span>'
            if depth.get("concalls"):
                sources_html += f'<span class="depth-badge">📞 {depth["concalls"]} Concalls</span>'
            if depth.get("announcements"):
                sources_html += f'<span class="depth-badge">📢 {depth["announcements"]} Announcements</span>'

        st.markdown(f'<div style="margin-bottom: 24px; display: flex; flex-wrap: wrap; gap: 8px;">{sources_html}</div>', unsafe_allow_html=True)

    with col_score:
        st.markdown(f"""
        <div style="text-align: center;">
            <div class="score-circle score-{color_class}">{score:.0f}</div>
            <div style="color: {severity_color(color_class)}; font-weight: 700; 
                font-size: 14px; text-transform: uppercase; letter-spacing: 1px; margin-top: 8px;">
                {level} RISK
            </div>
        </div>
        """, unsafe_allow_html=True)


def render_score_cards(report):
    """Agent risk score cards."""
    scores = report.get("scores", {})

    col1, col2, col3, col4 = st.columns(4)

    forensic = scores.get("forensic_risk", 0)
    mgmt = scores.get("management_risk", 0)
    rpt = scores.get("rpt_risk", 0)
    findings = report.get("findings_count", 0)

    with col1:
        st.metric(
            "🔍 Forensic Risk",
            f"{forensic:.0f}/100",
            delta=f"{'CRITICAL' if forensic >= 75 else 'HIGH' if forensic >= 55 else 'MODERATE' if forensic >= 35 else 'LOW'}",
            delta_color="inverse",
        )
    with col2:
        st.metric(
            "👔 Management Risk",
            f"{mgmt:.0f}/100" if mgmt > 0 else "N/A",
            delta="Data Insufficient" if mgmt == 0 else f"{'CRITICAL' if mgmt >= 75 else 'HIGH' if mgmt >= 55 else 'MODERATE'}",
            delta_color="inverse",
        )
    with col3:
        st.metric(
            "🔗 RPT Risk",
            f"{rpt:.0f}/100",
            delta=f"{'CRITICAL' if rpt >= 75 else 'HIGH' if rpt >= 55 else 'MODERATE' if rpt >= 35 else 'LOW'}",
            delta_color="inverse" if rpt >= 55 else "normal",
        )
    with col4:
        critical = report.get("critical_findings", 0)
        high = report.get("high_findings", 0)
        st.metric(
            "📊 Total Findings",
            findings,
            delta=f"{critical} critical, {high} high",
            delta_color="inverse" if critical > 0 else "off",
        )


def render_risk_meter(report):
    """Visual risk gauge."""
    score = report.get("overall_risk_score", 0)
    needle_pos = min(max(score, 0), 100)

    st.markdown(f"""
    <div style="margin: 24px 0 40px;">
        <div style="display: flex; justify-content: space-between; color: #64748b; font-size: 12px; margin-bottom: 6px;">
            <span>Low Risk</span><span>Moderate</span><span>High</span><span>Critical</span>
        </div>
        <div class="risk-meter">
            <div class="risk-needle" style="left: {needle_pos}%;"></div>
        </div>
        <div style="display: flex; justify-content: space-between; color: #94a3b8; font-size: 11px; margin-top: 2px;">
            <span>0</span><span>25</span><span>50</span><span>75</span><span>100</span>
        </div>
    </div>
    </div>
    """, unsafe_allow_html=True)


def render_narrative_report(report):
    """Render the narrative story."""
    narrative = report.get("narrative_report", "")
    if not narrative or "failed" in narrative:
        return

    st.markdown('<div class="section-header">📖 Detective Story</div>', unsafe_allow_html=True)
    
    st.markdown(f"""
    <div style="background: white; border-left: 4px solid #6366f1; padding: 20px; 
        border-radius: 0 8px 8px 0; font-family: 'Georgia', serif; font-size: 17px; 
        line-height: 1.7; color: #1e293b; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
        {narrative.replace(chr(10), '<br><br>')}
    </div>
    """, unsafe_allow_html=True)




def render_agent_research(report):
    """Agent-by-agent research summaries."""
    st.markdown('<div class="section-header">🕵️ Agent Research</div>', unsafe_allow_html=True)

    summaries = report.get("summary", {})
    scores = report.get("scores", {})

    agents = [
        {
            "name": "Forensic Accounting Agent",
            "key": "forensic",
            "icon": "🔍",
            "desc": "Revenue quality, cash flow analysis, working capital manipulation.",
            "score_key": "forensic_risk",
        },
        {
            "name": "Management Integrity Agent",
            "key": "management",
            "icon": "👔",
            "desc": "Promoter behavior, share pledging, board independence.",
            "score_key": "management_quality",
        },
        {
            "name": "Related Party Transaction Agent",
            "key": "rpt",
            "icon": "🔗",
            "desc": "RPT volume, related entity analysis, fund siphoning indicators.",
            "score_key": "rpt_risk",
        },
        {
            "name": "Market Intelligence Agent",
            "key": "market_intel",
            "icon": "🌐",
            "desc": "News, social sentiment, lawsuits, and qualitative red flags.",
            "score_key": "market_sentiment",
        },
    ]

    for agent in agents:
        summary = summaries.get(agent["key"], "")
        score = scores.get(agent["score_key"], 0)
        agent_findings = [
            f for f in report.get("findings", [])
            if f.get("agent_name") == agent["key"]
        ]

        with st.expander(
            f"{agent['icon']} **{agent['name']}** — Risk: {score:.0f} | {len(agent_findings)} findings",
            expanded=True,
        ):
            if summary:
                # Check for errors first
                if "Analysis failed" in summary or "LLM provider error" in summary:
                    st.warning("⚠️ This agent's analysis could not be completed.")
                    
                    if st.button(f"🔄 Retry {agent['name']}", key=f"retry_{agent['key']}"):
                         st.info(f"Restarting analysis for {report.get('ticker')}...")
                         subprocess.Popen(["python", "mvp_run.py", report.get("ticker"), "--analyze"])
                         st.success("Analysis restarted in background. Please wait a few minutes and refresh.")
                    
                    with st.expander("View Error Details"):
                        st.code(summary, language="text")
                else:
                    st.markdown(f"""
                    <div style="margin-bottom: 16px; color: #334155; font-size: 15px; line-height: 1.6;">
                        {summary}
                    </div>
                    """, unsafe_allow_html=True)

            if agent_findings:
                st.caption("KEY FINDINGS")
                for f in agent_findings:
                    sev = f.get("severity", "medium")
                    conf = f.get("confidence", 0)
                    conf_color = "#10b981" if conf >= 80 else "#f59e0b"

                    st.markdown(f"""
                    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; 
                        padding: 16px; margin: 8px 0; border-left: 4px solid {severity_color(sev)};">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <span class="badge-{sev}">{sev}</span>
                                <strong style="color: #0f172a; font-size: 14px;">{f.get('title', '')}</strong>
                            </div>
                            <div style="color: {conf_color}; font-family: 'JetBrains Mono'; font-size: 12px; font-weight: 500;">
                                {conf:.0f}% confidence
                            </div>
                        </div>
                        <p style="color: #475569; font-size: 14px; margin: 4px 0 8px; line-height: 1.5;">
                            {f.get('description', '')}
                        </p>
                        <div class="conf-bar-bg">
                            <div class="conf-bar-fill" style="width: {conf}%; background-color: {conf_color};"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)


def render_pros_cons(report):
    """Pros and cons from screener.in."""
    pros = report.get("pros", [])
    cons = report.get("cons", [])

    if not pros and not cons:
        return

    st.markdown('<div class="section-header">📊 Market Intelligence</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### ✅ Strengths", unsafe_allow_html=True)
        for p in pros:
            st.markdown(f"""
            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; color: #15803d;
                padding: 10px 14px; border-radius: 6px; margin: 8px 0; font-size: 14px;">
                {p}
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown("#### ⚠️ Concerns", unsafe_allow_html=True)
        for c in cons:
            st.markdown(f"""
            <div style="background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c;
                padding: 10px 14px; border-radius: 6px; margin: 8px 0; font-size: 14px;">
                {c}
            </div>
            """, unsafe_allow_html=True)


def render_batch_runner():
    """Batch processing interface for NSE Microcap 250."""
    st.title("Batch Analysis Runner")
    
    tickers = load_tickers()
    reports = load_reports()
    
    analyzed_tickers = {r['ticker'] for r in reports}
    
    # Separate lists
    pending = [t for t in tickers if t['ticker'] not in analyzed_tickers]
    completed = [t for t in tickers if t['ticker'] in analyzed_tickers]
    
    # Progress
    total = len(tickers)
    done = len(completed)
    pct = done / total if total > 0 else 0
    
    st.metric("Progress", f"{done}/{total} Companies", f"{pct:.1%} Complete")
    st.progress(pct)
    
    st.markdown("### 🏃 Batch Controls")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.info(f"**{len(pending)}** companies pending analysis.")
        
        if pending:
            next_batch = pending[:5]
            batch_tickers = [t['ticker'] for t in next_batch]
            batch_str = ", ".join(batch_tickers)
            
            st.markdown(f"**Next Batch:** `{batch_str}`")
            
            if st.button(f"Analyze Next 5 ({batch_str})", type="primary"):
                st.success(f"Starting analysis for: {batch_str}")
                # Run in background using nohup or similar if possible, or just blocking for MVP
                # For MVP, we'll try blocking with spinner as it's safer for demo
                with st.spinner("Running batch analysis... This may take 5-10 minutes."):
                    try:
                        cmd = ["python", "mvp_run.py", "--batch", ",".join(batch_tickers)]
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        if result.returncode == 0:
                            st.success("Batch analysis complete! Refreshing...")
                            st.rerun()
                        else:
                            st.error(f"Analysis failed: {result.stderr}")
                    except Exception as e:
                        st.error(f"Error launching process: {e}")
        else:
            st.success("🎉 All companies analyzed!")

    with col2:
        st.markdown("### 📋 Company List")
        
        # Format function for dropdown
        def format_func(ticker):
            is_done = ticker in analyzed_tickers
            name = next((t['name'] for t in tickers if t['ticker'] == ticker), ticker)
            prefix = "✅" if is_done else "⚪"
            return f"{prefix} {ticker} - {name}"
            
        all_ticker_codes = [t['ticker'] for t in tickers]
        selected_ticker = st.selectbox(
            "Select Company", 
            all_ticker_codes, 
            format_func=format_func
        )
        
        if selected_ticker and selected_ticker not in analyzed_tickers:
            if st.button(f"Analyze {selected_ticker} Now"):
                 with st.spinner(f"Analyzing {selected_ticker}..."):
                    cmd = ["python", "mvp_run.py", selected_ticker]
                    subprocess.run(cmd)
                    st.rerun()
def render_architecture():
    """Render the system architecture diagram."""
    st.title("System Architecture & Agent Flow")
    
    st.markdown("""
    ### 🧠 Multi-Agent Forensic Workflow
    
    The system uses a graph-based orchestration (LangGraph) to coordinate specialized agents.
    """)
    
    st.graphviz_chart("""
    digraph G {
        rankdir=LR;
        node [shape=box, style=filled, fillcolor="white", fontname="Inter"];
        edge [fontname="Inter"];

        subgraph cluster_0 {
            label = "Data Gathering";
            style=filled;
            color=lightgrey;
            node [style=filled,color=white];
            fetch [label="Data Fetcher\n(Screener/NSE)"];
            memory [label="Memory\n(Vector DB)"];
        }

        subgraph cluster_1 {
            label = "Parallel Analysis Agents";
            style=filled;
            color="#e0f2fe";
            forensic [label="Forensic Agent\n(Financials)", fillcolor="#dbeafe"];
            mgmt [label="Management Agent\n(Governance)", fillcolor="#dbeafe"];
            rpt [label="RPT Agent\n(Transactions)", fillcolor="#dbeafe"];
            market [label="Market Intel\n(Web Search)", fillcolor="#dbeafe"];
        }

        aggregate [label="Aggregator", shape=ellipse];
        critic [label="Critic Agent\n(Validation)", fillcolor="#fee2e2"];
        report [label="Report Generator", shape=note];

        fetch -> memory;
        memory -> forensic;
        memory -> mgmt;
        memory -> rpt;
        memory -> market;

        forensic -> aggregate;
        mgmt -> aggregate;
        rpt -> aggregate;
        market -> aggregate;

        aggregate -> critic;
        critic -> report [label="Approved"];
        critic -> forensic [label="Re-investigate", style=dashed, color=red];
    }
    """)
    
    st.markdown("""
    ### 🛠 Component Stack
    - **Orchestration**: LangGraph (StateGraph)
    - **LLM Layer**: Google Gemini / Antigravity Proxy (Anthropic)
    - **Agents**:
        - `ForensicAgent`: Cash flow & revenue recognition analysis
        - `ManagementAgent`: Promoter integrity & governance checks
        - `RPTAgent`: Related party transaction web analysis
        - `MarketIntelAgent`: Qualitative web/social signals
        - `CriticAgent`: Peer review & falst positive reduction
    - **Persistence**: PostgreSQL + Redis + JSON (MVP)
    """)


def main():
    reports = load_reports()
    page, selected = render_sidebar(reports)

    if page == "System Architecture":
        render_architecture()
        return

    if page == "Batch Runner":
        render_batch_runner()
        return

    if not selected:
        st.title("ForensicValue AI")
        
        # Add main area dropdown for selection when nothing is selected
        if reports:
            st.markdown("### Select a Company to Analyze")
            
            ticker_options = [r['ticker'] for r in reports]
            
            # Format function to show score
            def format_report(ticker):
                r = next((r for r in reports if r['ticker'] == ticker), None)
                if r:
                    return f"{ticker} - Risk: {r.get('overall_risk_score', 0):.0f}"
                return ticker
                
            new_selection = st.selectbox(
                "Choose from analyzed companies:", 
                ticker_options,
                format_func=format_report,
                index=None,
                placeholder="Select a company...",
                key="main_company_select"
            )
            
            if new_selection:
                st.session_state["selected_ticker"] = new_selection
                st.rerun()
        
        if not selected:
             # if still not selected (first run with no default?)
             # Try to set default if available
             if reports:
                 st.session_state["selected_ticker"] = reports[0]["ticker"]
                 st.rerun()
             
             st.info("Run an analysis or select a company to see results.")
             return

    # Add a dropdown at the top of the report to switch companies quickly
    if reports:
         # Get current index safely
         try:
             current_index = [r['ticker'] for r in reports].index(selected['ticker'])
         except ValueError:
             current_index = 0
         
         col_switch, _ = st.columns([1, 2])
         with col_switch:
             ticker_options = [r['ticker'] for r in reports]
             scope_key = "switch_company_dropdown"
             
             # Callback to update session state
             def on_change():
                 st.session_state["selected_ticker"] = st.session_state[scope_key]
             
             st.selectbox(
                 "Switch Company", 
                 ticker_options, 
                 index=current_index,
                 key=scope_key,
                 label_visibility="collapsed",
                 on_change=on_change
             )

    render_report_header(selected)
    render_score_cards(selected)
    render_risk_meter(selected)
    render_narrative_report(selected)
    render_agent_research(selected)
    render_pros_cons(selected)


if __name__ == "__main__":
    main()
