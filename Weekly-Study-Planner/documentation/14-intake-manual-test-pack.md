# Intake Manual Test Pack

This file defines the first five manual evaluation cases for the SkedioAI Intake Agent.

Purpose:
- test Intake in isolation before testing full supervisor -> planner orchestration
- check whether Intake asks the next useful question
- catch repetition, over-asking, premature approval, and vague contract handling

How to use:
1. Start a fresh intake-only run or a fresh chat thread that routes into Intake.
2. Paste the user turns in order.
3. After each Intake reply, judge it against the "Good signs" and "Bad signs" below.
4. Mark each case as `pass`, `weak`, or `fail`.

Global pass criteria:
- asks only the most important missing thing
- does not repeat already confirmed facts
- does not jump into timetable creation
- does not approve too early
- keeps the contract moving toward readiness in a few turns

## Case 1 — Clear User

### Goal
Check whether Intake handles a well-specified user without unnecessary friction.

### User turns
1. `I need a Class 10 CBSE Maths study plan for this week.`
2. `Polynomials and Quadratic Equations.`
3. `I want to finish by Sunday.`
4. `I can study 2 hours daily after 6 PM.`
5. `Focus more on revision and weak topics.`

### Good signs
- asks for scope, finish point, or capacity in a sensible order
- does not ask for things the user already gave
- does not overcomplicate the Sunday deadline
- reaches a lock summary quickly

### Bad signs
- asks about exact exam time too early
- asks multiple broad questions at once without need
- starts building a timetable instead of the contract
- stays pending forever after enough facts are known

## Case 2 — Vague User

### Goal
Check whether Intake can gently narrow a vague request instead of spiraling.

### User turns
1. `Make me a study plan for maths.`
2. `Class 10 CBSE.`
3. `Weak topics mostly.`
4. `Maybe for the next 5 days.`
5. `I can do around 90 minutes each day.`

### Good signs
- first question asks for the biggest missing contract fact
- handles "weak topics" as a usable direction, not as an error
- asks for missing scope if needed before approval
- converts rough duration into a reasonable planning window

### Bad signs
- responds with a generic lecture
- asks for too many details before narrowing the request
- gets confused by "weak topics" and stalls
- approves without enough academic scope

## Case 3 — Fuzzy Deadline User

### Goal
Check whether Intake handles rough finish targets without demanding fake precision.

### User turns
1. `I need to complete Science soon.`
2. `Class 10 CBSE. Light and Human Eye.`
3. `By next week ideally.`
4. `I can study around 1.5 to 2 hours daily.`
5. `Evenings are better.`

### Good signs
- accepts a rough finish target and refines only if needed
- does not obsess over exact cutoff time
- treats 1.5 to 2 hours as useful capacity info
- turns "evenings are better" into a planning constraint or note

### Bad signs
- demands exact timestamp too early
- ignores the fuzzy deadline completely
- asks repetitive variants of the same date question
- pretends the contract is precise when it is not

## Case 4 — Overload User

### Goal
Check whether Intake notices overload honestly instead of shrinking scope silently.

### User turns
1. `Make me a plan for Maths full syllabus in 3 days.`
2. `Class 10 CBSE.`
3. `I can only study 1 hour per day.`
4. `I mostly want revision plus practice.`

### Good signs
- keeps status pending
- explains the overload simply
- offers repair options such as reduce scope, revision-only, or extend the window
- does not fake small estimated hours just to make it fit

### Bad signs
- approves an obviously unrealistic contract
- silently reduces scope without saying so
- invents unrealistic capacity
- becomes overly dramatic instead of practical

## Case 5 — Change-of-Mind User

### Goal
Check whether Intake preserves confirmed facts but updates the contract cleanly when the user changes direction.

### User turns
1. `I need an English plan for Class 10 CBSE.`
2. `First Flight chapters and poetry revision.`
3. `Actually no, make it Science instead.`
4. `Light and Electricity.`
5. `Finish it by Saturday. I can do 2 hours daily.`

### Good signs
- updates subject/scope cleanly after the change
- does not cling to the old English contract
- preserves still-valid facts but replaces changed facts
- asks the next missing question after the switch

### Bad signs
- mixes English and Science in the same contract
- restarts from zero unnecessarily
- ignores the user's correction
- approves before the revised scope is settled

## Scoring Template

Use this simple format while reviewing results:

```text
Case 1 — Clear User
Verdict: pass | weak | fail
Why:
- ...
- ...

Case 2 — Vague User
Verdict: pass | weak | fail
Why:
- ...
- ...
```

## What To Do After Running These

If most failures are:
- repetition or over-asking -> simplify prompt turn rules
- bad date handling -> simplify deadline language
- premature approval -> tighten approval gate
- weak overload handling -> strengthen feasibility guidance
- bad contract edits after user correction -> strengthen "preserve confirmed facts unless changed"
