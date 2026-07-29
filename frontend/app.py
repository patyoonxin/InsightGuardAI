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
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Reset & base ── */
*, *::before, *::after { box-sizing: border-box; }

html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background-color: #ffffff !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background-color: #f8f9fb !important;
    border-right: 1px solid #e8eaed !important;
}
[data-testid="stSidebar"] * { font-family: 'Inter', sans-serif; }
[data-testid="stSidebarNav"] { padding-top: 0; }

/* Hide the sidebar collapse toggle button */
[data-testid="stSidebarCollapseButton"],
button[kind="header"],
[data-testid="collapsedControl"] {
    display: none !important;
}

/* ── Main content padding ── */
[data-testid="stMainBlockContainer"] { padding-top: 2rem; }

/* ── Typography ── */
h1 { font-size: 2rem    !important; font-weight: 700 !important; color: #0d1117 !important; letter-spacing: -0.02em; margin-bottom: 0.2rem !important; }
h2 { font-size: 1.5rem  !important; font-weight: 600 !important; color: #0d1117 !important; }
h3 { font-size: 1.2rem  !important; font-weight: 600 !important; color: #0d1117 !important; letter-spacing: -0.01em; }
p, li, label { color: #5c6370 !important; font-size: 1rem; }

/* ── Metric cards ── */
div[data-testid="metric-container"] {
    background: #ffffff;
    border: 1px solid #e8eaed;
    border-radius: 10px;
    padding: 16px 20px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    transition: box-shadow 0.15s ease;
}
div[data-testid="metric-container"]:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}
div[data-testid="metric-container"] [data-testid="stMetricLabel"] {
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #8a909a !important;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 2rem !important;
    font-weight: 700 !important;
    color: #0d1117 !important;
}
div[data-testid="metric-container"] [data-testid="stMetricDelta"] {
    font-size: 0.95rem !important;
    font-weight: 500 !important;
}

/* ── Divider ── */
hr { border-color: #e8eaed !important; margin: 1.25rem 0 !important; }

/* ── Severity badges ── */
.badge {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 3px 10px;
    border-radius: 4px;
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
.badge-critical { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }
.badge-high     { background: #fffbeb; color: #b45309; border: 1px solid #fde68a; }
.badge-medium   { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }
.badge-low      { background: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0; }

/* ── Alert card ── */
.alert-card {
    background: #ffffff;
    border: 1px solid #e8eaed;
    border-left: 3px solid #b91c1c;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 8px;
    transition: box-shadow 0.15s ease;
}
.alert-card:hover { box-shadow: 0 3px 10px rgba(0,0,0,0.07); }
.alert-card-high   { border-left-color: #b45309; }
.alert-card-medium { border-left-color: #1d4ed8; }
.alert-card-low    { border-left-color: #15803d; }

/* ── Domain card ── */
.domain-card {
    background: #ffffff;
    border: 1px solid #e8eaed;
    border-radius: 10px;
    padding: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    transition: box-shadow 0.15s ease;
    height: 100%;
}
.domain-card:hover { box-shadow: 0 4px 14px rgba(0,0,0,0.08); }

/* ── AI analysis card ── */
.ai-card {
    background: #f8f9fb;
    border: 1px solid #e8eaed;
    border-radius: 10px;
    padding: 22px;
}

/* ── Source tag ── */
.source-tag {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #f3f4f6;
    color: #374151;
    font-size: 0.9rem;
    font-weight: 500;
    padding: 5px 12px;
    border-radius: 20px;
    border: 1px solid #e5e7eb;
    margin-bottom: 16px;
}

/* ── Risk score bar ── */
.risk-bar-wrap { background: #f1f3f4; border-radius: 4px; height: 6px; width: 100%; margin-top: 8px; }
.risk-bar      { border-radius: 4px; height: 6px; }

/* ── Section header ── */
.section-header {
    font-size: 0.85rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #8a909a;
    margin-bottom: 12px;
}

/* ── Page header strip ── */
.page-header {
    padding-bottom: 14px;
    margin-bottom: 6px;
    border-bottom: 1px solid #e8eaed;
}
.page-header h1 { margin-bottom: 2px !important; }
.page-header p  { margin: 0; color: #8a909a !important; font-size: 0.85rem; }

/* ── Sidebar logo area ── */
.sidebar-brand {
    padding: 8px 4px 16px;
}
.sidebar-brand .brand-name {
    font-size: 1.2rem;
    font-weight: 700;
    color: #0d1117;
    letter-spacing: -0.02em;
}
.sidebar-brand .brand-sub {
    font-size: 0.85rem;
    color: #8a909a;
    margin-top: 2px;
}

/* ── Nav radio ── */
[data-testid="stRadio"] label {
    font-size: 1rem !important;
    font-weight: 500 !important;
    color: #374151 !important;
}

/* ── Buttons ── */
[data-testid="stBaseButton-primary"] {
    background-color: #0d1117 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 7px !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    transition: background 0.15s ease !important;
}
[data-testid="stBaseButton-primary"]:hover {
    background-color: #1a2230 !important;
}
[data-testid="stBaseButton-secondary"] {
    background-color: #ffffff !important;
    color: #0d1117 !important;
    border: 1px solid #d1d5db !important;
    border-radius: 7px !important;
    font-weight: 500 !important;
    font-size: 1rem !important;
}
[data-testid="stBaseButton-secondary"]:hover {
    background-color: #f8f9fb !important;
    border-color: #9ca3af !important;
}

/* ── Dataframe / table ── */
[data-testid="stDataFrame"] {
    border: 1px solid #e8eaed !important;
    border-radius: 8px !important;
    overflow: hidden;
}

/* ── Info / warning / error banners ── */
[data-testid="stAlert"] {
    border-radius: 8px !important;
    font-size: 1rem !important;
}

/* ── Spinner ── */
[data-testid="stSpinner"] { color: #0d1117 !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #f1f3f4; }
::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #9ca3af; }
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
    return {
        "critical": "#b91c1c",
        "high":     "#b45309",
        "medium":   "#1d4ed8",
        "low":      "#15803d",
    }.get(s, "#6b7280")


def risk_score_color(score: int):
    if score >= 75: return "#b91c1c"
    if score >= 55: return "#b45309"
    if score >= 35: return "#1d4ed8"
    return "#15803d"


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


def plotly_light_layout(**kwargs):
    """Return a consistent light-theme Plotly layout dict."""
    base = dict(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(family="Inter, -apple-system, sans-serif", color="#5c6370", size=14),
        margin=dict(t=44, b=24, l=10, r=10),
        xaxis=dict(showgrid=False, color="#9ca3af", linecolor="#e8eaed", tickfont_color="#9ca3af"),
        yaxis=dict(showgrid=True, gridcolor="#f1f3f4", color="#9ca3af", linecolor="#e8eaed", tickfont_color="#9ca3af"),
        legend=dict(bgcolor="rgba(255,255,255,0)", font_color="#5c6370"),
    )
    base.update(kwargs)
    return base


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div class="sidebar-brand">
        <div class="brand-name"> InsightGuardAI</div>
        <div class="brand-sub">Intelligent Early Warning System</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    page = st.radio(
        "Navigation",
        ["Executive Overview", "Finance", "Operations", "Customer", "AI Briefing"],
        label_visibility="collapsed",
    )

    st.divider()

    st.markdown('<p class="section-header">Filters</p>', unsafe_allow_html=True)
    severity_filter = st.multiselect(
        "Severity",
        ["critical", "high", "medium", "low"],
        default=["critical", "high"],
        label_visibility="collapsed",
    )

    st.divider()

    backend_ok = check_backend()
    if backend_ok:
        st.success("Backend connected", icon="✅")
    else:
        st.error("Backend offline", icon="🔴")
        st.code("uvicorn backend.main:app --reload", language="bash")

    st.markdown("")
    if st.button("Regenerate Data", use_container_width=True):
        fetch.clear()
        post("/api/regenerate-data")
        st.success("Data regenerated!")
        st.rerun()

    if st.button("Refresh Dashboard", use_container_width=True):
        fetch.clear()
        st.rerun()

    st.markdown(
        f"<p style='color:#c0c4cc;font-size:0.72rem;margin-top:12px;'>Last refresh: {datetime.now().strftime('%H:%M:%S')}</p>",
        unsafe_allow_html=True,
    )


# ── Backend check gate ────────────────────────────────────────────────────────
if not backend_ok:
    st.warning("Backend is not running. Please start the FastAPI server first.")
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Executive Overview
# ══════════════════════════════════════════════════════════════════════════════

if page == "Executive Overview":
    st.markdown("""
    <div class="page-header">
        <h1>Executive Overview</h1>
        <p>Real-time KPI health across Finance, Operations &amp; Customer domains</p>
    </div>
    """, unsafe_allow_html=True)

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
        st.metric("Overall Risk Score", f"{score}/100")
    with col2:
        st.metric("Total Anomalies", risk_data["total_anomalies"])
    with col3:
        st.metric("Critical Issues", risk_data["total_critical"])
    with col4:
        domains_at_risk = sum(1 for d in risk_data["domains"] if d["critical"] > 0 or d["high"] > 0)
        st.metric("Domains at Risk", f"{domains_at_risk}/3")

    st.divider()

    # ── Domain Risk Cards ─────────────────────────────────────────────────────
    st.markdown('<p class="section-header">Domain Risk Overview</p>', unsafe_allow_html=True)
    cols = st.columns(3)
    domain_icons = {"Finance": "💰", "Operations": "⚙️", "Customer": "👥"}

    for i, d in enumerate(risk_data["domains"]):
        with cols[i]:
            rs    = d["top_risk_score"]
            color = risk_score_color(rs)
            st.markdown(f"""
            <div class="domain-card">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">
                    <div style="font-size:0.95rem;font-weight:600;color:#374151;letter-spacing:-0.01em;">
                        {domain_icons.get(d['domain'],'📊')}&nbsp; {d['domain']}
                    </div>
                    <div style="font-size:0.7rem;font-weight:500;color:{color};background:{color}18;padding:2px 8px;border-radius:20px;border:1px solid {color}30;">
                        Risk Score
                    </div>
                </div>
                <div style="font-size:2.2rem;font-weight:700;color:{color};line-height:1;">{rs}<span style="font-size:0.9rem;font-weight:400;color:#9ca3af;">&thinsp;/100</span></div>
                <div class="risk-bar-wrap"><div class="risk-bar" style="width:{rs}%;background:{color};"></div></div>
                <div style="margin-top:12px;display:flex;gap:6px;flex-wrap:wrap;">
                    <span class="badge badge-critical">{d['critical']} Critical</span>
                    <span class="badge badge-high">{d['high']} High</span>
                    <span class="badge badge-medium">{d['medium']} Med</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # ── Target vs Actual ──────────────────────────────────────────────────────
    if tva and not isinstance(tva, dict):
        st.markdown('<p class="section-header">Target vs Actual Performance</p>', unsafe_allow_html=True)
        tva_cols = st.columns(len(tva))
        for i, item in enumerate(tva):
            with tva_cols[i]:
                delta_val   = item["gap_pct"]
                status_icon = {"on_track": "✅", "warning": "⚠️", "critical": "🔴"}.get(item["status"], "")
                st.metric(
                    label=f"{status_icon} {item['label']}",
                    value=fmt_value(item["actual"], item["unit"]),
                    delta=f"{delta_val:+.1f}% vs target",
                    delta_color="normal" if delta_val >= 0 else "inverse",
                )
        st.divider()

    # ── Active Alerts ─────────────────────────────────────────────────────────
    st.markdown('<p class="section-header">Active Alerts</p>', unsafe_allow_html=True)
    filtered_anoms = (
        [a for a in anomalies_all if a["severity"] in severity_filter]
        if not isinstance(anomalies_all, dict) else []
    )

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
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span class="badge badge-{sev}">{sev.upper()}</span>
                        <span style="font-size:1rem;font-weight:600;color:#0d1117;">{a['domain']} — {a['metric_label']}</span>
                    </div>
                    <div style="font-size:0.9rem;color:#9ca3af;">{a['date']}</div>
                </div>
                <div style="margin-top:7px;font-size:0.95rem;color:#5c6370;">
                    {dir_sym}&nbsp;<strong style="color:{color};">{fmt_value(a['value'], a['unit'])}</strong>
                    &nbsp;vs expected&nbsp;<strong style="color:#374151;">{fmt_value(a['expected'], a['unit'])}</strong>
                    &nbsp;·&nbsp;<span style="color:{color};font-weight:500;">{a['deviation_pct']:+.1f}%</span>
                    &nbsp;·&nbsp;Risk&nbsp;<strong style="color:{color};">{a['risk_score']}</strong>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ── Anomaly Distribution Charts ───────────────────────────────────────────
    if filtered_anoms:
        st.divider()
        st.markdown('<p class="section-header">Anomaly Distribution</p>', unsafe_allow_html=True)
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            domain_counts = pd.DataFrame(filtered_anoms).groupby("domain").size().reset_index(name="count")
            fig = px.bar(
                domain_counts, x="domain", y="count", color="domain",
                color_discrete_map={
                    "Finance":    "#3b82f6",
                    "Operations": "#f59e0b",
                    "Customer":   "#10b981",
                },
                title="Anomalies by Domain",
            )
            fig.update_layout(
                **plotly_light_layout(showlegend=False),
                title_font=dict(size=13, color="#0d1117", family="Inter"),
            )
            fig.update_traces(marker_line_width=0)
            st.plotly_chart(fig, use_container_width=True)

        with chart_col2:
            sev_counts    = pd.DataFrame(filtered_anoms).groupby("severity").size().reset_index(name="count")
            sev_color_map = {
                "critical": "#ef4444",
                "high":     "#f59e0b",
                "medium":   "#3b82f6",
                "low":      "#10b981",
            }
            fig2 = px.pie(
                sev_counts, names="severity", values="count",
                color="severity", color_discrete_map=sev_color_map,
                title="Severity Breakdown",
                hole=0.55,
            )
            fig2.update_layout(
                **plotly_light_layout(),
                title_font=dict(size=13, color="#0d1117", family="Inter"),
            )
            fig2.update_traces(
                textfont_size=12,
                marker=dict(line=dict(color="#ffffff", width=2)),
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
        "color": "#3b82f6",
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
        "color": "#f59e0b",
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
        "color": "#10b981",
    },
}


def render_domain_page(domain_name: str):
    cfg = DOMAIN_CONFIG[domain_name]

    st.markdown(f"""
    <div class="page-header">
        <h1>{cfg['icon']} {domain_name}</h1>
        <p>KPI performance, trend analysis and anomaly detection</p>
    </div>
    """, unsafe_allow_html=True)

    kpis      = fetch(f"/api/kpis/{cfg['key']}")
    anoms_raw = fetch(f"/api/anomalies?domain={domain_name}&limit=50")

    if isinstance(kpis, dict) and "error" in kpis:
        st.error(kpis["error"])
        return

    df = pd.DataFrame(kpis)
    df["date"] = pd.to_datetime(df["date"])
    anoms = (
        [a for a in anoms_raw if a["severity"] in severity_filter]
        if not isinstance(anoms_raw, dict) else []
    )

    # ── Latest KPIs ───────────────────────────────────────────────────────────
    st.markdown('<p class="section-header">Latest KPIs</p>', unsafe_allow_html=True)
    latest = df.iloc[-1]
    prev   = df.iloc[-2] if len(df) > 1 else df.iloc[-1]
    cols   = st.columns(min(len(cfg["metrics"]), 4))

    for i, (col_name, label, unit) in enumerate(cfg["metrics"][:4]):
        if col_name in df.columns:
            val   = latest[col_name]
            pval  = prev[col_name]
            delta = round(((val - pval) / abs(pval)) * 100, 1) if pval != 0 else 0
            with cols[i % 4]:
                st.metric(label, fmt_value(val, unit), delta=f"{delta:+.1f}% MoM")

    st.divider()

    # ── Trend Analysis ────────────────────────────────────────────────────────
    st.markdown('<p class="section-header">Trend Analysis</p>', unsafe_allow_html=True)
    metrics_to_plot = cfg["metrics"]
    n_cols = 2
    for row_start in range(0, len(metrics_to_plot), n_cols):
        row_metrics = metrics_to_plot[row_start:row_start + n_cols]
        c = st.columns(n_cols)
        for j, (col_name, label, unit) in enumerate(row_metrics):
            if col_name not in df.columns:
                continue
            with c[j]:
                anom_dates = {a["date"] for a in anoms if a["metric"] == col_name}
                fig = go.Figure()

                # Area fill
                r, g, b = tuple(int(cfg["color"].lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
                fig.add_trace(go.Scatter(
                    x=df["date"], y=df[col_name],
                    mode="lines",
                    name=label,
                    line=dict(color=cfg["color"], width=2),
                    fill="tozeroy",
                    fillcolor=f"rgba({r},{g},{b},0.07)",
                ))

                # Target line
                for actual_c, target_c, _ in cfg["target_pairs"]:
                    if actual_c == col_name and target_c in df.columns:
                        fig.add_trace(go.Scatter(
                            x=df["date"], y=df[target_c],
                            mode="lines", name="Target",
                            line=dict(color="#ef4444", width=1.5, dash="dash"),
                        ))

                # Anomaly markers
                anom_rows = df[df["date"].dt.strftime("%Y-%m-%d").isin(anom_dates)]
                if not anom_rows.empty:
                    fig.add_trace(go.Scatter(
                        x=anom_rows["date"], y=anom_rows[col_name],
                        mode="markers", name="Anomaly",
                        marker=dict(color="#ef4444", size=9, symbol="x", line=dict(width=2, color="#ef4444")),
                    ))

                fig.update_layout(
                    **plotly_light_layout(height=260),
                    title=dict(text=label, font=dict(size=12, color="#0d1117", family="Inter"), x=0),
                )
                st.plotly_chart(fig, use_container_width=True)

    # ── Anomalies Table ───────────────────────────────────────────────────────
    if anoms:
        st.divider()
        st.markdown(f'<p class="section-header">{domain_name} Anomalies &nbsp;<span style="font-weight:400;color:#9ca3af;">({len(anoms)})</span></p>', unsafe_allow_html=True)
        anom_df = pd.DataFrame([{
            "Date":       a["date"],
            "Metric":     a["metric_label"],
            "Severity":   a["severity"].upper(),
            "Value":      f"{a['value']}{a['unit']}",
            "Expected":   f"{a['expected']}{a['unit']}",
            "Deviation":  f"{a['deviation_pct']:+.1f}%",
            "Risk Score": a["risk_score"],
        } for a in anoms])
        st.dataframe(anom_df, use_container_width=True, hide_index=True)


if page in DOMAIN_CONFIG:
    render_domain_page(page)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: AI Briefing
# ══════════════════════════════════════════════════════════════════════════════

elif page == "AI Briefing":
    st.markdown("""
    <div class="page-header">
        <h1>AI Executive Briefing</h1>
        <p>AI-powered root-cause analysis and recommended actions</p>
    </div>
    """, unsafe_allow_html=True)

    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        run = st.button("Generate AI Briefing", type="primary", use_container_width=True)
    with col_info:
        st.caption(
            "Analyses the top anomalies and produces an executive briefing. "
            "Uses WorkBuddy MCP → OpenAI → Rule-based fallback."
        )

    if "ai_result" not in st.session_state:
        st.session_state.ai_result = None

    if run:
        with st.spinner("Analysing anomalies and generating briefing…"):
            result = post("/api/analyse", {"top_n": 8})
            if "error" not in result:
                st.session_state.ai_result = result
            else:
                st.error(f"Analysis failed: {result['error']}")

    if st.session_state.ai_result:
        r = st.session_state.ai_result
        source_color = {
            "WorkBuddy MCP": "#15803d",
            "OpenAI":        "#1d4ed8",
            "Rule-based":    "#6b7280",
        }.get(r.get("source", ""), "#6b7280")

        st.markdown(f"""
        <div style="margin-bottom:16px;">
            <span class="source-tag">
                ⚡ Source: <strong style="color:{source_color};">{r.get('source','Unknown')}</strong>
            </span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f'<div class="ai-card">', unsafe_allow_html=True)
        st.markdown(r.get("text", "No analysis available."))
        st.markdown("</div>", unsafe_allow_html=True)

        st.divider()
        st.markdown('<p class="section-header">Supporting Anomaly Data</p>', unsafe_allow_html=True)
        anoms_all = fetch("/api/anomalies?limit=8")
        if not isinstance(anoms_all, dict):
            supp_df = pd.DataFrame([{
                "Domain":     a["domain"],
                "Metric":     a["metric_label"],
                "Date":       a["date"],
                "Severity":   a["severity"].upper(),
                "Deviation":  f"{a['deviation_pct']:+.1f}%",
                "Risk Score": a["risk_score"],
            } for a in anoms_all])
            st.dataframe(supp_df, use_container_width=True, hide_index=True)
    else:
        st.info("Click **Generate AI Briefing** to run the analysis.")
