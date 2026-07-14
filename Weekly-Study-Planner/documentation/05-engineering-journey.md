# Engineering Journey

## Purpose

This document explains how SkedioAI evolved into its current shape.

The project did not begin with the final architecture already clear.
It moved through multiple ideas, splits, framework choices, and cleanup phases before stabilizing into the simpler current design.

## Starting Vision

The original vision was ambitious:

- conversational intake
- study-plan generation
- revision after changes
- monitoring
- user-aware memory
- backlog carry-forward
- curriculum grounding
- calendar integration

Very early on, it was natural to imagine this as a larger multi-agent ecosystem with multiple specialized workers.

That instinct was not wrong.
But it did create later complexity.

## Early Agent Decomposition

The project initially leaned toward multiple specialized agents for:

- supervisor
- intake
- planner
- rescheduler
- chat
- delete or confirmation flows
- memory/model builder ideas

In theory this offered clarity.
In practice it produced overlap.

## Why the Early Split Became Painful

The biggest issue was that some of the agent boundaries looked different on paper but were not truly different in responsibility.

The most important example was the planner/rescheduler split.

### Why a separate rescheduler looked attractive

At first, a separate rescheduler seemed reasonable because:

- create-plan flow and revise-plan flow feel different
- rescheduling sounds like a distinct capability
- routing sounds simpler if there is a worker already named for the revision case

### Why it became conceptually messy

As the system matured, the separation caused a hard identity problem:

- if a contract changes, is that intake territory?
- if a plan changes but the scope stays similar, is that planner or rescheduler territory?
- if planner creates a draft and rescheduler revises active state, what is the real difference in product-facing identity?

The answer was increasingly uncomfortable:

the rescheduler was effectively becoming planner logic under another name.

### Resulting decision

The project simplified toward:

- one intake agent
- one planner agent

Planner now owns both:

- draft generation
- schedule revision

That reduced conceptual duplication and made the ownership story cleaner.

## Intake Simplification

The intake layer also went through conceptual refinement.

It became clearer over time that intake should own:

- contract truth
- scope understanding
- planning constraints

and should not drift into:

- schedule generation
- timetable-like placement
- planner-style revision ownership

The more intake tried to act like a router or schedule worker, the worse its identity became.

## Supervisor Evolution

The supervisor also went through multiple phases.

### Earlier idea

There was an earlier, more aggressive supervisor concept that tried to do too much at the orchestration level.

### Simpler but insufficient idea

Then came a more constrained idea:

- supervisor only routes once per turn
- choose one worker
- done

That was cleaner, but it created a practical problem:

some turns clearly required worker output to be inspected before the next move could be decided.

### Final insight

The supervisor should not just classify the user message.
It should also be able to see the result of worker execution and decide what to do next.

That led to the stronger current idea:

- supervisor routes the turn
- worker acts
- supervisor can inspect the outcome
- user-facing handles final delivery

That was a much better orchestration model for the project.

## User-Facing Wrapper Introduction

One of the more important practical lessons came from observing the worker outputs directly.

The intake and planner workers often thought in a very technical, internal way.

That meant the raw outputs sometimes sounded like:

- engineering notes
- workflow status descriptions
- technical tradeoff language

rather than something a real student should read.

### Why this mattered

Even if the worker was correct internally, the user experience still felt wrong.

### Resulting decision

A user-facing wrapper layer was introduced so the final assistant response could be:

- faster
- lighter
- less technical
- more readable for humans

This was not meant to become another business-logic worker.
It was a communication boundary.

## Framework and Tooling Exploration

The project also explored other framework paths, especially around OpenHands and earlier orchestration choices.

That exploration reinforced the value of:

- explicit control
- structured state
- deterministic routing where needed
- debuggable handoffs

## Model Evolution Story

The model story was also part of the engineering journey.

### Grok via OpenRouter

At one stage, Grok/OpenRouter-based usage looked promising but became painful in practice.

The struggle was not just model quality.
It was also tooling behavior, integration weirdness, and downstream structured-output problems.

### GPT-4.1-mini

Later, `gpt-4.1-mini` became attractive because it was fast and workable, especially for intake-like tasks.

But it was not always clever enough for all planner constraints, especially when scheduling quality and strict rule following really mattered.

### GPT-5-mini

The current direction moved toward `gpt-5-mini` as a more workable compromise:

- not perfect
- but strong enough to accomplish the real task more reliably

## Why the Journey Matters

The final system only makes sense when the failed or painful steps are understood.

The current architecture was not chosen because it looked nice in a diagram.
It was chosen because earlier shapes repeatedly produced:

- routing confusion
- duplicated identities
- fragile prompt behavior
- poor user-facing language
- weak ownership boundaries

## Journey Summary

The engineering journey of SkedioAI can be summarized like this:

```text
big multi-agent ambition
-> too many overlapping identities
-> repeated cleanup and simplification
-> stronger ownership boundaries
-> better routing philosophy
-> planner/intake core pair
-> user-facing wrapper for communication quality
```

The system got better by getting simpler in the right places.
