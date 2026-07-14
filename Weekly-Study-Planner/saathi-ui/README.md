# SkedioAI Frontend

This folder contains the frontend application for SkedioAI.

It is the main user-facing interface for the study-planning system.

While the backend and agent logic live elsewhere, this folder is where the product experience comes together through:

- dashboard views
- chat interaction
- calendar and planning surfaces
- progress and checklist flows
- settings and profile views

## What This Frontend Is Responsible For

The frontend is responsible for presenting the product in a usable way.

At a practical level, it handles:

- showing plan and session data
- sending user chat turns to the backend
- rendering review and approval flows
- exposing progress, checklist, and session-completion actions
- visualizing calendar and knowledge-related surfaces
- maintaining client-side state for the active user experience

The frontend is not the source of truth for planning logic.
It is the application surface that talks to the backend runtime.

## Main Tech Stack

This frontend is built with:

- React
- Vite
- JavaScript
- component-level CSS and shared theme files

It also includes frontend-side helper modules for:

- API access
- plan adaptation
- session actions
- dashboard shaping
- lightweight client-state management

## Folder Structure

```text
saathi-ui/
├── README.md
├── package.json
├── vite.config.js
├── index.html
├── public/
├── scripts/
└── src/
```

## Important Subfolders

### `src/components/`

This contains the main UI surfaces and reusable application components.

Examples include:

- `Dashboard.jsx`
- `ChatPanel.jsx`
- `CalendarGrid.jsx`
- `KnowledgeGraph.jsx`
- `SettingsView.jsx`
- `SessionChecklistModal.jsx`
- `StudyPlanApp.jsx`

This is the best place to start if you want to understand the visible product structure.

### `src/lib/`

This contains frontend-side helpers and adapters for talking to backend APIs and shaping data for the UI.

Examples include:

- API clients
- chat helpers
- calendar API wiring
- session and plan adapters
- dashboard adapter logic
- lightweight performance helpers

### `src/hooks/`

This contains focused frontend logic such as session-action hooks and other reusable interaction behavior.

### `src/dev/`

This contains developer-oriented preview helpers and local mock support.

### `scripts/`

This contains frontend-specific test or utility scripts.

## Main User Flows Represented Here

The frontend supports several important product flows:

### 1. Chat and planning flow

The user talks to the system through the chat surface.

That conversation can lead to:

- intake clarification
- planning
- revision
- review requests
- user-facing explanations

### 2. Review and approval flow

The frontend surfaces draft-plan review states so the user can approve, reject, or request changes.

### 3. Session completion flow

The frontend allows users to:

- tick or untick work
- submit actual-hours information
- update progress state

### 4. Dashboard and progress flow

The frontend shows:

- plan state
- weekly shape
- session status
- broader progress and study surfaces

### 5. Calendar-connected flow

The frontend also represents calendar-driven planning and related schedule surfaces.

## How This Frontend Connects To The Rest Of The System

At a high level:

```text
React frontend
-> frontend API helpers
-> FastAPI backend
-> supervisor / agents / services
-> database and integration layers
```

So this folder is tightly connected to the backend runtime, but it does not own the deeper planning truth by itself.

## Important Files

- `package.json`  
  frontend dependencies and scripts

- `vite.config.js`  
  Vite configuration

- `src/main.jsx`  
  frontend entry point

- `src/App.jsx`  
  main app shell

- `src/theme.js`  
  theme definitions and shared frontend styling logic

- `src/index.css` and `src/App.css`  
  base frontend styling

## Running The Frontend

Typical local frontend workflow is:

```bash
npm install
npm run dev
```

Depending on the backend environment, the frontend may also expect the API server to be running for full behavior.

## Notes For Reviewers

A few useful things to know:

- this is not just a static UI shell; it is wired to a larger planning runtime
- several components are shaped around backend-driven state and review flows
- the visual and interaction layer is still connected to an evolving multi-agent product backend
- some UX surfaces exist to represent product concepts that are heavier than a simple CRUD dashboard

## Relationship To The Main Project

This folder is one part of:

- `../src/` for backend and orchestration
- `../tests/` for behavior validation
- `../documentation/` for architecture and workflow explanation

If you want to understand the frontend in system context, pair this folder with:

- `../README.md`
- `../documentation/12-api-and-frontend-runtime-flow.md`

## Summary

This folder is the user-facing frontend for SkedioAI.

It turns the backend planning system into an actual product experience by handling:

- chat
- planning views
- calendar views
- review flow
- progress flow
- dashboard surfaces

It is the visible face of the application layer.
