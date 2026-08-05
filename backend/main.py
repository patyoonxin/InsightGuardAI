"""
InsightGuardAI — FastAPI Backend
Endpoints:
  GET  /health
  GET  /api/kpis/{domain}          — raw KPI time-series
  GET  /api/anomalies              — all detected anomalies (enriched)
  GET  /api/risk-summary           — aggregated risk overview
  GET  /api/target-vs-actual       — target comparison
  GET  /api/insights               — full insight package (trends, forecasts, incidents)
  POST /api/analyse                — trigger AI analysis (enriched context)
  POST /api/regenerate-data        — regenerate synthetic data
"""

import os
import sys
from pathlib import Path

# Allow imports from project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import asyncio

from data.generate_data import generate_all
from backend.anomaly_engine import compute_anomalies, target_vs_actual, Anomaly
from backend.ai_analyst import analyse
from backend.insight_engine import build_insight_package

app = FastAPI(title="InsightGuardAI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = ROOT / "data"

# ── Data loading ──────────────────────────────────────────────────────────────

def _ensure_data():
    files = ["finance_kpis.csv", "operations_kpis.csv", "customer_kpis.csv"]
    if not all((DATA_DIR / f).exists() for f in files):
        generate_all(str(DATA_DIR))


def _load(domain: str) -> pd.DataFrame:
    mapping = {
        "finance":    "finance_kpis.csv",
        "operations": "operations_kpis.csv",
        "customer":   "customer_kpis.csv",
    }
    path = DATA_DIR / mapping[domain.lower()]
    if not path.exists():
        raise HTTPException(404, f"Data for domain '{domain}' not found.")
    df = pd.read_csv(path, parse_dates=["date"])
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    return df


def _get_domain_dfs() -> dict:
    return {
        "Finance":    _load("finance"),
        "Operations": _load("operations"),
        "Customer":   _load("customer"),
    }


def _get_all_anomalies() -> List[Anomaly]:
    all_anomalies = []
    for domain in ["finance", "operations", "customer"]:
        df = _load(domain)
        anoms = compute_anomalies(df, domain.capitalize())
        all_anomalies.extend(anoms)
    return sorted(all_anomalies, key=lambda x: -x.risk_score)


def _domain_summary(domain: str) -> dict:
    df = _load(domain)
    latest = df.iloc[-1].to_dict()
    latest.pop("domain", None)
    latest.pop("date", None)
    return {k: round(v, 2) if isinstance(v, float) else v for k, v in latest.items()}


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    _ensure_data()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "InsightGuardAI"}


@app.get("/api/kpis/{domain}")
def get_kpis(domain: str):
    valid = ["finance", "operations", "customer"]
    if domain.lower() not in valid:
        raise HTTPException(400, f"Domain must be one of {valid}")
    df = _load(domain)
    return df.to_dict(orient="records")


@app.get("/api/anomalies")
def get_anomalies(domain: Optional[str] = None, severity: Optional[str] = None, limit: int = 50):
    anomalies = _get_all_anomalies()
    if domain:
        anomalies = [a for a in anomalies if a.domain.lower() == domain.lower()]
    if severity:
        anomalies = [a for a in anomalies if a.severity.lower() == severity.lower()]
    return [vars(a) for a in anomalies[:limit]]


@app.get("/api/risk-summary")
def get_risk_summary():
    anomalies = _get_all_anomalies()

    def domain_risk(domain_name: str):
        domain_anoms = [a for a in anomalies if a.domain.lower() == domain_name.lower()]
        if not domain_anoms:
            return {"domain": domain_name, "total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0, "top_risk_score": 0}
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for a in domain_anoms:
            counts[a.severity] += 1
        return {
            "domain": domain_name,
            "total": len(domain_anoms),
            "top_risk_score": domain_anoms[0].risk_score,
            **counts,
        }

    overall_score = max((a.risk_score for a in anomalies), default=0)
    total_critical = sum(1 for a in anomalies if a.severity == "critical")

    return {
        "overall_risk_score": overall_score,
        "total_anomalies": len(anomalies),
        "total_critical": total_critical,
        "domains": [domain_risk("Finance"), domain_risk("Operations"), domain_risk("Customer")],
        "most_recent_critical": [vars(a) for a in anomalies if a.severity == "critical"][:3],
    }


@app.get("/api/target-vs-actual")
def get_target_vs_actual():
    results = []
    for domain in ["finance", "operations"]:
        df = _load(domain)
        results.extend(target_vs_actual(df))
    return results


@app.get("/api/insights")
def get_insights():
    """
    Full insight package: enriched anomalies, trend alerts, forecast alerts,
    consolidated incidents, and target gaps.
    """
    domain_dfs     = _get_domain_dfs()
    base_anomalies = _get_all_anomalies()
    tva            = []
    for domain in ["finance", "operations"]:
        tva.extend(target_vs_actual(_load(domain)))

    pkg = build_insight_package(domain_dfs, base_anomalies, tva)

    return {
        "anomalies": [vars(a) for a in pkg.anomalies],
        "trend_alerts": [vars(t) for t in pkg.trend_alerts],
        "forecast_alerts": [vars(f) for f in pkg.forecast_alerts],
        "incidents": [
            {
                "incident_id":      inc.incident_id,
                "title":            inc.title,
                "domain_tags":      inc.domain_tags,
                "severity":         inc.severity,
                "risk_score":       inc.risk_score,
                "root_metrics":     inc.root_metrics,
                "affected_metrics": inc.affected_metrics,
                "causal_chain":     inc.causal_chain,
                "recommendation":   inc.recommendation,
                "anomaly_count":    len(inc.anomalies),
                "trend_count":      len(inc.trend_alerts),
            }
            for inc in pkg.incidents
        ],
        "target_gaps":      pkg.target_gaps,
        "domain_summaries": pkg.domain_summaries,
    }


class AnalyseRequest(BaseModel):
    top_n: int = 8


@app.post("/api/analyse")
async def run_analysis(req: AnalyseRequest):
    domain_dfs     = _get_domain_dfs()
    base_anomalies = _get_all_anomalies()
    tva            = []
    for domain in ["finance", "operations"]:
        tva.extend(target_vs_actual(_load(domain)))

    pkg = build_insight_package(domain_dfs, base_anomalies, tva)

    # Pass enriched package to AI analyst
    result = await analyse(pkg)
    return result


@app.post("/api/regenerate-data")
def regenerate_data():
    generate_all(str(DATA_DIR))
    return {"status": "ok", "message": "Synthetic data regenerated."}
