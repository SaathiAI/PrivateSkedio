# Memory and Data Layer

## Purpose

This document explains how SkedioAI stores truth, retrieves context, and builds user-aware behavior over time.

This is one of the most important parts of the system because planning quality depends heavily on:

- what is stored durably
- what is retrieved semantically
- what is remembered about the user
- what the system assumes when information is incomplete

## Core Principle

SkedioAI uses two different persistence styles for two different jobs:

### Neo4j

Neo4j stores durable graph-shaped truth.

### Pinecone

Pinecone stores retrieval-oriented memory and semantic support data.

These are not interchangeable.

## Why Two Systems Exist

The project did not choose two systems for novelty.
It chose two systems because the product has two very different needs.

### Need 1: durable structured truth

The system needs a reliable place to store:

- users
- plans
- days
- sessions
- durable progress-linked state

That is best handled as explicit graph/data truth.

### Need 2: fuzzy recall and semantic personalization

The system also needs a place to retrieve:

- prior behavior
- backlogs
- semantic topic matches
- syllabus-like knowledge
- user context patterns

That is best handled through semantic retrieval support.

## Neo4j: Durable Truth

Neo4j is the product’s durable source of truth for planning state.

At a practical level, Neo4j is where the system trusts the final plan structure to live.

Typical truth stored here includes:

- plan objects
- day objects
- session objects
- session-content relations
- user-linked planning state

### Why Neo4j is important

Once a plan is committed, the system must be able to rebuild the active plan view from deterministic stored truth.

That is why:

- Neo4j writes matter first
- other memory layers should not become primary truth by accident

## Pinecone: Retrieval and Memory

Pinecone is used as the system’s semantic memory and retrieval layer.

It currently supports multiple logical memory categories.

### Main memory categories

1. backlog
2. episodic memory
3. user context
4. syllabus

Each one exists for a different reason.

### Current namespace shape

In practice, the memory layer is split into distinct Pinecone namespaces with different roles and different write behavior.

The most important namespaces are:

- `context`
- `episodic`
- `backlog`
- `syllabus`

This separation matters because each namespace behaves differently:

- some are append-style
- some are overwrite-style
- some are global
- some are user-specific

Internally, the current codebase may still use a technical identifier like `chapter_backlog_v2`, but in the documentation this should be understood simply as the backlog namespace.

## Backlog Memory

Backlog memory captures what remains incomplete or pending inside the learning workload.

This includes ideas like:

- unfinished work
- chapter/topic backlog
- actual hours already spent
- estimated hours still relevant

### Why backlog matters

Without backlog memory, each new planning pass risks pretending the student is starting fresh.

Backlog memory helps the system remember:

- what still exists
- what was left incomplete
- where work should be carried forward

### Backlog write behavior

Backlog is not meant to be an event stream.

It behaves closer to:

- one durable semantic projection per user + topic identity
- rewritten when backlog truth changes

This makes it useful for planning because the planner does not just need history.
It needs a current view of what is still unfinished.

### Why backlog became so important

One of the strongest product needs in SkedioAI is carrying unfinished work across planning cycles.

Without a dedicated backlog layer, the system would repeatedly risk treating the user like a new learner every time a plan changed.

## Episodic Memory

Episodic memory captures user activity over time.

This includes behavior traces from previous planning and execution events.

The point of episodic memory is not just historical storage.
It is to provide evidence for later personalization.

### What episodic memory helps with

- identifying repeated behavior
- identifying recurring constraints
- recognizing failure patterns
- recognizing success patterns

### Episodic write behavior

Episodic memory is intentionally much closer to append-only behavior.

Its job is to preserve evidence over time, not to collapse everything into one final summary immediately.

This makes it useful for later synthesis when the system wants to update the user model more intelligently.

### Why episodic memory must be interpreted carefully

One skipped session should not immediately become a stable personality label.

That means episodic memory is valuable as evidence, but it should not be promoted directly into stable truth without synthesis.

## User Context Memory

User context is the higher-level persistent user model.

The current mental model for user context includes three major categories:

1. personality
2. behavior
3. preference

### What those categories mean

#### Personality

Broad tendencies in how the user approaches work.

#### Behavior

Observed patterns in what the user actually does over time.

#### Preference

Explicit or implicit preferences about planning, timing, difficulty, or study style.

## How User Context Updates

User context should not be treated as a naive append-only log.

