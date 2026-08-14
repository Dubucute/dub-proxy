#!/usr/bin/env python3
"""Test all models with a simple 'hi' message without an API key."""

from openai import OpenAI

BASE_URL = "http://localhost:8000/v1"
MODELS = [
    "big-pickle",
    "mimo-v2.5-free",
    "deepseek-v4-flash-free",
    "hy3-free",
    "nemotron-3-ultra-free",
    "north-mini-code-free",
]

client = OpenAI(
    api_key="none",  # proxy ignores this
    base_url=BASE_URL,
)

for model in MODELS:
    print(f"\n{'='*60}")
    print(f"Testing model: {model}")
    print(f"{'='*60}")
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=50,
        )
        content = resp.choices[0].message.content
        print(f"OK: {content[:200]}")
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")
