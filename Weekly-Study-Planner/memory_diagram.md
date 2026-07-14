# SkedioAI Learner Memory Diagram

This document shows the proposed v1 learner memory architecture for SkedioAI.

This is not a small patch on top of the existing vector store.

The intended product concept is:

```text
SkedioAI Learner Model
```

The learner model is the controlled product brain that helps SkedioAI understand
the student across sessions.

It is not "remember everything forever."

The goal is:
- preserve useful learner continuity
- avoid stale memory poisoning
- keep planner/intake/supervisor grounded
- prevent raw chat history from becoming fake truth
- make the product feel personally aware without becoming creepy or overconfident

---

## Core Role

The learner model should help the product remember:

- stable learner preferences
- repeated behavior tendencies that matter for planning
- weak/strong subjects
- recurring scheduling friction
- recent important study events

Mental model:

```text
Chat history is not memory.
Memory is distilled, useful, persistent learner context.
```

The product should feel like:

```text
SkedioAI knows how this student studies.
```

It should not feel like:

```text
SkedioAI is storing every random sentence forever.
```

---

## Product Brain Shape

```mermaid
flowchart TB
    Chat["Chat History"] --> Evidence["Evidence Buffer"]
    Events["Plan / calendar / session events"] --> Evidence
    Triggers["Memory Triggers"] --> Writer["Memory Writer"]
    Evidence --> Writer
    Writer --> EventMemory["Event Memory"]

    EventMemory --> Synth["Memory Synthesizer"]
    Existing["Existing Learner Model"] --> Synth
    Synth --> LearnerModel["SkedioAI Learner Model"]

    LearnerModel --> Reader["Memory Reader"]
    EventMemory --> Reader
    Backlog["Backlog / unfinished work"] --> Reader
    Reader --> Brief["Learner Memory Brief"]

    Brief --> Supervisor["Supervisor"]
    Brief --> Intake["Intake"]
    Brief --> Planner["Planner / Rescheduler"]
```

This is the main v1 idea:

```text
chat history is saved every turn
-> important triggers pick useful evidence
-> memory writer records durable memory only when useful
-> synthesizer updates the learner model conservatively
-> reader builds a short useful brief
-> agents use the brief
```

Important rule:

```text
Every turn can be chat history.
Every turn should not become learner memory.
```

First implemented trigger:

```text
plan accepted
-> episodic plan evidence is written
-> learner-memory synthesis is scheduled if OPENAI_API_KEY is available
-> accepted plan still succeeds if memory is skipped or fails
```

Second implemented trigger:

```text
session completed / partial / skipped / ticked / unticked
-> Neo4j progress truth is updated
-> backlog is synced
-> episodic progress evidence is written
-> complete/partial/subtopic outcomes count toward periodic synthesis
-> skipped sessions trigger immediate synthesis because they are high-signal friction
-> progress update still succeeds if memory is skipped or fails
```

Third implemented trigger:

```text
meaningful chat turn
-> cheap structural gate counts only non-trivial user messages
-> every 10th meaningful turn runs chat memory review
-> extractor decides whether there is durable learner memory or nothing
-> normal chat reply still succeeds if review is skipped or fails
```

---

## Runtime Context vs Memory

```mermaid
flowchart TB
    Chat["Chat History"] --> Supervisor["Supervisor runtime"]
    Chat --> Intake["Intake runtime"]
    Chat --> Planner["Planner / Rescheduler runtime"]

    MemoryBrief["Learner Memory Brief"] --> Supervisor
    MemoryBrief --> Intake
    MemoryBrief --> Planner

    Chat -.not automatically persisted.-> Boundary["Memory boundary"]
    Boundary --> Extract["Only durable useful signals are extracted"]
    Extract --> LearnerModel["SkedioAI Learner Model"]
```

Chat history is still useful runtime context.

But chat history should not automatically become long-term memory.

---

## Memory Layers

```mermaid
flowchart TB
    LearnerModel["SkedioAI Learner Model"]
    LearnerModel --> Profile["Profile Memory"]
    LearnerModel --> Academic["Academic Memory"]
    LearnerModel --> Behavior["Behavior Memory"]
    LearnerModel --> Event["Event Memory"]

    Profile --> P1["grade / board / stable learner facts"]
    Profile --> P2["study preferences"]
    Profile --> P3["communication / motivation tone"]

    Academic --> A1["weak subjects"]
    Academic --> A2["strong subjects"]
    Academic --> A3["revision style"]
    Academic --> A4["backlog patterns"]

    Behavior --> B1["overcommit tendency"]
    Behavior --> B2["skip / reschedule pattern"]
    Behavior --> B3["fatigue pattern"]
    Behavior --> B4["session length tolerance"]

    Event --> E1["plan created"]
    Event --> E2["session missed"]
    Event --> E3["reschedule accepted"]
    Event --> E4["exam week / important milestone"]
```

---

## Source-of-Truth Split

```mermaid
flowchart LR
    Neo["Neo4j / durable structured truth"] --> Builder["Memory builder / reader layer"]
    Pine["Pinecone / retrieval memory"] --> Builder
    Builder --> Brief["Learner Memory Brief"]

    Neo --> Contract["intake contract truth"]
    Neo --> Plan["active plan / progress truth"]

    Pine --> ProfileMem["profile memory"]
    Pine --> EpisodicMem["episodic memory"]
    Pine --> BacklogMem["backlog memory"]
```

