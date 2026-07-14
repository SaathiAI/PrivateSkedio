# Planner to Intake Reroute Cases

Purpose:
- document when Planner should stop and route back to Intake
- prevent Planner from silently changing the study contract
- give future prompt work concrete examples of contract-level changes

Core idea:

```text
Intake owns the agreement.
Planner owns the timetable.
```

If the user says something during planning that changes the agreement, Planner
should not patch around it. It should route back to Intake with the user's latest
message, current intake contract, and any planner context that matters.

## Route Back When Contract Truth Changes

Route back to Intake when the user changes or reveals new truth about:
- study scope
- subject or chapters
- deadline or finish target
- daily capacity
- fixed blockers
- sleep/rest window
- learning mode
- priorities
- feasibility assumptions

Planner can handle simple timetable edits, but Intake must handle contract edits.

## Case A: Scope Change

Current contract:
- Maths plan
- Polynomials and Quadratic Equations

User says during Planner:

```text
Actually add Science Electricity also.
```

Why this routes back:
- subject changed
- scope changed
- workload changed
- syllabus/backlog may need to be checked again

Intake response style:

```text
Got it, adding Science changes the contract, not just the timetable. Do you want
this new plan to include Maths + Electricity together, or replace Maths with
Electricity?
```

Likely tools:
- `query_syllabus`
- `query_backlog`
- `commit_intake`

## Case B: Deadline Change

Current contract:
- finish by Sunday

User says during Planner:

```text
Can we finish by Friday instead?
```

Why this routes back:
- deadline changed
- feasibility may change
- scope may need to be reduced

Intake response style:

```text
Friday is tighter, so I need to recheck whether the same work still fits. Are
you okay reducing scope if needed, or should we try to keep everything?
```

Likely tools:
- `get_calendar_availability`
- `commit_intake`

## Case C: Availability Change

Current contract:
- 2 hours daily

User says during Planner:

```text
I forgot, I can't study Wednesday and Thursday.
```

Why this routes back:
- daily capacity changed
- available days changed
- feasibility may fail

Intake response style:

```text
That removes a big chunk of study time. I'll update the contract and check
feasibility again. Do you want to keep the same scope and make the plan tighter,
or reduce the work?
```

Likely tools:
- `get_calendar_availability`
- `commit_intake`

## Case D: Hidden Recurring Blocker

Current contract:
- evenings available

User says during Planner:

```text
Wait, I have tuition every evening 6-8.
```

Why this routes back:
- recurring blocker changed availability
- planner's usable windows changed

Intake response style:

```text
Thanks, that changes the availability contract. I'll protect 6-8 PM every
evening. Outside tuition, what study window is actually usable?
```

Likely tools:
- `commit_intake`
- optionally `get_calendar_availability`

## Case E: Learning Mode Change

Current contract:
- revision plan

User says during Planner:

```text
I actually don't understand Quadratic Equations at all.
```

Why this routes back:
- revision became relearning
- estimated hours likely increase
- priorities may need to change

Intake response style:

```text
That changes Quadratic Equations from revision to relearning, so the time needed
may go up. Should we keep all chapters, or make Quadratics the main focus?
```

Likely tools:
- `query_backlog`
- `commit_intake`

## Case F: Priority or Exclusion Change

Current contract:
- weak-topic plan includes Trigonometry

User says during Planner:

```text
Don't do Trigonometry, I only care about Polynomials.
```

Why this routes back:
- included work changed
- planner should not silently remove contract scope

Intake response style:

```text
Got it. I'll remove Trigonometry from this contract and make Polynomials the
main scope. Do you want Quadratic Equations still included, or only Polynomials?
```

Likely tools:
- `commit_intake`

## Case G: Calendar Feasibility Conflict

Current contract:
- 2 hours daily

Planner discovers:

```text
Calendar leaves only about 30 minutes per day.
```

Why this routes back:
- contract capacity does not match available windows
- user must choose a repair

Intake response style:

```text
The current contract does not fit your calendar. We need to either reduce scope,
extend the deadline, or choose different study windows. Which one should we
adjust?
```

Likely tools:
- `get_calendar_availability`
- `commit_intake`

## Case H: User Asks for More Work After Lock

Current contract:
- focused weak-topic plan

User says during Planner:

```text
Can you also add sample papers and a full revision test?
```

Why this routes back:
- workload increased
- plan may no longer fit capacity

Intake response style:

```text
That adds more work than the current contract includes. I can add sample papers,
but we should check whether they fit or replace something else. Should sample
papers be extra work, or should they replace some chapter practice?
```

Likely tools:
- `query_backlog`
- `commit_intake`

## Case I: User Reveals a New Constraint

Current contract:
- normal study sessions

User says during Planner:

```text
I can only do short 25-minute sessions. Long sessions don't work for me.
```

Why this may route back:
- if it only changes session style, Planner can handle it
- if it changes total focused capacity or feasibility, Intake should update the
  contract

Planner can handle:

```text
Break sessions into shorter blocks.
```

Route back to Intake if:

```text
This means the original daily hours are no longer realistic.
```

Likely tools when routed:
- `commit_intake`

## Case J: User Contradicts the Contract

Current contract:
- sleep protected 11 PM-7 AM

User says during Planner:

```text
Just schedule me at midnight, I can sleep later.
```

Why this routes back:
- rest window changed
- health/rest constraint changed
- feasibility may change

Intake response style:

```text
That changes the rest window we locked. Are you intentionally changing your
sleep window for this plan, or should I keep sleep protected and find another
slot?
```

Likely tools:
- `commit_intake`

## What Planner Can Handle Without Intake

Planner can usually handle:
- moving a session within the same available window
- swapping session order
- making sessions shorter while preserving total work
- choosing exact start/end times
- placing revision before practice
- spreading work across available days

These are timetable decisions, not contract decisions.

## Simple Routing Rule

Use this test:

```text
If the change would modify IntakeAgentOutput or scheduling_context, route to
Intake.

If the change only modifies exact placement inside the same contract, Planner can
handle it.
```

