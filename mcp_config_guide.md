# WorkBuddy MCP Configuration Guide

## What to add to your WorkBuddy MCP config

WorkBuddy uses a local `mcp.json` (or similar config file) to register MCP servers.
You need to expose a local HTTP server that InsightGuardAI can call for AI analysis.

### Option A: Use WorkBuddy's built-in MCP HTTP endpoint

If WorkBuddy already exposes an MCP SSE endpoint (common default: `http://localhost:3000/sse`),
no extra config is needed. Just set in your `.env`:

```
WORKBUDDY_MCP_URL=http://localhost:3000/sse
```

Then verify it's running:
```powershell
Invoke-WebRequest -Uri http://localhost:3000/sse -Method GET
```

### Option B: Register InsightGuardAI as an MCP client in WorkBuddy

In WorkBuddy, go to **Settings → MCP** (or open `mcp.json` in WorkBuddy's config directory).
Add the following entry:

```json
{
  "mcpServers": {
    "insightguard-ai": {
      "command": "uvicorn",
      "args": ["backend.main:app", "--port", "8000"],
      "cwd": "C:/Users/kwekj/OneDrive/Documents/Tencent Hackathon/InsightGuardAi",
      "env": {}
    }
  }
}
```

### Option C: Use DeepSeek as a cheap fallback (recommended for demos)

If you don't have WorkBuddy MCP running, use DeepSeek as the fallback.
In your `.env`:

```
OPENAI_API_KEY=your-deepseek-api-key
OPENAI_MODEL=deepseek-chat
OPENAI_BASE_URL=https://api.deepseek.com/v1
```

DeepSeek uses the same OpenAI-compatible API format and is very cost-effective.

---

## How the AI fallback chain works

1. **WorkBuddy MCP** — tries `POST {WORKBUDDY_MCP_URL.replace('/sse', '/message')}`
2. **OpenAI / DeepSeek** — if MCP unavailable, uses `OPENAI_API_KEY`
3. **Rule-based** — always works with no external dependencies
