# Active Plan Intake Update Cases

Purpose:
- document cases where the user already has an active plan
- show when a user message should route back to Intake instead of only Planner
- protect completed work and current progress when creating a new/update contract

This is trickier than first-plan intake.

When an active plan exists, Intake is no longer starting from zero. It must read
the current plan/progress context and build a contract for what is left or what
changed.

Core rule:

```text
Active plan progress is current truth.
New Intake contract should reflect remaining work, not the original full plan.
```

## Mental Model

For first plan:

```text
student goal -> intake contract -> planner schedule
```

For active plan update:

```text
active plan + progress + latest user change
-> Intake repair/update contract
-> Planner/rescheduler rebuilds only the future/remaining work
```

The system must not accidentally:
- re-add completed sessions
- re-plan completed subtopics
- ignore skipped/partial progress
- treat the original intake as if no work has happened
- let Planner silently change contract facts

## Route To Intake When An Active Plan User Changes Contract Truth

Route back to Intake when the user changes:
- study scope
- subject/chapter set
- deadline
- available hours
- blockers/rest
- learning mode
- priorities
- exam target
- what should be dropped or added

Planner/rescheduler can repair placement of remaining work. Intake must repair
the agreement itself.

## Case A: Add New Subject After Progress Exists

Active plan:
- Maths plan for Polynomials + Quadratic Equations
- Polynomials sessions already completed
- Quadratic Equations still pending

User says:

```text
Also add Science Electricity to this plan.
```

Why Intake:
- new subject/scope added
- workload changed
- current plan already has completed work
- updated contract should include remaining Maths + new Science, not all original
  Maths again

Intake response style:

```text
Got it. Since your Maths plan is already in progress, I won't restart the whole
thing. I'll keep completed Polynomials as done, keep the remaining Quadratic
Equations work, and check what adding Electricity would cost.
```

Likely tools/context:
- active plan context
- `query_syllabus`
- `query_backlog`
- `commit_intake`

Updated contract should represent:
- pending Quadratic Equations work
- new Electricity work
- completed Polynomials not rescheduled

## Case B: Remove A Chapter Already Partly Completed

Active plan:
- Science plan for Light + Electricity
- Light concept session completed
- Light practice pending
- Electricity pending

User says:

```text
Drop Light. I only want Electricity now.
```

Why Intake:
- scope changed
- some Light work is already completed
- future Light work should be removed, but completed history must stay untouched

Intake response style:

```text
Okay, I'll stop planning any remaining Light work. The Light session you already
completed stays as history; the updated contract will only carry Electricity
forward.
```

Likely tools/context:
- active plan context
- `query_backlog` if Electricity progress matters
- `commit_intake`

Updated contract should represent:
- Electricity remaining work
- no future Light work
- completed Light preserved as completed history

## Case C: User Says They Finished Something Outside The App

Active plan:
- Quadratic Equations practice pending

User says:

```text
I already finished Quadratic Equations by myself. Remove it.
```

Why Intake:
- progress claim changes remaining work
- active plan may still mark it pending
- system should not blindly replan it, but should also avoid losing truth

Intake response style:

```text
Nice. The plan still has Quadratic Equations marked pending, so I need to update
the contract carefully. Should I treat it as fully done and remove the remaining
sessions, or keep a short final review only?
```

Likely tools/context:
- active plan context
- `query_backlog`
- `commit_intake`

Updated contract should represent one of:
- Quadratic removed from remaining work
- or Quadratic downgraded to short review only

Important:
- if product has a separate progress-marking tool, use that path too
- Intake should not schedule completed work again

## Case D: Deadline Moves Earlier Mid-Plan

Active plan:
- 6 days remaining
- 3 sessions completed
- 5 sessions pending

User says:

```text
My test got moved to Friday. Finish before then.
```

Why Intake:
- deadline changed
- remaining work may no longer fit
- completed work should stay done

Intake response style:

```text
That changes the contract. I won't touch what you've already completed, but I
need to check if the remaining sessions can fit before Friday. If not, we'll
need to reduce scope or switch to emergency revision.
```

Likely tools/context:
- active plan context
- `get_calendar_availability`
- `commit_intake`

Updated contract should represent:
- only pending work
- new Friday cutoff
- any reduced scope or emergency mode agreed with user

## Case E: Deadline Moves Later Mid-Plan

Active plan:
- deadline Sunday
- user is ahead or on track

User says:

```text
Exam got postponed. We have one more week.
```

Why Intake:
- deadline changed
- new contract may add deeper practice or reduce pressure
- current completed work remains done

Intake response style:

```text
Good, that gives us breathing room. I'll keep completed work as done and update
the remaining contract around the new deadline. Do you want the extra time used
for deeper practice, revision buffer, or a lighter pace?
```

Likely tools/context:
- active plan context
- `query_backlog`
- `commit_intake`

Updated contract should represent:
- remaining original work
- optional added practice/buffer
- new deadline

## Case F: Capacity Drops After Some Sessions Are Done

Active plan:
- 2 hours/day contract
- some sessions completed

User says:

```text
For the rest of the week I can only do 45 minutes a day.
```

Why Intake:
- future capacity changed
- remaining work may not fit
- completed work should not be re-planned

Intake response style:

```text
Got it. I'll keep the work you've already done as complete. For the remaining
work, 45 minutes/day is a much smaller budget, so we may need to reduce scope or
make this revision-only.
```

