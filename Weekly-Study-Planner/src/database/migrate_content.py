"""
Migrate Content Nodes - Convert to PLURAL lists (subjects, chapters)
=======================================================
Run: python -m src.database.migrate_content

WARNING: This converts existing Content nodes!
OLD: c.subject (string) → NEW: c.subjects (list)
OLD: c.chapter (string) → NEW: c.chapters (list)
"""

from src.database.neo4j import Neo4jManager


def migrate_content():
    neo = Neo4jManager()

    print("=" * 60)
    print("MIGRATING TO PLURAL (subjects, chapters)")
    print("=" * 60)

    query = """
    MATCH (c:Content)
    RETURN c.match_key AS match_key, c.subject AS subject, c.chapter AS chapter
    """
    results = neo.graph.query(query)

    if not results:
        print("No Content nodes found!")
        return

    print(f"\nFound {len(results)} Content nodes")

    migrated = 0

    for row in results:
        match_key = row["match_key"]
        subject = row.get("subject")
        chapter = row.get("chapter")

        # Convert: string → list (plural)
        new_subjects = []
        new_chapters = []

        if isinstance(subject, str) and subject:
            new_subjects = [subject]
        elif isinstance(subject, list):
            new_subjects = subject

        if isinstance(chapter, str) and chapter:
            new_chapters = [chapter]
        elif isinstance(chapter, list):
            new_chapters = chapter

        # Update with PLURAL field names
        neo.graph.query(
            """
            MATCH (c:Content {match_key: $mk})
            SET c.subjects = $subjects, c.chapters = $chapters
        """,
            {"mk": match_key, "subjects": new_subjects, "chapters": new_chapters},
        )

        migrated += 1
        print(f"  {match_key}: {new_subjects}, {new_chapters}")

    print(f"\nDONE! Migrated: {migrated}")

    # Verify
    v = neo.graph.query("MATCH (c:Content) RETURN c.subjects, c.chapters LIMIT 3")
    print("\nSample:", v)


if __name__ == "__main__":
    migrate_content()
