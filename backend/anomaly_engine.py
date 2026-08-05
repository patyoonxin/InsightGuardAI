"""
Anomaly Detection Engine
Uses rolling Z-score to detect KPI anomalies and assign risk scores.
The insight_engine module builds advanced enrichments on top of this output.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Anomaly:
    domain: str
    metric: str
    date: str
    value: float
    expected: float
    deviation_pct: float
    z_score: float
    risk_score: int        # 1-100
    severity: str          # "critical", "high", "medium", "low"
    direction: str         # "above" or "below"
    metric_label: str
    unit: str


# Human-readable labels and units for each metric
METRIC_META = {
    # Finance
    "revenue":              ("Revenue",                 "USD",  "below"),
    "gross_margin_pct":     ("Gross Margin",            "%",    "below"),
    "ebitda_margin_pct":    ("EBITDA Margin",           "%",    "below"),
    "ar_days":              ("Accounts Receivable Days","days", "above"),
    "cash_balance":         ("Cash Balance",            "USD",  "below"),
    # Operations
    "oee_pct":              ("OEE",                     "%",    "below"),
    "defect_rate_pct":      ("Defect Rate",             "%",    "above"),
    "on_time_delivery_pct": ("On-Time Delivery",        "%",    "below"),
    "inventory_turnover":   ("Inventory Turnover",      "x",    "below"),
    "downtime_hours":       ("Downtime Hours",          "hrs",  "above"),
    "unit_cost":            ("Unit Cost",               "USD",  "above"),
    # Customer
    "nps":                  ("Net Promoter Score",      "pts",  "below"),
    "csat":                 ("CSAT Score",              "/5",   "below"),
    "churn_rate_pct":       ("Churn Rate",              "%",    "above"),
    "new_customers":        ("New Customers",           "cust", "below"),
    "avg_resolution_time_hrs": ("Avg Resolution Time", "hrs",  "above"),
    "customer_lifetime_value": ("Customer LTV",        "USD",  "below"),
}

# Columns to skip in anomaly detection
SKIP_COLS = {"date", "domain", "revenue_target", "oee_target_pct"}


def compute_anomalies(df: pd.DataFrame, domain: str, z_threshold: float = 2.0) -> List[Anomaly]:
    """Detect anomalies in a domain's KPI dataframe using rolling z-score."""
    anomalies = []
    numeric_cols = [c for c in df.columns if c not in SKIP_COLS and df[c].dtype in [float, int, np.float64, np.int64]]

    for col in numeric_cols:
        series = df[col].values.astype(float)
        if len(series) < 6:
            continue

        # Rolling statistics (window = 12 months)
        window = min(12, len(series) - 1)
        rolling_mean = pd.Series(series).rolling(window, min_periods=4).mean().values
        rolling_std  = pd.Series(series).rolling(window, min_periods=4).std().values

        for i in range(len(series)):
            mean = rolling_mean[i]
            std  = rolling_std[i]
            if pd.isna(mean) or pd.isna(std) or std < 1e-6:
                continue

            z = (series[i] - mean) / std
            if abs(z) < z_threshold:
                continue

            meta     = METRIC_META.get(col, (col, "", "above"))
            label, unit, concern_dir = meta
            actual   = series[i]
            expected = mean
            dev_pct  = ((actual - expected) / abs(expected)) * 100 if expected != 0 else 0

            # Only flag in the direction of concern
            if concern_dir == "above" and z < 0:
                continue
            if concern_dir == "below" and z > 0:
                continue

            risk_score = _risk_score(abs(z))
            severity   = _severity(risk_score)
            direction  = "above" if z > 0 else "below"

            anomalies.append(Anomaly(
                domain=domain,
                metric=col,
                date=str(df["date"].iloc[i])[:10],
                value=round(actual, 2),
                expected=round(expected, 2),
                deviation_pct=round(dev_pct, 1),
                z_score=round(z, 2),
                risk_score=risk_score,
                severity=severity,
                direction=direction,
                metric_label=label,
                unit=unit,
            ))

    return anomalies


def _risk_score(abs_z: float) -> int:
    """Map z-score magnitude to 1–100 risk score."""
    if abs_z >= 4.0:
        return min(100, int(85 + (abs_z - 4.0) * 5))
    elif abs_z >= 3.0:
        return int(65 + (abs_z - 3.0) * 20)
    elif abs_z >= 2.5:
        return int(45 + (abs_z - 2.5) * 40)
    else:
        return int(25 + (abs_z - 2.0) * 40)


def _severity(risk_score: int) -> str:
    if risk_score >= 75:
        return "critical"
    elif risk_score >= 55:
        return "high"
    elif risk_score >= 35:
        return "medium"
    else:
        return "low"


def target_vs_actual(df: pd.DataFrame) -> List[dict]:
    """Compare actual vs target for metrics that have targets defined."""
    results = []
    pairs = [
        ("revenue", "revenue_target", "Revenue vs Target", "USD"),
        ("oee_pct", "oee_target_pct", "OEE vs Target", "%"),
    ]
    for actual_col, target_col, label, unit in pairs:
        if actual_col not in df.columns or target_col not in df.columns:
            continue
        latest = df.iloc[-1]
        actual = latest[actual_col]
        target = latest[target_col]
        gap_pct = ((actual - target) / abs(target)) * 100 if target != 0 else 0
        results.append({
            "label": label,
            "actual": round(actual, 2),
            "target": round(target, 2),
            "gap_pct": round(gap_pct, 1),
            "unit": unit,
            "status": "on_track" if gap_pct >= -5 else ("warning" if gap_pct >= -15 else "critical"),
        })
    return results
