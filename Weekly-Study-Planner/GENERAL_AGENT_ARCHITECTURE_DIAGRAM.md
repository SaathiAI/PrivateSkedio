# General Agent Architecture Diagram

> Historical / generic reference only.
> This file is intentionally broader than the current SkedioAI system.
> For live system truth, prefer `documentation/03-system-architecture.md`,
> `supervisor_slop_diagram.md`, `intake_diagram.md`, and `planner_diagram.md`.
> If this file and the live docs disagree, the live docs win.

This file shows what the usual practical multi-agent architecture looks like in detail.

It is intentionally general, not SkedioAI-specific, but it is designed to answer niche architecture questions too:

- where routing happens
- what handoffs usually contain
- where verification usually lives
- where memory lives
- what gets stored in chat vs state
- where retries, replans, and escalation happen
- how fixed specialists differ from swarm-style systems

For SkedioAI specifically, treat this file as a mental-model explainer, not as implementation documentation.

---

## 1. The Most Common Real-World Shape

```text
                                    +----------------------+
                                    |        USER          |
                                    |  asks for something  |
                                    +----------+-----------+
                                               |
                                               v
                        +--------------------------------------------------+
                        |          ENTRY / FRONT DOOR LAYER                |
                        |--------------------------------------------------|
                        | - auth / identity                                |
                        | - request normalization                           |
                        | - session lookup                                  |
                        | - prior conversation fetch                        |
                        | - optional memory fetch                           |
                        +----------------------+---------------------------+
                                               |
                                               v
                        +--------------------------------------------------+
                        |        ORCHESTRATOR / SUPERVISOR LAYER           |
                        |--------------------------------------------------|
                        | decides:                                          |
                        | - what kind of task this is                       |
                        | - whether one specialist is enough                |
                        | - whether a plan is needed                        |
                        | - whether to ask user a question                  |
                        | - whether to verify / retry / finish             |
                        +----------------------+---------------------------+
                                               |
                     +-------------------------+--------------------------+
                     |                         |                          |
                     v                         v                          v
        +-----------------------+   +-----------------------+   +-----------------------+
        |  Specialist Agent A   |   |  Specialist Agent B   |   |  Specialist Agent C   |
        |  e.g. intake          |   |  e.g. planner         |   |  e.g. researcher      |
        +-----------+-----------+   +-----------+-----------+   +-----------+-----------+
                    |                           |                           |
                    v                           v                           v
         +----------------------+    +----------------------+    +----------------------+
         | tools / APIs / DBs   |    | tools / APIs / DBs   |    | tools / APIs / DBs   |
         | external execution   |    | external execution   |    | external execution   |
         +----------+-----------+    +----------+-----------+    +----------+-----------+
                    |                           |                           |
                    +-------------+-------------+-------------+-------------+
                                  |                           |
                                  v                           v
                    +--------------------------------------------------+
                    |      VERIFIER / POLICY / RULES / GUARDS          |
                    |--------------------------------------------------|
                    | checks:                                           |
                    | - schema                                           |
                    | - tool success                                     |
                    | - business rules                                   |
                    | - consistency                                      |
                    | - safety / policy                                  |
                    | - completeness                                     |
                    +----------------------+---------------------------+
                                               |
                          +--------------------+--------------------+
                          |                                         |
                          v                                         v
            +-------------------------------+       +-------------------------------+
            | success / acceptable result   |       | failure / missing / conflict  |
            +---------------+---------------+       +---------------+---------------+
                            |                                       |
                            v                                       v
              +-------------------------------+       +-------------------------------+
              | final synthesis / renderer    |       | retry / replan / ask user /  |
              | turn result into user reply   |       | escalate / stop               |
              +---------------+---------------+       +---------------+---------------+
                              |                                       |
                              +-------------------+-------------------+
                                                  |
                                                  v
                                    +------------------------------+
                                    |           USER               |
                                    | sees only final AI response  |
                                    +------------------------------+
```

---

## 2. The Layers In Detail

### A. Entry / Front Door Layer

This layer usually owns:

- authentication / tenant / user lookup
- request id / conversation id
- loading visible chat history
- loading durable state
- loading memory or retrieval context
- input normalization

It does **not** usually do the real task logic.

### B. Orchestrator / Supervisor Layer

This is usually the brain of workflow control, but in good systems it is **thin**.

It usually decides:

- route to one specialist
- route to multiple specialists in sequence
- ask user a clarification question
- verify result
- retry or stop

It usually should **not**:

- do deep domain work itself
- micromanage every specialist step
- rewrite every specialist output

### C. Specialist Layer

Each specialist usually has:

- one narrow responsibility
- its own prompt / instructions
- maybe its own tool set
- maybe its own state schema

