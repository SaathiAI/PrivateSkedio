#!/usr/bin/env python3
"""
Tiny check for the existing Gemini embedding path used by VectorStore.

Run:
  venv_linux313/bin/python -u scripts/test_existing_gemini_embedding.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


async def main() -> None:
    load_env()
    sys.path.insert(0, str(PROJECT_ROOT))

    from src.database.vector_store import VectorStore

    query = "Mathematics Class 10 CBSE"
    vs = VectorStore()

    print("[test] calling existing VectorStore.embed()", flush=True)
    print(f"[test] query: {query!r}", flush=True)

    started = time.perf_counter()
    try:
        vector = await asyncio.wait_for(vs.embed(query), timeout=30)
    except Exception as exc:
        elapsed = time.perf_counter() - started
        print(f"[test] FAILED after {elapsed:.2f}s", flush=True)
        print(f"[test] error type: {type(exc).__name__}", flush=True)
        print(f"[test] error repr: {exc!r}", flush=True)
        return

    elapsed = time.perf_counter() - started
    print(f"[test] OK after {elapsed:.2f}s", flush=True)
    print(f"[test] vector dimension: {len(vector)}", flush=True)
    print(f"[test] first 5 values: {vector[:5]}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
