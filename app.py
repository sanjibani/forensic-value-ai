"""
ForensicValue AI — Streamlit Dashboard

Main UI for initiating analyses, viewing results, and providing feedback.
"""
import streamlit as st
import json
from datetime import datetime

# Page config
st.set_page_config(
    page_title="ForensicValue AI",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    .stApp {
        font-family: 'Inter', sans-serif;
    }

    .risk-critical { color: #FF4444; font-weight: 700; }
    .risk-high { color: #FF8C00; font-weight: 600; }
    .risk-moderate { color: #FFD700; font-weight: 600; }
    .risk-low { color: #32CD32; font-weight: 600; }

    .finding-card {
        border: 1px solid #333;
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    }

    .metric-box {
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.1);
    }

    .severity-critical { border-left: 4px solid #FF4444; }
    .severity-high { border-left: 4px solid #FF8C00; }
    .severity-medium { border-left: 4px solid #FFD700; }
    .severity-low { border-left: 4px solid #32CD32; }

    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
    }
</style>
""", unsafe_allow_html=True)


def init_services():
    """Initialize backend services (cached)."""
    if "services_initialized" not in st.session_state:
        try:
            from src.config import settings
            from src.llm.provider import LLMProvider
            from src.storage.postgres import PostgresManager
            from src.storage.redis_cache import RedisCache
            from src.graph.workflow import ForensicWorkflow

            st.session_state.postgres = PostgresManager()
            st.session_state.llm = LLMProvider()

            try:
                st.session_state.redis = RedisCache()
            except Exception:
                st.session_state.redis = None

            st.session_state.workflow = ForensicWorkflow(
                llm=st.session_state.llm,
                postgres=st.session_state.postgres,
                redis=st.session_state.redis,
            )
            st.session_state.services_initialized = True
        except Exception as e:
            st.error(f"Failed to initialize services: {e}")
            st.session_state.services_initialized = False


def render_sidebar():
    """Render the sidebar."""
    with st.sidebar:
        st.markdown("# 🔍 ForensicValue AI")
        st.markdown("*Multi-agent forensic accounting analysis*")
        st.divider()

        page = st.radio(
            "Navigation",
            ["🏠 Dashboard", "📊 New Analysis", "📋 Analysis History", "⚙️ Settings"],
            label_visibility="collapsed",
        )

        st.divider()

        # Health check
        st.markdown("### System Status")
        if st.session_state.get("services_initialized"):
            pg_ok = st.session_state.postgres.health_check()
            st.markdown(f"{'✅' if pg_ok else '❌'} PostgreSQL")

            if st.session_state.redis:
                redis_ok = st.session_state.redis.health_check()
                st.markdown(f"{'✅' if redis_ok else '❌'} Redis")
            else:
                st.markdown("⚠️ Redis (not connected)")

            st.markdown("✅ LLM Provider")
        else:
            st.markdown("❌ Services not initialized")

        return page


def render_dashboard():
    """Main dashboard page."""
    st.markdown("## 📊 Dashboard")

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    if st.session_state.get("services_initialized"):
        try:
            recent = st.session_state.postgres.get_recent_analyses(20)
            total = len(recent)
            completed = len([a for a in recent if a.get("status") == "complete"])
            high_risk = len(
                [a for a in recent
                 if a.get("risk_score") and float(a["risk_score"]) >= 55]
            )
            avg_risk = (
                sum(float(a["risk_score"]) for a in recent if a.get("risk_score"))
                / max(1, len([a for a in recent if a.get("risk_score")]))
            )
        except Exception:
            total = completed = high_risk = 0
            avg_risk = 0
    else:
        total = completed = high_risk = 0
        avg_risk = 0

    with col1:
        st.metric("Total Analyses", total)
    with col2:
        st.metric("Completed", completed)
    with col3:
        st.metric("High Risk Alerts", high_risk)
    with col4:
        st.metric("Avg Risk Score", f"{avg_risk:.1f}")

    st.divider()

    # Recent analyses
    st.markdown("### Recent Analyses")
    if st.session_state.get("services_initialized"):
        try:
            analyses = st.session_state.postgres.get_recent_analyses(10)
            if analyses:
                for a in analyses:
                    risk = float(a.get("risk_score") or 0)
                    risk_class = (
                        "critical" if risk >= 75
                        else "high" if risk >= 55
                        else "moderate" if risk >= 35
                        else "low"
                    )

                    with st.expander(
                        f"**{a['company_ticker']}** — {a.get('company_name', '')} "
                        f"| Risk: {risk:.0f} | {a.get('status', 'unknown')}"
                    ):
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            st.markdown(f"**Sector:** {a.get('sector', 'N/A')}")
                        with col_b:
                            st.markdown(
                                f"**Risk Score:** "
                                f"<span class='risk-{risk_class}'>{risk:.1f}</span>",
                                unsafe_allow_html=True,
                            )
                        with col_c:
                            st.markdown(f"**Findings:** {a.get('findings_count', 0)}")

                        if a.get("id"):
                            if st.button(
                                "View Details",
                                key=f"view_{a['id']}",
                            ):
                                st.session_state.selected_analysis = a["id"]
            else:
                st.info("No analyses yet. Start a new analysis from the sidebar.")
        except Exception as e:
            st.warning(f"Could not load analyses: {e}")
    else:
        st.warning("Backend services not connected. Check configuration.")


def render_new_analysis():
    """New analysis form."""
    st.markdown("## 📊 New Forensic Analysis")

    with st.form("analysis_form"):
        col1, col2 = st.columns(2)

        with col1:
            ticker = st.text_input(
                "Stock Ticker (NSE)",
                placeholder="e.g., INFY, RELIANCE, TCS",
            ).upper()
            company_name = st.text_input(
                "Company Name (optional)",
                placeholder="Auto-detected if available",
            )

        with col2:
            sector = st.selectbox(
                "Sector",
                [
                    "Auto-detect",
                    "Information Technology",
                    "Banking & Finance",
                    "Pharmaceuticals",
                    "Consumer Goods",
                    "Automobile",
                    "Infrastructure",
                    "Energy",
                    "Metals & Mining",
                    "Real Estate",
                    "Telecom",
                    "Other",
                ],
            )
            analysis_depth = st.selectbox(
                "Analysis Depth",
                ["Full Analysis", "Quick Scan"],
            )

        st.divider()
        st.markdown("### 📄 Upload Annual Report (Optional)")
        pdf_file = st.file_uploader(
            "Upload PDF", type=["pdf"], label_visibility="collapsed"
        )

        submitted = st.form_submit_button(
            "🚀 Start Analysis",
            type="primary",
            use_container_width=True,
        )

    if submitted and ticker:
        if not st.session_state.get("services_initialized"):
            st.error("Services not initialized. Check your .env configuration.")
            return

        with st.spinner(f"Analyzing {ticker}... This may take 2-5 minutes."):
            try:
                report = st.session_state.workflow.analyze(
                    ticker=ticker,
                    company_name=company_name,
                    sector="" if sector == "Auto-detect" else sector,
                    analysis_depth="quick" if "Quick" in analysis_depth else "full",
                    hitl_mode="automatic",
                )

                if report.get("status") == "failed":
                    st.error(f"Analysis failed: {report.get('error', 'Unknown error')}")
                else:
                    st.success(
                        f"✅ Analysis complete for {ticker}! "
                        f"Risk Score: {report.get('overall_risk_score', 0):.1f}"
                    )
                    render_report(report)

            except Exception as e:
                st.error(f"Analysis error: {e}")

    elif submitted:
        st.warning("Please enter a stock ticker.")


def render_report(report: dict):
    """Render a full analysis report."""
    st.divider()
    st.markdown(f"## 📋 Report: {report.get('ticker', '')} — {report.get('company_name', '')}")

    # Score cards
    risk_score = report.get("overall_risk_score", 0)
    risk_level = report.get("risk_level", "UNKNOWN")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Overall Risk", f"{risk_score:.1f}", delta=risk_level)
    with col2:
        scores = report.get("scores", {})
        st.metric("Forensic Risk", f"{scores.get('forensic_risk', 0):.1f}")
    with col3:
        st.metric("Mgmt Quality", f"{scores.get('management_quality', 0):.1f}")
    with col4:
        st.metric("RPT Risk", f"{scores.get('rpt_risk', 0):.1f}")

    st.divider()

    # Summary tabs
    tab_summary, tab_findings, tab_raw = st.tabs(
        ["📝 Summary", "🔍 Findings", "📊 Raw Data"]
    )

    with tab_summary:
        summaries = report.get("summary", {})

        st.markdown("### Forensic Accounting")
        st.markdown(summaries.get("forensic", "No summary available."))

        st.markdown("### Management Integrity")
        st.markdown(summaries.get("management", "No summary available."))

        st.markdown("### Related Party Transactions")
        st.markdown(summaries.get("rpt", "No summary available."))

        if report.get("management_key_concerns"):
            st.markdown("### ⚠️ Key Concerns")
            for c in report["management_key_concerns"]:
                st.markdown(f"- {c}")

        if report.get("critic_summary"):
            st.markdown("### 🧪 Critic Assessment")
            st.markdown(report["critic_summary"])

    with tab_findings:
        findings = report.get("findings", [])
        if findings:
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            findings.sort(key=lambda f: severity_order.get(f.get("severity", "low"), 4))

            for i, f in enumerate(findings):
                severity = f.get("severity", "medium")
                emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")

                with st.expander(
                    f"{emoji} [{severity.upper()}] {f.get('title', 'Finding')} "
                    f"— Confidence: {f.get('confidence', 0):.0f}%"
                ):
                    st.markdown(f"**Agent:** {f.get('agent_name', 'N/A')}")
                    st.markdown(f"**Type:** {f.get('finding_type', 'N/A')}")
                    st.markdown(f"**Description:** {f.get('description', '')}")

                    evidence = f.get("evidence", [])
                    if evidence:
                        st.markdown("**Evidence:**")
                        for e in evidence:
                            if isinstance(e, dict):
                                st.json(e)
                            else:
                                st.markdown(f"- {e}")

                    # HITL feedback buttons
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        if st.button("✅ Approve", key=f"approve_{i}"):
                            st.success("Finding approved")
                    with col_b:
                        if st.button("❌ Reject", key=f"reject_{i}"):
                            st.warning("Finding rejected")
                    with col_c:
                        if st.button("🔍 Need More Info", key=f"more_{i}"):
                            st.info("Flagged for more info")
        else:
            st.info("No findings generated.")

    with tab_raw:
        st.json(report)


def render_history():
    """Analysis history page."""
    st.markdown("## 📋 Analysis History")

    if not st.session_state.get("services_initialized"):
        st.warning("Services not initialized.")
        return

    try:
        analyses = st.session_state.postgres.get_recent_analyses(50)
        if analyses:
            for a in analyses:
                risk = float(a.get("risk_score") or 0)
                st.markdown(
                    f"- **{a['company_ticker']}** ({a.get('company_name', '')}) "
                    f"| Risk: {risk:.0f} | Status: {a.get('status', '')} "
                    f"| {a.get('created_at', '')}"
                )
        else:
            st.info("No analyses found.")
    except Exception as e:
        st.error(f"Could not load history: {e}")


def render_settings():
    """Settings page."""
    st.markdown("## ⚙️ Settings")

    st.markdown("### LLM Provider Configuration")
    st.info(
        "Configure your LLM providers in the `.env` file. "
        "Set `GOOGLE_API_KEY` for Gemini, or enable "
        "`ANTIGRAVITY_ENABLED=true` for the proxy."
    )

    if st.session_state.get("services_initialized"):
        stats = st.session_state.llm.get_usage_stats()
        st.markdown("### Token Usage")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Calls", stats.get("calls", 0))
        with col2:
            st.metric("Input Tokens", f"{stats.get('input', 0):,}")
        with col3:
            st.metric("Output Tokens", f"{stats.get('output', 0):,}")


# ---- Main ----
def main():
    init_services()
    page = render_sidebar()

    if "Dashboard" in page:
        render_dashboard()
    elif "New Analysis" in page:
        render_new_analysis()
    elif "History" in page:
        render_history()
    elif "Settings" in page:
        render_settings()


if __name__ == "__main__":
    main()