Examples:

- intake specialist
- planner specialist
- coding specialist
- research specialist
- browser specialist
- reviewer specialist

### D. Verifier / Guards Layer

This is where real systems become reliable.

This layer often owns:

- Pydantic/schema validation
- business rules
- deterministic checks
- state consistency checks
- API/tool result checks
- test runs
- policy or compliance rules

This layer is often code, not just another LLM.

### E. Final Synthesis / Renderer

This layer converts internal results into:

- final user-facing answer
- final saved artifact
- final approval question
- final error explanation

This keeps raw envelopes, state blobs, and tool chatter out of normal chat.

---

## 3. Control Plane vs Data Plane

A useful way to think about agent systems is:

### Control Plane

The control plane decides **what should happen next**.

Usually includes:

- supervisor/orchestrator
- router/classifier
- replan logic
- stop conditions
- escalation logic

### Data Plane

The data plane does the actual **task work**.

Usually includes:

- specialist agents
- tools
- databases
- browser automation
- code execution
- file operations

Diagram:

```text
                CONTROL PLANE
   +----------------------------------------+
   | supervisor / router / verifier / retry |
   +-------------------+--------------------+
                       |
                       v
                 DATA PLANE
   +----------------------------------------+
   | specialists / tools / APIs / databases |
   +----------------------------------------+
```

Good systems keep this distinction clean.

---

## 4. What A Typical Handoff Usually Looks Like

In good systems, the next agent usually does **not** get random garbage.

It gets a handoff packet that often looks like this:

```text
Handoff Packet
--------------
- task
- user goal
- latest user message
- relevant visible history
- shared structured state
- previous agent output
- constraints / policies
- tool results if relevant
```

Detailed diagram:

```text
Supervisor
  |
  | builds handoff packet
  v
+-----------------------------------------------------------+
|                     HANDOFF PACKET                        |
|-----------------------------------------------------------|
| task: "what this next agent must do"                      |
| user_goal: "overall objective"                            |
| latest_user_message: freshest request                     |
| relevant_history: visible USER/AI conversation            |
| shared_state: structured state facts                      |
| previous_agent_output: last specialist result             |
| constraints: things this specialist must not change       |
| tool_truth: optional API/database/tool outputs            |
+-----------------------------------------------------------+
  |
  v
Specialist Agent
```

### What usually does NOT go in the handoff

- full scratchpad / hidden chain of thought
- every failed attempt
- every internal intermediate artifact
- irrelevant old conversation

---

## 5. What Usually Lives In Chat vs State vs Memory

This is one of the most important distinctions.

```text
                         +------------------------+
                         |     VISIBLE CHAT       |
                         |------------------------|
                         | USER messages          |
                         | final AI responses     |
                         | clarification turns    |
                         +-----------+------------+
                                     |
                                     |
                         +-----------v------------+
                         |   SHARED STRUCTURED    |
                         |         STATE          |
                         |------------------------|
                         | latest intake object   |
                         | latest plan draft      |
                         | worker envelope        |
                         | runtime flags          |
                         | verifier results       |
                         +-----------+------------+
                                     |
                                     |
                         +-----------v------------+
                         |    LONG-TERM MEMORY    |
                         |------------------------|
                         | user preferences       |
                         | prior behavior         |
                         | episodic history       |
                         | retrieval summaries    |
                         +------------------------+
```

### Normal rule of thumb

- `chat` = what the user and assistant say
- `state` = what the system needs to operate this workflow
- `memory` = what should persist across many turns/sessions

---

## 6. The Usual Sequential Workflow

This is probably the most common production pattern.

```text
User
-> supervisor
-> specialist A
-> verifier
-> specialist B
-> verifier
-> final renderer
-> user
```

Example:

```text
User asks for a task
-> supervisor classifies the request
-> intake specialist gathers or confirms structured input
-> validator checks whether input is usable
-> planner specialist creates output
-> verifier checks schedule or business rules
-> final response is rendered
```

This is very common because it is:

- understandable
- controllable
- debuggable
- good for stateful apps

---

## 7. The Usual Parallel Workflow

Used when different subproblems can be worked in parallel.

```text
                        +----------------------+
                        |     Supervisor       |
                        +----------+-----------+
                                   |
             +---------------------+---------------------+
             |                     |                     |
             v                     v                     v
   +------------------+  +------------------+  +------------------+
   | Specialist A     |  | Specialist B     |  | Specialist C     |
   | e.g. browsing    |  | e.g. analysis    |  | e.g. code scan   |
   +--------+---------+  +--------+---------+  +--------+---------+
            |                     |                     |
            +----------+----------+----------+----------+
                       |                     |
                       v                     v
              +--------------------------------------+
              |      aggregator / verifier           |
              +------------------+-------------------+
                                 |
                                 v
                       +----------------------+
                       | final synthesis      |
                       +----------------------+
```

