#!/usr/bin/env python3
"""
Diagnose Gemini embedding failures without changing app behavior.

Checks the same API key through:
1. DNS resolution
2. Direct REST embedContent
3. LangChain sync embed_query
4. LangChain async aembed_query
5. Existing VectorStore.embed

Run:
  venv_linux313/bin/python -u scripts/diagnose_gemini_embedding_path.py
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL = "models/gemini-embedding-001"
TEXT = "Mathematics Class 10 CBSE"
HOST = "generativelanguage.googleapis.com"


def log(message: str = "") -> None:
    print(message, flush=True)


def load_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def mask(value: str | None) -> str:
    if not value:
        return "MISSING"
    return f"{value[:6]}...{value[-4:]}" if len(value) > 12 else "SET"


def timed(label: str, fn):
    log(f"\n[{label}] start")
    started = time.perf_counter()
    try:
        result = fn()
    except Exception as exc:
        elapsed = time.perf_counter() - started
        log(f"[{label}] FAILED after {elapsed:.2f}s")
        log(f"[{label}] type={type(exc).__name__}")
        log(f"[{label}] repr={exc!r}")
        return None
    elapsed = time.perf_counter() - started
    log(f"[{label}] OK after {elapsed:.2f}s")
    return result


async def timed_async(label: str, coro, timeout: float = 30):
    log(f"\n[{label}] start")
    started = time.perf_counter()
    try:
        result = await asyncio.wait_for(coro, timeout=timeout)
    except Exception as exc:
        elapsed = time.perf_counter() - started
        log(f"[{label}] FAILED after {elapsed:.2f}s")
        log(f"[{label}] type={type(exc).__name__}")
        log(f"[{label}] repr={exc!r}")
        return None
    elapsed = time.perf_counter() - started
    log(f"[{label}] OK after {elapsed:.2f}s")
    return result


def check_dns() -> None:
    infos = socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)
    ips = sorted({item[4][0] for item in infos})
    log(f"[dns] host={HOST}")
    log(f"[dns] ips={ips[:6]}")


def direct_rest_embed() -> list[float]:
    api_key = os.getenv("GOOGLE_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/{MODEL}:embedContent?key={api_key}"
    payload = {
        "model": MODEL,
        "content": {"parts": [{"text": TEXT}]},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc

    return data.get("embedding", {}).get("values", [])


def summarize_vector(label: str, vector: list[float] | None) -> None:
    if vector is None:
        return
    log(f"[{label}] dim={len(vector)} first3={vector[:3]}")


async def main() -> None:
    load_env()
    sys.path.insert(0, str(PROJECT_ROOT))

    log("[config]")
    log(f"GOOGLE_API_KEY={mask(os.getenv('GOOGLE_API_KEY'))}")
    log(f"MODEL={MODEL}")
    log(f"TEXT={TEXT!r}")
    log(f"HTTP_PROXY={os.getenv('HTTP_PROXY')}")
    log(f"HTTPS_PROXY={os.getenv('HTTPS_PROXY')}")
    log(f"NO_PROXY={os.getenv('NO_PROXY')}")

    import langchain_google_genai
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    from src.database.vector_store import VectorStore

    log("\n[versions]")
    log(f"langchain_google_genai={getattr(langchain_google_genai, '__version__', 'unknown')}")

    timed("dns", check_dns)

    rest_vector = timed("direct-rest", direct_rest_embed)
    summarize_vector("direct-rest", rest_vector)

    embeddings = GoogleGenerativeAIEmbeddings(model=MODEL)

    sync_vector = timed("langchain-sync", lambda: embeddings.embed_query(TEXT))
    summarize_vector("langchain-sync", sync_vector)

    async_vector = await timed_async(
        "langchain-async",
        embeddings.aembed_query(TEXT),
        timeout=30,
    )
    summarize_vector("langchain-async", async_vector)

    vs = VectorStore()
    vector_store_vector = await timed_async(
        "vectorstore-embed",
        vs.embed(TEXT),
        timeout=30,
    )
    summarize_vector("vectorstore-embed", vector_store_vector)

    log("\n[repeat async x3]")
    for i in range(3):
        vector = await timed_async(
            f"langchain-async-repeat-{i + 1}",
            embeddings.aembed_query(TEXT),
            timeout=30,
        )
        summarize_vector(f"langchain-async-repeat-{i + 1}", vector)


if __name__ == "__main__":
    asyncio.run(main())
