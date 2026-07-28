"""
AI Analyst — generates contextual alerts and root-cause explanations.
Strategy: Try WorkBuddy MCP (HTTP JSON-RPC) first, fallback to OpenAI API, then rule-based.
"""

import os
import json
import httpx
import asyncio
from typing import List, Optional
from dotenv import load_dotenv
from backend.anomaly_engine import Anomaly

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
WORKBUDDY_MCP_URL = os.getenv("WORKBUDDY_MCP_URL", "http://127.0.0.1:52652/mcp")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL      = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL   = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")


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


# ── WorkBuddy MCP call ────────────────────────────────────────────────────────
async def _call_workbuddy_mcp(prompt: str) -> Optional[str]:
    """
    Call WorkBuddy MCP via standard HTTP JSON-RPC (MCP spec).
    Steps:
      1. POST /mcp with method=initialize to establish session
      2. POST /mcp with method=tools/list to discover available tools
      3. POST /mcp with method=tools/call to invoke the chat/AI tool
    """
    try:
        async with httpx.AsyncClient(timeout=60) as client:

            # ── Step 1: Initialize session ────────────────────────────────────
            init_resp = await client.post(
                WORKBUDDY_MCP_URL,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "clientInfo": {"name": "InsightGuardAI", "version": "1.0.0"},
                        "capabilities": {}
                    }
                },
                headers={"Content-Type": "application/json"},
            )
            if init_resp.status_code != 200:
                return None

            # ── Step 2: List available tools ──────────────────────────────────
            tools_resp = await client.post(
                WORKBUDDY_MCP_URL,
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/list",
                    "params": {}
                },
                headers={"Content-Type": "application/json"},
            )
            if tools_resp.status_code != 200:
                return None

            tools_data = tools_resp.json()
            tools = tools_data.get("result", {}).get("tools", [])
            tool_names = [t.get("name", "") for t in tools]

            # ── Step 3: Pick best available tool ─────────────────────────────
            # WorkBuddy MCP typically exposes: ainvoke, chat, ask, or codebuddy_chat
            preferred = ["ainvoke", "chat", "ask", "codebuddy_chat", "llm_chat"]
            chosen_tool = next((t for t in preferred if t in tool_names), None)

            # If none of the preferred names match, try the first tool available
            if not chosen_tool and tool_names:
                chosen_tool = tool_names[0]

            if not chosen_tool:
                return None

            # ── Step 4: Call the tool ─────────────────────────────────────────
            # Try common argument schemas for chat tools
            for args in [
                {"prompt": prompt},
                {"message": prompt},
                {"messages": [{"role": "user", "content": prompt}]},
                {"input": prompt},
                {"query": prompt},
            ]:
                call_resp = await client.post(
                    WORKBUDDY_MCP_URL,
                    json={
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {
                            "name": chosen_tool,
                            "arguments": args
                        }
                    },
                    headers={"Content-Type": "application/json"},
                )
                if call_resp.status_code == 200:
                    data = call_resp.json()
                    # Extract text from MCP response structure
                    result = data.get("result", {})
                    content = result.get("content", [])
                    if isinstance(content, list) and content:
                        text = content[0].get("text", "")
                        if text:
                            return text
                    # Alternative response shapes
                    text = (
                        result.get("text")
                        or result.get("output")
                        or result.get("response")
                        or (str(result) if result and "error" not in data else None)
                    )
                    if text:
                        return str(text)

    except Exception:
        pass
    return None


# ── OpenAI fallback ───────────────────────────────────────────────────────────
async def _call_openai(prompt: str) -> Optional[str]:
    if not OPENAI_API_KEY:
        return None
    try:
        payload = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": "You are an expert AI performance analyst providing executive briefings."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 600,
            "temperature": 0.4,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{OPENAI_BASE_URL}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        pass
    return None


# ── Rule-based fallback ───────────────────────────────────────────────────────
def _rule_based_analysis(anomalies: List[Anomaly]) -> str:
    if not anomalies:
        return "**Overall Risk Assessment**\n\nNo significant anomalies detected. All KPIs are within expected ranges.\n\n**Recommended Actions**\n- Continue monitoring current trends\n- Review targets for next quarter"

    critical = [a for a in anomalies if a.severity == "critical"]
    high      = [a for a in anomalies if a.severity == "high"]
    domains   = list({a.domain for a in anomalies})

    lines = [
        f"## Overall Risk Assessment",
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
    Generate AI analysis. Returns dict with 'text' and 'source'.
    """
    prompt = _build_prompt(anomalies, domain_summaries)

    # 1. Try WorkBuddy MCP
    result = await _call_workbuddy_mcp(prompt)
    if result:
        return {"text": result, "source": "WorkBuddy MCP"}

    # 2. Try OpenAI fallback
    result = await _call_openai(prompt)
    if result:
        return {"text": result, "source": "OpenAI"}

    # 3. Rule-based fallback
    return {"text": _rule_based_analysis(anomalies), "source": "Rule-based"}
