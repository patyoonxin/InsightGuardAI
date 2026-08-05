# InsightGuardAI

An executive early-warning dashboard that monitors KPIs across Finance, Operations, and Customer domains. It detects anomalies using statistical analysis, identifies sustained trends and cross-domain business incidents, forecasts near-term risks, and generates AI-powered briefings via the Gemini API.

---

## Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Reference](#api-reference)
- [AI Briefing Engine](#ai-briefing-engine)
- [Anomaly Detection](#anomaly-detection)
- [Advanced Analytics](#advanced-analytics)
- [Data Layer](#data-layer)

---

## Features

### Anomaly Detection Engine
Statistical outlier detection built on a **rolling Z-score** method. Each KPI is evaluated against its own 12-month rolling baseline, so the engine adapts to seasonal shifts and long-term trends automatically. Only anomalies in the direction that matters for each metric are surfaced (e.g. Revenue is only flagged when it drops; Defect Rate only when it rises), reducing noise significantly.

### Robust Statistics (Median / MAD)
An enhanced detection mode using **rolling Median and MAD** (Median Absolute Deviation) instead of mean/standard deviation. MAD is resistant to the influence of previous outliers distorting the baseline, making it more reliable when a KPI has already been anomalous for several periods.

### KPI Trend Deterioration Detection
Beyond single-point outliers, the system tracks whether a KPI is **continuously worsening over multiple consecutive months** — even when no individual reading crosses the anomaly threshold. For example: Revenue declining for 4 straight months, or Churn rising for 3. These sustained deteriorations are classified as `warning` or `critical` and surfaced separately so slow-burn risks are not missed.

### Cross-Domain Correlation
A built-in **causal relationship map** links KPIs across Finance, Operations and Customer domains (e.g. `Downtime ↑ → OEE ↓ → Revenue ↓`, `Churn ↑ → Revenue ↓`). When anomalies or trend alerts fire simultaneously across linked metrics, the engine identifies and explains the causal chain rather than treating each KPI in isolation.

### Consolidated Business Incidents
Instead of generating dozens of individual KPI alerts, the system **groups related anomalies and trends into named management incidents** — for example, *"Financial Performance Declining"* (Revenue + Gross Margin + EBITDA) or *"Customer Attrition Threatening Revenue"* (Churn + NPS + Revenue). Each incident includes: severity, risk score, root driver metrics, downstream affected metrics, causal chain, and a concrete leadership recommendation.

### Enhanced Risk Scoring
Risk scores (1–100) combine four factors:
- **Statistical severity** — magnitude of the Z-score deviation
- **Business importance** — KPI-specific weight (e.g. Revenue and EBITDA score higher than Inventory Turnover)
- **Persistence** — whether the same metric is also flagged by trend deterioration
- **Cross-domain correlation** — whether related KPIs in other domains are simultaneously anomalous

### Forecast-Based Early Warning
**Linear regression** is fitted to the last 12 months of each KPI and projected 3 months forward. The system alerts when a KPI is on track to miss its target or deteriorate significantly — before it crosses the anomaly threshold. Example output: *"Revenue is projected to fall to $4.2M in 3 months (−12.3%), missing target by 8.1%."*

### AI Executive Briefing
On demand, the system generates a structured **5-section executive briefing** powered by the Gemini API. The prompt passes rich context to the model: deviation magnitudes, trend durations, forecast results, target gaps, cross-domain incident summaries, and causal chains — so the output is substantively more insightful than a plain anomaly list. A deterministic **rule-based fallback** ensures a briefing is always produced even without an API key.

### Interactive KPI Dashboard
A Streamlit dashboard with interactive Plotly charts, anomaly overlay, severity badges, risk summary cards, target-vs-actual gauges, and a one-click briefing generator. The AI Briefing page displays consolidated incident cards, trend deterioration tables, forecast warning cards, and supports **PDF export**.

---

## Project Structure

```
InsightGuardAI/
├── backend/
│   ├── main.py              # FastAPI app — REST API routes
│   ├── anomaly_engine.py    # Rolling Z-score anomaly detection (base layer)
│   ├── insight_engine.py    # Advanced analytics: robust stats, trend detection,
│   │                        #   cross-domain correlation, incident consolidation,
│   │                        #   enhanced risk scoring, linear forecast
│   └── ai_analyst.py        # AI briefing: Gemini API → rule-based fallback
├── data/
│   ├── generate_data.py     # Synthetic KPI data generator
│   ├── finance_kpis.csv     # Auto-generated Finance KPI data (24 months)
│   ├── operations_kpis.csv  # Auto-generated Operations KPI data (24 months)
│   └── customer_kpis.csv    # Auto-generated Customer KPI data (24 months)
├── frontend/
│   └── app.py               # Streamlit dashboard UI
├── .env                     # Environment variables (create this — see Configuration)
├── .env.example             # Environment variable template
├── requirements.txt         # Python dependencies
├── start.ps1                # PowerShell script to start both services
└── README.md
```

---

## Architecture Overview

```
┌──────────────────────────────────────────────────┐
│               Streamlit Frontend                 │
│               http://localhost:8501              │
│                                                  │
│  • KPI Time-Series Charts (Plotly)               │
│  • Anomaly Table with Severity Badges            │
│  • Risk Summary Dashboard                        │
│  • Target vs Actual Gauges                       │
│  • Consolidated Incident Cards                   │
│  • Trend Deterioration Table                     │
│  • Forecast Early Warning Cards                  │
│  • AI Executive Briefing + PDF Export            │
└────────────────────┬─────────────────────────────┘
                     │  HTTP REST API
                     ▼
┌──────────────────────────────────────────────────┐
│               FastAPI Backend                    │
│               http://localhost:8000              │
│                                                  │
│  GET  /api/kpis/{domain}                         │
│  GET  /api/anomalies                             │
│  GET  /api/risk-summary                          │
│  GET  /api/target-vs-actual                      │
│  GET  /api/insights                              │
│  POST /api/analyse           ────────────────────┼──► AI Agent
│  POST /api/regenerate-data                       │
└──────────────┬──────────────────────────────────-┘
               │
               ├── anomaly_engine.py  (rolling Z-score detection)
               │         │
               └── insight_engine.py (enrichment layer)
                         │  robust stats, trend detection,
                         │  cross-domain correlation,
                         │  incident consolidation,
                         │  linear forecast
                         │
                         └──► ai_analyst.py
                                  │
                                  ├── 1. Gemini API  (GEMINI_API_KEY)
                                  └── 2. Rule-based  (always available)
                     │  Reads CSV files
                     ▼
┌──────────────────────────────────────────────────┐
│                  Data Layer                      │
│                                                  │
│  finance_kpis.csv                                │
│  operations_kpis.csv                             │
│  customer_kpis.csv                               │
└──────────────────────────────────────────────────┘
```

---

## Prerequisites

- **Python 3.10+**
- **pip**
- (Optional) **Gemini API key** — required for AI-generated briefings; the system falls back to rule-based analysis without one

---

## Installation

```powershell
# 1. Clone or navigate to the project directory
cd InsightGuardAI

# 2. (Recommended) Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt
```

**Dependencies:**

| Package | Purpose |
|---------|---------|
| `fastapi` | Backend REST API framework |
| `uvicorn` | ASGI server for FastAPI |
| `streamlit` | Frontend dashboard UI |
| `pandas` | Data manipulation and rolling statistics |
| `numpy` | Numerical computations, linear regression |
| `plotly` | Interactive KPI charts |
| `httpx` | Async HTTP client for Gemini API calls |
| `pydantic` | Data validation |
| `python-dotenv` | Load `.env` configuration |
| `reportlab` | PDF report generation |

---

## Configuration

Create a `.env` file in the project root (same level as `requirements.txt`):

```env
# Gemini API — required for AI-generated briefings
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash    # optional, this is the default
```

If `GEMINI_API_KEY` is not set, the system automatically falls back to the built-in rule-based analysis engine — no configuration is required to run the dashboard.

---

## Running the Application

**Option A — one command (recommended):**

```powershell
.\start.ps1
```

This opens two terminal windows: one for the FastAPI backend and one for the Streamlit frontend.

**Option B — manually:**

```powershell
# Terminal 1 — FastAPI backend
python -m uvicorn backend.main:app --reload --port 8000

# Terminal 2 — Streamlit frontend
python -m streamlit run frontend/app.py --server.port 8501
```

### Access the app

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:8501 |
| FastAPI backend | http://localhost:8000 |
| Interactive API docs | http://localhost:8000/docs |

---

## API Reference

All endpoints are served from `http://localhost:8000`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/kpis/{domain}` | Raw KPI time-series (`finance`, `operations`, `customer`) |
| `GET` | `/api/anomalies` | Enriched anomalies (query params: `domain`, `severity`, `limit`) |
| `GET` | `/api/risk-summary` | Aggregated risk overview across all domains |
| `GET` | `/api/target-vs-actual` | Target vs actual for Revenue and OEE |
| `GET` | `/api/insights` | Full insight package: enriched anomalies, trend alerts, forecast alerts, consolidated incidents, domain summaries |
| `POST` | `/api/analyse` | Generate AI executive briefing (body: `{"top_n": 8}`) |
| `POST` | `/api/regenerate-data` | Regenerate synthetic KPI data |

---

## AI Briefing Engine

Implemented in `backend/ai_analyst.py`, triggered by clicking **"Generate AI Briefing"** in the dashboard.

### How it works

1. **Full insight package** — The backend builds an `InsightPackage` via `insight_engine.py` containing enriched anomalies, trend deteriorations, forecast alerts, consolidated incidents, target gaps, and domain snapshots.

2. **Rich prompt construction** — All of the above is passed to the model in structured sections, so the LLM receives deviation magnitudes, trend durations, causal chains, forecast projections, and target gaps — not just a list of raw numbers.

3. **Two-tier call chain:**

   | Priority | Source | Requirement |
   |----------|--------|-------------|
   | 1 | **Gemini API** | `GEMINI_API_KEY` set in `.env` |
   | 2 | **Rule-based** | No configuration needed — always available |

4. **Output format** — Five-section structured briefing:
   - Overall Risk Assessment
   - Critical Alerts (top 3, with root cause and trend context)
   - Cross-Domain Patterns & Causal Chains
   - Forward-Looking Warnings (forecast-based)
   - Recommended Actions (prioritised, with timeframes)

5. **Response** — Returns `{"text": "...", "source": "Gemini / Rule-based", "incident_count": N, "trend_count": N, "forecast_count": N}`. The source is shown in the frontend.

---

## Anomaly Detection

Implemented in `backend/anomaly_engine.py` (base layer) and enhanced by `backend/insight_engine.py`.

### Rolling Z-Score (base)

- A 12-month rolling window computes the mean and standard deviation for each KPI.
- A point is flagged if its Z-score exceeds `±2.0`.
- Direction filtering: only the concern direction is flagged per metric.

### Robust Z-Score (enhanced)

- Uses rolling **Median + MAD** (×1.4826 consistency constant).
- Threshold raised to `±2.5` (MAD is naturally tighter than std).
- Resistant to outlier contamination of the rolling baseline.

### Enhanced Risk Scoring

| Component | Contribution |
|-----------|-------------|
| Z-score magnitude | Base score (25–100) |
| KPI business importance | Multiplier (1.0×–2.0×) |
| Persistence (trend overlap) | +3 per extra month (up to +12) |
| Cross-domain correlation | +2 per correlated KPI (up to +8) |

**Severity thresholds:**

| Risk Score | Severity |
|------------|----------|
| 75 – 100 | Critical |
| 55 – 74 | High |
| 35 – 54 | Medium |
| 1 – 34 | Low |

### Monitored KPIs

| Domain | Metrics |
|--------|---------|
| **Finance** | Revenue, Gross Margin %, EBITDA Margin %, Accounts Receivable Days, Cash Balance |
| **Operations** | OEE %, Defect Rate %, On-Time Delivery %, Inventory Turnover, Downtime Hours, Unit Cost |
| **Customer** | NPS, CSAT, Churn Rate %, New Customers, Avg Resolution Time (hrs), Customer LTV |

---

## Advanced Analytics

Implemented in `backend/insight_engine.py`. All features are computed on every `/api/insights` or `/api/analyse` call.

### Trend Deterioration Detection

Scans the tail of each KPI time series for **consecutive periods of worsening**:
- Concern direction is per-metric (declining Revenue is bad; rising Churn is bad).
- Minimum streak to alert: **3 consecutive months**.
- Severity: `warning` (3–4 months or <15% total change), `critical` (5+ months or >15% change).

### Cross-Domain Correlation & Causal Links

13 predefined causal relationships are evaluated at runtime. Active pairs are surfaced in both the incident cards and the AI prompt. Examples:

```
Downtime ↑  →  OEE ↓  →  Revenue ↓
NPS ↓       →  Churn ↑  →  Revenue ↓
Unit Cost ↑ →  Gross Margin ↓  →  EBITDA ↓
AR Days ↑   →  Cash Balance ↓
```

### Business Incident Consolidation

Five incident templates group related KPIs:

| Incident | Trigger Metrics |
|----------|----------------|
| Financial Performance Declining | Revenue, Gross Margin %, EBITDA %, Cash Balance |
| Operational Efficiency Breakdown | OEE %, Downtime, Defect Rate, Unit Cost |
| Customer Health Deteriorating | Churn, NPS, CSAT, Avg Resolution Time, New Customers |
| Operations Disruption Impacting Revenue | Downtime, OEE %, Revenue, On-Time Delivery % |
| Customer Attrition Threatening Revenue | Churn, Revenue, New Customers, Customer LTV |

An incident fires when **≥2 trigger metrics** are simultaneously anomalous or deteriorating. Risk score = weighted average of contributing anomaly scores + trend bonus + correlation bonus.

### Forecast Early Warning

- **Method:** `numpy.polyfit` degree-1 linear regression on the last 12 months.
- **Horizon:** 3 months forward.
- **Alert conditions:** worsening slope >0.5%/month AND projected total change >5%.
- **Target gap:** if a target column exists, the projected gap is calculated and severity set to `critical` when gap >15%.

---

## Data Layer

`data/generate_data.py` generates **24 months of synthetic KPI data** (starting August 2024) with realistic trends, seasonality, noise, and intentionally injected anomalies for demo purposes.

Data is auto-generated on first backend startup if CSV files are absent. To regenerate manually:

```powershell
python data/generate_data.py
```

Or via the API:

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/api/regenerate-data
```
