"""
AI Analyst — generates contextual executive briefings.
Strategy: Call Gemini API first; fall back to rule-based analysis.

Configure via .env:
  GEMINI_API_KEY=AIza...
  GEMINI_MODEL=gemini-2.5-flash    # optional, defaults to gemini-2.5-flash
"""

import os
import json
import httpx
from typing import List, Optional
from dotenv import load_dotenv

from backend.insight_engine import InsightPackage

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"


# ══════════════════════════════════════════════════════════════════════════════
# 7. Richer Prompt Builder
# ══════════════════════════════════════════════════════════════════════════════

def _build_prompt(pkg: InsightPackage) -> str:
    sections: List[str] = []

    # ── Anomalies ─────────────────────────────────────────────────────────────
    if pkg.anomalies:
        lines = []
        for a in pkg.anomalies[:10]:
            lines.append(
                f"  • [{a.severity.upper()}] {a.domain} / {a.metric_label}: "
                f"actual={a.value}{a.unit}, baseline≈{a.expected}{a.unit}, "
                f"deviation={a.deviation_pct:+.1f}%, z={a.z_score:.1f}, "
                f"risk={a.risk_score}/100, direction={a.direction}, date={a.date}"
            )
        sections.append("POINT ANOMALIES (statistical outliers):\n" + "\n".join(lines))

    # ── Trend deteriorations ──────────────────────────────────────────────────
    if pkg.trend_alerts:
        lines = []
        for t in pkg.trend_alerts:
            lines.append(
                f"  • [{t.severity.upper()}] {t.domain} / {t.metric_label}: "
                f"{t.direction} for {t.consecutive_periods} consecutive months, "
                f"total change={t.total_change_pct:+.1f}% "
                f"({t.start_value}{t.unit} → {t.latest_value}{t.unit}, "
                f"since {t.start_date})"
            )
        sections.append("TREND DETERIORATIONS (sustained directional worsening):\n" + "\n".join(lines))

    # ── Forecast alerts ───────────────────────────────────────────────────────
    if pkg.forecast_alerts:
        lines = []
        for f in pkg.forecast_alerts[:6]:
            lines.append(f"  • [{f.severity.upper()}] {f.domain} / {f.message}")
        sections.append("FORECAST EARLY WARNINGS (3-month linear projection):\n" + "\n".join(lines))

    # ── Target gaps ───────────────────────────────────────────────────────────
    if pkg.target_gaps:
        lines = []
        for tg in pkg.target_gaps:
            lines.append(
                f"  • {tg['label']}: actual={tg['actual']}{tg['unit']}, "
                f"target={tg['target']}{tg['unit']}, gap={tg['gap_pct']:+.1f}%, "
                f"status={tg['status'].upper()}"
            )
        sections.append("TARGET VS ACTUAL (latest month):\n" + "\n".join(lines))

    # ── Consolidated incidents ────────────────────────────────────────────────
    if pkg.incidents:
        lines = []
        for inc in pkg.incidents:
            causal = "; ".join(inc.causal_chain) if inc.causal_chain else "N/A"
            lines.append(
                f"  • [{inc.severity.upper()}] '{inc.title}' (risk={inc.risk_score}/100)\n"
                f"    Domains: {', '.join(inc.domain_tags)}\n"
                f"    Root drivers: {', '.join(inc.root_metrics)}\n"
                f"    Downstream impact: {', '.join(inc.affected_metrics) or 'N/A'}\n"
                f"    Causal links: {causal}"
            )
        sections.append("CONSOLIDATED BUSINESS INCIDENTS (cross-domain):\n" + "\n".join(lines))

    # ── Domain snapshots ──────────────────────────────────────────────────────
    if pkg.domain_summaries:
        lines = []
        for domain, stats in pkg.domain_summaries.items():
            lines.append(f"  {domain}: {json.dumps(stats)}")
        sections.append("LATEST DOMAIN SNAPSHOTS:\n" + "\n".join(lines))

    # ── Assemble ──────────────────────────────────────────────────────────────
    context_block = "\n\n".join(sections)

    prompt = f"""You are an AI performance analyst for an executive early-warning dashboard.
Analyse the following comprehensive KPI intelligence report for a manufacturing/services company.

{context_block}

Using ALL the data above (anomalies, trends, forecasts, target gaps, and cross-domain incidents), \
produce a structured executive briefing with exactly the following sections:

## 1. Overall Risk Assessment
2–3 sentences summarising the current health of the business, \
citing the most critical incident or risk cluster.

## 2. Critical Alerts
Top 3 issues. For each:
- **[Metric / Incident]**: What is happening, why it matters, likely root cause, \
  and whether it has been deteriorating (trend) or is a sudden spike.

## 3. Cross-Domain Patterns & Causal Chains
Identify systemic relationships between domains (e.g. Ops → Finance, Customer → Revenue). \
Explain the business impact chain in plain language.

## 4. Forward-Looking Warnings
Highlight the 2–3 most important forecast alerts or deteriorating trends \
that are not yet anomalies but pose near-term risk.

## 5. Recommended Actions
5 concrete next steps for leadership, prioritised by urgency. \
Reference specific KPIs and timeframes where possible.

Keep the tone professional and concise. Total length: 450–550 words. Use markdown formatting."""

    return prompt


