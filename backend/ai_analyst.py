"""
AI Analyst — generates contextual alerts and root-cause explanations.
Strategy: Try WorkBuddy MCP (HTTP JSON-RPC) first, fallback to LLM API, then rule-based.
MCP URL is auto-discovered by scanning local ports (WorkBuddy uses a dynamic port).

LLM API supports OpenAI, Gemini (via OpenAI-compatible endpoint), DeepSeek, or any
OpenAI-compatible provider. Configure via .env:

  # OpenAI (default)
  LLM_API_KEY=sk-...
  LLM_MODEL=gpt-4o-mini
  LLM_BASE_URL=https://api.openai.com/v1

  # Google Gemini
  LLM_API_KEY=AIza...
  LLM_MODEL=gemini-2.5-flash
  LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai

  # DeepSeek
  LLM_API_KEY=sk-...
  LLM_MODEL=deepseek-chat
  LLM_BASE_URL=https://api.deepseek.com/v1

Legacy env vars (OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL) are still supported
as fallbacks for backwards compatibility.
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
WORKBUDDY_MCP_URL = os.getenv("WORKBUDDY_MCP_URL", "")   # optional hint; auto-discovered if empty/unreachable

# LLM API config — supports OpenAI, Gemini, DeepSeek, or any OpenAI-compatible provider
# New env vars (LLM_*) take priority; OPENAI_* kept for backwards compatibility
OPENAI_API_KEY = (
    os.getenv("LLM_API_KEY")
    or os.getenv("GEMINI_API_KEY")
    or os.getenv("OPENAI_API_KEY", "")
)
OPENAI_MODEL = (
    os.getenv("LLM_MODEL")
    or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
)
OPENAI_BASE_URL = (
    os.getenv("LLM_BASE_URL")
    or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
)

# Detect provider for logging
def _detect_provider() -> str:
    if "generativelanguage.googleapis.com" in OPENAI_BASE_URL:
        return "Gemini"
    if "deepseek.com" in OPENAI_BASE_URL:
        return "DeepSeek"
    if "openai.com" in OPENAI_BASE_URL:
        return "OpenAI"
    return "LLM"

_LLM_PROVIDER = _detect_provider()

# ── Port-discovery cache ──────────────────────────────────────────────────────
_discovered_mcp_url: Optional[str] = None   # cached after first successful discovery

# Scan every single port in the ephemeral range — no stepping/sampling
# so we never miss the actual port WorkBuddy picked
_SCAN_START = 49152
_SCAN_END   = 65535
_PROBE_BATCH = 100   # concurrent probes per batch
_PROBE_TIMEOUT = httpx.Timeout(connect=0.3, read=0.5, write=0.3, pool=0.3)


async def _probe_port(client: httpx.AsyncClient, port: int) -> Optional[str]:
    """Try to handshake with an MCP server on the given port. Returns URL if alive."""
    url = f"http://127.0.0.1:{port}/mcp"
    try:
        resp = await client.post(
            url,
            json={
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {"name": "probe", "version": "1"},
                    "capabilities": {},
                },
            },
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code == 200:
            return url
    except Exception:
        pass
    return None


async def _discover_mcp_url() -> Optional[str]:
    """
    Return a live WorkBuddy MCP URL.
    Priority:
      1. Cached URL (still alive)
      2. .env WORKBUDDY_MCP_URL hint (if reachable)
      3. Full concurrent port scan of 49152–65535 (every port, no gaps)
    Caches the result so subsequent calls skip the scan.
    """
    global _discovered_mcp_url

    # 1. Return cached URL if it is still alive
    if _discovered_mcp_url:
        try:
            cached_port = int(_discovered_mcp_url.split(":")[2].split("/")[0])
            async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
                result = await _probe_port(client, cached_port)
                if result:
                    return _discovered_mcp_url
        except Exception:
            pass
        print(f"[MCP] Cached URL {_discovered_mcp_url} no longer reachable — rescanning…")
        _discovered_mcp_url = None

    # 2. Try the .env hint first (fast path)
    if WORKBUDDY_MCP_URL:
        try:
            hint_port = int(WORKBUDDY_MCP_URL.split(":")[2].split("/")[0])
            async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
                result = await _probe_port(client, hint_port)
                if result:
                    print(f"[MCP] Using .env hint URL: {result}")
                    _discovered_mcp_url = result
                    return result
            print(f"[MCP] .env hint port {hint_port} is unreachable — falling through to full scan.")
        except Exception as e:
            print(f"[MCP] .env hint error: {e}")

    # 3. Full port scan — every port from 49152 to 65535
    print(f"[MCP] Scanning all ports {_SCAN_START}–{_SCAN_END} for WorkBuddy MCP server…")
    all_ports = list(range(_SCAN_START, _SCAN_END + 1))
    async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
        for i in range(0, len(all_ports), _PROBE_BATCH):
            batch = all_ports[i : i + _PROBE_BATCH]
            tasks = [_probe_port(client, p) for p in batch]
            results = await asyncio.gather(*tasks)
            for url in results:
                if url:
                    print(f"[MCP] Discovered MCP server at {url}")
                    _discovered_mcp_url = url
                    return url

    print("[MCP] No live MCP server found on any port 49152–65535.")
    return None


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


# ── WorkBuddy MCP call (internal — receives pre-discovered URL + logs list) ───
async def _call_workbuddy_mcp_with_url(prompt: str, mcp_url: str, logs: List[str]) -> Optional[str]:
    """
    Execute a WorkBuddy MCP JSON-RPC call against a known-live URL.
    Writes diagnostic messages into `logs`.
    """
    global _discovered_mcp_url
    try:
        async with httpx.AsyncClient(timeout=60) as client:

            # ── Step 1: Initialize session ────────────────────────────────────
            logs.append("   → initialize…")
            init_resp = await client.post(
                mcp_url,
                json={
                    "jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "clientInfo": {"name": "InsightGuardAI", "version": "1.0.0"},
                        "capabilities": {}
                    }
                },
                headers={"Content-Type": "application/json"},
            )
            logs.append(f"   → initialize HTTP {init_resp.status_code}")
            if init_resp.status_code != 200:
                logs.append(f"   ❌ initialize failed: {init_resp.text[:200]}")
                return None

            # ── Step 2: List available tools ──────────────────────────────────
            logs.append("   → tools/list…")
            tools_resp = await client.post(
                mcp_url,
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                headers={"Content-Type": "application/json"},
            )
            logs.append(f"   → tools/list HTTP {tools_resp.status_code}")
            if tools_resp.status_code != 200:
                logs.append(f"   ❌ tools/list failed: {tools_resp.text[:200]}")
                return None

            tools_data = tools_resp.json()
            tools = tools_data.get("result", {}).get("tools", [])
            tool_names = [t.get("name", "") for t in tools]
            logs.append(f"   → available tools: {tool_names}")

            # ── Step 3: Pick best available tool ─────────────────────────────
            preferred = ["ainvoke", "chat", "ask", "codebuddy_chat", "llm_chat"]
            chosen_tool = next((t for t in preferred if t in tool_names), None)
            if not chosen_tool and tool_names:
                chosen_tool = tool_names[0]
            if not chosen_tool:
                logs.append("   ❌ No usable tool found in tools/list response.")
                return None
            logs.append(f"   → selected tool: {chosen_tool}")

            # ── Step 4: Call the tool ─────────────────────────────────────────
            for args in [
                {"prompt": prompt},
                {"message": prompt},
                {"messages": [{"role": "user", "content": prompt}]},
                {"input": prompt},
                {"query": prompt},
            ]:
                call_resp = await client.post(
                    mcp_url,
                    json={
                        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                        "params": {"name": chosen_tool, "arguments": args}
                    },
                    headers={"Content-Type": "application/json"},
                )
                logs.append(f"   → tools/call (args={list(args.keys())}) HTTP {call_resp.status_code}")
                if call_resp.status_code == 200:
                    data = call_resp.json()
                    result = data.get("result", {})
                    content = result.get("content", [])
                    if isinstance(content, list) and content:
                        text = content[0].get("text", "")
                        if text:
                            return text
                    text = (
                        result.get("text")
                        or result.get("output")
                        or result.get("response")
                        or (str(result) if result and "error" not in data else None)
                    )
                    if text:
                        return str(text)
                    logs.append(f"   ⚠ tools/call returned 200 but no text. Response: {str(data)[:300]}")
                else:
                    logs.append(f"   ⚠ tools/call non-200: {call_resp.text[:200]}")

    except Exception as e:
        logs.append(f"   ❌ Exception during MCP call: {e}")
        print(f"[MCP] Call failed ({e}); clearing cached URL to force re-discovery.")
        _discovered_mcp_url = None
    return None


# Keep old signature as a shim so nothing else breaks
async def _call_workbuddy_mcp(prompt: str) -> Optional[str]:
    mcp_url = await _discover_mcp_url()
    if not mcp_url:
        return None
    return await _call_workbuddy_mcp_with_url(prompt, mcp_url, [])


# ── OpenAI fallback ───────────────────────────────────────────────────────────
async def _call_openai(prompt: str, logs: Optional[List[str]] = None) -> Optional[str]:
    if logs is None:
        logs = []
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
            logs.append(f"   → {_LLM_PROVIDER} HTTP {resp.status_code}")
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            else:
                logs.append(f"   ❌ {_LLM_PROVIDER} error body: {resp.text[:300]}")
    except Exception as e:
        logs.append(f"   ❌ {_LLM_PROVIDER} exception: {e}")
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
    Generate AI analysis.
    Returns dict with 'text', 'source', and 'debug_log' (list of diagnostic strings).
    """
    logs: List[str] = []
    prompt = _build_prompt(anomalies, domain_summaries)

    # ── 1. Try WorkBuddy MCP ──────────────────────────────────────────────────
    # Skip MCP scan entirely if an LLM API key is already configured — no need
    # to spend time scanning thousands of ports when a direct API path is available.
    if OPENAI_API_KEY:
        logs.append("⏭ Step 1: Skipping WorkBuddy MCP scan (LLM API key is configured).")
    elif WORKBUDDY_MCP_URL:
        logs.append(f"🔍 Step 1: Attempting WorkBuddy MCP (hint: {WORKBUDDY_MCP_URL})…")
        mcp_url = await _discover_mcp_url()
        if mcp_url:
            logs.append(f"   ✅ MCP server found at: {mcp_url}")
            result = await _call_workbuddy_mcp_with_url(prompt, mcp_url, logs)
            if result:
                logs.append("   ✅ MCP call succeeded.")
                return {"text": result, "source": "WorkBuddy MCP", "debug_log": logs}
            else:
                logs.append("   ❌ MCP server found but call returned no usable response.")
        else:
            logs.append(f"   ❌ MCP hint URL unreachable.")
    else:
        logs.append("⏭ Step 1: Skipping WorkBuddy MCP scan (no WORKBUDDY_MCP_URL set and no LLM key to fall back on — will try port scan).")
        mcp_url = await _discover_mcp_url()
        if mcp_url:
            logs.append(f"   ✅ MCP server found at: {mcp_url}")
            result = await _call_workbuddy_mcp_with_url(prompt, mcp_url, logs)
            if result:
                logs.append("   ✅ MCP call succeeded.")
                return {"text": result, "source": "WorkBuddy MCP", "debug_log": logs}
            else:
                logs.append("   ❌ MCP server found but call returned no usable response.")
        else:
            logs.append(f"   ❌ No MCP server found on ports {_SCAN_START}–{_SCAN_END}.")

    # ── 2. Try LLM API fallback (OpenAI / Gemini / DeepSeek / compatible) ────
    logs.append(f"🔍 Step 2: Attempting {_LLM_PROVIDER} API…")
    if not OPENAI_API_KEY:
        logs.append("   ❌ LLM_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY is empty — skipping.")
    else:
        logs.append(f"   Key found. Model={OPENAI_MODEL}, Base={OPENAI_BASE_URL}")
        result = await _call_openai(prompt, logs)
        if result:
            logs.append(f"   ✅ {_LLM_PROVIDER} call succeeded.")
            return {"text": result, "source": _LLM_PROVIDER, "debug_log": logs}
        else:
            logs.append(f"   ❌ {_LLM_PROVIDER} call failed (check key/model/base URL).")

    # ── 3. Rule-based fallback ────────────────────────────────────────────────
    logs.append("🔍 Step 3: Falling back to rule-based analysis.")
    return {"text": _rule_based_analysis(anomalies), "source": "Rule-based", "debug_log": logs}
