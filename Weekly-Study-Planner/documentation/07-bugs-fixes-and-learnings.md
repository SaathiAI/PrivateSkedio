# Bugs, Fixes, and Learnings

## Purpose

This document records the debugging battles, fixes, and practical lessons that shaped the project.

It is intentionally not polished into a fake-clean story.

## Latency Battle

Latency was a recurring engineering concern.

Important observations included:

- some prompts were doing too much
- some model paths added reasoning overhead without enough value
- some nodes were reading or rebuilding more context than necessary
- some commit or planning steps were slower than they needed to be

### Key latency-oriented changes

- removed unnecessary prompt modifiers where they were not helping enough
- simplified commit-node behavior so it did not do avoidable extra work
- identified memory-related prompt bloat as a real source of performance pressure
- explored parallelization opportunities

### Learning

Good architecture is not enough if prompts, memory payloads, and commit paths silently blow up runtime cost.

## Model-Integration Pain

One major practical battle was not just model quality, but model integration behavior.

Examples:

- reasoning-token pollution
- structured-output instability
- wrapper differences between providers
- integration quirks from third-party routing layers

### Learning

Provider choice is not just about benchmark quality.
It also changes runtime reliability and debugging pain.

## Model Migration Story

The model journey itself became part of the debugging and reliability story.

### Grok via OpenRouter

Grok looked appealing because it could reason well in some cases, but the practical experience was rough.

The pain was not just “the model made mistakes.”
The pain was also operational:

- structured-output instability
- reasoning-token pollution
- odd wrapper behavior
- downstream extraction headaches

This created a lot of hidden engineering work.

### GPT-4.1-mini

The move to `gpt-4.1-mini` improved speed and made some intake behavior more workable.

But it still had clear limits:

- it was fast
- it was decent for some structured tasks
- it was not always clever enough for planner-grade constraint obedience

That made it useful, but not fully satisfying in the planner role.

### GPT-5-mini

The move toward `gpt-5-mini` became a more workable compromise:

- not perfect
- but more capable under real planning constraints
- more acceptable as the current working choice

### Why this matters

These model changes were not cosmetic.
They changed:

- latency
- structured-output reliability
- planning quality
- operational stress

## Eternal Subtopic Bug

One of the nastier correctness bugs involved subtopics appearing incorrectly across sessions.

### Nature of the bug

The system was effectively showing merged topic/subtopic truth where session-specific truth was needed.

### Why it mattered

If every session appears to contain the same full set of subtopics, the plan stops being trustworthy at a very practical user level.

### Learning

Session-local truth and topic-global truth must not be mixed casually.

## Backlog Search Problems

Backlog retrieval had multiple rounds of issues, including:

- initialization problems
- wrong parameter expectations
- search-shape mismatches
- weak query shaping

### Learning

Semantic retrieval is powerful, but the shape of stored keys and query formats matters a lot more than people think.

## Planner Constraint Failures

The planner struggled at different times with:

- respecting day windows
- respecting capacity limits
- reconstructing sessions correctly after changes
- keeping consistent match-key behavior
- reacting correctly to tighter schedules

### Learning

Prompting alone is not enough.
Critical planning rules need deterministic reinforcement and explicit verifier pressure.

## Review and Commit Robustness

The project also learned that:

- draft creation
- draft display
- draft approval
- durable commit

must be separated clearly.

If those blur together, failure becomes much more expensive.

### Same-turn approval bug

A confusing failure happened when one user message caused:

```text
Intake approved
-> Planner created verified draft
-> Supervisor re-read the same user message
-> Planner committed
```

The product problem was not that Supervisor can command Planner to commit. That
power is intentional. The problem was lifecycle timing: the user message existed
before the Planner draft existed, so it should not count as approval for that
new draft.

### Fix

Planner `awaiting_approval` is now treated as a display-ready worker outcome:

```text
Planner verified draft
-> deterministic route to user-facing
-> show draft/review actions
-> end turn
```

Approval, typed changes, or cancellation are handled in a later turn after the
draft has actually been shown.

## Frontend Calendar UX Fixes

The frontend had several calendar-surface bugs that made the product feel less trustworthy.

### Fake/admin state leaking into normal user flow

Normal users were seeing admin/dev-style preview behavior.

### Fix

Admin preview is now explicit.
Normal login should remain normal login.
Dev/admin behavior is only entered through the intended admin path.

### Learning

Preview data is useful, but it must never silently override real user state.

## Calendar-connect empty state

The Planner tab previously could show a calendar-like surface even when the calendar was not connected.

### Fix

When calendar is disconnected, Planner shows a dedicated connect-calendar state.

The empty state:

- explains that calendar connection is needed
- provides a Google Calendar connect button
- keeps the layout aligned with the sidebar-height work surface
- prevents the chat launcher from opening into a planning flow without calendar context

### Learning

An empty state is not just decoration.
It should protect the workflow from invalid assumptions.

## Calendar grid rendering issues

The calendar grid had several practical UI bugs:

- event rows felt too tall
- short blockers became oversized cards
- lunch text could clip after row-height reduction
- compact blockers could hide their time
- the current-time marker was visually offset below the actual computed time
- a dynamic event-based visible range made the calendar feel unlike a real calendar

### Fix

The calendar grid now:

- renders a full day from `12 AM` to `11 PM`
- uses denser hour rows
- separates blocker styling from study-session styling
- shows compact blockers as one-line title/time bars
- keeps long blockers as filled time-range blocks
- places the current-time line by exact minute position
- computes the current-time marker in `Asia/Kolkata`

### Learning

Calendar UI should be boring in the right way.

Users already understand calendar tools.
The product should not invent a dynamic timeline when a stable full-day grid is the clearer model.

### Pros

- more familiar calendar behavior
- less fake-looking event layout
- clearer distinction between busy time and study sessions
- current-time marker is easier to trust
- compact events remain readable

### Cons

- full-day grids create more vertical scroll
- denser rows make very short events harder to show with rich text
- event rendering needs special handling for tiny, compact, and long blocks
- matching calendar familiarity reduces room for unusual custom layout ideas

## Remaining Weak Spot: Checkbox / Actual-Hours Assumption

This is one of the most important still-open practical issues.

The system can depend on actual study-hour truth when it tries to reason about later plan multiplication, progress realism, or revision behavior.

But in reality:

- a user may simply click a checkbox
- the user may not provide actual hours
- the system may still need to decide what that completion means

### Why this matters

If completion semantics are weak, later planning logic may build on shaky assumptions.

### Current status

This area is not fully resolved and should remain explicitly documented as an open operational tension.

### Why it can hurt later planning

If checkbox completion is treated as strong evidence of completed effort when actual hours are weak or missing, later revision logic may build on false certainty.

That can affect:

- remaining workload estimation
- pace realism
- trust in progress
- how aggressively future sessions are placed

## Remaining Weak Spot: Interactive Email Boundaries

Email is useful in the workflow, but it is not yet a perfect conversational surface.

The system currently works better when email acts as:

- a notification surface
- a review-link surface
- a bridge back into the main product flow

than as a fully rich back-and-forth planning medium.

### Learning

Workflow entry through email is strong.
Full interaction through email is a harder product problem.

### Current practical email shape

Right now email is strongest when it:

- notifies the user that something changed
- provides a review link or entry point
- sends the user back into the normal site/chat workflow

That is much cleaner than pretending email is already a full freeform planning channel.

## Remaining Weak Spot: Latency

Latency has improved, but it still deserves to be tracked as a first-class concern.

Especially sensitive areas include:

- plan generation
- memory-heavy reasoning
- review flow overhead
- integration-related overhead

### Important latency lesson

Every extra “smart” layer has a cost.

That includes:

- prompt enhancers
- oversized memory payloads
- redundant model hops
- synchronous side effects in the wrong place

Part of the project’s maturity came from removing clever-looking things that did not earn their latency cost.

## Real Bug Examples Worth Preserving

The following bug stories matter because they illustrate real system truths.

### 1. Reasoning-token pollution bug

One ugly class of bug came from provider or wrapper behavior leaking reasoning-style content into places that were expected to stay clean for structured extraction.

That was a strong lesson that integration details can quietly corrupt downstream logic.

### 2. Eternal subtopic bug

This bug mattered because it exposed how easy it is to confuse:

- topic-global subtopic truth
- session-specific assigned subtopic truth

It was not just a display issue.
It was a planning-truth issue.

### 3. Backlog search fragility

Backlog retrieval problems repeatedly showed that:

- initialization matters
- canonical naming matters
- query shape matters
- semantic search still has edge cases with abbreviations and chapter shorthand

### 4. Calendar and side-effect overhead

Some latency improvements came from realizing that slow side effects should not always sit in the hot path of the user-facing response.

This mattered for things like:

- calendar operations
- backlog sync
- other slower follow-up work

### 5. Prompt-only fixing eventually stops scaling

Prompt fixes helped many times.
But one of the strongest lessons was that prompt patching alone cannot permanently rescue confused ownership or weak state boundaries.

## Big Lessons

### 1. Prompt quality matters, but system behavior matters more

Prompting can improve things, but it cannot rescue weak ownership boundaries or broken state flow forever.

### 2. Worker identity clarity matters

When two workers seem to own the same conceptual job, the whole product becomes harder to reason about.

### 3. Data-shape bugs can be more damaging than visible UI bugs

If the wrong truth is stored or retrieved, the user-facing layer becomes misleading even when it looks polished.

### 4. Structured workflows beat fuzzy interpretation for important state transitions

Approval, changes, commit, and revision all behave better when the system treats them as explicit workflow states.

### 5. Integration pain is real engineering work

Calendar, email, vector stores, wrappers, model providers, environment setup, and framework behavior all consumed meaningful engineering effort.

That work may not look glamorous in a feature list, but it absolutely shaped the real project timeline.

## Summary

This project improved not by avoiding bugs, but by learning from them aggressively.

The debugging history is part of the architecture story, not separate from it.