The intended update model is closer to:

```text
existing user context
+ recent episodic evidence
+ new signals
-> revised user context
```

In other words, the system tries to synthesize a better current model by looking at both:

- what it believed before
- what the recent evidence suggests now

This is important because the user is not static.

### Why this merge-style update matters

The project intentionally moved away from a naive model where:

- one new event rewrites the user completely
- or the whole user profile is rebuilt from zero every time

The intended approach is a middle road:

- preserve stable patterns when they still seem true
- revise stale beliefs when recent evidence strongly contradicts them
- avoid letting noise dominate long-term planning behavior

### What user context is meant to influence

User context can influence:

- timing sensitivity
- revision preference
- subject comfort
- pacing realism
- overload avoidance
- tone and planning style

## Syllabus Memory

The syllabus namespace stores curriculum-related information.

Its role is to help the system reason about the current curriculum instead of relying entirely on generic model memory.

### Why this exists

Curriculum information is:

- domain-specific
- sometimes version-sensitive
- potentially correctable by users or later updates

### Why this remains difficult

Syllabus truth is one of the hardest unresolved data problems in the project because:

- external websites are not always trustworthy
- official curriculum updates may be infrequent or hard to normalize
- an LLM alone should not be blindly trusted as the source of latest curriculum detail

This is one of the areas where retrieval strategy, verification strategy, and update trust all collide.

### Why syllabus retrieval still exists despite the pain

The system still needs a more grounded alternative to blindly trusting generic model memory for curriculum truth.

Syllabus retrieval helps with things like:

- avoiding removed or inactive topics
- supporting curriculum-aware planning
- grounding subject/topic coverage

### Why syllabus remains one of the hardest open data problems

The real problem is not just storing syllabus entries.

The deeper question is:

```text
what should count as trustworthy enough to update academic truth?
```

That is still not a trivial problem.

## Truth Ordering Rule

One of the important data-layer rules in the project is:

```text
write durable truth first
write retrieval/memory support after
```

In practice, that means:

- Neo4j success should come before Pinecone-dependent follow-up writes
- Pinecone is valuable, but it should not become the single point of failure for durable plan truth

### Why this ordering was important in practice

The project learned that stale Pinecone state is frustrating, but stale or broken durable plan truth is much worse.

If Neo4j is correct and Pinecone lags:

- retrieval quality may degrade temporarily
- backlog can become stale
- personalization can weaken

But the core plan is still safely stored.

That is a much better failure order than the reverse.

## Why Memory Matters for Planning

Memory is not a side feature in SkedioAI.
It affects:

- prioritization
- tone of planning
- scope realism
- backlog carry-forward
- revision behavior
- personalization

Without memory, the system would behave closer to a single-shot planner.

With memory, the system can try to behave like a planning companion that actually remembers how the user studies.

### Where memory is consumed

Memory affects different layers in different ways:

- intake can use backlog and syllabus truth
- planner can use backlog and syllabus to avoid invalid assumptions
- user context can shape how plans are framed or softened
- episodic evidence can later feed context updates

## Current Memory Strengths

The current memory/data-layer design is strong in these ways:

- durable plan truth is separated from semantic recall
- backlog has a clear planning role
- user context can represent long-lived user patterns
- syllabus retrieval can support domain grounding

## Current Memory Weak Spots

The current memory/data-layer still has real gaps:

1. syllabus freshness remains a trust problem
2. actual-hours truth is not as robust as the planning loop would ideally want
3. some user context synthesis logic can still be improved
4. memory timing and update cadence can create behavior gaps

### Additional practical tensions

There are also more practical retrieval tensions such as:

- semantic mismatch between abbreviated user phrasing and long canonical chapter names
- deciding when durable truth should beat memory-inferred convenience
- keeping retrieval rich without creating prompt bloat and latency spikes

## Current Summary Of The Data Layer

The current data layer is intentionally asymmetric:

- Neo4j stores canonical structured truth
- Pinecone stores semantic memory and retrieval support
- backlog helps carry unfinished work forward
- episodic memory preserves evidence
- context memory models the user over time
- syllabus memory grounds curriculum assumptions

## Summary

The memory and data layer of SkedioAI is built on a deliberate split:

- Neo4j for durable plan truth
- Pinecone for backlog, context, episodic signals, and syllabus retrieval

That split is one of the main reasons the system can support both structured planning and personalized adaptation.
