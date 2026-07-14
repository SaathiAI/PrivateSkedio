# Calendar Diagram

This document maps the live calendar stack used by SkedioAI.

Relevant files:
- `src/tools/calendar_ops.py`
- `src/api/calendar_service.py`
- `src/tools/test_mcp_client.py`
- `src/api/routes.py`
- `src/api/calendar_webhook.py`
- `src/agents/monitor.py`

This is a layered system:
- per-user OAuth token retrieval
- Google Calendar API helpers
- MCP client wrapper
- FastAPI integration
- webhook clash handling
- missed-session monitoring

---

## High-Level Calendar Stack

```mermaid
flowchart TD
    Frontend["React frontend"]
    Routes["FastAPI routes"]
    MCPClient["CalendarClient MCP wrapper"]
    MCPServer["calendar_mcp_server"]
    Core["calendar_ops core functions"]
    OAuth["calendar_service per-user OAuth tokens"]
    Google["Google Calendar API"]
    Supabase["Supabase user_settings"]

    Frontend --> Routes
    Routes --> MCPClient
    MCPClient --> MCPServer
    MCPServer --> Core
    Core --> OAuth
    OAuth --> Supabase
    OAuth --> Google
```

---

## Main Layers

### 1. `calendar_service.py`

Purpose:
- fetch per-user Google Calendar tokens from Supabase
- refresh them when expired
- build a Google Calendar service for that user

Main functions:
- `get_supabase`
- `get_calendar_service_for_user`
- `is_calendar_connected`

### 2. `calendar_ops.py`

Purpose:
- core calendar operations against Google Calendar
- fallback to local dev token when allowed

Main functions:
- `create_event_core`
- `create_events_from_plan_core`
- `list_events_core`
- `delete_skedioai_events_in_range_core`
- `delete_skedioai_event_by_slot_core`
- `mark_event_completed_core`
- `get_non_skedioai_events_core`

### 3. `test_mcp_client.py`

Purpose:
- MCP client wrapper used by the app/backend

Main methods:
- `connect`
- `disconnect`
- `_call`
- `create_event`
- `create_events_from_plan`
- `list_events`
- `delete_skedioai_events_in_range`
- `delete_skedioai_event_by_slot`
- `mark_event_completed`
- `get_non_skedioai_events`

### 4. `routes.py`

Purpose:
- initialize shared calendar client
- expose blocker data to frontend
- sync session completion state to calendar

### 5. `calendar_webhook.py`

Purpose:
- detect external calendar changes that clash with future incomplete SkedioAI sessions
- trigger planner review flow when needed

### 6. `monitor.py`

Purpose:
- periodically detect missed incomplete SkedioAI study sessions
- send alert emails

---

## Authentication / Token Flow

```mermaid
sequenceDiagram
    participant Core as calendar_ops
    participant OAuth as calendar_service
    participant SB as Supabase
    participant G as Google OAuth

    Core->>OAuth: get_calendar_service_for_user(user_id)
    OAuth->>SB: read user_settings tokens
    SB-->>OAuth: access_token + refresh_token + expiry
    OAuth->>G: refresh token if expired
    OAuth-->>Core: Google service + calendar_id
```

Important rule:

```text
Production should use per-user OAuth tokens.
Local fallback token is a dev convenience only.
```

---

## Fallback Rule

`calendar_ops.py` supports a local fallback path.

```mermaid
flowchart TD
    NeedService["need calendar service"] --> HasUser{"user_id present?"}
    HasUser -->|yes| OAuthTry["try per-user OAuth service"]
    HasUser -->|no| FallbackCheck["is local fallback allowed?"]
    OAuthTry --> Success{"OAuth succeeded?"}
    Success -->|yes| ReturnOAuth["return user calendar service"]
    Success -->|no| FallbackCheck
    FallbackCheck -->|yes| Local["use local create_events.json token"]
    FallbackCheck -->|no| Error["raise not connected error"]
```

This is why local dev can work even when a user has not connected calendar.

---

## Non-SkedioAI Blocker Read Path

This is the most important calendar read path for planning.

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as /calendar/events/external
    participant Client as CalendarClient
    participant Core as get_non_skedioai_events_core
    participant G as Google Calendar

    FE->>API: request start_date/end_date
    API->>Client: get_non_skedioai_events(...)
    Client->>Core: MCP tool call
    Core->>G: list events in date range
    G-->>Core: all events
    Core-->>Client: blocked_slots JSON
    Client-->>API: JSON string
    API-->>FE: blocker payload