# ══════════════════════════════════════════════════════════════════════════════
# Gemini API call
# ══════════════════════════════════════════════════════════════════════════════

async def _call_gemini(prompt: str, logs: List[str]) -> Optional[str]:
    if not GEMINI_API_KEY:
        logs.append("   ❌ GEMINI_API_KEY is not set — skipping.")
        return None
    try:
        payload = {
            "model": GEMINI_MODEL,
            "messages": [
                {
                    "role":    "system",
                    "content": "You are an expert AI performance analyst producing executive briefings.",
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 1200,
            "temperature": 0.4,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{_GEMINI_BASE_URL}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {GEMINI_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            logs.append(f"   → Gemini HTTP {resp.status_code}")
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            else:
                logs.append(f"   ❌ Gemini error: {resp.text[:300]}")
    except Exception as e:
        logs.append(f"   ❌ Gemini exception: {e}")
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Rule-based fallback
# ══════════════════════════════════════════════════════════════════════════════

def _rule_based_analysis(pkg: InsightPackage) -> str:
    anomalies    = pkg.anomalies
    trend_alerts = pkg.trend_alerts
    forecasts    = pkg.forecast_alerts
    incidents    = pkg.incidents

    if not anomalies and not trend_alerts:
        return (
            "## Overall Risk Assessment\n\n"
            "No significant anomalies or deteriorating trends detected. "
            "All KPIs are within expected ranges.\n\n"
            "## Recommended Actions\n"
            "- Continue monitoring current trends\n"
            "- Review targets for the next quarter"
        )

    critical_anoms = [a for a in anomalies if a.severity == "critical"]
    high_anoms     = [a for a in anomalies if a.severity == "high"]
    domains        = list({a.domain for a in anomalies} | {t.domain for t in trend_alerts})

    lines = [
        "## 1. Overall Risk Assessment",
        (
            f"**{len(critical_anoms)} critical** and **{len(high_anoms)} high** severity anomalies "
            f"detected across **{len(domains)} domain(s)** ({', '.join(domains)}). "
            f"{len(trend_alerts)} KPI(s) show sustained deterioration. "
            "Immediate management attention is required."
        ),
        "",
        "## 2. Critical Alerts",
    ]

    shown: set = set()
    top_items = sorted(anomalies, key=lambda x: -x.risk_score)
    for a in top_items[:3]:
        key = f"{a.domain}-{a.metric}"
        if key in shown:
            continue
        shown.add(key)
        direction_word = "spike" if a.direction == "above" else "drop"
        lines.append(
            f"- **{a.domain} – {a.metric_label}** (Risk: {a.risk_score}/100): "
            f"Detected {direction_word} of {abs(a.deviation_pct):.1f}% vs baseline on {a.date}. "
            f"Value: {a.value}{a.unit} vs expected {a.expected}{a.unit}."
        )

    if incidents:
        lines += ["", "## 3. Cross-Domain Patterns & Causal Chains"]
        for inc in incidents[:2]:
            chain = "; ".join(inc.causal_chain) if inc.causal_chain else "Multiple KPIs affected across domains."
            lines.append(
                f"- **{inc.title}**: {chain}"
            )

    if forecasts:
        lines += ["", "## 4. Forward-Looking Warnings"]
        for f in forecasts[:3]:
            lines.append(f"- [{f.severity.upper()}] {f.message}")

    lines += [
        "",
        "## 5. Recommended Actions",
        "- Convene emergency review with domain leads for all critical-severity metrics",
        "- Validate data integrity for anomalous periods before escalating externally",
        "- Review operational and market events coinciding with anomaly dates",
        "- Adjust Q+1 revenue and OEE forecasts based on current trend trajectory",
        "- Escalate all critical incidents to C-suite within 24 hours",
    ]

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# Main entry point
# ══════════════════════════════════════════════════════════════════════════════

async def analyse(pkg: InsightPackage) -> dict:
    """
    Generate AI analysis from a full InsightPackage.
    Returns dict with 'text', 'source', and 'debug_log'.
    """
    logs: List[str] = []
    prompt = _build_prompt(pkg)

    # ── 1. Try Gemini API ─────────────────────────────────────────────────────
    logs.append(f"🔍 Step 1: Attempting Gemini API (model={GEMINI_MODEL})…")
    result = await _call_gemini(prompt, logs)
    if result:
        logs.append("   ✅ Gemini call succeeded.")
        return {
            "text":         result,
            "source":       "Gemini",
            "debug_log":    logs,
            "incident_count":  len(pkg.incidents),
            "trend_count":     len(pkg.trend_alerts),
            "forecast_count":  len(pkg.forecast_alerts),
        }

    logs.append("   ❌ Gemini call failed (check GEMINI_API_KEY / GEMINI_MODEL).")

    # ── 2. Rule-based fallback ────────────────────────────────────────────────
    logs.append("🔍 Step 2: Falling back to rule-based analysis.")
    return {
        "text":         _rule_based_analysis(pkg),
        "source":       "Rule-based",
        "debug_log":    logs,
        "incident_count":  len(pkg.incidents),
        "trend_count":     len(pkg.trend_alerts),
        "forecast_count":  len(pkg.forecast_alerts),
    }
