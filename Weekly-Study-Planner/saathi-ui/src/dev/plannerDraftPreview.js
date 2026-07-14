const addDays = (isoDate, offset) => {
  const next = new Date(`${isoDate}T12:00:00`);
  next.setDate(next.getDate() + offset);
  return next.toISOString().split("T")[0];
};

const buildContents = (subject, items) => (
  items.map((item, index) => ({
    match_key: `${subject.toLowerCase()}_${item.toLowerCase().replace(/[^a-z0-9]+/g, "_")}_${index + 1}`,
    name: item,
    canonical_name: item,
    subjects: [subject],
    status: "pending",
    time_spent: 0,
  }))
);

export const buildPlannerDraftPreview = (baseDate) => {
  const dayOne = addDays(baseDate, 0);
  const dayTwo = addDays(baseDate, 1);
  const dayThree = addDays(baseDate, 2);

  return {
    plan_id: "draft_preview_plan",
    title: "Maths exam push",
    status: "draft",
    total_hours: 8.5,
    days: [
      {
        date: dayOne,
        capacity_hours: 3,
        total_hours: 2.5,
        buffer_hours: 0.5,
        sessions: [
          {
            session_id: "draft_preview_day1_session1",
            title: "Polynomials core concepts",
            topic: "Polynomials core concepts",
            start_time: "16:00",
            end_time: "17:15",
            estimated_hours: 1.25,
            status: "pending",
            contents: buildContents("Maths", [
              "Zeros of a polynomial",
              "Relationship between zeroes and coefficients",
              "Graph intuition review",
            ]),
          },
          {
            session_id: "draft_preview_day1_session2",
            title: "Statistics worked examples",
            topic: "Statistics worked examples",
            start_time: "19:00",
            end_time: "20:15",
            estimated_hours: 1.25,
            status: "pending",
            contents: buildContents("Maths", [
              "Mean from grouped data",
              "Median from frequency table",
              "Mode practice set",
            ]),
          },
        ],
      },
      {
        date: dayTwo,
        capacity_hours: 3,
        total_hours: 3,
        buffer_hours: 0,
        sessions: [
          {
            session_id: "draft_preview_day2_session1",
            title: "Weak-area repair sprint",
            topic: "Weak-area repair sprint",
            start_time: "07:00",
            end_time: "08:30",
            estimated_hours: 1.5,
            status: "pending",
            contents: buildContents("Maths", [
              "Polynomial identities mistakes",
              "Application word problems",
              "Statistics interpretation traps",
            ]),
          },
          {
            session_id: "draft_preview_day2_session2",
            title: "Mixed timed drill",
            topic: "Mixed timed drill",
            start_time: "18:30",
            end_time: "20:00",
            estimated_hours: 1.5,
            status: "pending",
            contents: buildContents("Maths", [
              "12-question mixed worksheet",
              "Marking and error log",
            ]),
          },
        ],
      },
      {
        date: dayThree,
        capacity_hours: 3,
        total_hours: 3,
        buffer_hours: 0,
        sessions: [
          {
            session_id: "draft_preview_day3_session1",
            title: "Final exam rehearsal",
            topic: "Final exam rehearsal",
            start_time: "09:00",
            end_time: "11:00",
            estimated_hours: 2,
            status: "pending",
            contents: buildContents("Maths", [
              "Mini mock paper",
              "Self-check with corrections",
            ]),
          },
          {
            session_id: "draft_preview_day3_session2",
            title: "Formula and mistakes recap",
            topic: "Formula and mistakes recap",
            start_time: "17:30",
            end_time: "18:30",
            estimated_hours: 1,
            status: "pending",
            contents: buildContents("Maths", [
              "Formula flash review",
              "Last-minute error notebook",
            ]),
          },
        ],
      },
    ],
  };
};

export const buildPlannerReviewPreviewPayload = (baseDate) => {
  const draftPlan = buildPlannerDraftPreview(baseDate);

  return {
    reply: "Planner draft ready. I mapped the sessions onto the calendar and parked the plan in review mode. Nothing is saved yet.",
    phase: "create_plan",
    plan_committed: false,
    draft_plan: draftPlan,
    pending_ui: {
      type: "plan_review",
      actions: [
        { id: "approve_plan", label: "Approve plan" },
        { id: "request_changes", label: "Request changes" },
        { id: "cancel_plan", label: "Cancel plan" },
      ],
    },
  };
};

export const debugPlannerReviewPayload = (payload) => {
  if (typeof console !== "undefined") {
    console.groupCollapsed("[SkedioAI Dev] planner review payload");
    console.log(payload);
    console.groupEnd();
  }
  return payload;
};
