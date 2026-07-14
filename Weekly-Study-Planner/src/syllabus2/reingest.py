"""
Syllabus Re-Ingest
==================
One-shot: Delete all syllabus + Re-fetch + Re-ingest

Run:
    python -m src.syllabus2.reingest              # All subjects
    python -m src.syllabus2.reingest --check      # Check current state
    python -m src.syllabus2.reingest Mathematics Science  # Specific subjects
"""

import asyncio
import argparse
import logging
from datetime import datetime
from typing import List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ACADEMIC_YEAR = "2025-26"

SUBJECTS = [
    "Mathematics",
    "Science",
    "English",
    "Social Science",
    "Hindi",
    "Sanskrit",
]


async def reingest_syllabus(subjects: Optional[List[str]] = None) -> dict:
    """
    ONE-SHOT: Clear + Fetch + Ingest CBSE syllabus.

    Args:
        subjects: List of subjects to update (default: all 6)
    """
    from src.syllabus.clear_syllabus import clear_syllabus
    from src.syllabus.updater import run_full_update

    print("\n🗑️  Clearing syllabus...")
    await clear_syllabus()

    print("🌐 Fetching from web...")
    results = await run_full_update(subjects)

    print("\n✅ Done!")
    return results


async def check_state():
    """Check what's currently in syllabus."""
    from src.database.vector_store import VectorStore

    vs = VectorStore()
    seeded = await vs.syllabus_is_seeded()

    print(f"\n📊 Syllabus seeded: {'✅ Yes' if seeded else '❌ No'}")

    for subject in SUBJECTS:
        results = await vs.search_syllabus(f"CBSE Class 10 {subject}", top_k=5)
        print(f"  {subject}: {len(results)} entries")

    return seeded


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("subjects", nargs="*")
    args = parser.parse_args()

    if args.check:
        asyncio.run(check_state())
    else:
        subjects = args.subjects if args.subjects else None
        asyncio.run(reingest_syllabus(subjects))
