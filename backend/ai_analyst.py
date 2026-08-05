"""
AI Analyst — generates contextual alerts and root-cause explanations.
Strategy: Call Gemini API first, fall back to rule-based analysis.

Configure via .env:

  GEMINI_API_KEY=AIza...
  GEMINI_MODEL=gemini-2.5-flash        # optional, defaults to gemini-2.5-flash
"""

import os
import json
import httpx
from typing import List, Optional
from dotenv import load_dotenv
from backend.anomaly_engine import Anomaly

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Gemini uses the OpenAI-compatible endpoint
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"


# ── Prompt builder ────────────────────────────────────────────────────────────
def _build_prompt(anomalies: List[Anomaly], domain_summaries: dict) -> str:
    anomaly_lines = []
    for a in anomalies[:10]:
        anomaly_lines.append(
            f"- [{a.severity.upper()}] {a.domain} / {a.metric_label}: "
            f"value={a.value}{a.unit}, expected≈{a.expected}{a.unit}, "
            f"deviation={a.deviation_pct:+.1f}%, z={a.z_score:.1f}, date={a.date}"
        )

    summary_lines = []
    for domain, stats in domain_summaries.items():
        summary_lines.append(f"- {domain}: {json.dumps(stats)}")

    prompt = f"""You are an AI performance analyst for an executive early-warning dashboard.
Analyse the following KPI anomalies detected across Finance, Operations, and Customer domains.

DETECTED ANOMALIES:
{chr(10).join(anomaly_lines)}

DOMAIN SUMMARIES (latest month):
{chr(10).join(summary_lines)}

Provide a concise executive briefing with:
1. **Overall Risk Assessment** (2-3 sentences, overall health status)
2. **Critical Alerts** (top 3 issues, each with: what, why it matters, likely root cause)
3. **Cross-Domain Patterns** (any correlations or systemic signals across domains)
4. **Recommended Actions** (3-5 concrete next steps for leadership)

Keep it professional, actionable, and under 400 words. Use markdown formatting."""
    return prompt


# ── Gemini API call ───────────────────────────────────────────────────────────
async def _call_gemini(prompt: str, logs: List[str]) -> Optional[str]:
    if not GEMINI_API_KEY:
        logs.append("   ❌ GEMINI_API_KEY is not set — skipping.")
        return None
    try:
        payload = {
            "model": GEMINI_MODEL,
            "messages": [
                {"role": "system", "content": "You are an expert AI performance analyst providing executive briefings."},
                {"role": "user",   "content": prompt},
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


# ── Rule-based fallback ───────────────────────────────────────────────────────
def _rule_based_analysis(anomalies: List[Anomaly]) -> str:
    if not anomalies:
        return (
            "**Overall Risk Assessment**\n\n"
            "No significant anomalies detected. All KPIs are within expected ranges.\n\n"
            "**Recommended Actions**\n"
            "- Continue monitoring current trends\n"
            "- Review targets for next quarter"
        )

    critical = [a for a in anomalies if a.severity == "critical"]
    high      = [a for a in anomalies if a.severity == "high"]
    domains   = list({a.domain for a in anomalies})

    lines = [
        "## Overall Risk Assessment",
        f"**{len(critical)} critical** and **{len(high)} high** severity anomalies detected across "
        f"**{len(domains)} domain(s)**: {', '.join(domains)}. Immediate management attention is required.",
        "",
        "## Critical Alerts",
    ]

    shown = set()
    for a in sorted(anomalies, key=lambda x: -x.risk_score)[:3]:
        key = f"{a.domain}-{a.metric}"
        if key in shown:
            continue
        shown.add(key)
        direction_word = "spike" if a.direction == "above" else "drop"
        lines.append(
            f"- **{a.domain} – {a.metric_label}** (Risk Score: {a.risk_score}/100): "
            f"Detected {direction_word} of {abs(a.deviation_pct):.1f}% vs expected on {a.date}. "
            f"Value: {a.value}{a.unit} vs expected {a.expected}{a.unit}."
        )

    lines += [
        "",
        "## Recommended Actions",
        "- Convene emergency review with domain leads for flagged metrics",
        "- Validate data integrity for anomalous periods",
        "- Review operational changes or external events coinciding with anomaly dates",
        "- Adjust alert thresholds based on business context",
        "- Escalate critical items to C-suite within 24 hours",
    ]

    return "\n".join(lines)


# ── Main entry point ──────────────────────────────────────────────────────────
async def analyse(anomalies: List[Anomaly], domain_summaries: dict) -> dict:
    """
    Generate AI analysis.
    Returns dict with 'text', 'source', and 'debug_log' (list of diagnostic strings).
    """
    logs: List[str] = []
    prompt = _build_prompt(anomalies, domain_summaries)

    # ── 1. Try Gemini API ─────────────────────────────────────────────────────
    logs.append(f"🔍 Step 1: Attempting Gemini API (model={GEMINI_MODEL})…")
    result = await _call_gemini(prompt, logs)
    if result:
        logs.append("   ✅ Gemini call succeeded.")
        return {"text": result, "source": "Gemini", "debug_log": logs}
    else:
        logs.append("   ❌ Gemini call failed (check GEMINI_API_KEY / GEMINI_MODEL).")

    # ── 2. Rule-based fallback ────────────────────────────────────────────────
    logs.append("🔍 Step 2: Falling back to rule-based analysis.")
    return {"text": _rule_based_analysis(anomalies), "source": "Rule-based", "debug_log": logs}
