"""
CBSE Syllabus System Tests
===========================
Tests for new 3-tool system: verify_syllabus, get_chapter_details, verify_and_act

Run with:
    python -m src.syllabus.test_syllabus
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Timer:
    """Context manager for timing operations."""

    def __init__(self, name: str):
        self.name = name
        self.start = 0.0
        self.elapsed = 0.0

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed = time.perf_counter() - self.start
        print(f"  [TIME] {self.name}: {self.elapsed:.2f}s")


async def test_seed_check():
    """Test 1: Check if Pinecone is seeded."""
    print("\n" + "=" * 60)
    print("TEST 1 — Seed Check")
    print("=" * 60)

    from src.database.vector_store import VectorStore
    from src.syllabus.updater import run_full_update

    with Timer("Check seed status"):
        vs = VectorStore()
        seeded = await vs.syllabus_is_seeded()

    print(f"  Seeded: {seeded}")

    if not seeded:
        print("  WARNING: Not seeded - running seed for Mathematics & Science...")
        with Timer("Seed Mathematics"):
            await run_full_update(["Mathematics"])
        with Timer("Seed Science"):
            await run_full_update(["Science"])
        seeded = await vs.syllabus_is_seeded()
        print(f"  Seeded after update: {seeded}")

    return seeded


async def test_verify_syllabus():
    """Test 2: Verify syllabus tool."""
    print("\n" + "=" * 60)
    print("TEST 2 — verify_syllabus")
    print("=" * 60)

    from src.syllabus.tools import verify_syllabus

    queries = [
        "Polynomials in Class 10 Math",
        "Light in CBSE Science",
        "Quadratic Equations CBSE Mathematics",
    ]

    for q in queries:
        print(f"\n  Query: {q}")
        with Timer(f"Verify '{q[:30]}...'"):
            result = await verify_syllabus.ainvoke({"query": q})

        print(f"    Exists: {result.get('exists')}")
        print(f"    Topic Key: {result.get('topic_key')}")
        print(f"    Subject: {result.get('subject')}")
        print(f"    Chapter: {result.get('chapter_name')}")
        print(f"    Status: {result.get('chapter_status')}")
        print(f"    Confidence: {result.get('confidence')}")
        print(f"    Source: {result.get('source')}")

        active = result.get("active_topics", [])
        if active:
            print(f"    Active Topics: {', '.join(active[:3])}...")


async def test_get_chapter_details():
    """Test 3: Get chapter details tool."""
    print("\n" + "=" * 60)
    print("TEST 3 — get_chapter_details")
    print("=" * 60)

    from src.syllabus.tools import get_chapter_details

    # Test: specific chapter
    print("\n  Test A: Specific chapter")
    with Timer("Get Polynomials details"):
        result = await get_chapter_details.ainvoke(
            {"subject": "Mathematics", "chapter": "Polynomials"}
        )

    print(f"  Found: {result.get('found')}")
    if result.get("chapters"):
        ch = result["chapters"][0]
        print(f"  Chapter: {ch.get('chapter_name')}")
        print(f"  Subject: {ch.get('subject')}")
        print(f"  Status: {ch.get('status')}")
        print(f"  Weightage: {ch.get('weightage_marks')} marks")

        topics = ch.get("topics", [])
        print(f"  Topics ({len(topics)}): {', '.join(topics[:5])}")

        removed = ch.get("removed_topics", [])
        if removed:
            print(f"  Removed: {', '.join(removed)}")

    # Test: all chapters for subject
    print("\n  Test B: All chapters for Science")
    with Timer("Get Science chapters"):
        result = await get_chapter_details.ainvoke({"subject": "Science"})

    print(f"  Found: {result.get('found')}")
    if result.get("chapters"):
        print(f"  Chapters count: {len(result['chapters'])}")
        for ch in result["chapters"][:3]:
            print(f"    - {ch.get('chapter_name')} ({ch.get('status')})")


async def test_verify_and_act():
    """Test 4: Self-correction tool."""
    print("\n" + "=" * 60)
    print("TEST 4 — verify_and_act")
    print("=" * 60)

    from src.syllabus.tools import verify_and_act

    print("\n  Test A: User claims chapter is back")
    with Timer("Verify claim (back)"):
        result = await verify_and_act.ainvoke(
            {
                "subject": "Mathematics",
                "chapter": "Linear Equations",
                "user_claim": "is back in 2025-26 syllabus",
            }
        )

    print(f"  Confirmed: {result.get('confirmed')}")
    print(f"  Corrected: {result.get('corrected')}")
    print(f"  Message: {result.get('message')}")

    print("\n  Test B: User claims chapter removed")
    with Timer("Verify claim (removed)"):
        result = await verify_and_act.ainvoke(
            {
                "subject": "Science",
                "chapter": "Light",
                "user_claim": "was removed from 2025-26 syllabus",
            }
        )

    print(f"  Confirmed: {result.get('confirmed')}")
    print(f"  Corrected: {result.get('corrected')}")
    print(f"  Message: {result.get('message')}")


async def test_verify_syllabus_not_exists():
    """Test 5: Query that doesn't exist."""
    print("\n" + "=" * 60)
    print("TEST 5 — verify_syllabus (not exists)")
    print("=" * 60)

    from src.syllabus.tools import verify_syllabus

    query = "quantum computing class 10 cbse"

    print(f"  Query: {query}")
    with Timer("Verify non-existent"):
        result = await verify_syllabus.ainvoke({"query": query})

    print(f"  Exists: {result.get('exists')}")
    print(f"  Error: {result.get('error')}")
    print(f"  Message: {result.get('message')}")