This is common for:

- research tasks
- broad repo analysis
- document review
- multiple independent fetches

---

## 8. Retry / Replan / Escalation Loop

Production systems usually need a failure branch.

```text
             +----------------------+
             | specialist result    |
             +----------+-----------+
                        |
                        v
             +----------------------+
             | verifier / rules     |
             +----+------------+----+
                  |            |
          pass    |            | fail
                  |            |
                  v            v
      +----------------+   +----------------------+
      | final response |   | retry / repair       |
      +----------------+   | or ask user          |
                           | or escalate          |
                           +----------+-----------+
                                      |
                                      v
                           +----------------------+
                           | supervisor decides   |
                           | next step            |
                           +----------------------+
```

The most common failure strategies are:

- retry same specialist with verifier feedback
- route to another specialist
- ask user for missing info
- escalate to human/operator
- stop and return partial result

---

## 9. Where Companies Usually Put Determinism

Real systems often mix LLM and code like this:

```text
LLM is allowed to:
- interpret user intent
- draft candidate output
- summarize or explain
- propose structure

Code is allowed to:
- validate schema
- enforce rules
- compute canonical fields
- commit durable truth
- call side-effectful APIs safely
```

Diagram:

```text
             +----------------------+
             |      LLM LAYER       |
             |----------------------|
             | interpret            |
             | draft                |
             | summarize            |
             +----------+-----------+
                        |
                        v
             +----------------------+
             |      CODE LAYER      |
             |----------------------|
             | validate             |
             | compute              |
             | enforce              |
             | persist              |
             +----------------------+
```

This hybrid is extremely common.

---

## 10. Fixed Specialists vs Dynamic Agents

### Fixed specialists

```text
Supervisor
-> Intake
-> Planner
-> Reviewer
```

Pros:

- easier to debug
- clearer ownership
- stable prompts
- stable contracts

Used very often in practical systems.

### Dynamic spawned agents

```text
Supervisor
-> create temporary agent for subtask X
-> create temporary agent for subtask Y
-> collect results
```

Pros:

- flexible
- useful for varied research tasks

Cons:

- harder to observe
- harder to prompt well
- more moving parts

Used less often for stateful product workflows.

---

## 11. Thin Supervisor vs Fat Supervisor

### Thin supervisor

```text
Supervisor responsibilities:
- classify
- route
- pass context
- decide stop / continue
```

This is usually good.

### Fat supervisor

```text
Supervisor responsibilities:
- classify
- reason deeply
- rewrite outputs
- verify semantics
- micromanage all workers
- remember all sub-agent states
```

This is usually bad because:

- context bottleneck
- more latency
- more token cost
- single point of failure

---

## 12. Where Swarm Differs

The architecture above is the normal practical architecture.

A pure swarm is different:

```text
Agent A <-> Agent B <-> Agent C
     \        |         /
      \       |        /
        ---- shared context ----
```

Characteristics:

- weaker central control
- more peer-to-peer movement
- more parallelism or consensus
- more need for shared-context integrity

Better for:

- exploration
- idea generation
- research
- decentralized consensus

Worse for:

- structured transactional systems
- hard state ownership
- easy debugging

---

## 13. Typical Failure Map

When a multi-agent system fails, the fault is usually in one of these places:

```text
1. routing failure
   supervisor sent the task to the wrong specialist

2. handoff failure
   the right specialist got the wrong context

3. specialist failure
   the agent prompt/logic/tool use was weak

4. verification failure
   the result was bad but no guard caught it

5. synthesis failure
   the internal result was okay but the final answer was bad

6. persistence failure
   the state/database commit was wrong
```

This is why clean boundaries matter.

---

## 14. The Most Common Good Pattern In One Picture

```text
User
-> entry layer
-> thin supervisor
-> fixed specialist
-> verifier / rules
-> maybe next specialist
-> final renderer
-> user

With:
- visible chat
- structured state
- long-term memory
- tools / APIs / DBs
- retry / replan / escalation path
```

---

## 15. The Practical Default Recommendation

If you do not know what to choose, the default practical architecture is:

```text
thin supervisor
+ fixed specialist agents
+ structured handoffs
+ deterministic verification
+ final synthesis layer
```

That is the usual strong default.

---

## 16. References

- Chain-of-Agents: https://arxiv.org/abs/2406.02818
- AgentOrchestra: https://arxiv.org/abs/2506.12508
- Autonoma: https://arxiv.org/abs/2603.19270
- Verified Multi-Agent Orchestration: https://arxiv.org/abs/2603.11445
