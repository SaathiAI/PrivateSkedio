# SkedioAI

SkedioAI is an AI-powered study planning platform designed to help students turn overwhelming academic goals into clear, realistic, and adaptable study plans.

It brings together planning, scheduling, progress tracking, and guidance in one system so students can stay organized without losing flexibility.

## What The Project Is About

SkedioAI is built for students who do not just need a timetable, but a smarter way to study.

Instead of asking students to manually organize everything on their own, SkedioAI helps them:

- understand what they need to work on
- convert that into a practical study plan
- see their schedule clearly
- track progress over time
- adjust when real life changes

The product is meant to feel like a study companion that is structured, supportive, and aware of how actual academic planning works.

## Core Features

- intelligent study planning
- calendar-aware scheduling
- plan review before commitment
- progress tracking across sessions and subtopics
- graph-based learning visibility
- notification and review support through email-linked flows

## Core User Experience

At a high level, a student can use SkedioAI to:

1. describe what they need to study
2. generate a structured study plan
3. review the plan before making it active
4. work through scheduled sessions
5. track progress over time
6. adapt the plan when circumstances change

## Repository Structure

The primary reviewable parts of this repository are:

```text
.
├── skedio-landing/         # public-facing landing page
├── Weekly-Study-Planner/   # main SkedioAI application
└── README.md               # overall project overview
```

There are also supporting local-development and archive folders in the repository root, but the two folders above are the intended project deliverables.

## Project Parts

### `skedio-landing/`

This folder contains the landing page for SkedioAI.

It represents the presentation side of the project:

- what the product is
- who it is for
- how it should feel on first impression

### `Weekly-Study-Planner/`

This folder contains the main application.

It includes the actual product implementation, including:

- frontend and backend application logic
- study-planning workflows
- review and progress flows
- agent orchestration
- memory and database integration
- product documentation

## How To Review This Repository

For a quick walkthrough:

1. read this root README for the overall product picture
2. open `skedio-landing/` for the landing-page side of the project
3. open `Weekly-Study-Planner/` for the main application and technical implementation

Each project folder includes its own README with more specific detail.

## Summary

SkedioAI is a study planning product focused on helping students move from confusion to clarity.

This repository is split into two main parts:

- a landing page that presents the product
- the main application that powers the actual planning experience
