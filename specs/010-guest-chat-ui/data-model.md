# Data Model: Guest Chat UI

## No new persistent schema

This feature adds **zero new database tables or columns**. Both entities named in `spec.md`'s Key
Entities section are runtime concepts, not rows:

## Conversation (session-scoped, not a DB row)

Maps directly onto ADK's own session concept (`research.md` §2) — not a separate thing this feature
builds. Identified by a single random UUID, generated client-side on first page load and held only
in browser memory for that tab's lifetime (never written to `localStorage`/cookies, matching FR-009
— nothing should tie a return visit back to a prior one).

| Field | Type | Notes |
|---|---|---|
| `session_id` | UUID string | Generated client-side; doubles as ADK's `user_id` and `session_id` (research.md §2) |
| messages | in-memory, browser only | Held in React state for the page's lifetime; never sent anywhere for storage |

## Message (session-scoped, not a DB row)

A single turn, rendered client-side. Not persisted server-side beyond what ADK's own (in-memory,
per Technical Context) session service holds for the duration of that session.

| Field | Type | Notes |
|---|---|---|
| `role` | `"user"` \| `"assistant"` | |
| `text` | string | May arrive incrementally (streamed) for `"assistant"` messages |
| `isConfirmationRequest` | boolean | True when the assistant's message represents a Tier 3 tool's confirmation gate (FR-004) — rendered distinctly, but still just a message, not a new entity |

## Existing schema reused, not modified (FR-011's reset mechanism)

The scheduled reset (`research.md` §6) reads and deletes existing rows — it does not add columns.
Listed here for traceability back to `specs/001-foundation`'s schema, since this feature depends on
columns that phase already shipped:

| Table | Column relied on | Why |
|---|---|---|
| `guests` | `created_at`, `legacy_guest_id` | Distinguishes a public-demo-created profile (`created_at` after the baseline cutoff) from one of the original 300 seeded guests (`legacy_guest_id IS NOT NULL`, always preserved) |
| `reservations` | `created_at` | Same cutoff logic — anything created after the baseline is a public-demo artifact, deleted on reset |
| `rooms` | `occupancy_status`, `housekeeping_status` | Reset back to defaults (`vacant`/`clean`) rather than deleted — rooms are shared physical inventory, not per-visitor data |
| `reservation_products` | `reservation_id` (FK) | Deleted alongside any `reservations` row the reset removes, so no orphaned breakfast line items remain |

## Configuration values (not schema, not secrets)

| Name | Purpose |
|---|---|
| `DEMO_BASELINE_CUTOFF` | Fixed timestamp (set once, at first deploy) marking "everything before this is real seed data, never touched by reset" — an environment variable on the agent's Cloud Run service, not a DB value |
| Rate-limit window/cap | e.g. 20 messages / 5 minutes per session — a constant in `web/lib/rate-limit.ts`, tuned during the tasks phase, not stored anywhere |
