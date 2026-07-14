
This document maps the current React frontend under `saathi-ui/src`.

It is current live truth for the shipped frontend app surface.

It focuses on the main study-planner app surface:
- auth gate
- calendar view
- AI drawer
- draft-plan review UI
- API wrapper flow

---

## Entry Flow

```mermaid
flowchart TD
    Main["main.jsx"] --> App["App.jsx"]
    App --> AuthProvider["AuthProvider"]
    AuthProvider --> StudyPlanApp["StudyPlanApp"]
```

`StudyPlanApp` is the live shell for the product.

---

## High-Level UI Structure

```mermaid
flowchart LR
    Sidebar["Left sidebar"]
    Workspace["Main workspace"]
    Drawer["Right AI drawer"]

    Sidebar --> Workspace
    Workspace --> Drawer
```

The key live views are:
- Calendar
- Plan History
- Settings
- Knowledge Graph modal
- Profile modal
- Session checklist modal
- Chat drawer

---

## Main Component Tree

```mermaid
flowchart TB
    StudyPlanApp["StudyPlanApp"]

    StudyPlanApp --> GlobalStyles["GlobalStyles"]
    StudyPlanApp --> CalendarGrid["CalendarGrid"]
    StudyPlanApp --> ChatPanel["ChatPanel"]
    StudyPlanApp --> PlanHistory["PlanHistoryView"]
    StudyPlanApp --> Settings["SettingsView"]
    StudyPlanApp --> Graph["KnowledgeGraphModal"]
    StudyPlanApp --> Profile["ProfileDashboardModal"]
    StudyPlanApp --> SessionModal["SessionChecklistModal"]
    StudyPlanApp --> ErrorBoundary["ViewErrorBoundary"]
```

`StudyPlanApp` is the state hub.

It owns:
- loaded plans
- active plan
- draft plan preview
- external calendar blockers
- current tab
- AI drawer visibility
- AI drawer width
- thread id

---

## Data Flow In `StudyPlanApp`

```mermaid
flowchart TD
    App["StudyPlanApp state"]
    App --> PlanApi["planApi"]
    App --> StatsApi["statsApi"]
    App --> CalendarApi["calendarApi"]
    App --> ChatPanel["ChatPanel props"]
    App --> CalendarGrid["CalendarGrid props"]

    PlanApi --> ActivePlan["active plan"]
    StatsApi --> Stats["dashboard stats"]
    CalendarApi --> External["external blockers"]
    ChatPanel --> Draft["draft plan / commit callbacks"]
    Draft --> App
```

Main page hydration uses:
- `planApi.getActive()`
- `planApi.listAll()`
- `statsApi.dashboard()`
- `calendarApi.externalEvents(...)`

---

## Calendar View

`CalendarGrid.jsx` renders:
- day columns
- hour rails
- current time line
- external blockers
- SkedioAI sessions
- draft sessions

```mermaid
flowchart TD
    Inputs["allDays + externalEvents + draftMode"] --> Merge["merge days with external blockers"]
    Merge --> Render["render sticky day header + hour grid"]
    Render --> Blocks["render external blocker cards"]
    Render --> Sessions["render session cards"]
    Sessions --> Click["onSessionClick -> modal/open details"]
```

Important live behavior:
- external blockers are inserted into the same day columns
- draft sessions get a red “DRAFT” styling path
- completed/skipped sessions render differently from active ones

---

## Chat Drawer

`ChatPanel.jsx` is the live AI interaction surface.

It owns:
- local message list for the thread
- input box
- request-changes mode
- action button handling
- streaming reply assembly

```mermaid
flowchart TD
    User["user types chat"] --> Send["chatApi.sendStream"]
    Send --> Stream["receive NDJSON chunks"]
    Stream --> LocalState["append assistant text progressively"]
    LocalState --> FinalPayload["done payload"]
    FinalPayload --> DraftState["onDraftStateChange"]
    FinalPayload --> CommitRefresh["onPlanCommitted when committed"]
```

---

## Draft Review UI Flow

This is the most important current frontend behavior.

```mermaid
flowchart TD
    Backend["ChatResponse with pending_ui + draft_plan"] --> ChatPanel["buildAssistantMessage"]
    ChatPanel --> ActionGroups["buildActionGroups"]
    ActionGroups --> Core["Approve / Request changes / Cancel"]
    Core --> Action["chatApi.action(...)"]
```

Important rule:

```text
The frontend does not guess review actions.
It renders structured actions from backend payload.
```

---

## Draft Plan Overlay Flow

`StudyPlanApp` chooses:

```text
visiblePlan = draftPlan || plan
```

That means:
- when backend returns a draft, the calendar can preview it immediately
- when committed or cleared, the app falls back to the durable active plan

```mermaid
flowchart LR
    Active["durable active plan"] --> Visible["visiblePlan"]
    Draft["temporary draft plan"] --> Visible
    Visible --> CalendarGrid["calendar render"]
```

---

## Client API Layer

The frontend API wrappers are simple and separated by domain:

```mermaid
flowchart TB
    API["lib/api.js"]
    API --> PlanApi["planApi"]
    API --> ChatApi["chatApi"]
    API --> CalendarApi["calendarApi"]
    API --> SessionApi["sessionApi"]
```

### `api.js`

Base helpers:
- `authFetch`
- timeout wrapper
- GET/POST helpers
- JSON/error helpers
- query-string builder

### `planApi`

- get active plan
- list plans
- allocation summary

### `chatApi`

- send normal chat
- send stream
- send UI action

### `calendarApi`

- status
- connect URL
- disconnect
- external blockers

### `sessionApi`

- complete session
- update content status
- undo session
- skip session

---

## Streaming Chat Flow

The streaming chat path is:

```mermaid
sequenceDiagram
    participant User
    participant ChatPanel
    participant chatApi
    participant FastAPI

    User->>ChatPanel: submit message
    ChatPanel->>chatApi: sendStream(message, threadId)
    chatApi->>FastAPI: POST /chat/send/stream
    FastAPI-->>chatApi: NDJSON chunk events
    chatApi-->>ChatPanel: onChunk(text)
    FastAPI-->>chatApi: done payload
    chatApi-->>ChatPanel: final response payload
```

The final payload may contain:
- `reply`
- `plan_committed`
- `actions`
- `draft_plan`
- `pending_ui`

---

## Dev Preview Path

The current frontend has a local preview harness for draft-plan review UI.

```mermaid
flowchart TD
    DevButton["Dev: Preview draft"] --> PreviewBuilder["plannerDraftPreview.js"]
    PreviewBuilder --> FakePayload["review payload shaped like backend response"]
    FakePayload --> ChatPanel["preview assistant message"]
    FakePayload --> StudyPlanApp["draft plan overlay"]
```

This is useful for iterating on UI without running the full agent flow.

---

## Most Important Surfaces To Read

If you are debugging the frontend, read in this order:

1. `src/components/StudyPlanApp.jsx`
2. `src/components/ChatPanel.jsx`
3. `src/components/CalendarGrid.jsx`
4. `src/lib/chatApi.js`
5. `src/lib/planApi.js`
6. `src/lib/calendarApi.js`
7. `src/lib/sessionApi.js`

That usually tells you whether the bug is:
- state ownership
- chat payload handling
- calendar rendering
- or API integration
