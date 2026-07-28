"""
InsightGuardAI — Streamlit Executive Dashboard
"""

import streamlit as st
import httpx
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="InsightGuardAI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Main background */
[data-testid="stAppViewContainer"] { background-color: #0f1117; }
[data-testid="stSidebar"]          { background-color: #161b22; border-right: 1px solid #21262d; }

/* Metric cards */
div[data-testid="metric-container"] {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 12px 16px;
}

/* Headers */
h1, h2, h3 { color: #e6edf3 !important; }
p, li       { color: #8b949e !important; }

/* Severity badges */
.badge-critical { background:#da3633; color:#fff; padding:2px 8px; border-radius:4px; font-size:0.75rem; font-weight:600; }
.badge-high     { background:#d29922; color:#fff; padding:2px 8px; border-radius:4px; font-size:0.75rem; font-weight:600; }
.badge-medium   { background:#388bfd; color:#fff; padding:2px 8px; border-radius:4px; font-size:0.75rem; font-weight:600; }
.badge-low      { background:#3fb950; color:#fff; padding:2px 8px; border-radius:4px; font-size:0.75rem; font-weight:600; }

/* Alert card */
.alert-card {
    background: #161b22;
    border-left: 4px solid #da3633;
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 10px;
}
.alert-card-high   { border-left-color: #d29922; }
.alert-card-medium { border-left-color: #388bfd; }
.alert-card-low    { border-left-color: #3fb950; }

/* AI analysis card */
.ai-card {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 20px;
}

/* Source tag */
.source-tag {
    display:inline-block;
    background:#21262d;
    color:#8b949e;
    font-size:0.72rem;
    padding:2px 8px;
    border-radius:12px;
    margin-bottom:12px;
}

/* Risk score bar */
.risk-bar-wrap { background:#21262d; border-radius:4px; height:8px; width:100%; margin-top:4px; }
.risk-bar      { border-radius:4px; height:8px; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def fetch(endpoint: str):
    try:
        r = httpx.get(f"{API_BASE}{endpoint}", timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def post(endpoint: str, body: dict = {}):
    try:
        r = httpx.post(f"{API_BASE}{endpoint}", json=body, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def severity_color(s: str):
    return {"critical": "#da3633", "high": "#d29922", "medium": "#388bfd", "low": "#3fb950"}.get(s, "#8b949e")


def risk_score_color(score: int):
    if score >= 75: return "#da3633"
    if score >= 55: return "#d29922"
    if score >= 35: return "#388bfd"
    return "#3fb950"


def fmt_value(v, unit):
    if unit == "USD":
        if abs(v) >= 1_000_000: return f"${v/1_000_000:.2f}M"
        if abs(v) >= 1_000:     return f"${v/1_000:.1f}K"
        return f"${v:.0f}"
    return f"{v}{unit}"


def check_backend():
    try:
        r = httpx.get(f"{API_BASE}/health", timeout=5)
        return r.status_code == 200
    except:
        return False


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🛡️ InsightGuardAI")
    st.markdown("*Intelligent Early Warning System*")
    st.divider()

    page = st.radio(
        "Navigation",
        ["Executive Overview", "Finance", "Operations", "Customer", "AI Briefing"],
        label_visibility="collapsed",
    )

    st.divider()

    severity_filter = st.multiselect(
        "Severity Filter",
        ["critical", "high", "medium", "low"],
        default=["critical", "high"],
    )

    st.divider()

    backend_ok = check_backend()
    if backend_ok:
        st.success("Backend connected", icon="✅")
    else:
        st.error("Backend offline — start FastAPI", icon="🔴")
        st.code("uvicorn backend.main:app --reload", language="bash")

    if st.button("Regenerate Data", use_container_width=True):
        fetch.clear()
        post("/api/regenerate-data")
        st.success("Data regenerated!")
        st.rerun()

    if st.button("Refresh Dashboard", use_container_width=True):
        fetch.clear()
        st.rerun()

    st.markdown(f"<small style='color:#444'>Last refresh: {datetime.now().strftime('%H:%M:%S')}</small>", unsafe_allow_html=True)


# ── Backend check gate ────────────────────────────────────────────────────────
if not backend_ok:
    st.warning("⚠️ Backend is not running. Please start the FastAPI server first.")
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Executive Overview
# ══════════════════════════════════════════════════════════════════════════════

if page == "Executive Overview":
    st.markdown("# Executive Overview")
    st.markdown("*Real-time KPI health across Finance, Operations & Customer domains*")

    risk_data     = fetch("/api/risk-summary")
    anomalies_all = fetch("/api/anomalies?limit=100")
    tva           = fetch("/api/target-vs-actual")

    if "error" in risk_data:
        st.error(f"Failed to load data: {risk_data['error']}")
        st.stop()

    # ── KPI Summary Row ───────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    score = risk_data["overall_risk_score"]
    score_color = risk_score_color(score)
    with col1:
        st.metric("Overall Risk Score", f"{score}/100", delta=None)
    with col2:
        st.metric("Total Anomalies", risk_data["total_anomalies"])
    with col3:
        st.metric("Critical Issues", risk_data["total_critical"])
    with col4:
        domains_at_risk = sum(1 for d in risk_data["domains"] if d["critical"] > 0 or d["high"] > 0)
        st.metric("Domains at Risk", f"{domains_at_risk}/3")

    st.divider()

    # ── Domain Risk Cards ─────────────────────────────────────────────────────
    st.markdown("### Domain Risk Overview")
    cols = st.columns(3)
    domain_icons = {"Finance": "💰", "Operations": "⚙️", "Customer": "👥"}

    for i, d in enumerate(risk_data["domains"]):
        with cols[i]:
            rs = d["top_risk_score"]
            color = risk_score_color(rs)
            st.markdown(f"""
            <div style="background:#161b22;border:1px solid #21262d;border-radius:8px;padding:16px;">
                <div style="font-size:1.3rem;margin-bottom:4px;">{domain_icons.get(d['domain'],'📊')} {d['domain']}</div>
                <div style="font-size:2rem;font-weight:700;color:{color};">{rs}<span style="font-size:1rem;color:#8b949e;">/100</span></div>
                <div class="risk-bar-wrap"><div class="risk-bar" style="width:{rs}%;background:{color};"></div></div>
                <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap;">
                    <span class="badge-critical">{d['critical']} Critical</span>
                    <span class="badge-high">{d['high']} High</span>
                    <span class="badge-medium">{d['medium']} Med</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # ── Target vs Actual ─────────────────────────────────────────────────────
    if tva and not isinstance(tva, dict):
        st.markdown("### Target vs Actual Performance")
        tva_cols = st.columns(len(tva))
        for i, item in enumerate(tva):
            with tva_cols[i]:
                delta_val = item["gap_pct"]
                status_icon = {"on_track": "✅", "warning": "⚠️", "critical": "🔴"}.get(item["status"], "")
                st.metric(
                    label=f"{status_icon} {item['label']}",
                    value=fmt_value(item["actual"], item["unit"]),
                    delta=f"{delta_val:+.1f}% vs target",
                    delta_color="normal" if delta_val >= 0 else "inverse",
                )
        st.divider()

    # ── Critical Alerts ───────────────────────────────────────────────────────
    st.markdown("### Active Alerts")
    filtered_anoms = [a for a in anomalies_all if a["severity"] in severity_filter] if not isinstance(anomalies_all, dict) else []

    if not filtered_anoms:
        st.info("No anomalies match the current severity filter.")
    else:
        for a in filtered_anoms[:8]:
            sev     = a["severity"]
            color   = severity_color(sev)
            dir_sym = "▲" if a["direction"] == "above" else "▼"
            st.markdown(f"""
            <div class="alert-card alert-card-{sev}">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <span class="badge-{sev}">{sev.upper()}</span>
                        <span style="color:#e6edf3;font-weight:600;margin-left:8px;">{a['domain']} — {a['metric_label']}</span>
                    </div>
                    <div style="color:#8b949e;font-size:0.8rem;">{a['date']}</div>
                </div>
                <div style="margin-top:6px;color:#8b949e;">
                    {dir_sym} <strong style="color:{color};">{fmt_value(a['value'], a['unit'])}</strong>
                    &nbsp;vs expected <strong>{fmt_value(a['expected'], a['unit'])}</strong>
                    &nbsp;·&nbsp; <span style="color:{color};">{a['deviation_pct']:+.1f}%</span>
                    &nbsp;·&nbsp; Risk Score: <strong style="color:{color};">{a['risk_score']}</strong>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ── Anomaly Count by Domain Chart ─────────────────────────────────────────
    if filtered_anoms:
        st.divider()
        st.markdown("### Anomaly Distribution")
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            domain_counts = pd.DataFrame(filtered_anoms).groupby("domain").size().reset_index(name="count")
            fig = px.bar(
                domain_counts, x="domain", y="count", color="domain",
                color_discrete_map={"Finance": "#388bfd", "Operations": "#d29922", "Customer": "#3fb950"},
                title="Anomaly Count by Domain",
            )
            fig.update_layout(
                paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
                font_color="#8b949e", showlegend=False,
                title_font_color="#e6edf3",
                xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#21262d"),
                margin=dict(t=40, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)

        with chart_col2:
            sev_counts = pd.DataFrame(filtered_anoms).groupby("severity").size().reset_index(name="count")
            sev_color_map = {"critical": "#da3633", "high": "#d29922", "medium": "#388bfd", "low": "#3fb950"}
            fig2 = px.pie(
                sev_counts, names="severity", values="count",
                color="severity", color_discrete_map=sev_color_map,
                title="Severity Breakdown",
                hole=0.5,
            )
            fig2.update_layout(
                paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
                font_color="#8b949e", title_font_color="#e6edf3",
                margin=dict(t=40, b=20),
            )
            st.plotly_chart(fig2, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Domain Detail (Finance / Operations / Customer)
# ══════════════════════════════════════════════════════════════════════════════

DOMAIN_CONFIG = {
    "Finance": {
        "key": "finance",
        "icon": "💰",
        "metrics": [
            ("revenue",           "Revenue",           "USD"),
            ("gross_margin_pct",  "Gross Margin",      "%"),
            ("ebitda_margin_pct", "EBITDA Margin",     "%"),
            ("ar_days",           "AR Days",           " days"),
            ("cash_balance",      "Cash Balance",      "USD"),
        ],
        "target_pairs": [("revenue", "revenue_target", "Revenue Target")],
        "color": "#388bfd",
    },
    "Operations": {
        "key": "operations",
        "icon": "⚙️",
        "metrics": [
            ("oee_pct",              "OEE",              "%"),
            ("defect_rate_pct",      "Defect Rate",      "%"),
            ("on_time_delivery_pct", "On-Time Delivery", "%"),
            ("downtime_hours",       "Downtime Hours",   " hrs"),
            ("unit_cost",            "Unit Cost",        " USD"),
        ],
        "target_pairs": [("oee_pct", "oee_target_pct", "OEE Target")],
        "color": "#d29922",
    },
    "Customer": {
        "key": "customer",
        "icon": "👥",
        "metrics": [
            ("nps",                      "NPS",               " pts"),
            ("csat",                     "CSAT",              "/5"),
            ("churn_rate_pct",           "Churn Rate",        "%"),
            ("new_customers",            "New Customers",     ""),
            ("avg_resolution_time_hrs",  "Resolution Time",   " hrs"),
            ("customer_lifetime_value",  "Customer LTV",      " USD"),
        ],
        "target_pairs": [],
        "color": "#3fb950",
    },
}


def render_domain_page(domain_name: str):
    cfg = DOMAIN_CONFIG[domain_name]
    st.markdown(f"# {cfg['icon']} {domain_name} KPIs")

    kpis      = fetch(f"/api/kpis/{cfg['key']}")
    anoms_raw = fetch(f"/api/anomalies?domain={domain_name}&limit=50")

    if isinstance(kpis, dict) and "error" in kpis:
        st.error(kpis["error"])
        return

    df = pd.DataFrame(kpis)
    df["date"] = pd.to_datetime(df["date"])
    anoms = [a for a in anoms_raw if a["severity"] in severity_filter] if not isinstance(anoms_raw, dict) else []

    # Latest metrics summary row
    latest = df.iloc[-1]
    prev   = df.iloc[-2] if len(df) > 1 else df.iloc[-1]

    st.markdown("### Latest KPIs")
    cols = st.columns(min(len(cfg["metrics"]), 4))
    for i, (col_name, label, unit) in enumerate(cfg["metrics"][:4]):
        if col_name in df.columns:
            val  = latest[col_name]
            pval = prev[col_name]
            delta = round(((val - pval) / abs(pval)) * 100, 1) if pval != 0 else 0
            with cols[i % 4]:
                st.metric(label, fmt_value(val, unit), delta=f"{delta:+.1f}% MoM")

    st.divider()

    # KPI trend charts
    st.markdown("### Trend Analysis")
    metrics_to_plot = cfg["metrics"]
    n_cols = 2
    for row_start in range(0, len(metrics_to_plot), n_cols):
        row_metrics = metrics_to_plot[row_start:row_start + n_cols]
        c = st.columns(n_cols)
        for j, (col_name, label, unit) in enumerate(row_metrics):
            if col_name not in df.columns:
                continue
            with c[j]:
                # Mark anomaly dates on chart
                anom_dates = {a["date"] for a in anoms if a["metric"] == col_name}

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df["date"], y=df[col_name],
                    mode="lines",
                    name=label,
                    line=dict(color=cfg["color"], width=2),
                    fill="tozeroy",
                    fillcolor=f"rgba{tuple(int(cfg['color'].lstrip('#')[i:i+2],16) for i in (0,2,4)) + (0.07,)}",
                ))

                # Add target line if applicable
                for actual_c, target_c, _ in cfg["target_pairs"]:
                    if actual_c == col_name and target_c in df.columns:
                        fig.add_trace(go.Scatter(
                            x=df["date"], y=df[target_c],
                            mode="lines", name="Target",
                            line=dict(color="#da3633", width=1.5, dash="dash"),
                        ))

                # Anomaly markers
                anom_rows = df[df["date"].dt.strftime("%Y-%m-%d").isin(anom_dates)]
                if not anom_rows.empty:
                    fig.add_trace(go.Scatter(
                        x=anom_rows["date"], y=anom_rows[col_name],
                        mode="markers", name="Anomaly",
                        marker=dict(color="#da3633", size=10, symbol="x"),
                    ))

                fig.update_layout(
                    title=label, title_font_color="#e6edf3",
                    paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
                    font_color="#8b949e", margin=dict(t=40, b=20, l=10, r=10),
                    xaxis=dict(showgrid=False, color="#8b949e"),
                    yaxis=dict(showgrid=True, gridcolor="#21262d", color="#8b949e"),
                    legend=dict(bgcolor="rgba(0,0,0,0)", font_color="#8b949e"),
                    height=280,
                )
                st.plotly_chart(fig, use_container_width=True)

    # Domain anomalies table
    if anoms:
        st.divider()
        st.markdown(f"### {domain_name} Anomalies ({len(anoms)})")
        anom_df = pd.DataFrame([{
            "Date": a["date"],
            "Metric": a["metric_label"],
            "Severity": a["severity"].upper(),
            "Value": f"{a['value']}{a['unit']}",
            "Expected": f"{a['expected']}{a['unit']}",
            "Deviation": f"{a['deviation_pct']:+.1f}%",
            "Risk Score": a["risk_score"],
        } for a in anoms])
        st.dataframe(anom_df, use_container_width=True, hide_index=True)


if page in DOMAIN_CONFIG:
    render_domain_page(page)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: AI Briefing
# ══════════════════════════════════════════════════════════════════════════════

elif page == "AI Briefing":
    st.markdown("# 🤖 AI Executive Briefing")
    st.markdown("*AI-powered root-cause analysis and recommended actions*")

    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        run = st.button("Generate AI Briefing", type="primary", use_container_width=True)
    with col_info:
        st.caption("Analyses the top anomalies and produces an executive briefing. Uses WorkBuddy MCP → OpenAI → Rule-based fallback.")

    if "ai_result" not in st.session_state:
        st.session_state.ai_result = None

    if run:
        with st.spinner("Analysing anomalies and generating briefing..."):
            result = post("/api/analyse", {"top_n": 8})
            if "error" not in result:
                st.session_state.ai_result = result
            else:
                st.error(f"Analysis failed: {result['error']}")

    if st.session_state.ai_result:
        r = st.session_state.ai_result
        source_color = {"WorkBuddy MCP": "#3fb950", "OpenAI": "#388bfd", "Rule-based": "#8b949e"}.get(r.get("source", ""), "#8b949e")
        st.markdown(f"""
        <div style="margin-bottom:16px;">
            <span class="source-tag">⚡ Source: <strong style="color:{source_color};">{r.get('source','Unknown')}</strong></span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(r.get("text", "No analysis available."))

        st.divider()
        # Supporting anomaly table
        st.markdown("### Supporting Anomaly Data")
        anoms_all = fetch("/api/anomalies?limit=8")
        if not isinstance(anoms_all, dict):
            supp_df = pd.DataFrame([{
                "Domain": a["domain"],
                "Metric": a["metric_label"],
                "Date": a["date"],
                "Severity": a["severity"].upper(),
                "Deviation": f"{a['deviation_pct']:+.1f}%",
                "Risk Score": a["risk_score"],
            } for a in anoms_all])
            st.dataframe(supp_df, use_container_width=True, hide_index=True)
    else:
        st.info("Click **Generate AI Briefing** to run the analysis.")
