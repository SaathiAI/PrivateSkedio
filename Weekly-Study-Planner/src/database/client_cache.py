"""
Singleton clients for performance optimization.
Reuses LLM and embedding clients across all requests.
"""

import os
from functools import lru_cache
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv

load_dotenv()
# ─────────────────────────────────────────────
# ChatOpenAI Cache (LRU by model+temp)
# ─────────────────────────────────────────────

_llm_cache = {}

os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGCHAIN_PROJECT", "skedioai-final-eval-v1")
for _env_key in ("PINECONE_API_KEY", "GOOGLE_API_KEY"):
    _env_val = os.getenv(_env_key)
    if _env_val:
        os.environ[_env_key] = _env_val


def get_llm(
    model: str = "gpt-5-mini",
    temperature: float = 0,
    reasoning_effort: Optional[str] = None,
) -> ChatOpenAI:
    """Get cached ChatOpenAI client - avoids recreating each call."""
    key = f"{model}:{temperature}:{reasoning_effort or 'default'}"
    if key not in _llm_cache:
        client_kwargs = {
            "model": model,
            "temperature": temperature,
            "api_key": os.getenv("OPENAI_API_KEY"),
        }
        if reasoning_effort is not None:
            client_kwargs["reasoning_effort"] = reasoning_effort

        _llm_cache[key] = ChatOpenAI(
            **client_kwargs,
        )
    return _llm_cache[key]


# ─────────────────────────────────────────────
# Google Embeddings Singleton
# ─────────────────────────────────────────────

_embedding_client = None


def get_embedding_client() -> GoogleGenerativeAIEmbeddings:
    """Get cached Google embeddings client."""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = GoogleGenerativeAIEmbeddings(
            model="gemini-embedding-001",
        )
    return _embedding_client


# ─────────────────────────────────────────────
# Clear cache (for testing)
# ─────────────────────────────────────────────


def clear_llm_cache():
    """Clear LLM cache - mainly for testing."""
    global _llm_cache
    _llm_cache.clear()


def clear_embedding_client():
    """Clear embedding client - mainly for testing."""
    global _embedding_client
    _embedding_client = None


# ─────────────────────────────────────────────
# Health check for Gemini embedding
# ───────────────────────────────────────────── 


def check_gemini_health() -> dict:
    """Check if Gemini API and embedding are working."""
    try:
        client = get_embedding_client()
        test_text = "health check test"
        result = client.embed_query(test_text)

        if result and len(result) > 0:
            return {
                "status": "healthy",
                "result": result,
                "embedding_dimension": len(result),
                "message": "Gemini embedding API is working",
            }
        else:
            return {"status": "unhealthy", "message": "Empty embedding returned"}
    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}


from langchain_core.tools import tool
from src.database.vector_store import VectorStore


@tool
async def get_syllabus(subject: str) -> str:
    """Get all chapters for a given subject from CBSE syllabus."""
    vs = VectorStore()
    result = await vs.vector_filter(subject=subject)
    return result


async def quick_fetch(
    namespace: str = "syllabus", top_k: int = 3, timeout: float = 5.0
):
    """Simple query to fetch from vector DB."""
    import asyncio
    from pinecone import Pinecone

    async def _fetch():
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        index = pc.Index("final")
        return index.query(
            vector=[0.0] * 3072, top_k=top_k, namespace=namespace, include_metadata=True
        )

    try:
        return await asyncio.wait_for(_fetch(), timeout=timeout)
    except asyncio.TimeoutError:
        return {"error": f"Query timed out after {timeout}s"}

async def embed(text: str) -> list[float]:
    """Embed text using Gemini embedding-001 (3072 dim) - cached client."""
    from src.database.client_cache import get_embedding_client

    embeddings = get_embedding_client()
    return await embeddings.aembed_query(text.strip())




    

    
