"""
Clear Syllabus Namespace
=======================
Run: python -m src.syllabus.clear_syllabus

WARNING: This deletes ALL syllabus vectors from Pinecone!
"""

import asyncio
from dotenv import load_dotenv

load_dotenv()


async def clear_syllabus():
    from pinecone import Pinecone
    import os

    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

    # Get index name from your vector_store
    index_name = "saathi-class-10"  # Change if different

    # Delete all vectors in syllabus namespace
    index = pc.Index(index_name)

    print("Deleting all vectors in 'syllabus' namespace...")

    # Delete all vectors in namespace
    index.delete(delete_all=True, namespace="context")
    index.delete(delete_all=True, namespace="episodic")
    from src.database.vector_store import BACKLOG_NAMESPACE

    index.delete(delete_all=True, namespace=BACKLOG_NAMESPACE)

    print("All syllabus vectors deleted!")

    # Verify
    stats = index.describe_index_stats()
    print(f"Total vectors in index: {stats.total_vector_count}")
    print(f"Namespaces: {stats.namespaces}")


if __name__ == "__main__":
    asyncio.run(clear_syllabus())
