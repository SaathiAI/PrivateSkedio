# Email, Tools, and Review Flow

## Purpose

This document explains three parts of SkedioAI that are easy to feel but easy to under-document:

- what email actually does in the product
- which tools belong to which worker
- how a planner draft moves through review before commit

These are important because the product is not just chat.
It is a workflow system with multiple re-entry paths.

## Email as a Workflow Surface

Email in SkedioAI is not meant to replace the main app.

It is used as a bridge when the system needs to pull the learner back into the loop, especially when something changed outside the chat window.

In practice, email currently supports:

- missed-session alerts
- planner review emails for calendar-driven draft changes
- conflict-style escalation when auto-adjustment is not clean

The intended product idea is:

```text
app remains the main workspace
email becomes the tap-on-the-shoulder
```

## Current Email Types

### 1. Missed-session alert email

This is the background reminder path.

It is triggered by the monitor job, not by a new chat turn.

The monitor checks whether:

- a SkedioAI-created calendar event exists
- that event has already ended
- it is still marked incomplete
- a missed alert has not already been sent

If all of that is true, the learner receives an alert email.

The current user-facing idea of that email is:

```text
you missed one or more planned study sessions
here is what slipped
come back into SkedioAI and repair it
```

### 2. Planner review email

This is the more product-rich email path.

It happens when:

- an external calendar change arrives through the webhook path
- the system detects a clash with future incomplete study sessions
- planner creates a revised verified draft
- the system stores that draft in the normal review thread
- the learner gets an email with review buttons

That email currently includes:

- a short explanation of what changed
- the affected sessions
- a note from the planner reply
- an `Approve` button
- a `Change it` button
- an `Open app` button

This is important:

```text
the email does not create a separate review universe
it points back into the same review workflow
```

### 3. Conflict / fallback email

If planner cannot produce a clean safe revision, the system falls back to a conflict-style alert.

That means the automation stops short of commit and asks the learner to come back into the app flow.

This is the safer posture for the current system.

## Review Flow Truth

One of the most important design choices in SkedioAI is that draft generation and durable commit are separate.

The review flow is:

```text
planner draft
-> deterministic verification
-> pending review state
-> user approval or request changes
-> commit
```

This applies both to:

- normal in-app planning flow
- calendar-triggered revision flow

## Where Pending Review Lives

Pending review is stored inside the normal supervisor thread state.

That means:

- the planner creates a verified draft
- supervisor state carries `verified_plan`
- `draft_status` becomes reviewable
- UI actions and email actions both return to the same thread logic

For calendar-triggered review specifically, the system builds a scoped review thread and stores:

- the auto-generated message
- planner reply
- intake snapshot
- scheduling context
- active plan context
- verified plan
- pending review UI metadata

This is a strong design choice because it avoids splitting app review and email review into two unrelated systems.

## Review Actions

The current review action shape is intentionally small.

The main actions are:

- `approve_plan`
- `request_changes`
- `cancel_plan`

The practical behavior is:

### Approve

```text
user approves
-> supervisor marks planner as next owner
-> planner moves from verified draft toward commit
```

### Request changes

```text
user requests changes
-> system keeps the verified draft as the working object
-> user is asked what should change
-> planner revises based on that feedback
```

### Cancel

```text
user cancels
-> pending review UI is cleared
-> draft is not committed
```

## In-App Review vs Email Review

The product tries to make these feel like one story.

### In-app review

This is the native path:

- planner produces verified draft
- frontend can show review UI
- user clicks review actions
- supervisor routes accordingly

### Email review

This is the re-entry path:

- system emails links
- links include review thread and review action
- frontend opens the same review flow
- user still lands back in the app-backed supervisor thread

So the right mental model is:

```text
email is a doorway
the real room is still the app review thread
```

## Tool Ownership

The system works better when each worker only gets tools that support its actual job.

## Intake Tools

The intake worker currently owns the evidence-gathering tools most closely tied to contract formation:

- `query_backlog`
- `get_calendar_availability`
- `query_syllabus`
- `verify_claim_search`
- `update_syllabus_entry`
- `commit_intake`

### `query_backlog`

Purpose:

- look up learner progress truth
- understand incomplete work
- inspect what is already done versus pending

Why intake needs it:

- contract formation should not blindly trust vague user wording when backlog truth already exists

### `get_calendar_availability`

Purpose:

- fetch calendar blockers for a date range
- ground available time in actual connected calendar evidence

Why intake needs it:

- intake is responsible for forming a realistic contract
- it needs to know whether the requested timeframe is even plausible

### `query_syllabus`

Purpose:

- retrieve curriculum truth
- confirm official chapter/topic structure

Why intake needs it:

- scope should not be formed around hallucinated or banned topics

### `verify_claim_search`

Purpose:

- perform an external web check for a disputed syllabus claim
- support exceptional cases where local syllabus truth may need challenge or confirmation

Why intake needs it:

- intake is the worker that owns contract truth
- if the learner strongly disputes curriculum reality, intake may need outside evidence before finalizing scope

Important boundary:

- this is not an ordinary planning tool
- this is not a first-choice tool
- local syllabus retrieval should be preferred first

The right use shape is:

```text
query_syllabus first
-> only if real dispute remains
-> verify_claim_search
```

### `update_syllabus_entry`

Purpose:

- update the syllabus record when a disputed syllabus fact has been sufficiently confirmed

Why intake needs it:

- if intake is the worker deciding scope truth, it also needs the controlled path for correcting that truth when the evidence is strong enough

Important boundary:

- this is a rare maintenance-style tool
- it should not be used casually
- it exists for correction, not for day-to-day planning

### `commit_intake`

Purpose:

- validate and save the current intake contract checkpoint
- pass the latest full `IntakeAgentOutput` through the acceptance gate

Why intake needs it:

- intake does not merely gather evidence
- it must eventually turn that evidence into one validated contract state

Important boundary:

- this is the contract gate, not just another lookup
- it is what lets intake move from conversational collection into planner-ready truth

## Planner Tools

Planner currently uses:

- `query_backlog`
- `query_syllabus`

Planner does not fetch fresh calendar truth directly.
It is expected to work from the scheduling context already prepared by intake or runtime services.

That boundary matters.
It helps prevent planner from behaving like an uncontrolled free-roaming operator.

### Why planner keeps backlog access

Planner may still need backlog truth when placing sessions, especially if the contract needs progress-aware sequencing.

### Why planner keeps syllabus access

Planner may need curriculum truth to avoid shaping sessions around the wrong material or inventing weird placement logic for topics that should not be there.

## Tools Are Not the Final Authority

An important rule in SkedioAI is that tools help workers see evidence, but tools alone do not make the system safe.

Safety also depends on deterministic layers such as:

- intake validation
- feasibility shaping
- planner verification
- commit logic

So the real pattern is:

```text
tool evidence
-> worker reasoning
-> deterministic validation / verification
-> review
-> commit
```

That is much stronger than letting one prompt decide everything.

## Known Limitations in These Flows

Even with the current improvements, a few parts are still imperfect:

- email is a workflow bridge, not a full conversational inbox
- interactive email actions still rely on returning into the app flow
- planner review is strong for approval and revision, but the surrounding UX can still be polished
- the missed-session email path is simpler than the planner review email path
- live end-to-end prompt behavior could not be fully re-tested in this run because the OpenAI API key was unavailable

## Why This Matters

Without this layer, SkedioAI would be only a schedule generator.

With it, the system becomes closer to an ongoing study operator:

- it notices slippage
- it notices external change
- it prepares drafts instead of silently mutating truth
- it gives the learner a clean approval path

That is one of the more product-important parts of the entire system.
