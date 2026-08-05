"""
InsightGuardAI — Insight Engine
Provides advanced analytics on top of the base anomaly detection layer.

Enhancements implemented:
  1. Robust Statistics        — rolling median + MAD for anomaly detection
  2. Trend Deterioration      — detect sustained directional worsening
  3. Cross-Domain Correlation — group related anomalies into business incidents
  4. Enhanced Risk Scoring    — combines z-score, KPI importance, persistence, correlation count
  5. Alert Consolidation      — merge related KPI alerts into management incidents
  6. Forecast Early Warning   — linear-regression projection with target-miss alerts
  7. Richer LLM Context       — structured payload for ai_analyst.py

No new third-party dependencies beyond what already exists (pandas, numpy, scipy is NOT used).
Linear regression uses numpy.polyfit only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple

from backend.anomaly_engine import Anomaly, METRIC_META, SKIP_COLS


# ══════════════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════════════

# KPI business importance weight (1.0 = baseline, higher = more important)
KPI_IMPORTANCE: Dict[str, float] = {
    "revenue":                   2.0,
    "ebitda_margin_pct":         1.8,
    "gross_margin_pct":          1.6,
    "cash_balance":              1.5,
    "ar_days":                   1.2,
    "oee_pct":                   1.5,
    "downtime_hours":            1.4,
    "defect_rate_pct":           1.3,
    "on_time_delivery_pct":      1.2,
    "unit_cost":                 1.1,
    "inventory_turnover":        1.0,
    "churn_rate_pct":            1.6,
    "nps":                       1.4,
    "csat":                      1.3,
    "new_customers":             1.2,
    "avg_resolution_time_hrs":   1.0,
    "customer_lifetime_value":   1.3,
}

# Cross-domain causal relationships: (cause_metric, effect_metric, description)
CAUSAL_LINKS: List[Tuple[str, str, str]] = [
    ("downtime_hours",       "oee_pct",            "Equipment downtime suppresses OEE"),
    ("defect_rate_pct",      "oee_pct",            "High defects drag down OEE"),
    ("oee_pct",              "revenue",            "OEE decline impacts production capacity → revenue"),
    ("downtime_hours",       "revenue",            "Downtime reduces output → revenue loss"),
    ("churn_rate_pct",       "revenue",            "Customer churn erodes recurring revenue"),
    ("churn_rate_pct",       "customer_lifetime_value", "Churn shortens customer lifetime"),
    ("nps",                  "churn_rate_pct",     "Low NPS leads to higher churn"),
    ("csat",                 "churn_rate_pct",     "Low CSAT drives customer churn"),
    ("avg_resolution_time_hrs", "csat",            "Slow resolution reduces CSAT"),
    ("avg_resolution_time_hrs", "nps",             "Slow resolution reduces NPS"),
    ("unit_cost",            "gross_margin_pct",   "Rising unit costs compress gross margin"),
    ("ar_days",              "cash_balance",       "Slow receivables drain cash"),
    ("gross_margin_pct",     "ebitda_margin_pct",  "Margin compression flows to EBITDA"),
]

# Minimum consecutive periods to flag a trend deterioration
TREND_MIN_PERIODS = 3

# Forecast horizon (months ahead)
FORECAST_HORIZON = 3


# ══════════════════════════════════════════════════════════════════════════════
# Data classes
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TrendAlert:
    """A KPI that has been consistently worsening for N consecutive periods."""
    domain: str
    metric: str
    metric_label: str
    unit: str
    consecutive_periods: int
    direction: str          # "declining" | "rising"
    total_change_pct: float
    start_value: float
    latest_value: float
    start_date: str
    latest_date: str
    severity: str           # "warning" | "critical"


@dataclass
class ForecastAlert:
    """A KPI projected to miss its target or hit a critical level."""
    domain: str
    metric: str
    metric_label: str
    unit: str
    current_value: float
    projected_value: float
    projection_date: str
    trend_slope_pct_per_month: float
    target_value: Optional[float]
    projected_gap_pct: Optional[float]   # vs target
    severity: str                        # "warning" | "critical"
    message: str


@dataclass
class BusinessIncident:
    """A consolidated group of anomalies/trends forming a single business issue."""
    incident_id: str
    title: str
    domain_tags: List[str]
    severity: str
    risk_score: int
    root_metrics: List[str]         # primary drivers
    affected_metrics: List[str]     # downstream KPIs
    anomalies: List[Anomaly]        # contributing anomaly objects
    trend_alerts: List[TrendAlert]
    causal_chain: List[str]         # human-readable explanation
    recommendation: str


@dataclass
class InsightPackage:
    """Full analytics payload passed downstream to ai_analyst.py."""
    anomalies: List[Anomaly]
    trend_alerts: List[TrendAlert]
    forecast_alerts: List[ForecastAlert]
    incidents: List[BusinessIncident]
    target_gaps: List[dict]
    domain_summaries: Dict[str, dict]


# ══════════════════════════════════════════════════════════════════════════════
# 1. Robust Statistics — Rolling Median + MAD Z-score
# ══════════════════════════════════════════════════════════════════════════════

def robust_zscore_series(series: np.ndarray, window: int = 12, min_periods: int = 4) -> np.ndarray:
    """
    Compute a rolling robust Z-score using Median and MAD.
    robust_z = (x - rolling_median) / (1.4826 * rolling_MAD)
    The constant 1.4826 makes MAD consistent with std for normal distributions.
    Falls back to np.nan when insufficient data.
    """
    n = len(series)
    z_scores = np.full(n, np.nan)
    s = pd.Series(series)

    for i in range(n):
        start = max(0, i - window + 1)
        window_data = s.iloc[start:i + 1].dropna()
        if len(window_data) < min_periods:
            continue
        median = window_data.median()
        mad = (window_data - median).abs().median()
        if mad < 1e-8:
            # Zero MAD → fall back to mean/std if available, else skip
            std = window_data.std()
            if std < 1e-8:
                continue
            z_scores[i] = (series[i] - window_data.mean()) / std
        else:
            z_scores[i] = (series[i] - median) / (1.4826 * mad)

    return z_scores


def compute_robust_anomalies(
    df: pd.DataFrame,
    domain: str,
    z_threshold: float = 2.5,   # MAD-based scores are tighter; 2.5 is appropriate
) -> List[Anomaly]:
    """
    Drop-in replacement for compute_anomalies() using robust (median/MAD) statistics.
    Produces Anomaly objects identical in structure to the base engine.
    """
    anomalies: List[Anomaly] = []
    numeric_cols = [
        c for c in df.columns
        if c not in SKIP_COLS and df[c].dtype in [float, int, np.float64, np.int64]
    ]

    window = min(12, len(df) - 1)

    for col in numeric_cols:
        series = df[col].values.astype(float)
        if len(series) < 6:
            continue

        z_arr = robust_zscore_series(series, window=window)
        rolling_median = pd.Series(series).rolling(window, min_periods=4).median().values

        meta = METRIC_META.get(col, (col, "", "above"))
        label, unit, concern_dir = meta

        for i in range(len(series)):
            z = z_arr[i]
            if np.isnan(z) or abs(z) < z_threshold:
                continue
            if concern_dir == "above" and z < 0:
                continue
            if concern_dir == "below" and z > 0:
                continue

            expected = rolling_median[i] if not np.isnan(rolling_median[i]) else series[i]
            actual   = series[i]
            dev_pct  = ((actual - expected) / abs(expected)) * 100 if expected != 0 else 0

            rs  = _enhanced_risk_score(abs(z), col, persistence=1)
            sev = _severity(rs)
            anomalies.append(Anomaly(
                domain=domain,
                metric=col,
                date=str(df["date"].iloc[i])[:10],
                value=round(actual, 2),
                expected=round(expected, 2),
                deviation_pct=round(dev_pct, 1),
                z_score=round(z, 2),
                risk_score=rs,
                severity=sev,
                direction="above" if z > 0 else "below",
                metric_label=label,
                unit=unit,
            ))

    return anomalies


# ══════════════════════════════════════════════════════════════════════════════
# 2. Trend Deterioration Detection
# ══════════════════════════════════════════════════════════════════════════════

def detect_trend_deterioration(
    df: pd.DataFrame,
    domain: str,
    min_periods: int = TREND_MIN_PERIODS,
) -> List[TrendAlert]:
    """
    Detect KPIs that consistently worsen for min_periods consecutive months,
    even without crossing an anomaly threshold.
    """
    alerts: List[TrendAlert] = []
    numeric_cols = [
        c for c in df.columns
        if c not in SKIP_COLS and df[c].dtype in [float, int, np.float64, np.int64]
    ]

    for col in numeric_cols:
        meta = METRIC_META.get(col, (col, "", "above"))
        label, unit, concern_dir = meta
        series = df[col].dropna().values.astype(float)
        dates  = df.loc[df[col].notna(), "date"].values

        if len(series) < min_periods + 1:
            continue

        # Compute period-over-period changes
        diffs = np.diff(series)

        # "Worsening" direction depends on concern_dir
        # concern_dir="below" → declining is bad (negative diff = bad)
        # concern_dir="above" → rising is bad (positive diff = bad)
        if concern_dir == "below":
            bad = diffs < 0   # declining is bad
        else:
            bad = diffs > 0   # rising is bad

        # Find the longest current streak at the tail of the series
        streak = 0
        for i in range(len(bad) - 1, -1, -1):
            if bad[i]:
                streak += 1
            else:
                break

        if streak < min_periods:
            continue

        # Characterise the streak
        streak_start_idx = len(series) - streak - 1
        start_val  = series[streak_start_idx]
        latest_val = series[-1]
        total_chg  = ((latest_val - start_val) / abs(start_val)) * 100 if start_val != 0 else 0
        direction  = "declining" if latest_val < start_val else "rising"
        severity   = "critical" if streak >= 5 or abs(total_chg) > 15 else "warning"

        alerts.append(TrendAlert(
            domain=domain,
            metric=col,
            metric_label=label,
            unit=unit,
            consecutive_periods=streak,
            direction=direction,
            total_change_pct=round(total_chg, 1),
            start_value=round(start_val, 2),
            latest_value=round(latest_val, 2),
            start_date=str(dates[streak_start_idx])[:10],
            latest_date=str(dates[-1])[:10],
            severity=severity,
        ))

    return alerts


# ══════════════════════════════════════════════════════════════════════════════
# 3 & 5. Cross-Domain Correlation + Alert Consolidation → BusinessIncident
# ══════════════════════════════════════════════════════════════════════════════

# Incident templates: each defines a title, list of trigger metrics, and recommended action
_INCIDENT_TEMPLATES = [
    {
        "id":          "financial_performance",
        "title":       "Financial Performance Declining",
        "triggers":    {"revenue", "gross_margin_pct", "ebitda_margin_pct", "cash_balance"},
        "domain_tags": ["Finance"],
        "recommendation": (
            "Convene an urgent Finance review. Analyse revenue pipeline, COGS drivers, and "
            "EBITDA levers. Assess cash runway and consider accelerating receivables collection."
        ),
    },
    {
        "id":          "operational_breakdown",
        "title":       "Operational Efficiency Breakdown",
        "triggers":    {"oee_pct", "downtime_hours", "defect_rate_pct", "unit_cost"},
        "domain_tags": ["Operations"],
        "recommendation": (
            "Initiate root-cause analysis on production equipment. Review maintenance schedules, "
            "supplier quality, and shift patterns. Escalate persistent downtime to Plant Manager."
        ),
    },
    {
        "id":          "customer_health",
        "title":       "Customer Health Deteriorating",
        "triggers":    {"churn_rate_pct", "nps", "csat", "avg_resolution_time_hrs", "new_customers"},
        "domain_tags": ["Customer"],
        "recommendation": (
            "Launch immediate customer satisfaction intervention. Review support SLAs, "
            "escalate top-churn segments to Account Management, and assess onboarding pipeline."
        ),
    },
    {
        "id":          "ops_to_finance",
        "title":       "Operations Disruption Impacting Revenue",
        "triggers":    {"downtime_hours", "oee_pct", "revenue", "on_time_delivery_pct"},
        "domain_tags": ["Operations", "Finance"],
        "recommendation": (
            "Quantify revenue impact of operational disruption. Assess recovery timeline, "
            "communicate customer delivery risk proactively, and review production contingency plans."
        ),
    },
    {
        "id":          "customer_to_finance",
        "title":       "Customer Attrition Threatening Revenue",
        "triggers":    {"churn_rate_pct", "revenue", "new_customers", "customer_lifetime_value"},
        "domain_tags": ["Customer", "Finance"],
        "recommendation": (
            "Analyse churn by cohort to identify at-risk segments. Model revenue impact over "
            "3–6 months. Develop a retention programme and adjust revenue forecasts accordingly."
        ),
    },
]


def _build_causal_chain(anomalies: List[Anomaly], trend_alerts: List[TrendAlert]) -> List[str]:
    """Return a list of human-readable causal statements supported by data."""
    active_metrics = {a.metric for a in anomalies} | {t.metric for t in trend_alerts}
    chain = []
    for cause, effect, description in CAUSAL_LINKS:
        if cause in active_metrics and effect in active_metrics:
            chain.append(description)
    return chain


def consolidate_incidents(
    anomalies: List[Anomaly],
    trend_alerts: List[TrendAlert],
) -> List[BusinessIncident]:
    """
    Match anomalies and trend alerts to incident templates.
    Each template fires if ≥2 of its trigger metrics are active.
    Incidents are returned sorted by risk score descending.
    """
    active_anomaly_metrics  = {a.metric for a in anomalies}
    active_trend_metrics    = {t.metric for t in trend_alerts}
    active_metrics          = active_anomaly_metrics | active_trend_metrics

    incidents: List[BusinessIncident] = []

    for tpl in _INCIDENT_TEMPLATES:
        matched = active_metrics & tpl["triggers"]
        if len(matched) < 2:
            continue

        contributing_anomalies = [a for a in anomalies if a.metric in matched]
        contributing_trends    = [t for t in trend_alerts if t.metric in matched]

        # Determine root (highest-risk) vs affected metrics
        # Root: metrics that appear as "cause" in CAUSAL_LINKS for this incident's matched set
        cause_metrics  = {c for c, _, _ in CAUSAL_LINKS if c in matched}
        effect_metrics = {e for _, e, _ in CAUSAL_LINKS if e in matched}
        root_metrics   = list(cause_metrics - effect_metrics) or list(matched)
        affected       = list((matched - set(root_metrics)))

        # Severity = worst contributing anomaly or trend
        sev_order = {"critical": 3, "high": 2, "medium": 1, "warning": 1, "low": 0}
        all_sevs  = (
            [a.severity for a in contributing_anomalies]
            + [t.severity for t in contributing_trends]
        )
        top_sev = max(all_sevs, key=lambda s: sev_order.get(s, 0), default="medium")

        # Risk score = weighted average of contributing anomaly scores + trend bonus
        anom_scores   = [a.risk_score for a in contributing_anomalies]
        trend_bonus   = len(contributing_trends) * 5
        base_score    = int(np.mean(anom_scores)) if anom_scores else 40
        correlation_bonus = min(len(matched) * 3, 15)
        risk_score    = min(100, base_score + trend_bonus + correlation_bonus)

        causal_chain  = _build_causal_chain(contributing_anomalies, contributing_trends)

        # Human-readable metric labels
        root_labels    = [METRIC_META.get(m, (m, "", ""))[0] for m in root_metrics]
        affected_labels = [METRIC_META.get(m, (m, "", ""))[0] for m in affected]

        incidents.append(BusinessIncident(
            incident_id=tpl["id"],
            title=tpl["title"],
            domain_tags=tpl["domain_tags"],
            severity=top_sev,
            risk_score=risk_score,
            root_metrics=root_labels,
            affected_metrics=affected_labels,
            anomalies=contributing_anomalies,
            trend_alerts=contributing_trends,
            causal_chain=causal_chain,
            recommendation=tpl["recommendation"],
        ))

    # Deduplicate: if an anomaly appears in multiple incidents, keep highest-risk owner
    seen_anomaly_dates: set = set()
    unique_incidents: List[BusinessIncident] = []
    for inc in sorted(incidents, key=lambda x: -x.risk_score):
        keys = {(a.metric, a.date) for a in inc.anomalies}
        if not keys.issubset(seen_anomaly_dates):
            unique_incidents.append(inc)
            seen_anomaly_dates.update(keys)

    return unique_incidents


# ══════════════════════════════════════════════════════════════════════════════
# 4. Enhanced Risk Scoring
# ══════════════════════════════════════════════════════════════════════════════

def _enhanced_risk_score(
    abs_z: float,
    metric: str,
    persistence: int = 1,
    correlated_count: int = 0,
) -> int:
    """
    Risk score combining:
      - Statistical severity (z-score)
      - Business importance weight
      - Persistence (how many consecutive periods abnormal)
      - Number of correlated anomalies in other domains
    Result: 1–100 integer.
    """
    # Base z-score score (same scale as original engine)
    if abs_z >= 4.0:
        base = min(100, int(85 + (abs_z - 4.0) * 5))
    elif abs_z >= 3.0:
        base = int(65 + (abs_z - 3.0) * 20)
    elif abs_z >= 2.5:
        base = int(45 + (abs_z - 2.5) * 40)
    else:
        base = int(25 + (abs_z - 2.0) * 40)

    importance   = KPI_IMPORTANCE.get(metric, 1.0)
    persistence_bonus    = min(persistence - 1, 4) * 3   # up to +12
    correlation_bonus    = min(correlated_count, 4) * 2  # up to +8

    raw = base * importance + persistence_bonus + correlation_bonus
    return min(100, max(1, int(raw)))


def _severity(risk_score: int) -> str:
    if risk_score >= 75:
        return "critical"
    elif risk_score >= 55:
        return "high"
    elif risk_score >= 35:
        return "medium"
    return "low"


def enrich_anomaly_risk_scores(
    anomalies: List[Anomaly],
    trend_alerts: List[TrendAlert],
) -> List[Anomaly]:
    """
    Re-score anomalies using the enhanced formula, factoring in:
    - KPI importance
    - Persistence (does the same metric appear in trend_alerts?)
    - Cross-domain correlation count (how many other domains share anomalies in the same period?)
    Returns the same list with updated risk_score and severity.
    """
    trend_metric_set = {t.metric for t in trend_alerts}

    # Build a simple cross-domain co-occurrence map: metric → count of domains with anomalies
    domain_count: Dict[str, int] = {}
    for a in anomalies:
        domain_count[a.metric] = domain_count.get(a.metric, 0) + 1

    enriched = []
    for a in anomalies:
        persistence     = trend_alerts[0].consecutive_periods if a.metric in trend_metric_set else 1
        correlated      = sum(
            1 for cause, effect, _ in CAUSAL_LINKS
            if (cause == a.metric or effect == a.metric)
            and any(b.metric in {cause, effect} and b.domain != a.domain for b in anomalies)
        )
        new_score = _enhanced_risk_score(abs(a.z_score), a.metric, persistence, correlated)
        new_sev   = _severity(new_score)
        # Re-create with updated fields (dataclass is mutable)
        a.risk_score = new_score
        a.severity   = new_sev
        enriched.append(a)

    return sorted(enriched, key=lambda x: -x.risk_score)


# ══════════════════════════════════════════════════════════════════════════════
# 6. Forecast-Based Early Warning (Linear Regression)
# ══════════════════════════════════════════════════════════════════════════════

def compute_forecasts(
    df: pd.DataFrame,
    domain: str,
    horizon: int = FORECAST_HORIZON,
    target_cols: Optional[Dict[str, str]] = None,
) -> List[ForecastAlert]:
    """
    Fit a linear trend to the last 12 months of each KPI and project forward.
    Generates alerts when:
      - Projected value would miss a target by >5%
      - Trend direction is worsening (based on concern_dir) and slope is significant
    target_cols: {actual_col: target_col} mapping for metrics with targets.
    """
    alerts: List[ForecastAlert] = []
    target_cols = target_cols or {}

    numeric_cols = [
        c for c in df.columns
        if c not in SKIP_COLS and df[c].dtype in [float, int, np.float64, np.int64]
    ]

    for col in numeric_cols:
        meta = METRIC_META.get(col, (col, "", "above"))
        label, unit, concern_dir = meta

        series = df[col].dropna().values.astype(float)
        if len(series) < 6:
            continue

        # Use last min(12, n) data points for regression
        n_fit  = min(12, len(series))
        y      = series[-n_fit:]
        x      = np.arange(n_fit)

        # numpy polyfit: degree 1
        try:
            coeffs = np.polyfit(x, y, 1)
        except (np.linalg.LinAlgError, ValueError):
            continue

        slope = coeffs[0]   # units/month
        intercept = coeffs[1]

        # Project forward
        projected_x   = n_fit - 1 + horizon
        projected_val = slope * projected_x + intercept
        current_val   = series[-1]

        # Slope significance: must be >0.5% of current value per month
        slope_pct_per_month = (slope / abs(current_val)) * 100 if current_val != 0 else 0
        if abs(slope_pct_per_month) < 0.5:
            continue  # flat trend, not interesting

        # Is trend worsening?
        worsening = (concern_dir == "below" and slope < 0) or (concern_dir == "above" and slope > 0)
        if not worsening:
            continue

        # Compute gap vs target if available
        target_col   = target_cols.get(col)
        target_value: Optional[float] = None
        gap_pct: Optional[float]      = None
        severity = "warning"

        if target_col and target_col in df.columns:
            target_value = float(df[target_col].iloc[-1])
            if target_value != 0:
                gap_pct = ((projected_val - target_value) / abs(target_value)) * 100
                if concern_dir == "below" and gap_pct < -15:
                    severity = "critical"
                elif concern_dir == "above" and gap_pct > 15:
                    severity = "critical"

        # Projected deterioration threshold: >8% worsening in horizon months
        total_projected_chg = ((projected_val - current_val) / abs(current_val)) * 100 if current_val != 0 else 0
        if abs(total_projected_chg) < 5:
            continue  # not significant enough

        # Build message
        direction_word = "fall" if projected_val < current_val else "rise"
        if target_value and gap_pct is not None:
            msg = (
                f"{label} is projected to {direction_word} to "
                f"{round(projected_val, 2)}{unit} in {horizon} months "
                f"({total_projected_chg:+.1f}%), missing target "
                f"({target_value}{unit}) by {abs(gap_pct):.1f}%."
            )
        else:
            msg = (
                f"{label} is projected to {direction_word} to "
                f"{round(projected_val, 2)}{unit} in {horizon} months "
                f"({total_projected_chg:+.1f}% from current {round(current_val, 2)}{unit})."
            )

        # Estimate projection date
        last_date = pd.to_datetime(str(df["date"].iloc[-1])[:10])
        proj_date = last_date + pd.DateOffset(months=horizon)

        alerts.append(ForecastAlert(
            domain=domain,
            metric=col,
            metric_label=label,
            unit=unit,
            current_value=round(current_val, 2),
            projected_value=round(projected_val, 2),
            projection_date=proj_date.strftime("%Y-%m-%d"),
            trend_slope_pct_per_month=round(slope_pct_per_month, 2),
            target_value=round(target_value, 2) if target_value is not None else None,
            projected_gap_pct=round(gap_pct, 1) if gap_pct is not None else None,
            severity=severity,
            message=msg,
        ))

    # Sort: critical first, then by abs slope magnitude
    return sorted(alerts, key=lambda a: (0 if a.severity == "critical" else 1, -abs(a.trend_slope_pct_per_month)))


# ══════════════════════════════════════════════════════════════════════════════
# Orchestrator: build full InsightPackage
# ══════════════════════════════════════════════════════════════════════════════

def build_insight_package(
    domain_dfs: Dict[str, pd.DataFrame],
    base_anomalies: List[Anomaly],
    target_vs_actual: List[dict],
) -> InsightPackage:
    """
    Given per-domain DataFrames and the base anomaly list from anomaly_engine,
    produce a complete InsightPackage with all enrichments.

    domain_dfs: {"Finance": df, "Operations": df, "Customer": df}
    """
    # ── Trend deterioration per domain ────────────────────────────────────────
    all_trends: List[TrendAlert] = []
    for domain, df in domain_dfs.items():
        all_trends.extend(detect_trend_deterioration(df, domain))

    # ── Enrich anomaly risk scores ────────────────────────────────────────────
    enriched_anomalies = enrich_anomaly_risk_scores(list(base_anomalies), all_trends)

    # ── Forecast per domain ───────────────────────────────────────────────────
    all_forecasts: List[ForecastAlert] = []
    domain_target_map = {
        "Finance":    {"revenue": "revenue_target"},
        "Operations": {"oee_pct": "oee_target_pct"},
        "Customer":   {},
    }
    for domain, df in domain_dfs.items():
        target_cols = domain_target_map.get(domain, {})
        all_forecasts.extend(compute_forecasts(df, domain, target_cols=target_cols))

    # ── Incident consolidation ────────────────────────────────────────────────
    incidents = consolidate_incidents(enriched_anomalies, all_trends)

    # ── Domain summaries ──────────────────────────────────────────────────────
    domain_summaries: Dict[str, dict] = {}
    for domain, df in domain_dfs.items():
        latest = df.iloc[-1].to_dict()
        latest.pop("domain", None)
        latest.pop("date", None)
        domain_summaries[domain] = {
            k: round(v, 2) if isinstance(v, float) else v
            for k, v in latest.items()
        }

    return InsightPackage(
        anomalies=enriched_anomalies,
        trend_alerts=all_trends,
        forecast_alerts=all_forecasts,
        incidents=incidents,
        target_gaps=target_vs_actual,
        domain_summaries=domain_summaries,
    )