Likely tools/context:
- active plan context
- `get_calendar_availability`
- `commit_intake`

Updated contract should represent:
- pending work only
- lower daily capacity
- chosen repair: reduce scope, extend, or lighter mode

## Case G: New Recurring Blocker After Plan Exists

Active plan:
- evening study sessions scheduled

User says:

```text
I now have tuition every evening 6-8.
```

Why Intake:
- availability contract changed
- existing future sessions may be invalid
- completed past sessions stay untouched

Intake response style:

```text
I'll protect 6-8 PM from now on. Past/completed sessions stay as they are. For
the remaining work, I'll re-check whether we can still fit it after tuition or
need to reduce something.
```

Likely tools/context:
- active plan context
- `get_calendar_availability`
- `commit_intake`

Updated contract should represent:
- remaining work only
- new recurring blocker
- possibly changed daily capacity/window

## Case H: Learning Mode Changes For Remaining Work

Active plan:
- Quadratic Equations was planned as revision
- one revision session completed
- practice pending

User says:

```text
I still don't understand Quadratic Equations. Practice is not enough.
```

Why Intake:
- learning mode changed from revision/practice to relearning
- remaining work estimate may increase
- planner should not just move practice sessions around

Intake response style:

```text
That changes the remaining work. I'll keep the revision session you already did,
but future Quadratic sessions should shift toward concept rebuild before
practice. This may need more time.
```

Likely tools/context:
- active plan context
- `query_backlog`
- `commit_intake`

Updated contract should represent:
- completed revision preserved
- remaining Quadratic work changed to relearning + practice
- updated estimated hours

## Case I: User Wants A Fresh Plan But Has Active Progress

Active plan:
- mixed Maths plan in progress

User says:

```text
Forget this plan. Make a new one.
```

Why Intake:
- could mean archive/restart, or could mean repair remaining work
- dangerous to discard progress without clarity

Intake response style:

```text
I can rebuild it, but I don't want to throw away progress by accident. Do you
mean start a completely new contract, or rebuild the remaining work from your
current plan?
```

Likely tools/context:
- active plan context
- `commit_intake`

If user chooses rebuild remaining:
- new contract should use only remaining work

If user chooses new contract:
- old active plan may need archive/delete flow outside Intake

## Case J: User Adds Practice/Test After Completing Core Work

Active plan:
- core chapter work mostly completed
- final review pending

User says:

```text
Add a full sample paper and mistake review.
```

Why Intake:
- new workload added
- may fit only because core work is already done
- contract should not re-add core work

Intake response style:

```text
Since most core work is already done, this can become a practice-heavy update.
I'll keep completed chapter work out of the new contract and add sample paper +
mistake review as remaining work if it fits.
```

Likely tools/context:
- active plan context
- `query_backlog`
- `get_calendar_availability`
- `commit_intake`

Updated contract should represent:
- sample paper
- mistake review
- remaining review only
- no duplicate completed core sessions

## Case K: User Missed Sessions And Changes The Goal

Active plan:
- two sessions missed
- three sessions pending

User says:

```text
I missed two days. Just help me pass the test now.
```

Why Intake:
- missed work affects remaining budget
- goal changed from full prep to minimum viable pass/emergency plan
- contract mode changed

Intake response style:

```text
Okay, this becomes an emergency repair plan. I won't pretend the original plan is
still fully possible. I'll use what is completed, what is missed, and what time
is left to rebuild only the highest-impact remaining work.
```

Likely tools/context:
- active plan context
- `query_backlog`
- `get_calendar_availability`
- `commit_intake`

Updated contract should represent:
- emergency/high-impact remaining work
- missed sessions not blindly copied forward
- completed sessions preserved

## Case L: User Says A Completed Topic Is Still Weak

Active plan:
- Trigonometry marked completed

User says:

```text
I completed Trigonometry but I still feel weak in it.
```

Why Intake:
- completed does not mean mastered
- user is asking for additional reinforcement, not redoing original work

Intake response style:

```text
Got it. I won't redo the whole Trigonometry plan, but I can add a short
reinforcement block for the weak parts. Which feels weak: formulas, identities,
or solving mixed questions?
```

Likely tools/context:
- active plan context
- `query_backlog`
- `commit_intake`

Updated contract should represent:
- additional reinforcement/mistake review
- not original completed sessions

## What Intake Must Preserve

When active plan exists, Intake should preserve:
- completed sessions
- completed content/subtopics
- actual progress status
- skipped/partial state as useful evidence
- active plan identity/context
- user-confirmed constraints that still apply

## What Intake May Change

Intake may update:
- remaining study scope
- future deadline
- future capacity
- future blockers
- future rest windows
- learning mode for remaining work
- priority/order guidance for Planner
- estimated hours for remaining work

## Simple Test

Ask:

```text
Would this new contract cause Planner to schedule work that is already complete?
```

If yes, the contract is wrong.

Then ask:

```text
Does this update only affect session placement, or does it change what the
student has agreed to study / by when / with what capacity?
```

If it changes the agreement, route to Intake.

## Good Active-Plan Intake Behavior

Good behavior sounds like:

```text
I won't restart the whole plan. I'll keep completed work as done and update only
what remains.
```

Bad behavior sounds like:

```text
Sure, I'll make a new plan for the full original scope again.
```

