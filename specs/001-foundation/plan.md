# Implementation Plan: Foundation, Room Inventory & Guest Lifecycle

**Branch**: `001-foundation` | **Date**: 2026-08-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-foundation/spec.md`

## Summary

Replace the flat, unauthenticated `guests` table and broken lookup tool with a real schema
(`guests` + `reservations` + room inventory) and a full guest-lifecycle tool set on
`concierge_agent`: identity verification, check-in/check-out, booking creation, date
modification/cancellation (confirmation-gated), and a minimal human-handoff escape hatch. This is
three originally-separate proposal phases (0, 1, 2) merged into one gated unit because Phase 2's
tools are unusable without Phase 0's `reservations` table and Phase 1's room inventory both
existing first (see spec.md Clarifications).

## Technical Context

**Language/Version**: Python 3.14 (current `agent/.venv`), SQL (PostgreSQL 15+ via Supabase)

**Primary Dependencies**: `google-adk` 2.5.0 (agent framework, `LiteLlm` model wrapper), `psycopg`
3.3.4 (Postgres driver), `pgvector` 0.5.0 (vector column support — unaffected by this phase, kept
for `policy_chunks`), `voyageai` 0.5.0 (embeddings — unaffected by this phase), `python-dotenv`
1.2.2

**Storage**: Single PostgreSQL instance via Supabase, `pgvector` extension already enabled. No new
data store introduced (constitution Principle V).

**Testing**: No automated test suite exists yet (R6) and building one is not this phase's job — the
MVP week schedule puts a dedicated testing day after this phase. Verification here is manual: each
user story's acceptance scenarios are checked by hand via the agent's `adk run`/`adk web` dev UI and
direct SQL row-count checks. `quickstart.md` documents these as repeatable steps.

**Target Platform**: Local development only — Supabase-hosted Postgres (remote), agent process run
locally. No deployment target exists yet (R7); out of scope per this phase's Assumptions.

**Project Type**: Single backend project (agent + SQL migrations). No frontend — `web/` stays empty
this phase (§15 of the proposal is unscoped for the MVP week).

**Performance Goals**: Not applicable at this phase's scale — demo-sized data (300 seed rows plus
whatever's created live in a session), single local user at a time.

**Constraints**: The agent currently opens one shared `psycopg` connection at import time with no
reconnect logic (R3). Not fixed this phase — that's Addendum D / Phase 3 (resilience) territory —
but every tool this phase adds must still fail structurally (FR-008: `{status, data, error}`, never
raise) rather than crash the process if that connection drops mid-call.

**Scale/Scope**: 300 pre-existing guest/reservation rows (migrated, not replaced), 6 room types
(the source proposal's own count — research.md §1), 60 room instances total (10 per type) —
single-property scope, confirmed by the proposal's decision to drop the Kaggle `hotel` column.

## Constitution Check

*GATE: Must pass before Phase 0 (this plan's) research. Re-checked after Phase 1 design below.*

| Principle | Check | Result |
|---|---|---|
| I. Guide, Don't Generate | This plan and its artifacts are agent-authored (planning docs, not implementation code); the actual `.sql` and `.py` changes in `tasks.md` are written by the human, reviewed after each task per the Daily loop. | Pass |
| II. Four Primitives | `Guest` and `Room`/`RoomType` are Who (Actor/Resource). `Reservation` is the connective schema between them, already fixed in the source proposal (§4/§8) — not a new primitive invented this phase. | Pass |
| III. Risk Tiering | Every new tool is explicitly tiered in spec.md: T1 (`verify_guest_identity`, `request_human_handoff`), T2 (`check_in_guest`, `check_out_guest`, `create_booking`), T3 (`modify_booking`, `cancel_booking`, confirmation-gated). | Pass |
| IV. Fixed Agent Topology | All new tools attach to the existing `concierge_agent`; no new agent introduced. | Pass |
| V. SQL-Only | All three migrations extend the existing single Postgres/pgvector instance. No document/vector-DB addition. | Pass |
| VI. Mocked-Adapter Boundary | No new external mocked system introduced this phase (keycards/sensors explicitly deferred). | N/A |
| VII. Tool Contract & Idempotency | FR-008 (uniform `{status,data,error}`) and FR-022 (idempotency key on every write tool) are explicit requirements, carried into every tool's contract below. | Pass |
| VIII. Append-Only Billing | No billing table touched this phase. | N/A |
| IX. No Speculative Features | The three-phase merge is a **resequencing** of already-scoped proposal phases under one gate, not new scope — no requirement in spec.md exists that wasn't already specified for Phases 0/1/2 in the source doc. Keycards, sensors, `rate_calendar`, and `staff_tasks`-backed routing (all present in the source phases) are explicitly excluded to keep the merge from becoming scope creep. Documented in Complexity Tracking below. | Pass, with documented rationale |

**Post-design re-check** (after Phase 1 artifacts below): The one addition not explicit in the
source proposal is the `idempotency_keys` table (research.md #2, data-model.md) — this *implements*
Principle VII's existing mandatory requirement rather than adding new scope, so it doesn't change
any row above. No other new entity, tool, or table was introduced during data-model/contracts design
beyond what spec.md's FRs already required. Gate still passes.

## Project Structure

### Documentation (this feature)

```text
specs/001-foundation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/             # Phase 1 output
│   ├── tools.md
│   └── migrations.md
└── tasks.md              # Phase 2 output (/speckit-tasks — not created by this command)
```

### Source Code (repository root)

```text
db/
└── migrations/
    ├── 001_initial_schema.sql
    ├── 002_refactor_guests_reservations.sql
    └── 003_rooms_inventory.sql

agent/
├── requirements.txt              # NEW — closes R4, exact-pinned per Clarifications
└── concierge_agent/
    ├── agent.py                   # updated: register new tools, revise instructions
    └── tools.py                   # updated: replace lookup_guest_profile, add lifecycle tools
```

**Structure Decision**: Single-project layout (constitution's SQL-only, fixed-topology principles
rule out a frontend/backend split this phase). Migrations live in a repo-root `db/migrations/`
directory rather than nested under `agent/` — they're database-level artifacts independent of the
Python package, and every later phase's migration (004 onward, per the source proposal's own
manifest in §17.2) belongs in the same place. `requirements.txt` lives at `agent/`, next to the
`.venv` and package it actually describes, not the repo root, since `web/` and `data/` have no
Python runtime dependency on it.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| Three proposal phases (0/1/2) gated and delivered as one spec/plan/tasks unit, instead of three | Phase 2's tool signatures (`verify_guest_identity`, `check_in_guest`, `create_booking`) are written in the source proposal against tables that don't exist until Phase 0 (`reservations`) and Phase 1 (`room_types`/`rooms`) both ship. Building them separately would land two intermediate states with nothing guest-facing to demo. | Sequencing them as originally planned (three short-path phases after this one full-gate phase) was rejected because the *first* demoable guest-lifecycle behavior wouldn't exist until all three shipped anyway — splitting the gate work without splitting the actual dependency chain adds process overhead without adding safety. |
