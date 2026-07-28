"""
InsightGuardAI — FastAPI Backend
Endpoints:
  GET  /health
  GET  /api/kpis/{domain}          — raw KPI time-series
  GET  /api/anomalies              — all detected anomalies
  GET  /api/risk-summary           — aggregated risk overview
  GET  /api/target-vs-actual       — target comparison
  POST /api/analyse                — trigger AI analysis
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


class AnalyseRequest(BaseModel):
    top_n: int = 8


@app.post("/api/analyse")
async def run_analysis(req: AnalyseRequest):
    anomalies = _get_all_anomalies()[:req.top_n]
    summaries = {
        "Finance":    _domain_summary("finance"),
        "Operations": _domain_summary("operations"),
        "Customer":   _domain_summary("customer"),
    }
    result = await analyse(anomalies, summaries)
    return result


@app.post("/api/regenerate-data")
def regenerate_data():
    generate_all(str(DATA_DIR))
    return {"status": "ok", "message": "Synthetic data regenerated."}
