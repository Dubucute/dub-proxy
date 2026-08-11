# dub-proxy — thin OpenAI-compatible proxy to opencode.ai
# Direct first; on 429 or Cloudflare-HTML-403, rotate through IPVanish SOCKS5.
# All models pass through verbatim. No context limits, no dashboard.
"""dub-proxy: OpenAI-SDK-backed proxy to opencode.ai free models.

Design (per user requirement):
  - Direct connection to opencode.ai/zen/v1 first (fastest).
  - On HTTP 429 (rate limit) or a 403 HTML block page (Cloudflare), rotate.
  - Pass through ALL models verbatim. No context trimming, no curation.
  - Uses the OpenAI Python SDK to talk to upstream (streaming/SSE handled).
  - Thin FastAPI+uvicorn listener so clients get an OpenAI-compatible endpoint.
"""

import logging
import os
import random

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from openai import OpenAI, APIStatusError, APIConnectionError

from config import (
    UPSTREAM_BASE, UPSTREAM_API_KEY, PROXIES, UA,
    DIRECT_ORDER, PROXY_RETRY_STATUSES, RETRY_HTML_403,
)

log = logging.getLogger("dub-proxy")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="dub-proxy", version="1.0.0")

# Each entry: (label, base_url, http_client_kwargs)
_routes = []
_direct_lbl = "direct"

def build_routes():
    global _routes
    r = []
    # 1) direct (no proxy)
    r.append((_direct_lbl, UPSTREAM_BASE, {}))
    # 2) proxies
    for p in PROXIES:
        r.append((p["label"], UPSTREAM_BASE, {"proxy": p["url"]}))
    # shuffling keeps 429 fallback varied; direct stays first
    rest = r[1:]
    random.shuffle(rest)
    _routes = [r[0]] + rest

build_routes()


def make_client(base_url: str, kwargs: dict) -> OpenAI:
    # Proxy (SOCKS) is plumbed through an httpx.Client, not a constructor kwarg.
    http_client = None
    if "proxy" in kwargs:
        import httpx
        http_client = httpx.Client(proxy=kwargs["proxy"])
    # Proxy routes get a shorter timeout so a dead proxy pool returns quickly
    # instead of hanging; direct keeps a generous timeout.
    timeout = 15.0 if http_client is not None else 120.0
    client = OpenAI(
        api_key=UPSTREAM_API_KEY,  # "public" — opencode.ai treats as anonymous
        base_url=base_url,
        default_headers={"User-Agent": UA},
        http_client=http_client,
        max_retries=0,  # we handle 429 rotation ourselves
        timeout=timeout,
    )
    return client


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/v1/models")
def models():
    # Pass-through model list from upstream is heavy/blocked; respond with a
    # lightweight OpenAI list since we forward any model id anyway.
    return JSONResponse({
        "object": "list", "data": [
            {"id": "big-pickle", "object": "model", "owned_by": "dub"},
            {"id": "mimo-v2.5-free", "object": "model", "owned_by": "dub"},
            {"id": "deepseek-v4-flash-free", "object": "model", "owned_by": "dub"},
            {"id": "hy3-free", "object": "model", "owned_by": "dub"},
            {"id": "nemotron-3-ultra-free", "object": "model", "owned_by": "dub"},
            {"id": "north-mini-code-free", "object": "model", "owned_by": "dub"},
        ],
    })


def route_request(payload: dict, stream: bool):
    last_err = None
    # keys we control explicitly; everything else passes through verbatim
    passthrough = {k: v for k, v in payload.items()
                   if k not in ("model", "messages", "stream")}
    for label, base_url, kwargs in _routes:
        client = make_client(base_url, kwargs)
        try:
            resp = client.chat.completions.create(
                model=payload.get("model"),
                messages=payload.get("messages"),
                stream=stream,
                **passthrough,
            )
            log.info("route=%s ok model=%s", label, payload.get("model"))
            return {"route": label, "resp": resp}

        except APIStatusError as e:
            code = e.status_code
            body_text = e.response.text or ""
            # Retry on explicit 429 rate limits,
            # OR on a 403 whose body is an HTML block page (Cloudflare 1010).
            # A 403 with JSON body is a real API rejection -> return as-is.
            is_block = (
                RETRY_HTML_403 and code == 403 and
                ("<html" in body_text.lower() or body_text.strip().startswith("<!DOCTYPE"))
            )
            if code in PROXY_RETRY_STATUSES or is_block:
                log.warning("route=%s HTTP %d%s -> rotating", label, code,
                            " (html block)" if is_block else "")
                last_err = e
                continue
            log.info("route=%s HTTP %d -> return as-is", label, code)
            return {"route": label, "status": code, "body": body_text,
                    "err": e}

        except APIConnectionError as e:
            log.warning("route=%s connection error -> rotating", label)
            last_err = e
            continue

        except Exception as e:  # unexpected
            log.error("route=%s unexpected %r", label, e)
            last_err = e
            continue

    # exhausted
    if isinstance(last_err, APIStatusError):
        try:
            return {"route": _direct_lbl, "status": last_err.status_code,
                    "body": last_err.response.text, "err": last_err}
        except Exception:
            return {"route": _direct_lbl, "status": 502, "body": "upstream error", "err": None}
    return {"route": _direct_lbl, "status": 502,
            "body": "all routes failed", "err": last_err}


@app.post("/v1/chat/completions")
async def chat(payload: dict, _req: Request):
    stream = bool(payload.get("stream", False))
    result = route_request(payload, stream)

    if result.get("resp") is not None:
        resp = result["resp"]  # OpenAI response or iterator
        if stream:
            def gen():
                for chunk in resp:
                    if chunk is not None:
                        yield f"data: {chunk.model_dump_json()}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(gen(), media_type="text/event-stream")
        return JSONResponse(resp.model_dump())

    # error
    status = result.get("status", 502)
    body = result.get("body", "all routes failed")
    if isinstance(body, str):
        try:
            import json
            body = json.loads(body)
        except Exception:
            body = {"error": {"message": body, "type": "upstream_error"}}
    return JSONResponse(body, status_code=status)