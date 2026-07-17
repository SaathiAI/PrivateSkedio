# Project Overview

## What SkedioAI Is

SkedioAI is an AI-powered study planning system designed to help students turn broad academic goals into realistic, reviewable, and adaptable study plans.

The product is built around a simple idea:

- students usually know they need to study
- they often do not know how to scope it properly
- even when they make a plan, life changes break it
- generic planners rarely adapt intelligently

SkedioAI exists to bridge that gap.

It is not just a timetable generator, and it is not just a chatbot.
It is a planning system that combines conversation, scheduling, progress tracking, and revision workflows into one product.

## Who It Is For

The current product is oriented around school-level learners, especially the Class 10 study-planning use case that shaped most of the project decisions.

The system assumes a student may have:

- unclear scope
- inconsistent availability
- fixed commitments
- backlogs from previous plans
- changing urgency across subjects
- real-world disruptions like illness, exams, or new calendar events

## The Problem It Solves

Most study planning tools fail in one or more of these ways:

1. They create static schedules that do not adapt.
2. They ignore unfinished work from earlier plans.
3. They assume unrealistic consistency from the user.
4. They do not carry behavioral context forward.
5. They do not give the user a clean review step before changes become active.

SkedioAI is designed to solve those failures by building a loop instead of a one-time output.

## Core Product Promise

The intended product experience is:

```text
Student describes the goal
-> system understands scope and constraints
-> system builds a clean planning contract
-> system generates a timed draft plan
-> user reviews the draft
-> approved plan becomes active
-> progress is tracked over time
-> later changes can trigger a revision instead of a full restart
```

That loop is the heart of the product.

## Visible Product Features

### 1. Guided study intake

The system helps the user define:

- what they need to study
- by when
- with what daily capacity
- under what commitments or rest constraints

### 2. Drafted study plans

The system turns the intake result into a timed study plan rather than a vague to-do list.

### 3. Review-before-commit workflow

The plan is not automatically accepted.
The user can review it, approve it, ask for changes, or discard it.

### 4. Calendar-aware planning

The system can use calendar blockers and availability constraints so that the study plan fits into real life instead of fighting it.

### 5. Progress tracking

The product tracks plan execution through:

- session completion
- subtopic completion
- visible progress summaries
- plan-aware state updates

### 6. Knowledge graph / learning map

The system includes a graph-style learning view to expose concept relationships and progress shape in a more structural way.

### 7. Email-linked review and notification flow

Email is part of the workflow.

It is used for things like:

- draft review links
- planning notifications
- reconnecting the user back into the main planning/chat flow

### 8. Adaptive revision

When circumstances change, the system can revise the remaining schedule instead of forcing the user to start over from scratch.

## Current Frontend Product Shape

The current live frontend is not a marketing shell.
It is an authenticated product workspace shaped around a small number of operational surfaces.

The main visible areas today are:

- planner calendar workspace
- AI assistant drawer and review surface
- dashboard / overview surface
- knowledge graph modal
- plan history
- settings and integrations
- auth flow

The planner is currently the clearest primary surface.
It includes a week-based calendar, session cards, blocker overlays, draft-plan preview, and session interaction paths.

The AI assistant is not treated as a decorative chatbot.
It is part of the planning workflow:

- creating or revising a plan
- presenting review actions
- returning structured draft data
- helping the user commit, request changes, or cancel

This matters because the product should be understood as:

```text
workspace first
assistant second
planner loop at the center
```

not as “chat with an AI and maybe get a schedule.”

## Product Philosophy

The product tries to combine:

- human-like conversation
- code-enforced structure
- realistic scheduling
- durable progress state

The system should feel supportive, but it should not rely entirely on fuzzy language understanding.

A core design belief behind the project is:

```text
LLMs should reason, ask, explain, and draft.
Code should validate, verify, store, and enforce truth.
```

That principle influenced nearly every major architecture decision in the project.

## What Makes It Different

SkedioAI is different from a generic planning assistant because it is trying to preserve:

- scope
- timing
- feasibility
- progress
- context

across multiple turns and over time.

That means the system is not judged only by the first plan it creates.
It is also judged by how well it behaves when the plan needs to change.

## Current Product Shape

At a product level, SkedioAI currently includes:

- a frontend workspace with planner-first UI
- a backend API layer
- a supervisor-driven orchestration flow
- an intake workflow
- a planner workflow
- a review/approval path
- progress operations
- memory and retrieval support
- calendar integration
- email-linked workflow support

The internals are described in later documents.
This file is only meant to establish the project purpose and product shape.
