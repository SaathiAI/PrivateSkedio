"""
Backlog seeder for intake agent testing — 12 diverse entries.
Run: python seed_backlog.py

Subjects covered: Mathematics, Science, English, Social Science, Hindi
Statuses: DONE, IN_PROGRESS, PENDING
Priorities: HIGH, MEDIUM, LOW
"""

import asyncio
from src.database.vector_store import VectorStore  # adjust to your actual import path

TEST_USER_ID = "test_user_99"

MOCK_ENTRIES = [

    # ── 1. Math | Trigonometry — DONE ────────────────────────────────────────
    # Full overlap test. Agent should not re-add as new topic.
    {
        "match_key": "mathematics|trigonometry",
        "data": {
            "chapter": "Trigonometry",
            "subject": "Mathematics",
            "status": "DONE",
            "priority": "LOW",
            "difficulty_signal": "easy",
            "mastery_level": "MASTERED",
            "study_mode": "normal",
            "hours_actual": 4.5,
            "subtopics": [
                "mathematics_trigonometry_sine_rule",
                "mathematics_trigonometry_cosine_rule",
                "mathematics_trigonometry_identities",
            ],
            "subtopics_completed": [
                "mathematics_trigonometry_sine_rule",
                "mathematics_trigonometry_cosine_rule",
                "mathematics_trigonometry_identities",
            ],
            "subtopics_remaining": [],
            "content_match_keys": ["mathematics|trigonometry"],
            "last_studied": "2026-04-26T06:30:00+00:00",
        },
    },

    # ── 2. Math | Quadratic Equations — PENDING ───────────────────────────────
    # Never started. Should surface as high priority backlog.
    {
        "match_key": "mathematics|quadratic_equations",
        "data": {
            "chapter": "Quadratic Equations",
            "subject": "Mathematics",
            "status": "PENDING",
            "priority": "HIGH",
            "difficulty_signal": "medium",
            "mastery_level": "NOT_STARTED",
            "study_mode": "normal",
            "hours_actual": 0.0,
            "subtopics": [
                "mathematics_quadratic_factoring",
                "mathematics_quadratic_formula",
                "mathematics_quadratic_discriminant",
            ],
            "subtopics_completed": [],
            "subtopics_remaining": [
                "mathematics_quadratic_factoring",
                "mathematics_quadratic_formula",
                "mathematics_quadratic_discriminant",
            ],
            "content_match_keys": ["mathematics|quadratic_equations"],
            "last_studied": "",
        },
    },

    # ── 3. Math | Statistics — IN_PROGRESS ───────────────────────────────────
    # Half done. Tests time leftover calculation.
    {
        "match_key": "mathematics|statistics",
        "data": {
            "chapter": "Statistics",
            "subject": "Mathematics",
            "status": "IN_PROGRESS",
            "priority": "MEDIUM",
            "difficulty_signal": "easy",
            "mastery_level": "PARTIAL",
            "study_mode": "normal",
            "hours_actual": 1.5,
            "subtopics": [
                "mathematics_statistics_mean_median_mode",
                "mathematics_statistics_cumulative_frequency",
                "mathematics_statistics_ogive",
            ],
            "subtopics_completed": [
                "mathematics_statistics_mean_median_mode",
            ],
            "subtopics_remaining": [
                "mathematics_statistics_cumulative_frequency",
                "mathematics_statistics_ogive",
            ],
            "content_match_keys": ["mathematics|statistics"],
            "last_studied": "2026-04-27T09:00:00+00:00",
        },
    },

    # ── 4. Math | Coordinate Geometry — DONE (rushed) ────────────────────────
    # Tests: should agent flag this for a quick revision pass?
    {
        "match_key": "mathematics|coordinate_geometry",
        "data": {
            "chapter": "Coordinate Geometry",
            "subject": "Mathematics",
            "status": "DONE",
            "priority": "LOW",
            "difficulty_signal": "medium",
            "mastery_level": "MODERATE",
            "study_mode": "normal",
            "hours_actual": 2.0,
            "subtopics": [
                "mathematics_coord_distance_formula",
                "mathematics_coord_section_formula",
                "mathematics_coord_area_of_triangle",
            ],
            "subtopics_completed": [
                "mathematics_coord_distance_formula",
                "mathematics_coord_section_formula",
                "mathematics_coord_area_of_triangle",
            ],
            "subtopics_remaining": [],
            "content_match_keys": ["mathematics|coordinate_geometry"],
            "last_studied": "2026-04-25T11:00:00+00:00",
        },
    },

    # ── 5. Science | Electricity — IN_PROGRESS ────────────────────────────────
    # 2 of 4 subtopics done. Tests partial overlap + remaining time factoring.
    {
        "match_key": "science|electricity",
        "data": {
            "chapter": "Electricity",
            "subject": "Science",
            "status": "IN_PROGRESS",
            "priority": "HIGH",
            "difficulty_signal": "hard",
            "mastery_level": "PARTIAL",
            "study_mode": "deep",
            "hours_actual": 2.0,
            "subtopics": [
                "science_electricity_ohms_law",
                "science_electricity_circuits",
                "science_electricity_resistance",
                "science_electricity_power",
            ],
            "subtopics_completed": [
                "science_electricity_ohms_law",
                "science_electricity_circuits",
            ],
            "subtopics_remaining": [
                "science_electricity_resistance",
                "science_electricity_power",
            ],
            "content_match_keys": ["science|electricity"],
            "last_studied": "2026-04-28T14:00:00+00:00",
        },
    },

    # ── 6. Science | Chemical Reactions — IN_PROGRESS (almost done) ──────────
    # Only 1 subtopic left. Tests: should agent nudge user to just finish it?
    {
        "match_key": "science|chemical_reactions",
        "data": {
            "chapter": "Chemical Reactions and Equations",
            "subject": "Science",
            "status": "IN_PROGRESS",
            "priority": "HIGH",
            "difficulty_signal": "medium",
            "mastery_level": "PARTIAL",
            "study_mode": "normal",
            "hours_actual": 3.0,
            "subtopics": [
                "science_chem_types_of_reactions",
                "science_chem_balancing_equations",
                "science_chem_oxidation_reduction",
                "science_chem_corrosion",
            ],
            "subtopics_completed": [
                "science_chem_types_of_reactions",
                "science_chem_balancing_equations",
                "science_chem_oxidation_reduction",
            ],
            "subtopics_remaining": [
                "science_chem_corrosion",
            ],
            "content_match_keys": ["science|chemical_reactions"],
            "last_studied": "2026-04-29T10:00:00+00:00",
        },
    },

    # ── 7. Science | Life Processes — PENDING ─────────────────────────────────
    # Untouched. High board weightage. Should surface as priority backlog.
    {
        "match_key": "science|life_processes",
        "data": {
            "chapter": "Life Processes",
            "subject": "Science",
            "status": "PENDING",
            "priority": "HIGH",
            "difficulty_signal": "medium",
            "mastery_level": "NOT_STARTED",
            "study_mode": "normal",
            "hours_actual": 0.0,
            "subtopics": [
                "science_life_nutrition",
                "science_life_respiration",
                "science_life_transportation",
                "science_life_excretion",
            ],
            "subtopics_completed": [],
            "subtopics_remaining": [
                "science_life_nutrition",
                "science_life_respiration",
                "science_life_transportation",
                "science_life_excretion",
            ],
            "content_match_keys": ["science|life_processes"],
            "last_studied": "",
        },
    },

    # ── 8. Science | Light Reflection and Refraction — DONE ──────────────────
    # Already done. Session 1 user asked to re-study this.
    # Tests: agent should detect overlap and confirm / skip.
    {
        "match_key": "science|light_reflection_refraction",
        "data": {
            "chapter": "Light - Reflection and Refraction",
            "subject": "Science",
            "status": "DONE",
            "priority": "LOW",
            "difficulty_signal": "medium",
            "mastery_level": "MASTERED",
            "study_mode": "normal",
            "hours_actual": 7.0,
            "subtopics": [
                "science_light_reflection_laws",
                "science_light_mirrors",
                "science_light_refraction_laws",
                "science_light_lenses",
                "science_light_human_eye",
            ],
            "subtopics_completed": [
                "science_light_reflection_laws",
                "science_light_mirrors",
                "science_light_refraction_laws",
                "science_light_lenses",
                "science_light_human_eye",
            ],
            "subtopics_remaining": [],
            "content_match_keys": ["science|light_reflection_refraction"],
            "last_studied": "2026-04-30T08:00:00+00:00",
        },
    },

    # ── 9. English | Essay Writing — PENDING ──────────────────────────────────
    # User typically skips English in intake. Tests graceful ignore handling.
    {
        "match_key": "english|essay_writing",
        "data": {
            "chapter": "Essay Writing",
            "subject": "English",
            "status": "PENDING",
            "priority": "MEDIUM",
            "difficulty_signal": "easy",
            "mastery_level": "NOT_STARTED",
            "study_mode": "normal",
            "hours_actual": 0.0,
            "subtopics": [
                "english_essay_introduction",
                "english_essay_body_paragraphs",
                "english_essay_conclusion",
            ],
            "subtopics_completed": [],
            "subtopics_remaining": [
                "english_essay_introduction",
                "english_essay_body_paragraphs",
                "english_essay_conclusion",
            ],
            "content_match_keys": ["english|essay_writing"],
            "last_studied": "",
        },
    },

    # ── 10. English | Letter Writing — IN_PROGRESS ────────────────────────────
    # Half done. Tests multi-subject session where English gets factored in.
    {
        "match_key": "english|letter_writing",
        "data": {
            "chapter": "Letter Writing",
            "subject": "English",
            "status": "IN_PROGRESS",
            "priority": "MEDIUM",
            "difficulty_signal": "easy",
            "mastery_level": "PARTIAL",
            "study_mode": "normal",
            "hours_actual": 1.0,
            "subtopics": [
                "english_letter_formal",
                "english_letter_informal",
            ],
            "subtopics_completed": [
                "english_letter_formal",
            ],
            "subtopics_remaining": [
                "english_letter_informal",
            ],
            "content_match_keys": ["english|letter_writing"],
            "last_studied": "2026-04-27T16:00:00+00:00",
        },
    },

    # ── 11. Social Science | Nationalism in India — PENDING ───────────────────
    # Untouched SST. Tests a subject the agent may not proactively suggest.
    # Also tests match when user says "history" vs "social science".
    {
        "match_key": "social_science|nationalism_in_india",
        "data": {
            "chapter": "Nationalism in India",
            "subject": "Social Science",
            "status": "PENDING",
            "priority": "HIGH",
            "difficulty_signal": "medium",
            "mastery_level": "NOT_STARTED",
            "study_mode": "normal",
            "hours_actual": 0.0,
            "subtopics": [
                "sst_nationalism_non_cooperation_movement",
                "sst_nationalism_civil_disobedience",
                "sst_nationalism_sense_of_collective_belonging",
            ],
            "subtopics_completed": [],
            "subtopics_remaining": [
                "sst_nationalism_non_cooperation_movement",
                "sst_nationalism_civil_disobedience",
                "sst_nationalism_sense_of_collective_belonging",
            ],
            "content_match_keys": ["social_science|nationalism_in_india"],
            "last_studied": "",
        },
    },

    # ── 12. Hindi | Kshitij Prose — IN_PROGRESS ───────────────────────────────
    # Non-STEM subject. Tests whether agent handles Hindi gracefully.
    {
        "match_key": "hindi|kshitij_prose",
        "data": {
            "chapter": "Kshitij - Prose Section",
            "subject": "Hindi",
            "status": "IN_PROGRESS",
            "priority": "LOW",
            "difficulty_signal": "easy",
            "mastery_level": "PARTIAL",
            "study_mode": "normal",
            "hours_actual": 1.5,
            "subtopics": [
                "hindi_kshitij_netaji_ka_chashma",
                "hindi_kshitij_balgobin_bhagat",
                "hindi_kshitij_lakhnavi_andaz",
            ],
            "subtopics_completed": [
                "hindi_kshitij_netaji_ka_chashma",
            ],
            "subtopics_remaining": [
                "hindi_kshitij_balgobin_bhagat",
                "hindi_kshitij_lakhnavi_andaz",
            ],
            "content_match_keys": ["hindi|kshitij_prose"],
            "last_studied": "2026-04-28T18:00:00+00:00",
        },
    },
]


async def seed(vs: VectorStore):
    print(f"Seeding backlog for user: {TEST_USER_ID}\n")
    results = []
    for entry in MOCK_ENTRIES:
        ok = await vs.upsert_backlog(
            user_id=TEST_USER_ID,
            match_key=entry["match_key"],
            data=entry["data"],
        )
        icon = "✅" if ok else "❌"
        label = f"{entry['data']['subject']} | {entry['data']['chapter']} [{entry['data']['status']}]"
        print(f"  {icon}  {label}")
        results.append(ok)

    passed = sum(results)
    print(f"\n{passed}/{len(MOCK_ENTRIES)} seeded successfully.")


if __name__ == "__main__":
    vs = VectorStore()  # adjust constructor if yours takes args
    asyncio.run(seed(vs))