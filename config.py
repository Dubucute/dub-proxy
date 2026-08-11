# dub-proxy configuration.
# Direct connection first; rotate through IPVanish SOCKS5 on 429 only.

import os

UPSTREAM_BASE = "https://opencode.ai/zen/v1"
# opencode.ai free models need NO API key — sending an invalid authorization gets
# rejected (e.g. "none" -> 401). BUT "public" is special: opencode.ai treats
# "Authorization: Bearer public" as ANONYMOUS and returns 200 (verified live).
# Clients may send apiKey "none" (some apps require one) — the proxy IGNORES it
# and always uses "public" internally. No real key is ever used.
UPSTREAM_API_KEY = "public"

# Browser-ish User-Agent so Cloudflare 1010 block doesn't trip.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# Only rotate on 429 (rate limit) OR on 403 whose body is an HTML block page
# (Cloudflare 1010 "Blocked"). A 403 with a JSON body is a real API rejection
# and is returned as-is. Direct retried after a transient block usually clears.
PROXY_RETRY_STATUSES = {429}
RETRY_HTML_403 = True
DIRECT_ORDER = "direct-first"

# ---- IPVanish SOCKS5 proxies (server, port, user, pass) ----
_IPV_USER = "4wKRruhNI"
_IPV_PASS = "CIfYtdMDe0"
_IPV_HOSTS = [
    "mel.socks.ipvanish.com", "tor.socks.ipvanish.com",
    "lin.socks.ipvanish.com", "ams.socks.ipvanish.com",
    "waw.socks.ipvanish.com", "sin.socks.ipvanish.com",
    "mad.socks.ipvanish.com", "lon.socks.ipvanish.com",
    "iad.socks.ipvanish.com", "atl.socks.ipvanish.com",
    "chi.socks.ipvanish.com", "cvg.socks.ipvanish.com",
    "dal.socks.ipvanish.com", "lax.socks.ipvanish.com",
    "mia.socks.ipvanish.com", "nyc.socks.ipvanish.com",
    "phx.socks.ipvanish.com", "sjc.socks.ipvanish.com",
]
_PORT = 1080

# Allow env override (Render --> set SOCKS5_PROXIES to comma-separated list of
# "host|port|user|pass" or "host" entries). If set, replaces the default list.
def _load_proxies():
    env = os.environ.get("SOCKS5_PROXIES")
    if env:
        out = []
        for raw in env.split(","):
            raw = raw.strip()
            if not raw:
                continue
            parts = raw.split("|")
            host = parts[0]
            port = int(parts[1]) if len(parts) > 1 else _PORT
            user = parts[2] if len(parts) > 2 else _IPV_USER
            pw = parts[3] if len(parts) > 3 else _IPV_PASS
            label = f"ipv-{host.split('.')[0]}"
            out.append({
                "label": label,
                "url": f"socks5://{user}:{pw}@{host}:{port}",
            })
        # if created from env, still random order at build time
        return out
    out = []
    for h in _IPV_HOSTS:
        label = f"ipv-{h.split('.')[0]}"
        out.append({
            "label": label,
            "url": f"socks5://{_IPV_USER}:{_IPV_PASS}@{h}:{_PORT}",
        })
    return out


PROXIES = _load_proxies()