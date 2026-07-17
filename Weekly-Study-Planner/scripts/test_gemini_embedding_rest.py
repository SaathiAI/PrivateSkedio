#!/usr/bin/env python3
"""
Tiny direct Gemini embedding REST test.

This does not use LangChain. It reads GOOGLE_API_KEY from .env, calls
gemini-embedding-001:embedContent, and prints a small summary.

Run:
  venv_linux313/bin/python scripts/test_gemini_embedding_rest.py
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL = "models/gemini-embedding-001"
TEXT = "Mathematics Class 10 CBSE"


def load_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def main() -> None:
    load_env()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("FAILED: GOOGLE_API_KEY missing")
        return

    url = f"https://generativelanguage.googleapis.com/v1beta/{MODEL}:embedContent?key={api_key}"
    payload = {
        "model": MODEL,
        "content": {
            "parts": [
                {"text": TEXT},
            ]
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    print(f"Embedding text: {TEXT!r}")
    print(f"Model: {MODEL}")
    started = time.perf_counter()

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = response.status
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"FAILED HTTP {exc.code}")
        print(exc.read().decode("utf-8")[:1000])
        return
    except Exception as exc:
        print(f"FAILED {type(exc).__name__}: {exc!r}")
        return

    elapsed = time.perf_counter() - started
    values = data.get("embedding", {}).get("values", [])

    print(f"HTTP: {status}")
    print(f"Time: {elapsed:.2f}s")
    print(f"Dimension: {len(values)}")
    print(f"First 8 values: {values[:8]}")


if __name__ == "__main__":
    main()
