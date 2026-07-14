const contentName = (content = {}) => (
  content.name
  || content.canonical_name
  || content.match_key
  || "Untitled content"
);

export const normalizeSession = (session = {}) => {
  const contents = Array.isArray(session.contents)
    ? session.contents.map(content => ({
        ...content,
        name: contentName(content),
        status: content.status || "pending",
        time_spent: content.time_spent || 0,
      }))
    : [];

  const completedContents = contents
    .filter(content => content.status === "done")
    .map(content => content.match_key);

  const title = session.title || session.topic || session.session_title || "Study Session";

  return {
    ...session,
    title,
    topic: session.topic || title,
    contents,
    completed_contents: session.completed_contents || completedContents,
    completed: session.completed ?? session.status === "done",
    status: session.status || (session.completed ? "done" : "pending"),
    allocated_hours: Array.isArray(session.allocated_hours) ? session.allocated_hours : [],
    estimated_hours: session.estimated_hours || 0,
    actual_time: session.actual_time || session.actual_hours || 0,
  };
};

export const normalizeDay = (day = {}) => ({
  ...day,
  sessions: Array.isArray(day.sessions) ? day.sessions.map(normalizeSession) : [],
  capacity_hours: day.capacity_hours || 0,
  total_hours: day.total_hours || 0,
  buffer_hours: day.buffer_hours ?? Math.max((day.capacity_hours || 0) - (day.total_hours || 0), 0),
});

export const normalizePlan = (plan) => {
  if (!plan) return null;
  return {
    ...plan,
    days: Array.isArray(plan.days) ? plan.days.map(normalizeDay) : [],
  };
};
