"""
V1 Test Data Cleanup
Removes all test data created for V1 testing
"""

from src.database.neo4j import Neo4jManager
from src.database.vector_store import VectorStore
import asyncio

TEST_USER = "test_v1_001"
TEST_PLAN = "test_plan_001"


def cleanup_test_data():
    neo = Neo4jManager()
    vs = VectorStore()

    print("=" * 60)
    print("V1 TEST DATA CLEANUP")
    print("=" * 60)

    # 1. Delete Sessions
    print("\n[1] Deleting Sessions...")
    neo.graph.query("""
        MATCH (s:Session)
        WHERE s.session_id CONTAINS 'test_v1_001'
        DETACH DELETE s
    """)
    print("    [OK] Sessions deleted")

    # 2. Delete Tasks
    print("\n[2] Deleting Tasks...")
    neo.graph.query(
        """
        MATCH (t:Task)
        WHERE t.user_id = $uid
        DETACH DELETE t
    """,
        {"uid": TEST_USER},
    )
    print("    [OK] Tasks deleted")

    # 3. Delete Days
    print("\n[3] Deleting Days...")
    neo.graph.query(
        """
        MATCH (p:Plan {plan_id: $pid})-[r:HAS_DAY]->(d:Day)
        DELETE r, d
    """,
        {"pid": TEST_PLAN},
    )
    print("    [OK] Days deleted")

    # 4. Delete Plan
    print("\n[4] Deleting Plan...")
    neo.graph.query(
        """
        MATCH (p:Plan {plan_id: $pid})
        DETACH DELETE p
    """,
        {"pid": TEST_PLAN},
    )
    print("    [OK] Plan deleted")

    # 5. Delete User
    print("\n[5] Deleting User...")
    neo.graph.query(
        """
        MATCH (u:User {id: $uid})
        DETACH DELETE u
    """,
        {"uid": TEST_USER},
    )
    print("    [OK] User deleted")

    # 6. Delete Test Content nodes (only the ones we created)
    print("\n[6] Deleting Test Content nodes...")
    content_to_delete = [
        "maths_trig_sine_rule",
        "maths_trig_cos_rule",
        "maths_trig_tan_rule",
        "maths_quadratic_formula",
        "science_light_reflection",
    ]
    for key in content_to_delete:
        neo.graph.query(
            """
            MATCH (c:Content {match_key: $key})
            DETACH DELETE c
        """,
            {"key": key},
        )
    print("    [OK] Content nodes deleted")

    # 7. Clean Pinecone backlog entries
    print("\n[7] Cleaning Pinecone backlog...")

    # Delete test backlog entries
    async def delete_pinecone():
        from src.database.vector_store import BACKLOG_NAMESPACE, EMBEDDING_DIM

        index = vs._get_index()
        # Query all backlog for test user
        results = index.query(
            vector=[0] * EMBEDDING_DIM,
            top_k=100,
            namespace=BACKLOG_NAMESPACE,
            filter={"user_id": {"$eq": TEST_USER}},
            include_metadata=True,
        )
        print(f"    Found {len(results.matches)} backlog entries for {TEST_USER}")

        # Delete them
        for m in results.matches:
            if m.id:
                try:
                    index.delete(ids=[m.id], namespace=BACKLOG_NAMESPACE)
                    print(f"    Deleted: {m.metadata.get('match_key')}")
                except:
                    pass

    asyncio.run(delete_pinecone())
    print("    [OK] Pinecone cleaned")

    print("\n" + "=" * 60)
    print("CLEANUP COMPLETE!")
    print("=" * 60)

    # Verify
    result = neo.graph.query(
        "MATCH (n) WHERE n.user_id = $uid RETURN count(n)", {"uid": TEST_USER}
    )
    print(f"\n[VERIFY] Remaining nodes: {result[0]['count(n)']}")

    return True


if __name__ == "__main__":
    cleanup_test_data()
