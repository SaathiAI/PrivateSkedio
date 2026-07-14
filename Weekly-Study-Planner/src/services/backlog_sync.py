"""
Chapter-Level Backlog Sync
Plan -> Day -> Session -> Content -> Chapter Backlog
"""

import logging
import time
from typing import List

logger = logging.getLogger(__name__)
commit_logger = logging.getLogger("skedioai.commit")


async def sync_chapter_backlog(
    user_id: str,
    neo4j=None,
) -> bool:
    """
    Sync chapter-level backlog from Session -> Content relationships.

    Flow:
    1. Find all Content connected to user Sessions
    2. Group by subject + chapter
    3. For each chapter:
       - completed subtopics = content where Session->Content status done
       - pending subtopics = content where Session->Content status pending
       - hours_actual = sum time_spent for done content
    4. Upsert to Pinecone (chapter namespace)

    Backlog entry:
    {
        "scope_reference_key": "mathematics|trigonometry",  # normalized lowercase
        "subject": "Mathematics",
        "chapter": "Trigonometry",
        "status": "IN_PROGRESS",
        "hours_actual": 0,
        "subtopics_completed": ["math_trig_sine_rule"],  # match_keys
        "subtopics_pending": ["math_trig_cosine_rule"]
    }
    """
    if neo4j is None:
        from src.database.neo4j import Neo4jManager

        neo4j = Neo4jManager()

    # Query: Find all Content from user's Sessions
    query = """
    MATCH (u:User {id: $user_id})-[:PERFORMED]->(s:Session)-[r:TARGETS_CONTENT]->(c:Content)
    WITH c, r,
        collect(DISTINCT s.session_id) AS session_ids,
        collect(DISTINCT CASE WHEN r.status = 'done' THEN c.match_key END) AS done_keys,
        collect(DISTINCT CASE WHEN r.status = 'pending' THEN c.match_key END) AS pending_keys,
        sum(CASE WHEN r.status = 'done' THEN r.time_spent ELSE 0 END) AS hrs
    RETURN
        c.subjects AS subjects,
        c.chapters AS chapters,
        session_ids,
        [x IN done_keys WHERE x IS NOT NULL] AS subtopics_completed,
        [x IN pending_keys WHERE x IS NOT NULL] AS subtopics_pending,
        hrs AS hours_actual
    """

    t = time.perf_counter()
    commit_logger.info(
        "step=backlog_sync_query status=start user_id=%s",
        user_id,
    )
    rows = neo4j.graph.query(query, {"user_id": user_id})
    query_duration = round(time.perf_counter() - t, 2)
    commit_logger.info(
        "step=backlog_sync_query status=success user_id=%s duration_s=%s row_count=%s",
        user_id,
        query_duration,
        len(rows),
    )

    # Group by chapter
    chapter_backlogs = {}

    for row in rows:
        subjects = row.get("subjects") or []
        chapters = row.get("chapters") or []
        sub_completed = row.get("subtopics_completed") or []
        sub_pending = row.get("subtopics_pending") or []
        hours = row.get("hours_actual") or 0

        # Normalize and create key for each subject+chapter combo
        for subj in subjects:
            for ch in chapters:
                # Normalize: lowercase
                key = f"{subj.lower().strip()}|{ch.lower().strip()}"

                if key not in chapter_backlogs:
                    chapter_backlogs[key] = {
                        "scope_reference_key": key,
                        "subject": subj,
                        "chapter": ch,
                        "subtopics_completed": set(),
                        "subtopics_pending": set(),
                        "hours_actual": 0,
                    }

                # Aggregate
                chapter_backlogs[key]["subtopics_completed"].update(sub_completed)
                chapter_backlogs[key]["subtopics_pending"].update(sub_pending)
                chapter_backlogs[key]["hours_actual"] += hours

    # Build final backlog list
    backlog_batch = []

    for key, data in chapter_backlogs.items():
        completed = list(data["subtopics_completed"])
        pending = list(data["subtopics_pending"])

        # This is backlog progress status, not Intake/Planner priority/confidence.
        if completed and not pending:
            status = "DONE"
        elif completed:
            status = "IN_PROGRESS"
        else:
            status = "NOT_STARTED"

        vector_data = {
            "user_id": user_id,
            "scope_reference_key": key,
            "subject": data["subject"],
            "chapter": data["chapter"],
            "status": status,
            "hours_actual": round(data["hours_actual"], 2),
            "subtopics_completed": completed,
            "subtopics_pending": pending,
        }

        backlog_batch.append((key, vector_data))

    commit_logger.info(
        "step=backlog_sync_batch status=prepared user_id=%s batch_size=%s",
        user_id,
        len(backlog_batch),
    )
    if backlog_batch:
        for key, data in backlog_batch[:3]:
            commit_logger.debug(
                "step=backlog_sync_batch_preview key=%s progress_status=%s completed=%s pending=%s",
                key,
                data.get("status"),
                data.get("subtopics_completed"),
                data.get("subtopics_pending"),
            )

    if not backlog_batch:
        commit_logger.warning(
            "step=backlog_sync_batch status=empty user_id=%s",
            user_id,
        )
        return True

    # Upsert to Pinecone
    from src.database.vector_store import BACKLOG_NAMESPACE, VectorStore

    vs = VectorStore()

    t = time.perf_counter()
    try:
        for key, data in backlog_batch:
            result = await vs.upsert(
                namespace=BACKLOG_NAMESPACE,
                key=key,
                data=data,
            )
            commit_logger.info(
                "step=backlog_sync_upsert status=success key=%s result=%s",
                key,
                result,
            )
        commit_logger.info(
            "step=backlog_sync status=success user_id=%s synced_chapters=%s duration_s=%s",
            user_id,
            len(backlog_batch),
            round(time.perf_counter() - t, 2),
        )
        return True
    except Exception as e:
        commit_logger.error(
            "step=backlog_sync status=failed user_id=%s error=%s",
            user_id,
            e,
        )
        return False


# Keep old function for backward compat during transition
async def sync_v1_backlog_for_tasks(
    user_id: str,
    task_match_keys: List[str],
    vector_store=None,
    neo4j=None,
) -> bool:
    """Legacy V1 function - redirects to V2 for now."""
    return await sync_chapter_backlog(user_id, neo4j)