```

What `get_non_skedioai_events_core` does:
- includes non-SkedioAI events as blockers
- also treats completed SkedioAI events as blocked or completed time
- returns:
  - `has_blocks`
  - `blocked_slots`
  - `summary`

This is why planner and revision flows can avoid double-booking over real commitments.

---

## Create Events From Plan Path

```mermaid
flowchart TD
    Plan["StudyPlan JSON"] --> Tasks["_tasks_from_plan"]
    Tasks --> EventRows["session-level event rows"]
    EventRows --> Insert["create Google Calendar events"]
    Insert --> Mark["mark source=skedioai, event_id, plan_id, is_completed=false"]
```

Important rule:

```text
Calendar events are created at session level.
Checklist or content items live in the event description, not as separate calendar events.
```

---

## Completion Sync Path

When the user completes a session, the backend can mirror that into calendar:

```mermaid
flowchart TD
    SessionDone["session marked done in backend"] --> Route["_sync_calendar_session_status"]
    Route --> Client["CalendarClient.mark_event_completed"]
    Client --> Core["mark_event_completed_core"]
    Core --> Google["update event extendedProperties + color"]
```

Live behavior:
- marks `is_completed=true/false`
- may set event color
- is best-effort, not the source of truth

Important rule:

```text
Neo4j completion is authoritative.
Calendar completion is a sync side effect.
```

---

## SkedioAI vs Non-SkedioAI Event Distinction

```mermaid
flowchart LR
    GoogleEvent["Google event"] --> Source{"extendedProperties.private.source"}
    Source -->|skedioai| SkedioAI["SkedioAI-created session event"]
    Source -->|anything else / absent| External["external blocker or normal user event"]
```

This distinction drives:
- deletion behavior
- blocker extraction
- completion updates
- missed-session detection

---

## Main Calendar Operations

```mermaid
flowchart TB
    Ops["calendar_ops"]
    Ops --> Create["create_event_core"]
    Ops --> CreatePlan["create_events_from_plan_core"]
    Ops --> List["list_events_core"]
    Ops --> DeleteRange["delete_skedioai_events_in_range_core"]
    Ops --> DeleteSlot["delete_skedioai_event_by_slot_core"]
    Ops --> Complete["mark_event_completed_core"]
    Ops --> Blockers["get_non_skedioai_events_core"]
```

### `create_event_core`
- create one SkedioAI event

### `create_events_from_plan_core`
- explode a plan into session events

### `list_events_core`
- read events in range

### `delete_skedioai_events_in_range_core`
- remove only unfinished SkedioAI events

### `delete_skedioai_event_by_slot_core`
- delete one matching SkedioAI event

### `mark_event_completed_core`
- toggle completion state on one event

### `get_non_skedioai_events_core`
- extract blocker slots for planning

---

## Webhook vs Monitor Split

```mermaid
flowchart TD
    CalendarChange["external calendar change"] --> Webhook["calendar_webhook"]
    Webhook --> Clash["detect clash with future incomplete sessions"]
    Clash --> Review["planner review draft or conflict email"]

    TimePasses["time passes after session slot"] --> Monitor["monitor.py"]
    Monitor --> Missed["find incomplete past SkedioAI sessions"]
    Missed --> Alert["send missed-session alert email"]
```

The webhook is the immediate clash responder.
The monitor is the background missed-session watcher.

---

## Backend Integration Points

Current main usages:

```mermaid
flowchart LR
    Routes["FastAPI routes"] --> Blockers["external blocker fetch"]
    Routes --> Completion["session completion sync"]
    Webhook["calendar webhook"] --> Blockers
    Monitor["monitor job"] --> Completion
```

In practice:
- frontend uses external blockers for display
- planner and webhook-driven revision use blockers for schedule safety
- monitor uses completion metadata to detect missed study sessions

---

## Debugging Questions

When calendar behavior is wrong, ask:

1. Was this supposed to use per-user OAuth or local fallback?
2. Did `CalendarClient` connect successfully?
3. Did the MCP layer call the correct core function?
4. Was the event actually tagged with `source=skedioai`?
5. Is the issue in Google Calendar state, or in SkedioAI's interpretation of it?

That usually separates:
- auth/token bugs
- MCP connectivity bugs
- event-tagging bugs
- blocker-interpretation bugs
