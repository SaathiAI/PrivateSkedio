"""Neo4j persistence layer for SkedioAI's structured study state.

This file is the source-of-truth database wrapper for things that must remain
structurally consistent:
- users (identity, grade, board)
- plans (schedule root, days, sessions)
- content (learning units linked to sessions)

Graph shape:
    (User)-[:HAS_PLAN]->(Plan)-[:HAS_DAY]->(Day)-[:HAS_SESSION]->(Session)
    (Session)-[:TARGETS_CONTENT]->(Content)
    (User)-[:PERFORMED]->(Session)

Mental model:
- Neo4j stores the durable graph truth that the product operates on.
- Agent layers read/write through this manager, not raw Cypher.
- Vector memory (Pinecone) is downstream of Neo4j, never the source of truth.
"""

from langchain_neo4j import Neo4jGraph
import os
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import logging

load_dotenv()
logger = logging.getLogger(__name__)


class Neo4jManager:
    """Singleton gateway to the Neo4j graph.

    Provides the authoritative API for structured study data. All graph
    reads and writes go through this class to maintain consistency.
    """

    instance = None

    def __new__(cls):
        # Singleton pattern — one connection shared across the process.
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self):
        # Guard against re-initialization (singleton).
        if getattr(self, "_initialized", False):
            return
        load_dotenv()
        self.graph = Neo4jGraph(
            url=os.getenv("NEO4J_URI"),
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD"),
            database=os.getenv("NEO4J_DATABASE") or "neo4j",
        )
        self._initialized = True

    # ─────────────────────────────────────────────
    # USER
    # ─────────────────────────────────────────────
    # Users are the identity root. Every plan, session, and task
    # traces back to a User node via relationship paths.

    def create_user(self, user_id: str):
        """Idempotent user creation. MERGE ensures no duplicates."""
        query = """
        MERGE (u:User {id: $user_id})
        ON CREATE SET
            u.name = null,
            u.grade = '10',
            u.board = 'CBSE',
            u.created_at = datetime()
        RETURN u
        """
        result = self.graph.query(query, params={"user_id": user_id})
        return result[0] if result else None

    def get_user_model(self, user_id: str):
        """Fetch the user's profile fields (name, grade, board)."""
        query = """
        MATCH (u:User {id: $user_id})
        RETURN
            u.name AS name,
            u.grade AS grade,
            u.board AS board,
            u.created_at AS created_at
        """
        result = self.graph.query(query, params={"user_id": user_id})
        return result[0] if result else None

    # ─────────────────────────────────────────────
    # PLAN
    # ─────────────────────────────────────────────
    # Plans are the schedule root. A plan owns days, which own sessions.
    # Only one plan should be ACTIVE per user at a time.

    def create_plan(
        self,
        user_id: str,
        plan_id: str,
        plan_name: str,
        start_date: str,
        planned_end_date: str,
        estimated_duration: int,
        total_hours: float,
        study_items: List[str] = None,
        work_item_targets: Dict[str, float] = None,
        work_item_hours_spent: Dict[str, float] = None,
        intake_snapshot: Dict[str, Any] = None,
        availability_math: Dict[str, Any] = None,
        source: str = "planner",
    ) -> Dict[str, Any]:
        """Create a plan root node and attach it to the user.

        The planner may generate many drafts in memory; only committed
        plans should end up here. JSON-serializes dict/list params
        because Neo4j properties are flat.
        """
        query = """
        MATCH (u:User {id: $user_id})
        MERGE (p:Plan {plan_id: $plan_id})
        ON CREATE SET
            p.plan_name =          $plan_name,
            p.status =             'ACTIVE',
            p.start_date =         date($start_date),
            p.planned_end_date =   date($planned_end_date),
            p.actual_end_date =    null,
            p.estimated_duration = $estimated_duration,
            p.total_hours =        $total_hours,
            p.study_items =         $study_items,
            p.work_item_targets =  $work_item_targets,
            p.work_item_hours_spent = $work_item_hours_spent,
            p.intake_snapshot =    $intake_snapshot,
            p.availability_math =  $availability_math,
            p.source =             $source,
            p.created_at =         datetime()
        MERGE (u)-[:HAS_PLAN]->(p)
        RETURN
            p.plan_id           AS plan_id,
            p.plan_name         AS plan_name,
            p.status            AS status,
            p.start_date        AS start_date,
            p.planned_end_date  AS planned_end_date,
            p.estimated_duration AS estimated_duration,
            p.total_hours       AS total_hours,
            p.study_items        AS study_items
        """
        result = self.graph.query(
            query,
            params={
                "user_id": user_id,
                "plan_id": plan_id,
                "plan_name": plan_name,
                "start_date": start_date,
                "planned_end_date": planned_end_date,
                "estimated_duration": estimated_duration,
                "total_hours": total_hours,
                "study_items": study_items or [],
                "work_item_targets": json.dumps(work_item_targets or {}),
                "work_item_hours_spent": json.dumps(work_item_hours_spent or {}),
                "intake_snapshot": json.dumps(intake_snapshot or {}),
                "availability_math": json.dumps(availability_math or {}),
                "source": source,
            },
        )
        return result[0] if result else {}

    def append_to_change_log(self, user_id: str, entry: str) -> bool:
        """Append a timestamped entry to the user's change log array.

        Used to track plan lifecycle events like creation, rescheduling,
        and archival.
        """
        query = """
        MATCH (u:User {id: $user_id})
        SET u.change_log = coalesce(u.change_log, []) + [$entry]
        RETURN u.id AS user_id
        """
        result = self.graph.query(query, params={"user_id": user_id, "entry": entry})
        return bool(result)

    def get_plan_by_id(self, user_id: str, plan_id: str):
        """Fetch one historical plan in the V2 Session shape."""

        query = """
        MATCH (u:User {id: $user_id})-[:HAS_PLAN]->(p:Plan {plan_id: $plan_id})
        MATCH (p)-[:HAS_DAY]->(d:Day)
        OPTIONAL MATCH (d)-[:HAS_SESSION]->(s:Session)
        OPTIONAL MATCH (s)-[r:TARGETS_CONTENT]->(c:Content)

        WITH p, d, s,
            collect(DISTINCT CASE WHEN c IS NOT NULL THEN {
                match_key: c.match_key,
                canonical_name: c.canonical_name,
                subjects: c.subjects,
                chapters: c.chapters,
                type: c.type,
                status: r.status,
                time_spent: r.time_spent
            } END) AS contents,
            collect(DISTINCT CASE WHEN r.status = 'done' THEN c.match_key END) AS completed_content_keys

        RETURN
            p.plan_id               AS plan_id,
            p.plan_name             AS plan_name,
            p.status                AS plan_status,
            p.total_hours           AS plan_total_hours,
            p.source                AS source,
            p.work_item_targets     AS work_item_targets,
            p.work_item_hours_spent AS work_item_hours_spent,
            p.intake_snapshot       AS intake_snapshot,
            p.availability_math     AS availability_math,
            d.day_num               AS day_num,
            d.date                  AS date,
            d.capacity_hours        AS capacity_hours,
            d.total_hours           AS day_total_hours,
            s.session_id            AS session_id,
            s.title                 AS session_title,
            s.session_type          AS session_type,
            s.start_time            AS start_time,
            s.end_time              AS end_time,
            s.estimated_hours       AS estimated_hours,
            coalesce(s.allocated_hours_json, s.allocated_hours, "[]") AS allocated_hours,
            s.actual_time           AS actual_time,
            s.status                AS session_status,
            [c2 IN contents WHERE c2.match_key IS NOT NULL] AS contents,
            [k IN completed_content_keys WHERE k IS NOT NULL] AS completed_content_keys
        ORDER BY d.day_num, s.start_time
        """
        return self.graph.query(query, params={"user_id": user_id, "plan_id": plan_id})

    def list_plans_paginated(
        self, user_id: str, offset: int = 0, limit: int = 5
    ) -> Dict[str, Any]:
        query = """
        MATCH (u:User {id: $user_id})-[:HAS_PLAN]->(p:Plan)
        WITH p ORDER BY p.start_date DESC
        WITH collect(p) as all_plans
        RETURN all_plans as plans, size(all_plans) as total
        """
        result = self.graph.query(query, params={"user_id": user_id})
        if not result:
            return {"plans": [], "total": 0}

        all_plans = result[0]["plans"]
        total = result[0]["total"]
        paginated = all_plans[offset : offset + limit]

        plans_formatted = []
        for p in paginated:
            plans_formatted.append(
                {
                    "plan_id": p.get("plan_id"),
                    "plan_name": p.get("plan_name", "Untitled Plan"),
                    "status": p.get("status", "UNKNOWN"),
                    "start_date": str(p.get("start_date", "")),
                    "estimated_duration": p.get("estimated_duration", 0),
                    "planned_end_date": str(p.get("planned_end_date", "")),
                    "actual_end_date": str(p.get("actual_end_date", ""))
                    if p.get("actual_end_date")
                    else None,
                }
            )
        return {
            "plans": plans_formatted,
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    def search_plans_by_date(
        self, user_id: str, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        query = """
        MATCH (u:User {id: $user_id})-[:HAS_PLAN]->(p:Plan)
        WHERE p.start_date >= date($start_date)
          AND p.start_date <= date($end_date)
        RETURN p.plan_id AS plan_id,
               p.plan_name AS plan_name,
               p.status AS status,
               p.start_date AS start_date,
               p.estimated_duration AS estimated_duration,
               p.planned_end_date AS planned_end_date,
               p.actual_end_date AS actual_end_date
        ORDER BY p.start_date DESC
        """
        result = self.graph.query(
            query,
            params={"user_id": user_id, "start_date": start_date, "end_date": end_date},
        )
        plans = []
        for r in result:
            plans.append(
                {
                    "plan_id": r.get("plan_id"),
                    "plan_name": r.get("plan_name", "Untitled Plan"),
                    "status": r.get("status", "UNKNOWN"),
                    "start_date": str(r.get("start_date", "")),
                    "estimated_duration": r.get("estimated_duration", 0),
                    "planned_end_date": str(r.get("planned_end_date", "")),
                    "actual_end_date": str(r.get("actual_end_date", ""))
                    if r.get("actual_end_date")
                    else None,
                }
            )
        return plans

    def update_plan_name(self, user_id: str, plan_id: str, new_name: str) -> bool:
        query = """
        MATCH (u:User {id: $user_id})-[:HAS_PLAN]->(p:Plan {plan_id: $plan_id})
        SET p.plan_name = $new_name
        RETURN p.plan_id AS plan_id
        """
        result = self.graph.query(
            query,
            params={"user_id": user_id, "plan_id": plan_id, "new_name": new_name},
        )
        return bool(result)

    def update_plan_fields(self, user_id: str, plan_id: str, updates: dict) -> bool:
        if not updates:
            return False
        set_clauses = ", ".join([f"p.{k} = ${k}" for k in updates.keys()])
        query = f"""
        MATCH (u:User {{id: $user_id}})-[:HAS_PLAN]->(p:Plan {{plan_id: $plan_id}})
        SET {set_clauses}
        RETURN p.plan_id AS plan_id
        """
        result = self.graph.query(
            query, params={"user_id": user_id, "plan_id": plan_id, **updates}
        )
        return bool(result)

    def mark_other_plans_inactive(self, user_id: str, keep_plan_id: str) -> int:
        """
        Mark every ACTIVE plan inactive except the freshly committed plan.
        Keeps one active plan per user without archiving before commit succeeds.
        """
        query = """
        MATCH (u:User {id: $user_id})-[:HAS_PLAN]->(p:Plan {status: 'ACTIVE'})
        WHERE p.plan_id <> $keep_plan_id
        SET p.status = 'INACTIVE',
            p.archived_at = datetime(),
            p.actual_end_date = date()
        RETURN count(p) AS count
        """
        result = self.graph.query(
            query,
            params={"user_id": user_id, "keep_plan_id": keep_plan_id},
        )
        return result[0]["count"] if result else 0

    # ─────────────────────────────────────────────
    # CONTENT NODE
    # ─────────────────────────────────────────────
    # Content represents atomic learning units (subtopics, videos, etc.).
    # Content nodes are shared across users — they're the curriculum graph,
    # not per-user state. Sessions target content via TARGETS_CONTENT.

    @staticmethod
    def generate_content_match_key(
        subject: str, chapter: str, content_name: str
    ) -> str:
        """Generate a deterministic Content match_key from components.

        Format: {subject_slug}_{chapter_slug}_{content_name_slug}
        Example: maths_trigonometry_sine_rule
        """
        subject_slug = subject.lower().replace(" ", "_")
        chapter_slug = chapter.lower().replace(" ", "_")
        content_slug = content_name.lower().replace(" ", "_")
        return f"{subject_slug}_{chapter_slug}_{content_slug}"

    def resolve_content_nodes(
        self,
        contents: List[Dict[str, Any]],
    ) -> List[str]:
        """
        Resolve/create Content nodes from planner output.
        Returns list of match_keys that were created/merged.
        """
        created = []
        for c in contents:
            match_key = c.get("match_key")
            if not match_key:
                continue
            self.graph.query(
                """
                MERGE (c:Content {match_key: $match_key})
                ON CREATE SET
                    c.canonical_name = $name,
                    c.subjects = $subjects,
                    c.chapters = $chapters,
                    c.type = $content_type,
                    c.created_at = datetime()
                """,
                params={
                    "match_key": match_key,
                    "name": c.get("name", ""),
                    "subjects": c.get("subjects", []),
                    "chapters": c.get("chapters", []),
                    "content_type": c.get("type", "subtopic"),
                },
            )
            created.append(match_key)
        return created

    # ─────────────────────────────────────────────
    # SESSION NODE
    # ─────────────────────────────────────────────
    # Sessions are the execution truth — they record what actually happened.
    # A session belongs to a day (via HAS_SESSION) and a user (via PERFORMED).
    # Sessions target content via TARGETS_CONTENT relationships.

    def link_session_to_content(
        self,
        session_id: str,
        content_match_key: str,
        status: str = "pending",
        time_spent: float = 0,
    ) -> bool:
        """Link Session to Content with status (V2)."""
        query = """
        MATCH (s:Session {session_id: $session_id})
        MATCH (c:Content {match_key: $content_key})
        MERGE (s)-[r:TARGETS_CONTENT]->(c)
        SET r.status = $status, r.time_spent = $time_spent
        RETURN c.match_key AS content_key
        """
        result = self.graph.query(
            query,
            params={
                "session_id": session_id,
                "content_key": content_match_key,
                "status": status,
                "time_spent": time_spent,
            },
        )
        return bool(result)

    def create_session_with_day_link(
        self,
        session_id: str,
        user_id: str,
        plan_id: str,
        day_date: str,
        title: str,
        session_type: str,
        date: str,
        start_time: str,
        end_time: str,
        estimated_hours: float,
        allocated_hours: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[str]:
        """
        Create Session node with TWO relationships:
        - (Day)-[:HAS_SESSION]->(Session) — schedule
        - (User)-[:PERFORMED]->(Session) — history

        Uses MATCH for User and Day (production path).
        Returns None if User or Day doesn't exist.
        """
        query = """
        MATCH (u:User {id: $user_id})
        MATCH (p:Plan {plan_id: $plan_id})-[:HAS_DAY]->(d:Day {date: $day_date})
        CREATE (d)-[:HAS_SESSION]->(s:Session {
            session_id: $session_id,
            user_id: $user_id,
            plan_id: $plan_id,
            title: $title,
            session_type: $session_type,
            date: $date,
            start_time: $start_time,
            end_time: $end_time,
            estimated_hours: $estimated_hours,
            allocated_hours_json: $allocated_hours_json,
            actual_time: 0,
            status: 'pending',
            created_at: datetime()
        })
        CREATE (u)-[:PERFORMED]->(s)
        RETURN s.session_id AS session_id
        """
        result = self.graph.query(
            query,
            params={
                "session_id": session_id,
                "user_id": user_id,
                "plan_id": plan_id,
                "day_date": day_date,
                "title": title,
                "session_type": session_type,
                "date": date,
                "start_time": start_time,
                "end_time": end_time,
                "estimated_hours": estimated_hours,
                "allocated_hours_json": json.dumps(allocated_hours or []),
            },
        )

        return result[0]["session_id"] if result else None

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get Session node by session_id."""
        query = """
        MATCH (s:Session {session_id: $session_id})
        RETURN s.session_id AS session_id,
               s.user_id AS user_id,
               s.plan_id AS plan_id,
               s.title AS title,
               s.session_type AS session_type,
               s.date AS date,
               s.start_time AS start_time,
               s.end_time AS end_time,
               s.estimated_hours AS estimated_hours,
               coalesce(s.allocated_hours_json, s.allocated_hours, "[]") AS allocated_hours,
               s.actual_time AS actual_time,
               s.status AS status
        """
        result = self.graph.query(query, params={"session_id": session_id})
        if not result:
            return None
        row = dict(result[0])
        raw_allocations = row.get("allocated_hours")
        if isinstance(raw_allocations, str):
            try:
                row["allocated_hours"] = json.loads(raw_allocations)
            except Exception:
                row["allocated_hours"] = []
        return row

    def get_session_with_contents(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get Session with all its Content."""
        query = """
        MATCH (s:Session {session_id: $session_id})
        OPTIONAL MATCH (s)-[r:TARGETS_CONTENT]->(c:Content)
        RETURN s.session_id AS session_id,
               s.user_id AS user_id,
               s.plan_id AS plan_id,
               s.title AS title,
               s.session_type AS session_type,
               s.date AS date,
               s.start_time AS start_time,
               s.end_time AS end_time,
               s.estimated_hours AS estimated_hours,
               coalesce(s.allocated_hours_json, s.allocated_hours, "[]") AS allocated_hours,
               s.actual_time AS actual_time,
               s.status AS status,
               collect({
                   match_key: c.match_key,
                   canonical_name: c.canonical_name,
                   subjects: c.subjects,
                   chapters: c.chapters,
                   type: c.type,
                   status: r.status,
                   time_spent: r.time_spent
               }) AS contents
        """
        result = self.graph.query(query, params={"session_id": session_id})
        if not result:
            return None
        row = result[0]
        contents = row.get("contents") or []
        return {
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "plan_id": row["plan_id"],
            "title": row["title"],
            "session_type": row["session_type"],
            "date": row["date"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "estimated_hours": row["estimated_hours"],
            "allocated_hours": json.loads(row["allocated_hours"])
            if isinstance(row.get("allocated_hours"), str)
            else (row.get("allocated_hours") or []),
            "actual_time": row["actual_time"],
            "status": row["status"],
            "contents": [c for c in contents if c.get("match_key")],
        }

    # ─────────────────────────────────────────────
    # ACTIVE PLAN SESSIONS
    # ─────────────────────────────────────────────
    # This is the primary read path for the live schedule. Returns the
    # full plan hierarchy: plan → days → sessions → content targets.

    def get_active_plan_status(self, user_id: str) -> Dict[str, Any]:
        """Return whether the user has an active plan, plus its id if present."""

        query = """
MATCH (u:User {id: $user_id})-[:HAS_PLAN]->(p:Plan {status: 'ACTIVE'})
RETURN
    p.plan_id AS plan_id,
    p.plan_name AS plan_name,
    p.status AS plan_status
LIMIT 1
"""
        result = self.graph.query(query, params={"user_id": user_id})
        if not result:
            return {"has_plan": False, "plan_id": None, "plan_name": None, "status": None}

        row = result[0]
        return {
            "has_plan": True,
            "plan_id": row.get("plan_id"),
            "plan_name": row.get("plan_name"),
            "status": row.get("plan_status"),
        }

    def get_active_plan_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get the active plan with days, sessions, and content targets.

        Returns a flat list of rows (one per session), ordered by day and
        start_time. Each row includes the plan, day, and session fields
        plus an array of content targets.
        """
        query = """
MATCH (u:User {id: $user_id})-[:HAS_PLAN]->(p:Plan {status: 'ACTIVE'})
MATCH (p)-[:HAS_DAY]->(d:Day)
OPTIONAL MATCH (d)-[:HAS_SESSION]->(s:Session)
OPTIONAL MATCH (s)-[r:TARGETS_CONTENT]->(c:Content)

WITH p, d, s,
    collect(DISTINCT CASE WHEN c IS NOT NULL THEN {
        match_key: c.match_key,
        canonical_name: c.canonical_name,
        subjects: c.subjects,
        chapters: c.chapters,
        type: c.type,
        status: r.status,
        time_spent: r.time_spent
    } END) AS contents,
    collect(DISTINCT CASE WHEN r.status = 'done' THEN c.match_key END) AS completed_content_keys

RETURN
    p.plan_id AS plan_id,
    p.plan_name AS plan_name,
    p.status AS plan_status,
    p.total_hours AS plan_total_hours,
    p.source AS source,
    p.work_item_targets AS work_item_targets,
    p.work_item_hours_spent AS work_item_hours_spent,
    p.intake_snapshot AS intake_snapshot,
    p.availability_math AS availability_math,
    d.day_num AS day_num,
    d.date AS date,
    d.capacity_hours AS capacity_hours,
    d.total_hours AS day_total_hours,
    s.session_id AS session_id,
    s.title AS session_title,
    s.session_type AS session_type,
    s.start_time AS start_time,
    s.end_time AS end_time,
    s.estimated_hours AS estimated_hours,
    coalesce(s.allocated_hours_json, s.allocated_hours, "[]") AS allocated_hours,
    s.actual_time AS actual_time,
    s.status AS session_status,
    [c2 IN contents WHERE c2.match_key IS NOT NULL] AS contents,
    [k IN completed_content_keys WHERE k IS NOT NULL] AS completed_content_keys
ORDER BY d.day_num, s.start_time
"""
        return self.graph.query(query, params={"user_id": user_id})

    # ─────────────────────────────────────────────
    # SESSION COMPLETION
    # ─────────────────────────────────────────────
    # These methods handle the lifecycle of session completion:
    # marking done, distributing time across content, undoing, ticking.

    def complete_session(self, session_id: str, actual_time: float = None) -> bool:
        """Mark a session as done and distribute time across all its content.

        If actual_time is not provided, uses the estimated_hours from the
        session. Time is split equally across all linked content nodes.
        """
        result = self.graph.query(
            """
            MATCH (s:Session {session_id: $sid})-[r:TARGETS_CONTENT]->(c:Content)
            RETURN collect(c.match_key) AS content_keys, s.estimated_hours AS est
            """,
            {"sid": session_id},
        )
        if not result:
            return False

        content_keys = result[0]["content_keys"] or []
        actual = actual_time if actual_time is not None else result[0]["est"]
        time_per_content = actual / len(content_keys) if content_keys else 0

        self.graph.query(
            """
            MATCH (s:Session {session_id: $sid})
            SET s.actual_time = $actual, s.status = 'done'
            """,
            {"sid": session_id, "actual": actual},
        )

        for ck in content_keys:
            self.graph.query(
                """
                MATCH (s:Session {session_id: $sid})-[r:TARGETS_CONTENT]->(c:Content {match_key: $ck})
                SET c.actual_hours = coalesce(c.actual_hours, 0.0) - coalesce(r.time_spent, 0.0) + $time,
                    r.status = 'done',
                    r.time_spent = $time
                """,
                {"sid": session_id, "ck": ck, "time": time_per_content},
            )

        return True

    def update_session_content_times(
        self,
        session_id: str,
        content_updates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Update per-content actual time for a session.
        TARGETS_CONTENT.time_spent is the actual-time truth.
        Session.actual_time is recomputed as a summary from those relationships.
        """
        allowed_statuses = {"pending", "done", "skipped", "partial"}

        for item in content_updates:
            content_key = item.get("content_match_key") or item.get("match_key")
            if not content_key:
                continue

            status = (item.get("status") or "done").lower()
            if status not in allowed_statuses:
                status = "done"

            time_spent = float(item.get("time_spent") or 0)

            self.graph.query(
                """
                MATCH (s:Session {session_id: $sid})-[r:TARGETS_CONTENT]->(c:Content {match_key: $ck})
                SET c.actual_hours = coalesce(c.actual_hours, 0.0) - coalesce(r.time_spent, 0.0) + $time_spent,
                    r.status = $status,
                    r.time_spent = $time_spent,
                    r.completed_at = CASE WHEN $status = 'done' THEN datetime() ELSE null END
                """,
                {
                    "sid": session_id,
                    "ck": content_key,
                    "status": status,
                    "time_spent": time_spent,
                },
            )

        result = self.graph.query(
            """
            MATCH (s:Session {session_id: $sid})-[r:TARGETS_CONTENT]->(:Content)
            WITH s,
                 collect(r.status) AS statuses,
                 sum(CASE WHEN r.status = 'done' THEN coalesce(r.time_spent, 0) ELSE 0 END) AS actual_time
            SET s.actual_time = actual_time,
                s.status = CASE
                    WHEN all(x IN statuses WHERE x = 'done') THEN 'done'
                    WHEN any(x IN statuses WHERE x = 'done') THEN 'partial'
                    WHEN all(x IN statuses WHERE x = 'skipped') THEN 'skipped'
                    ELSE 'pending'
                END
            RETURN s.status AS status, s.actual_time AS actual_time
            """,
            {"sid": session_id},
        )

        return result[0] if result else {"status": "pending", "actual_time": 0}

    def reset_session(self, session_id: str) -> bool:
        """Undo a session completion — resets status to pending.

        Clears actual_time on the session and resets all content
        target statuses back to pending.
        """
        self.graph.query(
            """
            MATCH (s:Session {session_id: $sid})
            SET s.actual_time = 0, s.status = 'pending'
            """,
            {"sid": session_id},
        )

        self.graph.query(
            """
            MATCH (s:Session {session_id: $sid})-[r:TARGETS_CONTENT]->(c:Content)
            SET r.status = 'pending', r.time_spent = 0
            """,
            {"sid": session_id},
        )

        return True

    def mark_session_skipped(self, session_id: str) -> bool:
        """Mark a session and its content links as skipped.

        This is the closest semantic opposite of "complete for now":
        - session becomes skipped
        - per-content spent time is cleared from truth
        - content links become skipped
        """
        self.graph.query(
            """
            MATCH (s:Session {session_id: $sid})
            SET s.actual_time = 0, s.status = 'skipped'
            """,
            {"sid": session_id},
        )

        self.graph.query(
            """
            MATCH (s:Session {session_id: $sid})-[r:TARGETS_CONTENT]->(c:Content)
            SET c.actual_hours = coalesce(c.actual_hours, 0.0) - coalesce(r.time_spent, 0.0),
                r.status = 'skipped',
                r.time_spent = 0
            """,
            {"sid": session_id},
        )

        return True

    # ─────────────────────────────────────────────
    # CHAPTER BACKLOG
    # ─────────────────────────────────────────────
    # Aggregates content completion into chapter-level progress.
    # Used by the backlog sync to update Pinecone with chapter status.

    def get_chapter_backlog(self, user_id: str) -> List[Dict[str, Any]]:
        """Aggregate chapter-level backlog from session/content data.

        Groups by subject+chapter, counts completed/pending content,
        and determines overall status (DONE, IN_PROGRESS, NOT_STARTED).
        """
        query = """
        MATCH (u:User {id: $user_id})-[:PERFORMED]->(s:Session)-[r:TARGETS_CONTENT]->(c:Content)
        WITH c, r,
            collect(DISTINCT s.session_id) AS sessions,
            collect(DISTINCT CASE WHEN r.status = 'done' THEN c.match_key END) AS done_keys,
            collect(DISTINCT CASE WHEN r.status = 'pending' THEN c.match_key END) AS pending_keys,
            sum(CASE WHEN r.status = 'done' THEN r.time_spent ELSE 0 END) AS total_hours
        WITH c,
            sessions,
            [x IN done_keys WHERE x IS NOT NULL] AS subtopics_completed,
            [x IN pending_keys WHERE x IS NOT NULL] AS subtopics_pending,
            total_hours
        RETURN
            c.subjects AS subjects,
            c.chapters AS chapters,
            subtopics_completed,
            subtopics_pending,
            total_hours
        """
        rows = self.graph.query(query, params={"user_id": user_id})

        chapter_backlogs = {}
        for row in rows:
            subjects = row.get("subjects") or []
            chapters = row.get("chapters") or []
            sub_completed = row.get("subtopics_completed") or []
            sub_pending = row.get("subtopics_pending") or []
            hours = row.get("total_hours") or 0

            for subj in subjects:
                for ch in chapters:
                    key = f"{subj}|{ch}"
                    if key not in chapter_backlogs:
                        chapter_backlogs[key] = {
                            "scope_reference_key": key,
                            "subject": subj,
                            "chapter": ch,
                            "subtopics_completed": [],
                            "subtopics_pending": [],
                            "hours_actual": 0,
                        }
                    chapter_backlogs[key]["subtopics_completed"].extend(sub_completed)
                    chapter_backlogs[key]["subtopics_pending"].extend(sub_pending)
                    chapter_backlogs[key]["hours_actual"] += hours

        backlog_list = []
        for key, data in chapter_backlogs.items():
            completed = list(set(data["subtopics_completed"]))
            pending = list(set(data["subtopics_pending"]))

            if completed and not pending:
                status = "DONE"
            elif completed:
                status = "IN_PROGRESS"
            else:
                status = "NOT_STARTED"

            backlog_list.append(
                {
                    "scope_reference_key": data["scope_reference_key"],
                    "subject": data["subject"],
                    "chapter": data["chapter"],
                    "status": status,
                    "hours_actual": round(data["hours_actual"], 2),
                    "subtopics_completed": completed,
                    "subtopics_pending": pending,
                }
            )

        return backlog_list

    # ─────────────────────────────────────────────
    # TICK/UNTICK
    # ─────────────────────────────────────────────
    # Fine-grained content completion within a session.
    # Tick marks one content item as done; untick reverts it.
    # Session status is recomputed after each operation.

    def tick_content(
        self,
        session_id: str,
        content_match_key: str,
        time_spent: float = 0,
    ) -> str:
        """Mark a single content item as done within a session.

        Updates the TARGETS_CONTENT relationship status and recomputes
        the session's overall status (pending/partial/done).
        """
        self.graph.query(
            """
            MATCH (s:Session {session_id: $sid})-[r:TARGETS_CONTENT]->(c:Content {match_key: $ck})
            SET c.actual_hours = coalesce(c.actual_hours, 0.0) - coalesce(r.time_spent, 0.0) + $time_spent,
                r.status = 'done',
                r.time_spent = $time_spent,
                r.completed_at = datetime()
            """,
            {"sid": session_id, "ck": content_match_key, "time_spent": time_spent},
        )

        query = """
        MATCH (s:Session {session_id: $sid})-[r:TARGETS_CONTENT]->(c:Content)
        WITH s, collect(r.status) AS statuses, sum(CASE WHEN r.status = 'done' THEN r.time_spent ELSE 0 END) AS total_time
        SET s.status = CASE
            WHEN all(x IN statuses WHERE x = 'done') THEN 'done'
            WHEN any(x IN statuses WHERE x = 'done') THEN 'partial'
            ELSE 'pending' END,
            s.actual_time = total_time
        RETURN s.status
        """
        result = self.graph.query(query, {"sid": session_id})
        return result[0]["s.status"] if result else "pending"

    def untick_content(self, session_id: str, content_match_key: str) -> str:
        """Revert a content item from done back to pending.

        Resets the TARGETS_CONTENT.time_spent to 0 and recomputes
        the session's overall status.
        """
        query = """
        MATCH (s:Session {session_id: $sid})-[r:TARGETS_CONTENT]->(c:Content {match_key: $ck})
        SET c.actual_hours = coalesce(c.actual_hours, 0.0) - coalesce(r.time_spent, 0.0),
            r.status = 'pending',
            r.time_spent = 0
        RETURN c.match_key AS content_key
        """
        self.graph.query(query, {"sid": session_id, "ck": content_match_key})

        query = """
        MATCH (s:Session {session_id: $sid})-[r:TARGETS_CONTENT]->(c:Content)
        WITH s, collect(r.status) AS statuses, sum(CASE WHEN r.status = 'done' THEN r.time_spent ELSE 0 END) AS total_time
        SET s.status = CASE
            WHEN all(x IN statuses WHERE x = 'done') THEN 'done'
            WHEN any(x IN statuses WHERE x = 'done') THEN 'partial'
            ELSE 'pending' END,
            s.actual_time = total_time
        RETURN s.status
        """
        result = self.graph.query(query, {"sid": session_id})
        return result[0]["s.status"] if result else "pending"

    # ─────────────────────────────────────────────
    # STATS QUERIES
    # ─────────────────────────────────────────────

    def get_subtopic_counts(self, user_id: str) -> Dict[str, int]:
        """Return total and done subtopic counts for a user's active plan sessions."""
        query = """
        MATCH (u:User {id: $user_id})-[:PERFORMED]->(s:Session)-[r:TARGETS_CONTENT]->(c:Content)
        RETURN
            count(DISTINCT c.match_key) AS total_subtopics,
            count(DISTINCT CASE WHEN r.status = 'done' THEN c.match_key END) AS subtopics_done
        """
        res = self.graph.query(query, {"user_id": user_id})
        if res:
            return {
                "total_subtopics": res[0].get("total_subtopics", 0),
                "subtopics_done": res[0].get("subtopics_done", 0),
            }
        return {"total_subtopics": 0, "subtopics_done": 0}
