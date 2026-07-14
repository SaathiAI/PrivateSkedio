# Open Gaps and Future Work

## Purpose

This document records the parts of SkedioAI that are still limited, incomplete, or strategically deferred.

These are not failures to hide.
They are the next important improvement areas.

## 1. Actual-Hours Logging

One of the clearest open gaps is robust actual-time logging.

The system can reason about planned time, but actual completion time is not yet fully mature as a trustworthy product-wide signal.

### Why it matters

If the system cannot reliably understand:

- how long sessions actually took
- how complete a session really was

then later planning accuracy is limited.

## 2. Checkbox Completion Semantics

The system still has a practical ambiguity:

- what does a checkbox click mean if the user does not provide real hour data?

This matters because later plan reasoning may assume more certainty than the interaction actually provided.

## 3. Interactive Email Limitations

Email is useful and important, but it is not yet a perfect full interaction surface.

Current strength:

- review and re-entry workflows

Current weakness:

- deeper interactive planning through email alone

## 4. Syllabus Freshness and Trust

Syllabus truth remains one of the hardest unresolved data problems.

The system wants:

- latest curriculum accuracy
- user-correctable knowledge
- safe trust boundaries

But the available sources can still create tension between:

- LLM memory
- vector-stored curriculum data
- external website reliability

## 5. Single-Plan Limitation

The current product assumes one active plan model.

That keeps the system cleaner today, but it limits more advanced usage patterns involving multiple active plan tracks.

## 6. Auto-Reschedule UX and Policy

The system can revise plans, but the long-term product policy around:

- what should happen automatically
- what should require review
- what should trigger escalation

can still be refined further.

## 7. Latency

Latency remains an active concern.

Important future work areas include:

- reducing planner turnaround time
- reducing memory-heavy prompt cost
- keeping review flow snappy
- minimizing integration overhead

## 8. Stronger Progress Truth

Progress tracking exists, but it can still become more behaviorally accurate if:

- actual-hours truth improves
- completion semantics improve
- revision logic incorporates that stronger signal

## 9. Better Syllabus Update Workflow

Future work may include:

- more reliable syllabus verification/update path
- cleaner sync cadence
- better trust scoring for curriculum updates

## 10. UI and Workflow Polish

There is still room to improve:

- review interactions
- email-triggered flow clarity
- progress presentation
- planner-explanation quality

## Summary

SkedioAI already has a strong architecture core, but the next major quality gains will likely come from:

- stronger progress truth
- better actual-time handling
- cleaner email/review UX
- more trustworthy syllabus handling
- continued latency reduction

These are the open fronts that matter most.
