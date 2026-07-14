import assert from "node:assert/strict";
import {
  normalizeAllocationSummary,
  normalizeChapterBacklog,
} from "../src/lib/dashboardAdapters.js";

const directAllocations = [{ chapter: "Polynomials", subject: "Mathematics" }];
assert.deepEqual(normalizeAllocationSummary(directAllocations), directAllocations);

const wrappedAllocations = {
  plan_id: "plan_1",
  allocations: [{ chapter: "Light", subject: "Science" }],
};
assert.deepEqual(
  normalizeAllocationSummary(wrappedAllocations),
  wrappedAllocations.allocations,
);
assert.deepEqual(normalizeAllocationSummary(null), []);

const flatBacklog = {
  chapters: [
    {
      chapter: "Polynomials",
      subject: "Mathematics",
      status: "DONE",
      hours_actual: 1.5,
      subtopics_completed: ["zeros"],
      subtopics_pending: [],
    },
    {
      chapter: "Polynomials",
      subject: "Mathematics",
      status: "pending",
      hours_actual: 0,
      subtopics_completed: [],
      subtopics_pending: ["remainders"],
    },
  ],
};

const groupedBacklog = normalizeChapterBacklog(flatBacklog);
assert.equal(Object.keys(groupedBacklog).length, 1);
assert.equal(groupedBacklog.Polynomials.length, 2);
assert.equal(groupedBacklog.Polynomials[0].status, "done");
assert.equal(groupedBacklog.Polynomials[1].status, "pending");

const alreadyGrouped = {
  chapters: {
    Algebra: [{ name: "Mathematics", status: "done" }],
  },
};
assert.deepEqual(normalizeChapterBacklog(alreadyGrouped), alreadyGrouped.chapters);
assert.deepEqual(normalizeChapterBacklog({ chapters: null }), {});

console.log("dashboard_adapters: OK");
