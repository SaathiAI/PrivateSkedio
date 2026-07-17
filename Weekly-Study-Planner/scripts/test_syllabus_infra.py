#!/usr/bin/env python3
"""
Temporary syllabus infra diagnostic.

Checks:
1. .env loading
2. Gemini embedding call
3. Pinecone index connection for saathi-class-10
4. Pinecone syllabus namespace query using the Gemini vector

Run:
  venv_linux313/bin/python scripts/test_syllabus_infra.py
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
CORRECT_INDEX_NAME = "saathi-class-10"
EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIM = 3072


def log(message: str = "") -> None:
    print(message, flush=True)


def load_env() -> None:
    if not ENV_PATH.exists():
        log(f"[env] missing: {ENV_PATH}")
        return

    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

    log(f"[env] loaded: {ENV_PATH}")


def mask(value: str | None) -> str:
    if not value:
        return "MISSING"
    if len(value) <= 10:
        return "SET"
    return f"{value[:6]}...{value[-4:]}"


async def test_gemini_embedding(query: str) -> list[float] | None:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    log("\n[gemini] testing embedding")
    log(f"[gemini] model: {EMBEDDING_MODEL}")
    log(f"[gemini] query: {query!r}")

    started = time.perf_counter()
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)
        vector = await asyncio.wait_for(embeddings.aembed_query(query), timeout=20)
    except Exception as exc:
        elapsed = time.perf_counter() - started
        log(f"[gemini] FAILED after {elapsed:.2f}s")
        log(f"[gemini] error type: {type(exc).__name__}")
        log(f"[gemini] error repr: {exc!r}")
        return None

    elapsed = time.perf_counter() - started
    log(f"[gemini] OK after {elapsed:.2f}s")
    log(f"[gemini] vector dim: {len(vector)}")
    log(f"[gemini] expected dim: {EMBEDDING_DIM}")
    return vector


async def test_pinecone(vector: list[float]) -> None:
    from pinecone import Pinecone

    log("\n[pinecone] testing index")
    log(f"[pinecone] correct index: {CORRECT_INDEX_NAME}")
    log(f"[pinecone] .env PINECONE_INDEX_NAME: {os.getenv('PINECONE_INDEX_NAME')}")

    started = time.perf_counter()
    try:
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        index_names = [idx["name"] for idx in pc.list_indexes()]
        elapsed = time.perf_counter() - started
        log(f"[pinecone] list_indexes OK after {elapsed:.2f}s")
        log(f"[pinecone] indexes: {index_names}")

        if CORRECT_INDEX_NAME not in index_names:
            log(f"[pinecone] FAILED: {CORRECT_INDEX_NAME!r} not found")
            return

        index = pc.Index(CORRECT_INDEX_NAME)
        query_started = time.perf_counter()
        result = await asyncio.wait_for(
            asyncio.to_thread(
                index.query,
                vector=vector,
                top_k=5,
                namespace="syllabus",
                include_metadata=True,
            ),
            timeout=20,
        )
    except Exception as exc:
        elapsed = time.perf_counter() - started
        log(f"[pinecone] FAILED after {elapsed:.2f}s")
        log(f"[pinecone] error type: {type(exc).__name__}")
        log(f"[pinecone] error repr: {exc!r}")
        return

    query_elapsed = time.perf_counter() - query_started
    matches = getattr(result, "matches", []) or []
    log(f"[pinecone] query OK after {query_elapsed:.2f}s")
    log(f"[pinecone] syllabus matches: {len(matches)}")

    for i, match in enumerate(matches[:3], start=1):
        metadata = getattr(match, "metadata", {}) or {}
        log(
            f"[pinecone] match {i}: score={getattr(match, 'score', None)} "
            f"subject={metadata.get('subject')} chapter={metadata.get('chapter') or metadata.get('chapter_name')} "
            f"topic_key={metadata.get('topic_key')}"
        )


async def main() -> None:
    load_env()

    log("\n[config] key status")
    log(f"[config] GOOGLE_API_KEY: {mask(os.getenv('GOOGLE_API_KEY'))}")
    log(f"[config] PINECONE_API_KEY: {mask(os.getenv('PINECONE_API_KEY'))}")
    log(f"[config] PINECONE_INDEX_NAME: {os.getenv('PINECONE_INDEX_NAME')}")
    if os.getenv("PINECONE_INDEX_NAME") != CORRECT_INDEX_NAME:
        log(
            "[config] NOTE: .env index differs from the known correct index. "
            f"This diagnostic will still use {CORRECT_INDEX_NAME!r}."
        )

    query = "Mathematics Class 10 CBSE"
    vector = await test_gemini_embedding(query)
    if vector is None:
        log("\n[result] STOP: Gemini embedding failed, so syllabus search cannot reach Pinecone.")
        return

    await test_pinecone(vector)
    log("\n[result] done")


if __name__ == "__main__":
    asyncio.run(main())
