"""Generate a realistic local dummy dataset for planner/rescheduler testing."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_MODELS = ROOT / "data_models"


def write_json(name: str, payload: object) -> None:
    path = DATA_MODELS / name
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path.relative_to(ROOT)}")


def content(name: str, match_key: str, subject: str, chapter: str, kind: str = "subtopic") -> dict:
    return {
        "name": name,
        "match_key": match_key,
        "subjects": [subject],
        "chapters": [chapter],
        "type": kind,
    }


def alloc(subject: str, chapter: str, hours: float) -> dict:
    return {"subject": subject, "chapter": chapter, "hours": hours}


def build_commitments() -> dict:
    return {
        "2026-06-24": [
            {"title": "Protected sleep window", "start": "23:30", "end": "06:30", "source": "user_rest_window"},
        ],
        "2026-06-25": [
            {"title": "Protected sleep window", "start": "23:30", "end": "06:30", "source": "user_rest_window"},
            {"title": "Doctor follow-up", "start": "18:30", "end": "19:30", "source": "user_commitment"},
        ],
        "2026-06-26": [
            {"title": "Protected sleep window", "start": "23:30", "end": "06:30", "source": "user_rest_window"},
            {"title": "Family prayer visit", "start": "19:00", "end": "20:00", "source": "user_commitment"},
        ],
        "2026-06-27": [
            {"title": "Protected sleep window", "start": "23:30", "end": "06:30", "source": "user_rest_window"},
            {"title": "Cousin visit", "start": "10:30", "end": "12:00", "source": "user_commitment"},
        ],
        "2026-06-28": [
            {"title": "Protected sleep window", "start": "23:30", "end": "06:30", "source": "user_rest_window"},
            {"title": "Weekly room cleanup", "start": "16:00", "end": "17:00", "source": "user_commitment"},
        ],
        "2026-06-29": [
            {"title": "Protected sleep window", "start": "23:30", "end": "06:30", "source": "user_rest_window"},
            {"title": "Phone-off family dinner", "start": "20:00", "end": "21:00", "source": "user_commitment"},
        ],
        "2026-06-30": [
            {"title": "Protected sleep window", "start": "23:30", "end": "06:30", "source": "user_rest_window"},
        ],
    }


def build_calendar_blocks() -> list[dict]:
    """Mirror the visible time-blocking events from the screenshots."""

    return [
        {"date": "2026-06-24", "start_time": "11:30", "end_time": "12:15", "title": "Lunch", "source": "google_calendar"},
        {"date": "2026-06-24", "start_time": "12:30", "end_time": "13:00", "title": "Daily Standup", "source": "google_calendar"},
        {"date": "2026-06-24", "start_time": "13:00", "end_time": "13:15", "title": "Decompress", "source": "google_calendar"},
        {"date": "2026-06-24", "start_time": "13:15", "end_time": "17:15", "title": "Focus time", "source": "google_calendar"},
        {"date": "2026-06-25", "start_time": "11:30", "end_time": "12:15", "title": "Lunch", "source": "google_calendar"},
        {"date": "2026-06-25", "start_time": "12:30", "end_time": "13:00", "title": "Daily Standup", "source": "google_calendar"},
        {"date": "2026-06-25", "start_time": "13:00", "end_time": "13:15", "title": "Decompress", "source": "google_calendar"},
        {"date": "2026-06-25", "start_time": "13:15", "end_time": "17:15", "title": "Focus time", "source": "google_calendar"},
        {"date": "2026-06-26", "start_time": "11:30", "end_time": "12:15", "title": "Lunch", "source": "google_calendar"},
        {"date": "2026-06-26", "start_time": "12:30", "end_time": "13:00", "title": "Daily Standup", "source": "google_calendar"},
        {"date": "2026-06-26", "start_time": "13:00", "end_time": "13:15", "title": "Decompress", "source": "google_calendar"},
        {"date": "2026-06-26", "start_time": "13:15", "end_time": "17:15", "title": "Focus time", "source": "google_calendar"},
        {"date": "2026-06-29", "start_time": "11:30", "end_time": "12:15", "title": "Lunch", "source": "google_calendar"},
        {"date": "2026-06-29", "start_time": "12:30", "end_time": "13:00", "title": "Daily Standup", "source": "google_calendar"},
        {"date": "2026-06-29", "start_time": "13:00", "end_time": "13:15", "title": "Decompress", "source": "google_calendar"},
        {"date": "2026-06-29", "start_time": "13:15", "end_time": "17:15", "title": "Focus time", "source": "google_calendar"},
        {"date": "2026-06-30", "start_time": "08:00", "end_time": "11:00", "title": "Focus time", "source": "google_calendar"},
        {"date": "2026-06-30", "start_time": "11:30", "end_time": "12:15", "title": "Lunch", "source": "google_calendar"},
        {"date": "2026-06-30", "start_time": "12:30", "end_time": "13:00", "title": "Daily Standup", "source": "google_calendar"},
        {"date": "2026-06-30", "start_time": "13:00", "end_time": "13:15", "title": "Decompress", "source": "google_calendar"},
        {"date": "2026-06-30", "start_time": "13:15", "end_time": "17:00", "title": "Focus time", "source": "google_calendar"},
        {"date": "2026-06-30", "start_time": "17:00", "end_time": "18:00", "title": "Live commit threaded backlog test", "source": "google_calendar"},
    ]


def build_available_time_windows() -> dict:
    return {
        "2026-06-24": [
            {"start": "06:30", "end": "11:30"},
            {"start": "12:15", "end": "12:30"},
            {"start": "17:15", "end": "23:30"},
        ],
        "2026-06-25": [
            {"start": "06:30", "end": "11:30"},
            {"start": "12:15", "end": "12:30"},
            {"start": "17:15", "end": "18:30"},
            {"start": "19:30", "end": "23:30"},
        ],
        "2026-06-26": [
            {"start": "06:30", "end": "11:30"},
            {"start": "12:15", "end": "12:30"},
            {"start": "17:15", "end": "19:00"},
            {"start": "20:00", "end": "23:30"},
        ],
        "2026-06-27": [
            {"start": "06:30", "end": "10:30"},
            {"start": "12:00", "end": "23:30"},
        ],
        "2026-06-28": [
            {"start": "06:30", "end": "16:00"},
            {"start": "17:00", "end": "23:30"},
        ],
        "2026-06-29": [
            {"start": "06:30", "end": "11:30"},
            {"start": "12:15", "end": "12:30"},
            {"start": "17:15", "end": "20:00"},
            {"start": "21:00", "end": "23:30"},
        ],
        "2026-06-30": [
            {"start": "06:30", "end": "08:00"},
            {"start": "11:00", "end": "11:30"},
            {"start": "12:15", "end": "12:30"},
            {"start": "18:00", "end": "23:00"},
        ],
    }


def build_intake_output() -> dict:
    commitments = build_commitments()
    return {
        "status": "approved",
        "message": (
            "The study contract is locked for planner handoff. Use the 24 June to 30 June "
            "window, keep the 30 June 11:00 PM cutoff hard, and preserve the commitments "
            "and calendar blockers already reflected below."
        ),
        "goal": {
            "title": "Current-week revision block ending 30 June",
            "subjects": ["Mathematics", "Science", "Social Science"],
            "start_date": "2026-06-24",
            "end_date": "2026-06-30",
            "deadline_datetime": "2026-06-30T23:00:00+05:30",
            "study_scope": [
                {
                    "subject": "Mathematics",
                    "chapter": "Surface Areas and Volumes",
                    "intent": "Clean up formula retention and application mistakes before the week closes.",
                },
                {
                    "subject": "Mathematics",
                    "chapter": "Arithmetic Progressions",
                    "intent": "Finish direct-question practice and word-problem translation.",
                },
                {
                    "subject": "Science",
                    "chapter": "Control and Coordination",
                    "intent": "Repair concept gaps and diagram recall while energy is still decent.",
                },
                {
                    "subject": "Science",
                    "chapter": "Light - Reflection and Refraction",
                    "intent": "Fix numericals and sign-convention confusion.",
                },
                {
                    "subject": "Social Science",
                    "chapter": "Nationalism in India",
                    "intent": "Retain the timeline and source-map material with light review passes.",
                },
                {
                    "subject": "Social Science",
                    "chapter": "Resources and Development",
                    "intent": "Keep one selective revision track alive without letting it consume the whole week.",
                },
            ],
        },
        "availability": {
            "timezone": "Asia/Kolkata",
            "daily_study_hours": {
                "2026-06-24": 4.0,
                "2026-06-25": 3.5,
                "2026-06-26": 3.5,
                "2026-06-27": 3.5,
                "2026-06-28": 3.0,
                "2026-06-29": 2.5,
                "2026-06-30": 0.5,
            },
            "time_blocks": commitments,
            "planning_notes": [
                "Calendar-owned midday blockers are already heavy on 24, 25, 26, 29, and 30.",
                "The student can do better in morning or late-evening windows than in fragmented noon windows.",
                "30 June should stay as a very light landing day.",
                "Do not treat focus-time calendar blocks as free study windows.",
                "Visible calendar blocks should win over any optimistic scheduling instinct.",
            ],
        },
        "study_items": [
            {
                "scope_reference_key": "mathematics|surface_areas_and_volumes",
                "subject": "Mathematics",
                "chapter": "Surface Areas and Volumes",
                "estimated_hours": 4.0,
                "reason": "Still leaking marks on formula recall and mixed shape application.",
                "planning_notes": [
                    "Use this in clear-headed slots.",
                    "Keep formula recall close to practice, not isolated.",
                ],
                "remaining_subtopics": [
                    "mathematics_surface_area_formula_recall",
                    "mathematics_surface_area_cylinder_cone_mixed_questions",
                    "mathematics_surface_area_frustum_word_problems",
                    "mathematics_volume_conversion_units_errors",
                ],
            },
            {
                "scope_reference_key": "mathematics|arithmetic_progressions",
                "subject": "Mathematics",
                "chapter": "Arithmetic Progressions",
                "estimated_hours": 3.5,
                "reason": "Needs one more cycle of direct questions plus short word-problem translation work.",
                "planning_notes": [
                    "Keep AP practice compact and finishable.",
                ],
                "remaining_subtopics": [
                    "mathematics_ap_nth_term_direct_questions",
                    "mathematics_ap_sum_of_n_terms_practice",
                    "mathematics_ap_word_problem_translation",
                ],
            },
            {
                "scope_reference_key": "science|control_and_coordination",
                "subject": "Science",
                "chapter": "Control and Coordination",
                "estimated_hours": 4.0,
                "reason": "This chapter still has unstable recall and diagram confidence.",
                "planning_notes": [
                    "Prefer concept-plus-diagram pairings.",
                ],
                "remaining_subtopics": [
                    "science_control_coordination_reflex_arc_diagram",
                    "science_control_coordination_neuron_signal_path",
                    "science_control_coordination_hormones_table_recall",
                    "science_control_coordination_plant_tropism_examples",
                ],
            },
            {
                "scope_reference_key": "science|light_reflection_and_refraction",
                "subject": "Science",
                "chapter": "Light - Reflection and Refraction",
                "estimated_hours": 3.5,
                "reason": "Still needs numerical confidence and cleaner ray-diagram accuracy.",
                "planning_notes": [
                    "Do this where uninterrupted concentration is available.",
                ],
                "remaining_subtopics": [
                    "science_light_mirror_formula_sign_convention",
                    "science_light_lens_formula_numericals",
                    "science_light_ray_diagram_image_formation",
                    "science_light_magnification_direct_questions",
                ],
            },
            {
                "scope_reference_key": "social_science|nationalism_in_india",
                "subject": "Social Science",
                "chapter": "Nationalism in India",
                "estimated_hours": 2.5,
                "reason": "Works best as short review passes without stealing too much math/science time.",
                "planning_notes": [
                    "Use short recap slots, not giant reading blocks.",
                ],
                "remaining_subtopics": [
                    "sst_nationalism_timeline_gandhi_movements",
                    "sst_nationalism_congress_sessions_recall",
                    "sst_nationalism_visual_symbols_and_sources",
                    "sst_nationalism_map_linked_locations",
                ],
            },
            {
                "scope_reference_key": "social_science|resources_and_development",
                "subject": "Social Science",
                "chapter": "Resources and Development",
                "estimated_hours": 2.0,
                "reason": "Selective coverage only, but still worth keeping alive for breadth.",
                "planning_notes": [
                    "This is the most cuttable item if a squeeze happens.",
                ],
                "remaining_subtopics": [
                    "sst_resources_soil_types_recall",
                    "sst_resources_resource_classification_table",
                    "sst_resources_conservation_keywords",
                    "sst_resources_map_single_revision_cycle",
                ],
            },
        ],
    }


def build_scheduling_context(intake_output: dict) -> dict:
    return {
        "timezone": intake_output["availability"]["timezone"],
        "daily_study_hours": intake_output["availability"]["daily_study_hours"],
        "time_blocks": intake_output["availability"]["time_blocks"],
        "calendar_blocks": build_calendar_blocks(),
        "available_time_windows": build_available_time_windows(),
    }


def build_study_plan() -> dict:
    return {
        "plan_id": "demo_plan_20260624_current_week",
        "total_hours": 19.5,
        "days": [
            {
                "day_num": 1,
                "date": "2026-06-24",
                "total_hours": 4.0,
                "capacity_hours": 4.0,
                "sessions": [
                    {
                        "session_id": "sess_20260624_01",
                        "title": "Surface Areas formula and recall cleanup",
                        "session_type": "focused_chapter",
                        "estimated_hours": 1.5,
                        "start_time": "06:45",
                        "end_time": "08:15",
                        "allocated_hours": [alloc("Mathematics", "Surface Areas and Volumes", 1.5)],
                        "contents": [
                            content("Surface area formula recall", "mathematics_surface_area_formula_recall", "Mathematics", "Surface Areas and Volumes", "revision"),
                            content("Cylinder and cone mixed questions", "mathematics_surface_area_cylinder_cone_mixed_questions", "Mathematics", "Surface Areas and Volumes", "practice"),
                        ],
                    },
                    {
                        "session_id": "sess_20260624_02",
                        "title": "Control and Coordination concept repair",
                        "session_type": "focused_chapter",
                        "estimated_hours": 1.5,
                        "start_time": "17:45",
                        "end_time": "19:15",
                        "allocated_hours": [alloc("Science", "Control and Coordination", 1.5)],
                        "contents": [
                            content("Neuron signal path", "science_control_coordination_neuron_signal_path", "Science", "Control and Coordination"),
                            content("Reflex arc diagram", "science_control_coordination_reflex_arc_diagram", "Science", "Control and Coordination"),
                        ],
                    },
                    {
                        "session_id": "sess_20260624_03",
                        "title": "Nationalism short confidence pass",
                        "session_type": "review",
                        "estimated_hours": 1.0,
                        "start_time": "20:00",
                        "end_time": "21:00",
                        "allocated_hours": [alloc("Social Science", "Nationalism in India", 1.0)],
                        "contents": [
                            content("Gandhi movement timeline", "sst_nationalism_timeline_gandhi_movements", "Social Science", "Nationalism in India", "revision"),
                        ],
                    },
                ],
            },
            {
                "day_num": 2,
                "date": "2026-06-25",
                "total_hours": 3.0,
                "capacity_hours": 3.5,
                "sessions": [
                    {
                        "session_id": "sess_20260625_01",
                        "title": "Light sign convention and core numericals",
                        "session_type": "practice",
                        "estimated_hours": 1.5,
                        "start_time": "07:00",
                        "end_time": "08:30",
                        "allocated_hours": [alloc("Science", "Light - Reflection and Refraction", 1.5)],
                        "contents": [
                            content("Mirror formula sign convention", "science_light_mirror_formula_sign_convention", "Science", "Light - Reflection and Refraction"),
                            content("Lens formula numericals", "science_light_lens_formula_numericals", "Science", "Light - Reflection and Refraction", "practice"),
                        ],
                    },
                    {
                        "session_id": "sess_20260625_02",
                        "title": "Arithmetic Progressions direct practice",
                        "session_type": "practice",
                        "estimated_hours": 1.5,
                        "start_time": "20:00",
                        "end_time": "21:30",
                        "allocated_hours": [alloc("Mathematics", "Arithmetic Progressions", 1.5)],
                        "contents": [
                            content("AP nth term direct questions", "mathematics_ap_nth_term_direct_questions", "Mathematics", "Arithmetic Progressions", "practice"),
                            content("AP sum of n terms practice", "mathematics_ap_sum_of_n_terms_practice", "Mathematics", "Arithmetic Progressions", "practice"),
                        ],
                    },
                ],
            },
            {
                "day_num": 3,
                "date": "2026-06-26",
                "total_hours": 3.0,
                "capacity_hours": 3.5,
                "sessions": [
                    {
                        "session_id": "sess_20260626_01",
                        "title": "Surface Areas frustum drill",
                        "session_type": "practice",
                        "estimated_hours": 1.0,
                        "start_time": "07:00",
                        "end_time": "08:00",
                        "allocated_hours": [alloc("Mathematics", "Surface Areas and Volumes", 1.0)],
                        "contents": [
                            content("Frustum word problems", "mathematics_surface_area_frustum_word_problems", "Mathematics", "Surface Areas and Volumes", "practice"),
                        ],
                    },
                    {
                        "session_id": "sess_20260626_02",
                        "title": "Control and Coordination hormone repair",
                        "session_type": "focused_chapter",
                        "estimated_hours": 1.0,
                        "start_time": "08:30",
                        "end_time": "09:30",
                        "allocated_hours": [alloc("Science", "Control and Coordination", 1.0)],
                        "contents": [
                            content("Hormones table recall", "science_control_coordination_hormones_table_recall", "Science", "Control and Coordination"),
                        ],
                    },
                    {
                        "session_id": "sess_20260626_03",
                        "title": "Resources selective recap",
                        "session_type": "review",
                        "estimated_hours": 1.0,
                        "start_time": "20:30",
                        "end_time": "21:30",
                        "allocated_hours": [alloc("Social Science", "Resources and Development", 1.0)],
                        "contents": [
                            content("Soil types recall", "sst_resources_soil_types_recall", "Social Science", "Resources and Development", "revision"),
                            content("Resource classification table", "sst_resources_resource_classification_table", "Social Science", "Resources and Development", "revision"),
                        ],
                    },
                ],
            },
            {
                "day_num": 4,
                "date": "2026-06-27",
                "total_hours": 3.5,
                "capacity_hours": 3.5,
                "sessions": [
                    {
                        "session_id": "sess_20260627_01",
                        "title": "Light ray diagrams and application",
                        "session_type": "practice",
                        "estimated_hours": 2.0,
                        "start_time": "07:00",
                        "end_time": "09:00",
                        "allocated_hours": [alloc("Science", "Light - Reflection and Refraction", 2.0)],
                        "contents": [
                            content("Ray diagram image formation", "science_light_ray_diagram_image_formation", "Science", "Light - Reflection and Refraction"),
                            content("Magnification direct questions", "science_light_magnification_direct_questions", "Science", "Light - Reflection and Refraction", "practice"),
                        ],
                    },
                    {
                        "session_id": "sess_20260627_02",
                        "title": "Arithmetic Progressions short follow-up",
                        "session_type": "practice",
                        "estimated_hours": 1.0,
                        "start_time": "12:30",
                        "end_time": "13:30",
                        "allocated_hours": [alloc("Mathematics", "Arithmetic Progressions", 1.0)],
                        "contents": [
                            content("AP word problem translation", "mathematics_ap_word_problem_translation", "Mathematics", "Arithmetic Progressions", "practice"),
                        ],
                    },
                    {
                        "session_id": "sess_20260627_03",
                        "title": "Nationalism source recap",
                        "session_type": "review",
                        "estimated_hours": 0.5,
                        "start_time": "18:30",
                        "end_time": "19:00",
                        "allocated_hours": [alloc("Social Science", "Nationalism in India", 0.5)],
                        "contents": [
                            content("Visual symbols and sources", "sst_nationalism_visual_symbols_and_sources", "Social Science", "Nationalism in India", "revision"),
                        ],
                    },
                ],
            },
            {
                "day_num": 5,
                "date": "2026-06-28",
                "total_hours": 3.0,
                "capacity_hours": 3.0,
                "sessions": [
                    {
                        "session_id": "sess_20260628_01",
                        "title": "Surface Areas final mixed corrections",
                        "session_type": "practice",
                        "estimated_hours": 1.5,
                        "start_time": "07:00",
                        "end_time": "08:30",
                        "allocated_hours": [alloc("Mathematics", "Surface Areas and Volumes", 1.5)],
                        "contents": [
                            content("Volume conversion unit errors", "mathematics_volume_conversion_units_errors", "Mathematics", "Surface Areas and Volumes", "practice"),
                        ],
                    },
                    {
                        "session_id": "sess_20260628_02",
                        "title": "Resources plus short nationalism pass",
                        "session_type": "mixed",
                        "estimated_hours": 1.5,
                        "start_time": "17:30",
                        "end_time": "19:00",
                        "allocated_hours": [
                            alloc("Social Science", "Resources and Development", 1.0),
                            alloc("Social Science", "Nationalism in India", 0.5),
                        ],
                        "contents": [
                            content("Conservation keywords", "sst_resources_conservation_keywords", "Social Science", "Resources and Development", "revision"),
                            content("Map single revision cycle", "sst_resources_map_single_revision_cycle", "Social Science", "Resources and Development", "revision"),
                            content("Map-linked locations", "sst_nationalism_map_linked_locations", "Social Science", "Nationalism in India", "revision"),
                        ],
                    },
                ],
            },
            {
                "day_num": 6,
                "date": "2026-06-29",
                "total_hours": 2.5,
                "capacity_hours": 2.5,
                "sessions": [
                    {
                        "session_id": "sess_20260629_01",
                        "title": "Control and Coordination final recap",
                        "session_type": "review",
                        "estimated_hours": 1.5,
                        "start_time": "06:45",
                        "end_time": "08:15",
                        "allocated_hours": [alloc("Science", "Control and Coordination", 1.5)],
                        "contents": [
                            content("Plant tropism examples", "science_control_coordination_plant_tropism_examples", "Science", "Control and Coordination", "revision"),
                        ],
                    },
                    {
                        "session_id": "sess_20260629_02",
                        "title": "Arithmetic Progressions confidence pass",
                        "session_type": "review",
                        "estimated_hours": 1.0,
                        "start_time": "17:45",
                        "end_time": "18:45",
                        "allocated_hours": [alloc("Mathematics", "Arithmetic Progressions", 1.0)],
                        "contents": [
                            content("AP final confidence pass", "mathematics_ap_sum_of_n_terms_practice", "Mathematics", "Arithmetic Progressions", "revision"),
                        ],
                    },
                ],
            },
            {
                "day_num": 7,
                "date": "2026-06-30",
                "total_hours": 0.5,
                "capacity_hours": 0.5,
                "sessions": [
                    {
                        "session_id": "sess_20260630_01",
                        "title": "Nationalism final recall tap",
                        "session_type": "review",
                        "estimated_hours": 0.5,
                        "start_time": "18:30",
                        "end_time": "19:00",
                        "allocated_hours": [alloc("Social Science", "Nationalism in India", 0.5)],
                        "contents": [
                            content("Congress sessions recall", "sst_nationalism_congress_sessions_recall", "Social Science", "Nationalism in India", "revision"),
                        ],
                    },
                ],
            },
        ],
    }


def build_progress_budget(intake_output: dict) -> dict:
    items = {item["scope_reference_key"]: item for item in intake_output["study_items"]}
    return {
        "mathematics|surface_areas_and_volumes": {
            "subject": "Mathematics",
            "chapter": "Surface Areas and Volumes",
            "total": 4.0,
            "spent": 1.0,
            "remaining": 3.0,
            "completed_subtopics": ["Surface area formula recall"],
            "pending_subtopics": [
                "Cylinder and cone mixed questions",
                "Frustum word problems",
                "Volume conversion unit errors",
            ],
            "completed_match_keys": ["mathematics_surface_area_formula_recall"],
            "pending_match_keys": [
                "mathematics_surface_area_cylinder_cone_mixed_questions",
                "mathematics_surface_area_frustum_word_problems",
                "mathematics_volume_conversion_units_errors",
            ],
            "reason": items["mathematics|surface_areas_and_volumes"]["reason"],
            "planning_notes": items["mathematics|surface_areas_and_volumes"]["planning_notes"],
            "remaining_subtopics": items["mathematics|surface_areas_and_volumes"]["remaining_subtopics"],
        },
        "mathematics|arithmetic_progressions": {
            "subject": "Mathematics",
            "chapter": "Arithmetic Progressions",
            "total": 3.5,
            "spent": 0.0,
            "remaining": 3.5,
            "completed_subtopics": [],
            "pending_subtopics": [
                "AP nth term direct questions",
                "AP sum of n terms practice",
                "AP word problem translation",
            ],
            "completed_match_keys": [],
            "pending_match_keys": [
                "mathematics_ap_nth_term_direct_questions",
                "mathematics_ap_sum_of_n_terms_practice",
                "mathematics_ap_word_problem_translation",
            ],
            "reason": items["mathematics|arithmetic_progressions"]["reason"],
            "planning_notes": items["mathematics|arithmetic_progressions"]["planning_notes"],
            "remaining_subtopics": items["mathematics|arithmetic_progressions"]["remaining_subtopics"],
        },
        "science|control_and_coordination": {
            "subject": "Science",
            "chapter": "Control and Coordination",
            "total": 4.0,
            "spent": 0.75,
            "remaining": 3.25,
            "completed_subtopics": [],
            "pending_subtopics": [
                "Reflex arc diagram",
                "Neuron signal path",
                "Hormones table recall",
                "Plant tropism examples",
            ],
            "completed_match_keys": [],
            "pending_match_keys": [
                "science_control_coordination_reflex_arc_diagram",
                "science_control_coordination_neuron_signal_path",
                "science_control_coordination_hormones_table_recall",
                "science_control_coordination_plant_tropism_examples",
            ],
            "reason": items["science|control_and_coordination"]["reason"],
            "planning_notes": items["science|control_and_coordination"]["planning_notes"],
            "remaining_subtopics": items["science|control_and_coordination"]["remaining_subtopics"],
        },
        "science|light_reflection_and_refraction": {
            "subject": "Science",
            "chapter": "Light - Reflection and Refraction",
            "total": 3.5,
            "spent": 0.0,
            "remaining": 3.5,
            "completed_subtopics": [],
            "pending_subtopics": [
                "Mirror formula sign convention",
                "Lens formula numericals",
                "Ray diagram image formation",
                "Magnification direct questions",
            ],
            "completed_match_keys": [],
            "pending_match_keys": [
                "science_light_mirror_formula_sign_convention",
                "science_light_lens_formula_numericals",
                "science_light_ray_diagram_image_formation",
                "science_light_magnification_direct_questions",
            ],
            "reason": items["science|light_reflection_and_refraction"]["reason"],
            "planning_notes": items["science|light_reflection_and_refraction"]["planning_notes"],
            "remaining_subtopics": items["science|light_reflection_and_refraction"]["remaining_subtopics"],
        },
        "social_science|nationalism_in_india": {
            "subject": "Social Science",
            "chapter": "Nationalism in India",
            "total": 2.5,
            "spent": 0.0,
            "remaining": 2.5,
            "completed_subtopics": [],
            "pending_subtopics": [
                "Gandhi movement timeline",
                "Congress sessions recall",
                "Visual symbols and sources",
                "Map-linked locations",
            ],
            "completed_match_keys": [],
            "pending_match_keys": [
                "sst_nationalism_timeline_gandhi_movements",
                "sst_nationalism_congress_sessions_recall",
                "sst_nationalism_visual_symbols_and_sources",
                "sst_nationalism_map_linked_locations",
            ],
            "reason": items["social_science|nationalism_in_india"]["reason"],
            "planning_notes": items["social_science|nationalism_in_india"]["planning_notes"],
            "remaining_subtopics": items["social_science|nationalism_in_india"]["remaining_subtopics"],
        },
        "social_science|resources_and_development": {
            "subject": "Social Science",
            "chapter": "Resources and Development",
            "total": 2.0,
            "spent": 0.0,
            "remaining": 2.0,
            "completed_subtopics": [],
            "pending_subtopics": [
                "Soil types recall",
                "Resource classification table",
                "Conservation keywords",
                "Map single revision cycle",
            ],
            "completed_match_keys": [],
            "pending_match_keys": [
                "sst_resources_soil_types_recall",
                "sst_resources_resource_classification_table",
                "sst_resources_conservation_keywords",
                "sst_resources_map_single_revision_cycle",
            ],
            "reason": items["social_science|resources_and_development"]["reason"],
            "planning_notes": items["social_science|resources_and_development"]["planning_notes"],
            "remaining_subtopics": items["social_science|resources_and_development"]["remaining_subtopics"],
        },
    }


def build_active_plan_snapshot(intake_output: dict, study_plan: dict) -> dict:
    days = []
    for day in study_plan["days"]:
        sessions = []
        for session in day["sessions"]:
            session_copy = {
                **session,
                "actual_time": 0.0,
                "status": "pending",
                "contents": [
                    {**item, "status": "pending", "time_spent": 0.0}
                    for item in session["contents"]
                ],
            }
            sessions.append(session_copy)
        days.append(
            {
                "day_num": day["day_num"],
                "date": day["date"],
                "capacity_hours": day["capacity_hours"],
                "total_hours": day["total_hours"],
                "sessions": sessions,
            }
        )

    days[0]["sessions"][0]["status"] = "partial"
    days[0]["sessions"][0]["actual_time"] = 1.0
    days[0]["sessions"][0]["contents"][0]["status"] = "done"
    days[0]["sessions"][0]["contents"][0]["time_spent"] = 1.0

    days[0]["sessions"][1]["status"] = "partial"
    days[0]["sessions"][1]["actual_time"] = 0.75
    days[0]["sessions"][1]["contents"][0]["status"] = "partial"
    days[0]["sessions"][1]["contents"][0]["time_spent"] = 0.75

    progress = build_progress_budget(intake_output)

    return {
        "has_plan": True,
        "plan_details": {
            "plan_id": study_plan["plan_id"],
            "plan_name": "Current-week demo plan with live blockers",
            "status": "ACTIVE",
            "total_hours": study_plan["total_hours"],
            "start_date": "2026-06-24",
            "end_date": "2026-06-30",
            "intake_snapshot": intake_output,
            "days": days,
            "progress": {
                "work_item_budget": progress,
            },
        },
    }


def main() -> None:
    intake_output = build_intake_output()
    commitments = build_commitments()
    calendar_blocks = build_calendar_blocks()
    scheduling_context = build_scheduling_context(intake_output)
    study_plan = build_study_plan()
    active_plan_snapshot = build_active_plan_snapshot(intake_output, study_plan)

    bundle = {
        "intake_output": intake_output,
        "commitments": commitments,
        "calendar_blocks": calendar_blocks,
        "scheduling_context": scheduling_context,
        "study_plan": study_plan,
        "active_plan_snapshot": active_plan_snapshot,
    }

    write_json("rescheduler_demo_intake_output.json", intake_output)
    write_json("rescheduler_demo_commitments.json", commitments)
    write_json("rescheduler_demo_calendar_blocks.json", calendar_blocks)
    write_json("rescheduler_demo_plan.json", study_plan)
    write_json("rescheduler_demo_active_plan_snapshot.json", active_plan_snapshot)
    write_json("rescheduler_demo_bundle.json", bundle)


if __name__ == "__main__":
    main()
