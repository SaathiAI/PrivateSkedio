"""Commit pipeline for persisting verified plans and syncing side effects.

This file is the durable write boundary after planning succeeds.

Mental model:
- planner/verifier work in draft space
- this service performs the actual persistent write into Neo4j
- non-critical follow-up syncs, such as backlog projection, happen around that
  durable write
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.models.planner import StudyPlan


logger = logging.getLogger("skedioai.commit")


def ensure_commit_logging() -> logging.Logger:
    """Install a readable commit logger when the app has not configured one."""

    commit_logger = logging.getLogger("skedioai.commit")
    if not commit_logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        commit_logger.addHandler(handler)
    commit_logger.setLevel(logging.INFO)
    commit_logger.propagate = False
    return commit_logger


def _compact(value: Any, limit: int = 500) -> str:
    try:
        text = json.dumps(value, default=str, sort_keys=True)
    except Exception:
        text = str(value)
    if len(text) > limit:
        return text[:limit] + "...<truncated>"
    return text


def _log_step(
    commit_logger: logging.Logger,
    commit_id: str,
    step: str,
    status: str,
    **fields: Any,
) -> None:
    suffix = ""
    if fields:
        suffix = " " + " ".join(
            f"{key}={_compact(value)}" for key, value in fields.items()
        )
    commit_logger.info("commit_id=%s step=%s status=%s%s", commit_id, step, status, suffix)


def _verify_commit(
    neo4j, user_id: str, plan_id: str, expected_sessions: int
) -> dict:
    """Verify the graph was written correctly after commit.

    Checks that the Plan exists, has Days, and has the expected number of
    Sessions. Returns {"ok": True/False, ...} with details.
    """
    try:
        result = neo4j.graph.query(
            """
            MATCH (u:User {id: $uid})-[:HAS_PLAN]->(p:Plan {plan_id: $pid})
            OPTIONAL MATCH (p)-[:HAS_DAY]->(d:Day)
            OPTIONAL MATCH (d)-[:HAS_SESSION]->(s:Session)
            RETURN count(DISTINCT d) AS day_count,
                   count(DISTINCT s) AS session_count
            """,
            {"uid": user_id, "pid": plan_id},
        )
        if not result:
            return {"ok": False, "reason": "plan_not_found"}

        row = result[0]
        day_count = row.get("day_count", 0)
        session_count = row.get("session_count", 0)

        if day_count == 0:
            return {"ok": False, "reason": "no_days", "day_count": day_count}
        if session_count < expected_sessions:
            return {
                "ok": False,
                "reason": "missing_sessions",
                "expected": expected_sessions,
                "actual": session_count,
            }

        return {
            "ok": True,
            "day_count": day_count,
            "session_count": session_count,
        }
    except Exception as e:
        return {"ok": False, "reason": "exception", "error": str(e)}


def _cleanup_partial_commit(neo4j, user_id: str, plan_id: str) -> None:
    """Best-effort cleanup of a partially written plan.

    Detaches and deletes the Plan node (and any orphaned Days/Sessions).
    This is not transactional — it's a recovery heuristic.
    """
    try:
        neo4j.graph.query(
            """
            MATCH (u:User {id: $uid})-[:HAS_PLAN]->(p:Plan {plan_id: $pid})
            OPTIONAL MATCH (p)-[:HAS_DAY]->(d:Day)-[:HAS_SESSION]->(s:Session)
            DETACH DELETE s
            """,
            {"uid": user_id, "pid": plan_id},
        )
        neo4j.graph.query(
            """
            MATCH (p:Plan {plan_id: $pid})
            DETACH DELETE p
            """,
            {"pid": plan_id},
        )
        logger.warning("Cleaned up partial commit for plan %s", plan_id)
    except Exception as e:
        logger.error("Failed to cleanup partial commit %s: %s", plan_id, e)


async def commit_study_plan(
    user_id: str,
    plan: StudyPlan,
    work_item_targets: Optional[Dict[str, float]] = None,
    backlog_match_keys: Optional[List[str]] = None,
    intake_snapshot: Optional[Dict[str, Any]] = None,
    wait_for_backlog_sync: bool = False,
) -> dict:
    """Persist a verified StudyPlan into Neo4j and sync non-critical side effects.

    This is the first place that should mutate durable plan truth.

    Source of truth written here:
    Plan -> Day -> Session -> Content, plus Intake/availability snapshots.
    """
    from src.database.neo4j import Neo4jManager
    from src.services.active_plan import invalidate_active_plan_cache

    commit_logger = ensure_commit_logging()
    commit_id = f"commit_{uuid.uuid4().hex[:8]}"
    timings = {}
    total_start = time.perf_counter()

    async def sync_backlog_in_background(neo4j_client) -> bool:
        t = time.perf_counter()
        _log_step(commit_logger, commit_id, "backlog_sync_waited", "start")
        try:
            from src.services.backlog_sync import sync_chapter_backlog

            result = await sync_chapter_backlog(user_id, neo4j_client)
            _log_step(
                commit_logger,
                commit_id,
                "backlog_sync_waited",
                "success",
                duration_s=round(time.perf_counter() - t, 2),
                result=result,
            )
            return result
        except Exception as e:
            commit_logger.warning(
                "commit_id=%s step=backlog_sync_waited status=failed error=%s",
                commit_id,
                e,
            )
            return False

    def sync_backlog_in_worker_thread() -> bool:
        t = time.perf_counter()
        thread_logger = ensure_commit_logging()
        _log_step(thread_logger, commit_id, "backlog_sync_background", "start")
        try:
            from src.services.backlog_sync import sync_chapter_backlog

            result = asyncio.run(sync_chapter_backlog(user_id))
            _log_step(
                thread_logger,
                commit_id,
                "backlog_sync_background",
                "success",
                duration_s=round(time.perf_counter() - t, 2),
                result=result,
            )
            return result
        except Exception as e:
            thread_logger.warning(
                "commit_id=%s step=backlog_sync_background status=failed error=%s",
                commit_id,
                e,
            )
            return False

    try:
        _log_step(
            commit_logger,
            commit_id,
            "commit_study_plan",
            "start",
            user_id=user_id,
            source_plan_id=plan.plan_id,
            wait_for_backlog_sync=wait_for_backlog_sync,
        )

        _log_step(commit_logger, commit_id, "neo4j_manager_init", "start")
        neo4j = Neo4jManager()
        _log_step(commit_logger, commit_id, "neo4j_manager_init", "success")

        _log_step(commit_logger, commit_id, "create_user", "start", user_id=user_id)
        neo4j.create_user(user_id)
        _log_step(commit_logger, commit_id, "create_user", "success", user_id=user_id)

        _log_step(commit_logger, commit_id, "prepare_plan_payload", "start")
        data_dict = plan.model_dump()
        base_id = data_dict.get("plan_id") or "plan"
        plan_id = f"{base_id}-{uuid.uuid4().hex[:8]}"
        day_count = len(data_dict.get("days") or [])
        session_count = sum(len(day.get("sessions", [])) for day in data_dict.get("days", []))
        _log_step(
            commit_logger,
            commit_id,
            "prepare_plan_payload",
            "success",
            committed_plan_id=plan_id,
            day_count=day_count,
            session_count=session_count,
            total_hours=data_dict.get("total_hours"),
        )

        _log_step(commit_logger, commit_id, "resolve_missing_content_keys", "start")
        all_contents = []
        generated_match_keys = 0
        for day in data_dict["days"]:
            for session in day.get("sessions", []):
                for content in session.get("contents", []):
                    if not content.get("match_key"):
                        allocation = (session.get("allocated_hours") or [{}])[0]
                        subjects = (
                            content.get("subjects")
                            or ([content.get("subject")] if content.get("subject") else [])
                            or ([allocation.get("subject")] if allocation.get("subject") else [])
                            or session.get("subjects")
                            or []
                        )
                        chapters = (
                            content.get("chapters")
                            or ([content.get("chapter")] if content.get("chapter") else [])
                            or ([allocation.get("chapter")] if allocation.get("chapter") else [])
                            or session.get("chapters")
                            or []
                        )
                        content["match_key"] = neo4j.generate_content_match_key(
                            subject=subjects[0] if subjects else "unknown",
                            chapter=chapters[0] if chapters else "unknown",
                            content_name=content.get("name", "unknown"),
                        )
                        generated_match_keys += 1
                    all_contents.append(content)
        _log_step(
            commit_logger,
            commit_id,
            "resolve_missing_content_keys",
            "success",
            content_count=len(all_contents),
            generated_match_keys=generated_match_keys,
        )

        _log_step(
            commit_logger,
            commit_id,
            "resolve_content_nodes",
            "start",
            content_count=len(all_contents),
        )
        t = time.perf_counter()
        neo4j.resolve_content_nodes(all_contents)
        timings["content_resolution"] = round(time.perf_counter() - t, 2)
        _log_step(
            commit_logger,
            commit_id,
            "resolve_content_nodes",
            "success",
            duration_s=timings["content_resolution"],
        )

        start_date = data_dict["days"][0]["date"] if data_dict["days"] else None
        estimated_duration = len(data_dict["days"]) if data_dict["days"] else 0
        planned_end_date = data_dict["days"][-1]["date"] if data_dict["days"] else None

        plan_name = "Untitled Plan"
        if start_date:
            try:
                dt = datetime.strptime(start_date, "%Y-%m-%d")
                plan_name = f"{dt.strftime('%B')} {dt.day} Plan"
            except Exception:
                plan_name = "Untitled Plan"

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        work_item_targets = work_item_targets or data_dict.get("work_item_targets", {})
        backlog_match_keys = backlog_match_keys or data_dict.get("backlog_match_keys", [])
        intake_snapshot = intake_snapshot or data_dict.get("intake_snapshot", {})

        if not intake_snapshot:
            intake_snapshot = {
                "subjects": data_dict.get("subjects", []),
                "chapters": data_dict.get("chapters", []),
                "hours_per_day": data_dict.get("hours_per_day", 0),
                "skill_level": data_dict.get("skill_level", ""),
                "notes": data_dict.get("notes", ""),
                "work_item_targets": work_item_targets,
                "backlog_match_keys": backlog_match_keys,
                "created_at": now_str,
            }

        availability_math = {}
        if isinstance(intake_snapshot, dict):
            planner_input = intake_snapshot.get("planner_input") or {}
            availability_math = (
                intake_snapshot.get("availability_math")
                or planner_input.get("availability_math")
                or {}
            )

        _log_step(
            commit_logger,
            commit_id,
            "create_plan",
            "start",
            plan_id=plan_id,
            plan_name=plan_name,
            start_date=start_date,
            planned_end_date=planned_end_date,
            work_item_targets=work_item_targets,
        )
        t = time.perf_counter()
        work_item_hours_spent = {work_item: 0.0 for work_item in work_item_targets.keys()}

        neo4j.create_plan(
            user_id,
            plan_id,
            plan_name,
            start_date or "",
            planned_end_date or "",
            estimated_duration,
            data_dict["total_hours"],
            list(work_item_targets.keys()),
            work_item_targets,
            work_item_hours_spent,
            intake_snapshot,
            availability_math,
        )
        timings["plan_creation"] = round(time.perf_counter() - t, 2)
        _log_step(
            commit_logger,
            commit_id,
            "create_plan",
            "success",
            duration_s=timings["plan_creation"],
            plan_id=plan_id,
        )

        _log_step(
            commit_logger,
            commit_id,
            "create_days",
            "start",
            day_count=day_count,
        )
        t = time.perf_counter()
        days_query = """
        MATCH (p:Plan {plan_id: $plan_id})
        UNWIND $days AS day
        CREATE (p)-[:HAS_DAY]->(d:Day {
            day_num: day.day_num,
            date: day.date,
            total_hours: day.total_hours,
            capacity_hours: day.capacity_hours
        })
        """
        neo4j.graph.query(
            days_query,
            {"plan_id": plan_id, "days": data_dict["days"]},
        )
        timings["day_creation"] = round(time.perf_counter() - t, 2)
        _log_step(
            commit_logger,
            commit_id,
            "create_days",
            "success",
            duration_s=timings["day_creation"],
            day_count=day_count,
        )

        _log_step(
            commit_logger,
            commit_id,
            "create_sessions",
            "start",
            expected_sessions=session_count,
        )
        t = time.perf_counter()
        session_ids = []
        session_map = {}

        for day in data_dict["days"]:
            day_date = day["date"]
            for idx, session in enumerate(day.get("sessions", [])):
                session_id = f"session_{uuid.uuid4().hex[:12]}"
                session_ids.append(session_id)
                session_map[f"{day_date}-{idx}"] = session_id
                session["session_id"] = session_id

                _log_step(
                    commit_logger,
                    commit_id,
                    "create_session_with_day_link",
                    "start",
                    session_id=session_id,
                    date=day_date,
                    title=session.get("title", "Study Session"),
                    start_time=session.get("start_time", "00:00"),
                    end_time=session.get("end_time", "01:00"),
                    estimated_hours=session.get("estimated_hours", 1.0),
                )
                neo4j.create_session_with_day_link(
                    session_id,
                    user_id,
                    plan_id,
                    day_date,
                    session.get("title", "Study Session"),
                    session.get("session_type", "chapter"),
                    day_date,
                    session.get("start_time", "00:00"),
                    session.get("end_time", "01:00"),
                    session.get("estimated_hours", 1.0),
                    session.get("allocated_hours", []),
                )
                _log_step(
                    commit_logger,
                    commit_id,
                    "create_session_with_day_link",
                    "success",
                    session_id=session_id,
                )

                for content in session.get("contents", []):
                    if not content.get("match_key"):
                        allocation = (session.get("allocated_hours") or [{}])[0]
                        subjects = (
                            content.get("subjects")
                            or ([content.get("subject")] if content.get("subject") else [])
                            or ([allocation.get("subject")] if allocation.get("subject") else [])
                            or session.get("subjects")
                            or []
                        )
                        chapters = (
                            content.get("chapters")
                            or ([content.get("chapter")] if content.get("chapter") else [])
                            or ([allocation.get("chapter")] if allocation.get("chapter") else [])
                            or session.get("chapters")
                            or []
                        )
                        content["match_key"] = neo4j.generate_content_match_key(
                            subject=subjects[0] if subjects else "unknown",
                            chapter=chapters[0] if chapters else "unknown",
                            content_name=content.get("name", "unknown"),
                        )
                    _log_step(
                        commit_logger,
                        commit_id,
                        "link_session_to_content",
                        "start",
                        session_id=session_id,
                        content_match_key=content["match_key"],
                    )
                    neo4j.link_session_to_content(
                        session_id,
                        content["match_key"],
                        "pending",
                        0,
                    )
                    _log_step(
                        commit_logger,
                        commit_id,
                        "link_session_to_content",
                        "success",
                        session_id=session_id,
                        content_match_key=content["match_key"],
                    )

        timings["session_creation"] = round(time.perf_counter() - t, 2)
        _log_step(
            commit_logger,
            commit_id,
            "create_sessions",
            "success",
            duration_s=timings["session_creation"],
            created_sessions=len(session_ids),
        )

        _log_step(
            commit_logger,
            commit_id,
            "schedule_backlog_sync",
            "start",
            wait_for_backlog_sync=wait_for_backlog_sync,
        )
        if wait_for_backlog_sync:
            t = time.perf_counter()
            backlog_sync_result = await sync_backlog_in_background(neo4j)
            timings["backlog_sync"] = round(time.perf_counter() - t, 2)
            backlog_sync = {
                "mode": "waited",
                "scheduled": True,
                "success": bool(backlog_sync_result),
            }
        else:
            threading.Thread(
                target=sync_backlog_in_worker_thread,
                name=f"backlog-sync-{user_id}",
                daemon=True,
            ).start()
            timings["backlog_sync"] = "scheduled_background"
            backlog_sync = {
                "mode": "background",
                "scheduled": True,
            }
        _log_step(
            commit_logger,
            commit_id,
            "schedule_backlog_sync",
            "success",
            backlog_sync=backlog_sync,
        )

        calendar_sync = {"success": False, "message": "not attempted"}
        calendar_client = None
        try:
            if data_dict.get("days"):
                from src.tools.test_mcp_client import get_calendar_client

                _log_step(commit_logger, commit_id, "calendar_get_client", "start")
                calendar_client = get_calendar_client()
                _log_step(commit_logger, commit_id, "calendar_get_client", "success")
                calendar_plan = {
                    "plan_id": plan_id,
                    "days": data_dict["days"],
                }
                sync_start = data_dict["days"][0]["date"]
                sync_end = data_dict["days"][-1]["date"]
                _log_step(
                    commit_logger,
                    commit_id,
                    "calendar_delete_skedioai_events",
                    "start",
                    time_min_iso=f"{sync_start}T00:00:00+05:30",
                    time_max_iso=f"{sync_end}T23:59:59+05:30",
                )
                delete_result = await calendar_client.delete_skedioai_events_in_range(
                    time_min_iso=f"{sync_start}T00:00:00+05:30",
                    time_max_iso=f"{sync_end}T23:59:59+05:30",
                    user_id=user_id,
                )
                _log_step(
                    commit_logger,
                    commit_id,
                    "calendar_delete_skedioai_events",
                    "success",
                    result=delete_result,
                )
                _log_step(
                    commit_logger,
                    commit_id,
                    "calendar_create_events_from_plan",
                    "start",
                    day_count=day_count,
                    session_count=len(session_ids),
                )
                create_result = await calendar_client.create_events_from_plan(
                    plan_json=json.dumps(calendar_plan),
                    user_id=user_id,
                )
                _log_step(
                    commit_logger,
                    commit_id,
                    "calendar_create_events_from_plan",
                    "success",
                    result=create_result,
                )
                calendar_sync = {
                    "success": True,
                    "delete_result": delete_result,
                    "create_result": create_result,
                }
        except Exception as calendar_err:
            calendar_sync = {"success": False, "error": str(calendar_err)}
            commit_logger.warning(
                "commit_id=%s step=calendar_sync status=failed_non_critical error=%s",
                commit_id,
                calendar_err,
            )
        finally:
            if calendar_client and hasattr(calendar_client, "disconnect"):
                try:
                    _log_step(commit_logger, commit_id, "calendar_disconnect", "start")
                    await calendar_client.disconnect()
                    _log_step(commit_logger, commit_id, "calendar_disconnect", "success")
                except Exception as disconnect_err:
                    commit_logger.warning(
                        "commit_id=%s step=calendar_disconnect status=failed_non_critical error=%s",
                        commit_id,
                        disconnect_err,
                    )

        _log_step(commit_logger, commit_id, "build_sessions_response", "start")
        sessions_response = []
        for day in data_dict["days"]:
            day_date = day["date"]
            for idx, session in enumerate(day.get("sessions", [])):
                sid = session_map.get(f"{day_date}-{idx}")
                sessions_response.append(
                    {
                        "session_id": sid,
                        "date": day_date,
                        "title": session.get("title", "Study Session"),
                        "start_time": session.get("start_time", "00:00"),
                        "end_time": session.get("end_time", "01:00"),
                        "estimated_hours": session.get("estimated_hours", 1.0),
                        "contents": session.get("contents", []),
                    }
                )
        _log_step(
            commit_logger,
            commit_id,
            "build_sessions_response",
            "success",
            sessions_returned=len(sessions_response),
        )

        timings["total"] = round(time.perf_counter() - total_start, 2)

        # ── Verification step ──────────────────────────────────────────
        # Confirm the graph was written correctly before reporting success.
        # This catches partial writes (e.g. Plan created but Sessions missing).
        _log_step(commit_logger, commit_id, "verify_commit", "start")
        verification = _verify_commit(neo4j, user_id, plan_id, len(session_ids))
        if not verification["ok"]:
            commit_logger.error(
                "commit_id=%s step=verify_commit status=failed details=%s",
                commit_id,
                verification,
            )
            # Attempt cleanup of the partially written plan.
            _cleanup_partial_commit(neo4j, user_id, plan_id)
            return {
                "success": False,
                "error": f"Commit verification failed: {verification}",
                "plan_id": plan_id,
            }
        _log_step(
            commit_logger,
            commit_id,
            "verify_commit",
            "success",
            details=verification,
        )

        _log_step(
            commit_logger,
            commit_id,
            "commit_study_plan",
            "success",
            plan_id=plan_id,
            sessions_created=len(session_ids),
            timings=timings,
            calendar_sync=calendar_sync,
            backlog_sync=backlog_sync,
        )
        invalidate_active_plan_cache(user_id)

        return {
            "success": True,
            "plan_id": plan_id,
            "sessions_created": len(session_ids),
            "sessions": sessions_response,
            "backlog_sync": backlog_sync,
            "calendar_sync": calendar_sync,
            "message": f"Plan committed with {len(session_ids)} sessions.",
        }

    except Exception as e:
        import traceback

        traceback.print_exc()
        commit_logger.exception(
            "commit_id=%s step=commit_study_plan status=failed error=%s",
            commit_id,
            e,
        )
        return {"success": False, "error": str(e)}