Meaning:

- Neo4j holds structured product truth
- vector memory can hold retrieval-friendly learner memory
- the learner model is the product-level contract
- the runtime builder returns a short agent-ready brief

Existing storage is allowed to change.

The design should not be limited by the current memory files.

---

## Memory Buckets

```mermaid
flowchart TB
    Memory["User Memory"]
    Memory --> Stable["Stable profile memory"]
    Memory --> Episodic["Recent episodic memory"]
    Memory --> Academic["Academic pattern memory"]
    Memory --> Scheduling["Scheduling friction memory"]

    Stable --> S1["preferred study times"]
    Stable --> S2["session length tolerance"]
    Stable --> S3["motivation / tone preference"]

    Episodic --> E1["recent skips"]
    Episodic --> E2["recent completions"]
    Episodic --> E3["recent reschedules"]

    Academic --> A1["weak subjects"]
    Academic --> A2["strong subjects"]
    Academic --> A3["revision preference"]

    Scheduling --> C1["overloaded days"]
    Scheduling --> C2["burnout patterns"]
    Scheduling --> C3["repeat clash tendencies"]
```

These buckets are conceptual.

They do not have to map one-to-one to current files.

---

## What We Store vs What We Do Not Store

```mermaid
flowchart LR
    Good["Store"] --> G1["stable preferences"]
    Good --> G2["repeat behavior patterns"]
    Good --> G3["study strengths / struggles"]
    Good --> G4["important recent events"]

    Bad["Do not store"] --> B1["raw entire conversations"]
    Bad --> B2["one-off emotional guesses"]
    Bad --> B3["temporary planner draft facts"]
    Bad --> B4["stale assumptions without review"]
```

This is a major safety boundary.

---

## Learner Memory Brief

Agents should receive memory as a short operational brief, not as raw database
or vector-store dumps.

Example:

```text
=== LEARNER MEMORY BRIEF ===
- Class 10 student.
- Usually handles 2-3 focused sessions per day better than many tiny scattered sessions.
- Recent issue: evening Science sessions were missed after tuition-heavy days.
- Academic pattern: Biology backlog is active; Chemistry numericals need slower placement.
- Planning implication: place harder topics earlier on lighter days when possible.
```

The brief should be:
- short
- evidence-based
- useful for the current agent
- clear about tendencies vs hard constraints

---

## Runtime Read Flow

```mermaid
sequenceDiagram
    participant App as App Route
    participant Reader as Memory Reader
    participant Neo as Neo4j
    participant VS as Vector Memory
    participant Synth as Learner Model
    participant Agent as Supervisor / Intake / Planner

    App->>Reader: build_learner_memory_brief(user_id, task)
    Reader->>Neo: fetch durable profile / plan truth if needed
    Reader->>VS: fetch relevant memory and recent events
    Reader->>Synth: read synthesized learner model
    Reader->>Reader: compress into agent-safe brief
    Reader->>Agent: return learner_memory_brief
```

---

## Write Flow

```mermaid
flowchart TD
    Start["User / system event happens"] --> Type{"what kind of update?"}

    Type -->|approved stable fact| ProfileWrite["write profile signal"]
    Type -->|important event| EventWrite["append event memory"]
    Type -->|backlog changed| BacklogWrite["update backlog projection"]
    Type -->|temporary draft only| Skip["do not write long-term memory"]

    ProfileWrite --> Synth["periodic learner model synthesis"]
    EventWrite --> Synth
    BacklogWrite --> Synth
    Synth --> End["learner model updated"]
    Skip --> End
```

Memory updates should be conservative.

One skipped session should not become a personality trait.

Repeated evidence can become a planning tendency.

---

## Ownership Boundary

```mermaid
flowchart TB
    Intake["Intake"] --> Own1["owns contract facts"]
    Planner["Planner / Rescheduler"] --> Own2["owns schedule decisions"]
    Supervisor["Supervisor"] --> Own3["owns routing"]
    Memory["Learner Memory"] --> Own4["owns persistent learner context"]

    Intake -.may emit stable learner signals.-> Memory
    Planner -.may emit important planning events.-> Memory
    Supervisor -.reads but should not invent learner truth.-> Memory
    Calendar["Calendar / session pipeline"] -.may emit events.-> Memory
```

---

## Conservative Update Rule

```mermaid
flowchart LR
    OneOff["one-off event"] --> EventOnly["store as event only"]
    Repeated["repeated pattern"] --> Candidate["candidate learner signal"]
    Candidate --> Evidence{"enough evidence?"}
    Evidence -->|no| EventOnly
    Evidence -->|yes| Model["update learner model"]
```

Bad memory:

```text
Skipped Maths once -> hates Maths.
```

Good memory:

```text
Late-night Maths sessions were missed 3 times in 4 weeks.
Planning implication: avoid heavy Maths late unless user asks.
```

---

## Recommended v1 Rule

```text
Memory should remember what helps future planning,
not everything the user ever said.
```

That means v1 should focus on:
- stable preferences
- recurring study behavior
- academic struggle/strength patterns
- recent important events
- recurring scheduling friction

and avoid:
- raw full-chat memory
- hidden personality overreach
- planner draft leakage into long-term memory
- treating weak evidence as a rule

V1 should optimize for:
- useful continuity
- student trust
- planning quality
- simple debuggability