async def test_get_chapter_no_params():
    """Test 6: Edge case - missing params."""
    print("\n" + "=" * 60)
    print("TEST 6 — get_chapter_details (edge cases)")
    print("=" * 60)

    from src.syllabus.tools import get_chapter_details

    # No params
    print("\n  Test A: No parameters")
    result = await get_chapter_details.ainvoke({})
    print(f"  Found: {result.get('found')}")
    print(f"  Error: {result.get('error')}")


async def test_vector_structure():
    """Test 7: Verify vector structure in Pinecone."""
    print("\n" + "=" * 60)
    print("TEST 7 — Vector Structure Check")
    print("=" * 60)

    from src.database.vector_store import VectorStore

    vs = VectorStore()

    with Timer("Search for structure check"):
        results = await vs.search_syllabus("Polynomials", top_k=1)

    if results:
        result = results[0]
        print("  Vector fields:")
        print(f"    topic_key: {result.get('topic_key')}")
        print(f"    subject: {result.get('subject')}")
        print(f"    chapter_name: {result.get('chapter_name')}")
        print(f"    chapter_status: {result.get('chapter_status')}")
        print(f"    chapter_weightage_marks: {result.get('chapter_weightage_marks')}")
        print(f"    last_updated: {result.get('last_updated')}")

        try:
            active = json.loads(result.get("active_topics", "[]"))
            print(f"    active_topics: {active[:3]}...")
        except:
            print(f"    active_topics: (not parseable)")
    else:
        print("  No results - may need seeding")


async def run_all_tests():
    """Run all tests with timing."""
    print("\n" + "=" * 30)
    print("CBSE SYLLABUS TOOLS TEST SUITE")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 30)

    overall_start = time.perf_counter()

    try:
        await test_seed_check()
        await test_verify_syllabus()
        await test_get_chapter_details()
        await test_verify_and_act()
        await test_verify_syllabus_not_exists()
        await test_get_chapter_no_params()
        await test_vector_structure()

        overall_elapsed = time.perf_counter() - overall_start

        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETE")
        print(f"Total Time: {overall_elapsed:.2f}s")
        print("=" * 60)

    except Exception as e:
        import traceback

        print(f"\nTest failed: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_tests())
