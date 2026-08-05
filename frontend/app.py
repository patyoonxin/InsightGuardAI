"""
InsightGuardAI — Streamlit Executive Dashboard
"""

import streamlit as st
import httpx
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import io
import re
import textwrap
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE = os.getenv(
    "API_URL",
    "http://localhost:8000"
)

st.set_page_config(
    page_title="InsightGuardAI",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap');

.ms {
    font-family: 'Material Symbols Outlined';
    font-style: normal;
    font-weight: normal;
    display: inline-block;
    line-height: 1;
    vertical-align: middle;
    font-size: 1.1em;
    user-select: none;
}

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
    color: #D3D3D3 !important;
}
[data-testid="stBaseButton-primary"] p,
[data-testid="stBaseButton-primary"] span {
    color: #ffffff !important;
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
        st.success("Backend connected")
    else:
        st.error("Backend offline", icon=":material/cancel:")
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
    domain_icons = {
        "Finance":    '<span class="ms">payments</span>',
        "Operations": '<span class="ms">precision_manufacturing</span>',
        "Customer":   '<span class="ms">group</span>',
    }

    for i, d in enumerate(risk_data["domains"]):
        with cols[i]:
            rs    = d["top_risk_score"]
            color = risk_score_color(rs)
            st.markdown(f"""
            <div class="domain-card">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">
                    <div style="font-size:0.95rem;font-weight:600;color:#374151;letter-spacing:-0.01em;">
                        {domain_icons.get(d['domain'], '<span class="ms">bar_chart</span>')}&nbsp; {d['domain']}
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
                status_icon = {"on_track": "✓", "warning": "⚠", "critical": "✕"}.get(item["status"], "")
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
        "icon": '<span class="ms">payments</span>',
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
        "icon": '<span class="ms">precision_manufacturing</span>',
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
        "icon": '<span class="ms">group</span>',
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
        <h1>{domain_name}</h1>
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


# ══════════════════════════════════════════════════════════════════════════════
# PDF EXPORT HELPER
# ══════════════════════════════════════════════════════════════════════════════

def generate_pdf_report(briefing_text: str, source: str, anomalies: list) -> bytes:
    """Generate a PDF executive briefing report and return as bytes."""
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    # ── Styles ─────────────────────────────────────────────────────────────────
    base_styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=base_styles["Heading1"],
        fontSize=22,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=4,
        alignment=TA_LEFT,
        fontName="Helvetica-Bold",
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=base_styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=2,
        fontName="Helvetica",
    )
    section_style = ParagraphStyle(
        "SectionHeader",
        parent=base_styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=14,
        spaceAfter=6,
        fontName="Helvetica-Bold",
    )
    body_style = ParagraphStyle(
        "BodyText",
        parent=base_styles["Normal"],
        fontSize=10,
        leading=15,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6,
        fontName="Helvetica",
    )
    bold_body_style = ParagraphStyle(
        "BoldBody",
        parent=body_style,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1e293b"),
    )
    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=base_styles["Normal"],
        fontSize=9,
        textColor=colors.white,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
    )
    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=base_styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#1e293b"),
        fontName="Helvetica",
        alignment=TA_LEFT,
    )
    footer_style = ParagraphStyle(
        "Footer",
        parent=base_styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#94a3b8"),
        alignment=TA_RIGHT,
        fontName="Helvetica",
    )

    SEVERITY_COLORS = {
        "CRITICAL": colors.HexColor("#dc2626"),
        "HIGH":     colors.HexColor("#ea580c"),
        "MEDIUM":   colors.HexColor("#d97706"),
        "LOW":      colors.HexColor("#16a34a"),
    }

    # ── Parse markdown into reportlab elements ─────────────────────────────────
    def md_to_elements(text: str, body_st, section_st):
        elems = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                elems.append(Spacer(1, 4))
                continue
            # H2 heading (## or **)
            if stripped.startswith("## "):
                elems.append(Paragraph(stripped[3:], section_st))
            elif stripped.startswith("# "):
                elems.append(Paragraph(stripped[2:], section_st))
            elif re.match(r"^\*\*(.+)\*\*$", stripped):
                heading_text = re.sub(r"^\*\*|\*\*$", "", stripped)
                elems.append(Paragraph(heading_text, bold_body_style))
            elif stripped.startswith("- ") or stripped.startswith("* "):
                # Bullet — convert inline **bold**
                item = stripped[2:]
                item = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", item)
                elems.append(Paragraph(f"• &nbsp; {item}", body_st))
            elif re.match(r"^\d+\.", stripped):
                # Numbered list
                item = re.sub(r"^\d+\.\s*", "", stripped)
                item = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", item)
                elems.append(Paragraph(item, body_st))
            else:
                # Normal paragraph — convert inline **bold**
                para = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", stripped)
                elems.append(Paragraph(para, body_st))
        return elems

    # ── Build document elements ────────────────────────────────────────────────
    elements = []
    generated_at = datetime.now().strftime("%B %d, %Y at %H:%M")

    # Header block
    elements.append(Paragraph("InsightGuardAI", title_style))
    elements.append(Paragraph("Executive KPI Briefing Report", subtitle_style))
    elements.append(Paragraph(f"Generated: {generated_at}  |  Source: {source}", subtitle_style))
    elements.append(Spacer(1, 6))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#3b82f6")))
    elements.append(Spacer(1, 10))

    # AI briefing body
    elements += md_to_elements(briefing_text, body_style, section_style)

    elements.append(Spacer(1, 12))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0")))
    elements.append(Spacer(1, 8))

    # Supporting anomaly table
    if anomalies:
        elements.append(Paragraph("Supporting Anomaly Data", section_style))
        elements.append(Spacer(1, 4))

        col_headers = ["Domain", "Metric", "Date", "Severity", "Deviation", "Risk Score"]
        table_data = [[Paragraph(h, table_header_style) for h in col_headers]]

        for a in anomalies:
            sev = a.get("severity", "").upper()
            sev_color = SEVERITY_COLORS.get(sev, colors.HexColor("#64748b"))
            sev_para = Paragraph(
                f'<font color="{sev_color.hexval() if hasattr(sev_color,"hexval") else "#64748b"}"><b>{sev}</b></font>',
                table_cell_style,
            )
            table_data.append([
                Paragraph(a.get("domain", ""), table_cell_style),
                Paragraph(a.get("metric_label", ""), table_cell_style),
                Paragraph(a.get("date", ""), table_cell_style),
                Paragraph(f"<b>{sev}</b>", table_cell_style),
                Paragraph(f"{a.get('deviation_pct', 0):+.1f}%", table_cell_style),
                Paragraph(str(a.get("risk_score", "")), table_cell_style),
            ])

        col_widths = [3.0*cm, 5.2*cm, 2.4*cm, 2.2*cm, 2.4*cm, 2.4*cm]
        tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
            ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING",  (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(KeepTogether([tbl]))

    elements.append(Spacer(1, 16))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0")))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        f"InsightGuardAI  •  Confidential  •  {generated_at}",
        footer_style,
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer.read()


if page in DOMAIN_CONFIG:
    render_domain_page(page)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: AI Briefing
# ══════════════════════════════════════════════════════════════════════════════

elif page == "AI Briefing":
    st.markdown("""
    <div class="page-header">
        <h1>AI Executive Briefing</h1>
        <p>AI-powered root-cause analysis with trend detection, forecasting and cross-domain incidents</p>
    </div>
    """, unsafe_allow_html=True)

    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        run = st.button("Generate AI Briefing", type="primary", use_container_width=True)
    with col_info:
        st.caption(
            "Analyses anomalies, sustained trends, 3-month forecasts and cross-domain incidents. "
            "Uses Gemini API → Rule-based fallback."
        )

    if "ai_result" not in st.session_state:
        st.session_state.ai_result = None
    if "insights_data" not in st.session_state:
        st.session_state.insights_data = None

    if run:
        with st.spinner("Running advanced analytics and generating briefing…"):
            result   = post("/api/analyse", {"top_n": 8})
            insights = fetch("/api/insights")
            if "error" not in result:
                st.session_state.ai_result    = result
                st.session_state.insights_data = insights if not isinstance(insights, dict) or "error" not in insights else None
            else:
                st.error(f"Analysis failed: {result['error']}")

    if st.session_state.ai_result:
        r        = st.session_state.ai_result
        insights = st.session_state.insights_data or {}

        # ── Source tag + summary counters ─────────────────────────────────────
        source_color = {
            "Gemini":     "#1d4ed8",
            "Rule-based": "#6b7280",
        }.get(r.get("source", ""), "#6b7280")

        mc1, mc2, mc3, mc4 = st.columns(4)
        anoms_all_raw = fetch("/api/anomalies?limit=100")
        anoms_all     = anoms_all_raw if not isinstance(anoms_all_raw, dict) else []
        with mc1:
            st.metric("Anomalies Detected", len(anoms_all))
        with mc2:
            st.metric("Trend Deteriorations", r.get("trend_count", 0))
        with mc3:
            st.metric("Forecast Warnings", r.get("forecast_count", 0))
        with mc4:
            st.metric("Business Incidents", r.get("incident_count", 0))

        st.markdown(f"""
        <div style="margin:14px 0 6px;">
            <span class="source-tag">
                <span class="ms" style="font-size:1em;">bolt</span>
                Source: <strong style="color:{source_color};">{r.get('source','Unknown')}</strong>
            </span>
        </div>
        """, unsafe_allow_html=True)

        # ── AI Briefing text ──────────────────────────────────────────────────
        st.markdown(r.get("text", "No analysis available."))

        # ── Consolidated Business Incidents ───────────────────────────────────
        incidents = insights.get("incidents", [])
        if incidents:
            st.divider()
            st.markdown('<p class="section-header">Consolidated Business Incidents</p>', unsafe_allow_html=True)
            for inc in incidents:
                sev   = inc.get("severity", "medium")
                color = severity_color(sev)
                roots   = ", ".join(inc.get("root_metrics", []))
                effects = ", ".join(inc.get("affected_metrics", [])) or "—"
                chain   = " → ".join(inc.get("causal_chain", [])) or "—"
                st.markdown(f"""
                <div class="alert-card alert-card-{sev}" style="margin-bottom:10px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                        <div style="display:flex;align-items:center;gap:8px;">
                            <span class="badge badge-{sev}">{sev.upper()}</span>
                            <span style="font-size:1rem;font-weight:600;color:#0d1117;">{inc.get('title','')}</span>
                            <span style="font-size:0.8rem;color:#9ca3af;">· {' & '.join(inc.get('domain_tags',[]))}</span>
                        </div>
                        <span style="font-size:0.9rem;font-weight:600;color:{color};">Risk {inc.get('risk_score',0)}/100</span>
                    </div>
                    <div style="font-size:0.9rem;color:#5c6370;margin-bottom:4px;">
                        <strong style="color:#374151;">Root drivers:</strong> {roots} &nbsp;·&nbsp;
                        <strong style="color:#374151;">Downstream:</strong> {effects}
                    </div>
                    <div style="font-size:0.85rem;color:#6b7280;margin-bottom:5px;">
                        <strong style="color:#374151;">Causal chain:</strong> {chain}
                    </div>
                    <div style="font-size:0.85rem;color:#374151;background:#f8f9fb;padding:6px 10px;border-radius:5px;border:1px solid #e8eaed;">
                        <span class="ms" style="font-size:0.9em;vertical-align:middle;">lightbulb</span>&nbsp;
                        {inc.get('recommendation','')}
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # ── Trend Deteriorations ──────────────────────────────────────────────
        trends = insights.get("trend_alerts", [])
        if trends:
            st.divider()
            st.markdown('<p class="section-header">Trend Deteriorations</p>', unsafe_allow_html=True)
            trend_df = pd.DataFrame([{
                "Domain":       t["domain"],
                "Metric":       t["metric_label"],
                "Direction":    t["direction"].capitalize(),
                "Periods":      t["consecutive_periods"],
                "Total Change": f"{t['total_change_pct']:+.1f}%",
                "Start → Latest": f"{t['start_value']}{t['unit']} → {t['latest_value']}{t['unit']}",
                "Since":        t["start_date"],
                "Severity":     t["severity"].upper(),
            } for t in trends])
            st.dataframe(trend_df, use_container_width=True, hide_index=True)

        # ── Forecast Early Warnings ───────────────────────────────────────────
        forecasts = insights.get("forecast_alerts", [])
        if forecasts:
            st.divider()
            st.markdown('<p class="section-header">Forecast Early Warnings (3-month outlook)</p>', unsafe_allow_html=True)
            for f in forecasts:
                sev   = f.get("severity", "warning")
                color = "#b91c1c" if sev == "critical" else "#b45309"
                badge = "critical" if sev == "critical" else "high"
                st.markdown(f"""
                <div class="alert-card alert-card-{badge}" style="margin-bottom:8px;">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                        <span class="badge badge-{badge}">{sev.upper()}</span>
                        <span style="font-size:0.95rem;font-weight:600;color:#0d1117;">
                            {f['domain']} — {f['metric_label']}
                        </span>
                        <span style="font-size:0.8rem;color:#9ca3af;">by {f['projection_date']}</span>
                    </div>
                    <div style="font-size:0.9rem;color:#5c6370;">{f['message']}</div>
                </div>
                """, unsafe_allow_html=True)

        # ── Supporting Anomaly Data ───────────────────────────────────────────
        st.divider()
        st.markdown('<p class="section-header">Supporting Anomaly Data</p>', unsafe_allow_html=True)
        if anoms_all:
            supp_df = pd.DataFrame([{
                "Domain":     a["domain"],
                "Metric":     a["metric_label"],
                "Date":       a["date"],
                "Severity":   a["severity"].upper(),
                "Deviation":  f"{a['deviation_pct']:+.1f}%",
                "Risk Score": a["risk_score"],
            } for a in anoms_all[:12]])
            st.dataframe(supp_df, use_container_width=True, hide_index=True)

        # ── Export to PDF ─────────────────────────────────────────────────────
        st.divider()
        st.markdown('<p class="section-header">Export Report</p>', unsafe_allow_html=True)

        export_col, _ = st.columns([1, 3])
        with export_col:
            try:
                pdf_bytes = generate_pdf_report(
                    briefing_text=r.get("text", ""),
                    source=r.get("source", "Unknown"),
                    anomalies=anoms_all[:12],
                )
                filename = f"InsightGuardAI_Briefing_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                st.download_button(
                    label="Download PDF Report",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    use_container_width=True,
                    type="primary",
                )
            except Exception as e:
                st.error(f"PDF generation failed: {e}")

    else:
        st.info("Click **Generate AI Briefing** to run the analysis.")
