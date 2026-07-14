# OpenHands Benchmark and Findings

## Purpose

This document records the OpenHands comparison work and what it revealed about SkedioAI’s architecture needs.

## Why OpenHands Was Explored

The project explored OpenHands to compare a custom orchestration approach against a framework-based agent architecture.

The goal was not just curiosity.
It was to test whether a framework-first path might reduce complexity or improve behavior.

## What Was Being Compared

The comparison centered around whether the planning system should remain:

- a custom orchestration flow

or be expressed through:

- an OpenHands-style agent framework approach

## What OpenHands Looked Good At

OpenHands offered attractive strengths such as:

- agent tooling ecosystem
- automation-oriented environment assumptions
- some convenience around tool surfaces and execution setup

## What Did Not Fit Well

The strongest mismatch was that SkedioAI is not fundamentally an autonomous software-engineering agent problem.

It is a:

- conversational
- stateful
- human-in-the-loop
- approval-sensitive
- multi-step planning workflow

That is a very different shape.

## Main Problems Observed

### 1. No native strong supervisor/routing story

The project needed real orchestration, not loose delegation.

### 2. Structured state management pressure

The project benefits heavily from explicit shared state and controlled handoff semantics.

### 3. Resume/state persistence complexity

The planning workflow requires strong continuity across turns and worker states.

### 4. Framework mismatch

OpenHands aligns better with autonomous engineering tasks than with this style of planning conversation architecture.

## Operational Pain

There was also practical pain around environment and configuration behavior, including:

- Docker vs non-Docker differences
- configuration file confusion
- invalid API configuration carried in the wrong path
- MCP-related complexity layered onto framework exploration

## Important Conclusion

The comparison was valuable because it clarified that the difficulty in SkedioAI is not just “having multiple agents.”

The real difficulty is:

- orchestration discipline
- state continuity
- ownership boundaries
- human approval flow
- reliable planner/intake handoff

Those are exactly the areas where the custom architecture retained stronger control.

## Final Takeaway

The OpenHands exploration was useful, but it did not replace the need for:

- explicit orchestration
- explicit planning state
- explicit ownership boundaries

The project kept learning from the comparison, but the custom orchestration direction remained the better fit for SkedioAI.
