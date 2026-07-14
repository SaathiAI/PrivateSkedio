export function normalizeAllocationSummary(raw) {
  if (Array.isArray(raw)) return raw;
  if (Array.isArray(raw?.allocations)) return raw.allocations;
  return [];
}

export function normalizeChapterBacklog(raw) {
  const chapters = raw?.chapters;
  if (!chapters) return {};

  if (Array.isArray(chapters)) {
    return chapters.reduce((acc, item) => {
      const chapterName = item?.chapter || "Unknown Chapter";
      if (!acc[chapterName]) acc[chapterName] = [];
      acc[chapterName].push({
        name: item?.subject || "Unknown Subject",
        status: String(item?.status || "unknown").toLowerCase(),
        hours_actual: item?.hours_actual || 0,
        subtopics_completed: item?.subtopics_completed || [],
        subtopics_pending: item?.subtopics_pending || [],
      });
      return acc;
    }, {});
  }

  if (typeof chapters === "object") return chapters;
  return {};
}
