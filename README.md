# InsightGuardAI

An executive early-warning dashboard that monitors KPIs across Finance, Operations, and Customer domains, detects anomalies using statistical analysis, and generates AI-powered briefings via WorkBuddy MCP or OpenAI.

---

## Table of Contents

- [Project Structure](#project-structure)
- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Reference](#api-reference)
- [AI Agent](#ai-agent)
- [Anomaly Detection](#anomaly-detection)
- [Data Layer](#data-layer)

---

## Project Structure

```
InsightGuardAi/
├── backend/
│   ├── main.py              # FastAPI app — REST API routes
│   ├── anomaly_engine.py    # Statistical anomaly detection (rolling Z-score)
│   └── ai_analyst.py        # AI Agent — generates executive briefings
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
┌─────────────────────────────────────────┐
│         Streamlit Frontend              │
│         http://localhost:8501           │
│                                         │
│  • KPI Time-Series Charts               │
│  • Anomaly Table with Severity Badges   │
│  • Risk Summary Dashboard               │
│  • AI Executive Briefing Page           │
└───────────────┬─────────────────────────┘
                │  HTTP REST API
                ▼
┌─────────────────────────────────────────┐
│         FastAPI Backend                 │
│         http://localhost:8000           │
│                                         │
│  GET  /api/kpis/{domain}               │
│  GET  /api/anomalies                   │
│  GET  /api/risk-summary                │
│  GET  /api/target-vs-actual            │
│  POST /api/analyse        ─────────────┼──► AI Agent
│  POST /api/regenerate-data             │
└───────────────┬─────────────────────────┘
                │  Reads CSV files
                ▼
┌─────────────────────────────────────────┐
│              Data Layer                 │
│                                         │
│  finance_kpis.csv                       │
│  operations_kpis.csv                    │
│  customer_kpis.csv                      │
└─────────────────────────────────────────┘

AI Agent call chain (priority order):
  1. WorkBuddy MCP  (http://127.0.0.1:<PORT>/mcp)
  2. OpenAI API     (requires OPENAI_API_KEY in .env)
  3. Rule-based     (always available, no config needed)
```

---

## Prerequisites

- **Python 3.10+**
- **pip**
- (Optional) **WorkBuddy / CodeBuddy** running with MCP enabled — for AI briefings via MCP
- (Optional) **OpenAI API key** — fallback for AI briefings

---

## Installation

```powershell
# 1. Clone or navigate to the project directory
cd \InsightGuardAi

# 2. (Recommended) Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt
```

**Dependencies installed:**

| Package | Purpose |
|---------|---------|
| `fastapi` | Backend REST API framework |
| `uvicorn` | ASGI server for FastAPI |
| `streamlit` | Frontend dashboard UI |
| `pandas` | Data manipulation |
| `numpy` | Numerical computations |
| `plotly` | Interactive charts |
| `httpx` | Async HTTP client (for MCP/OpenAI calls) |
| `pydantic` | Data validation |
| `python-dotenv` | Load `.env` configuration |

---

## Configuration

Create a `.env` file in the project root (same level as `requirements.txt`):

```env
# WorkBuddy MCP endpoint (find port in CodeBuddy MCP settings)
WORKBUDDY_MCP_URL=http://127.0.0.1:52652/mcp

# OpenAI API (optional — used as fallback if MCP is unavailable)
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
```

> **Note on MCP port**: The port (e.g. `52652`) is dynamically assigned each time CodeBuddy starts. After restarting CodeBuddy, check the current port in **CodeBuddy → Settings → MCP Servers** and update `WORKBUDDY_MCP_URL` accordingly.

### Using DeepSeek instead of OpenAI (free tier available)

DeepSeek is fully compatible with the OpenAI API format. To use it:

```env
OPENAI_API_KEY=sk-your-deepseek-key
OPENAI_MODEL=deepseek-chat
OPENAI_BASE_URL=https://api.deepseek.com/v1
```

---

## Running the Application

### Option A — One command (recommended)

From the project root in PowerShell:

```powershell
.\start.ps1
```

This opens two new PowerShell windows: one for the backend, one for the frontend.

### Option B — Manual (two terminals)

**Terminal 1 — FastAPI backend:**

```powershell
cd InsightGuardAi
python -m uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 — Streamlit frontend:**

```powershell
cd InsightGuardAi
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
| `GET` | `/api/kpis/{domain}` | Raw KPI time-series for a domain (`finance`, `operations`, `customer`) |
| `GET` | `/api/anomalies` | All detected anomalies (optional query params: `domain`, `severity`, `limit`) |
| `GET` | `/api/risk-summary` | Aggregated risk overview across all domains |
| `GET` | `/api/target-vs-actual` | Target vs actual comparison for Revenue and OEE |
| `POST` | `/api/analyse` | Trigger AI executive briefing (body: `{"top_n": 8}`) |
| `POST` | `/api/regenerate-data` | Regenerate synthetic KPI data |

---

## AI Agent

The AI Agent lives in `backend/ai_analyst.py`. It is triggered when the user clicks **"Generate AI Briefing"** in the frontend.

### How it works

1. **Data collection** — The backend gathers the top 8 anomalies by risk score and the latest monthly summary for each domain.

2. **Prompt construction** — The anomalies and summaries are formatted into an executive briefing prompt asking for:
   - Overall Risk Assessment
   - Critical Alerts (top 3, with root cause)
   - Cross-Domain Patterns
   - Recommended Actions

3. **Three-tier call chain** — The agent attempts each source in priority order, stopping at the first success:

   | Priority | Source | Requirement |
   |----------|--------|-------------|
   | 1 | **WorkBuddy MCP** | CodeBuddy running with MCP enabled; `WORKBUDDY_MCP_URL` set in `.env` |
   | 2 | **OpenAI API** | `OPENAI_API_KEY` set in `.env` |
   | 3 | **Rule-based** | No configuration needed — always available |

4. **Response** — Returns `{"text": "...", "source": "WorkBuddy MCP / OpenAI / Rule-based"}`. The source is displayed in the frontend so you can see which backend was used.

### WorkBuddy MCP integration

The MCP call uses standard JSON-RPC over HTTP:
1. `initialize` — establishes session
2. `tools/list` — discovers available tools
3. `tools/call` — invokes the best available chat/AI tool

To verify the MCP port is active:

```powershell
netstat -ano | findstr "LISTEN" | findstr "52652"
```

---

## Anomaly Detection

Implemented in `backend/anomaly_engine.py` using a **rolling Z-score** method:

- A 12-month rolling window computes the mean and standard deviation for each KPI.
- A data point is flagged as an anomaly if its Z-score exceeds `±2.0`.
- Only anomalies in the direction of concern are flagged (e.g., Revenue is only flagged when it drops, Defect Rate only when it rises).

### Risk scoring

| Z-score | Risk Score | Severity |
|---------|-----------|----------|
| 2.0 – 2.5 | 25 – 45 | Low |
| 2.5 – 3.0 | 45 – 65 | Medium |
| 3.0 – 4.0 | 65 – 85 | High |
| 4.0+ | 85 – 100 | Critical |

### Monitored KPIs

| Domain | Metrics |
|--------|---------|
| **Finance** | Revenue, Gross Margin %, EBITDA Margin %, Accounts Receivable Days, Cash Balance |
| **Operations** | OEE %, Defect Rate %, On-Time Delivery %, Inventory Turnover, Downtime Hours, Unit Cost |
| **Customer** | NPS, CSAT Score, Churn Rate %, New Customers, Avg Resolution Time, Customer LTV |

---

## Data Layer

`data/generate_data.py` generates **24 months of synthetic KPI data** (starting August 2024) with realistic trends, seasonality, noise, and intentionally injected anomalies for demo purposes.

Data is auto-generated on first backend startup if CSV files are not present. To manually regenerate:

```powershell
python data/generate_data.py
```

Or via the API:

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/api/regenerate-data
```
