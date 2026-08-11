# dub-proxy

Minimal OpenAI-compatible proxy to **opencode.ai** free models.
Direct connection first; rotates through IPVanish SOCKS5 proxies **only on HTTP 429** (rate limit).

No context limits. No model curation (all models pass through). No dashboard.

## Design
1. **Direct** to `https://opencode.ai/zen/v1` (Render's IP, browser User-Agent) — fast path.
2. On **429 only**, rotate through a randomized list of IPVanish SOCKS5 proxies.
3. Any other status (5xx, 4xx, timeout) is returned as-is — no pointless rotation.

Uses the official `openai` Python SDK to talk upstream (streaming / SSE handled by the SDK).

## Run locally
```bash
pip install -r requirements.txt
uvicorn main:app --port 8000
```

## Deploy to Render
Dashboard -> New+ -> Web Service -> paste this repo -> Free plan -> Create.
Or one-click: `https://render.com/deploy?repo=https://github.com/Dubucute/dub-proxy`

## Use
OpenAI-compatible endpoint: `https://dub-proxy.onrender.com/v1`
- baseURL: `https://dub-proxy.onrender.com/v1`
- apiKey: send `none` — the proxy ignores any client key (`none`, empty, or anything).
- model: any opencode.ai free model, e.g. `big-pickle`, `mimo-v2.5-free`, `deepseek-v4-flash-free`, `hy3-free`

> **Why "none"?** opencode.ai needs NO API key — sending an invalid one (like `none`) directly gets rejected with 401. The proxy accepts any client key but talks to opencode.ai as **anonymous** internally (`Bearer public`, which opencode.ai treats as no key — verified). So just put `none` and it works; some apps require a key field, and `none` satisfies that.

### Example (OpenAI SDK / ai sdk)
```ts
@ai-sdk/openai-compatible
baseURL: 'https://dub-proxy.onrender.com/v1'
apiKey: 'none'
model: 'big-pickle'
```

### IPVanish rotation
Default proxy list is in `config.py`. Override via env var on Render:
```
SOCKS5_PROXIES = host|port|user|pass,host|port|user|pass,...
```
(e.g. `lon.socks.ipvanish.com|1080|user|pass`)