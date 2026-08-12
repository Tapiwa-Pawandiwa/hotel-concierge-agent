# Data Model: Foundation, Room Inventory & Guest Lifecycle

Source: `docs/implementation_proposal.html` §4 (ERD, "Guest identity, rooms & stay lifecycle") and
§17.2 (migration manifest). Column lists here are the subset this phase actually creates/touches —
full attribute lists live in the source doc; nothing here contradicts it.

## guests (post-002, replaces the flat pre-migration table)

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | `gen_random_uuid()` |
| `legacy_guest_id` | text, unique | traceability back to `G0001`..`G0300` (FR-004) |
| `first_name` | text, not null | best-effort split from old `guest_name` |
| `last_name` | text, not null | |
| `email` | text | |
| `phone` | text | nullable this phase — no SMS/kiosk-auth flow yet |
| `country_code` | text | |
| `preferred_language` | text | |
| `stripe_customer_id` | text | nullable — no billing this phase |
| `accessibility_flags` | text[] | default `'{}'` |
| `dietary_flags` | text[] | default `'{}'` |
| `created_at` | timestamptz, not null | default `now()` |

**Validation**: `legacy_guest_id` uniqueness enforced by the migration (FR-003's row-count check
catches a collision indirectly; the constraint itself is the hard stop).

**Guest Profile Management (T018–T020, added 2026-08-12)**: this table isn't only populated by the
002 backfill and the T007-era seed guests — `create_guest_profile` (T019) inserts new rows here
directly, with `legacy_guest_id = NULL` (already nullable, no migration needed; Postgres `UNIQUE`
permits multiple `NULL`s). `search_guest_profiles` (T018) is a read-only match on `email`/`phone`/
name run *before* every new-guest creation, for any channel — this is how a guest without a prior
`booking_reference` (a walk-in, or a first-time online guest) gets a `guest_id` at all, resolving a
gap the original schema/tool signatures didn't cover: `create_booking` assumes a `guest_id` already
exists, `verify_guest_identity` assumes an existing `booking_reference` — neither creates one. See
`docs/implementation_proposal.html` §11 "Guest Profile Management" why-note for the full design
reasoning (Who vs. Request separation, why no auto-merge/scoring engine this phase).

## reservations (new in 002, extended in 003)

| Column | Type | Notes |
|---|---|---|
| `booking_reference` | text PK | synthesized `BK-<legacy_guest_id>` for backfilled rows; generated at creation for new bookings (FR-018) |
| `guest_id` | uuid FK → guests.id, `ON DELETE RESTRICT` | |
| `room_type_id` | uuid FK → room_types.id | nullable until 003 backfills it; required for new bookings (FR-019) |
| `room_id` | uuid FK → rooms.id | null until check-in (FR-014) — see research.md #1 |
| `check_in_date` | date, not null | |
| `check_out_date` | date, not null | `CHECK (check_out_date > check_in_date)` |
| `adr` | numeric(10,2) | |
| `status` | text, not null, default `'confirmed'` | `CHECK (status IN ('confirmed','checked_in','checked_out','cancelled'))` |

**State transitions** (FR-014/FR-015/FR-017/FR-020), with every tool's required precondition state
made explicit (closes the ambiguity a reader would otherwise have to guess at for
`modify_booking`/`cancel_booking`):

```
confirmed --check_in_guest--> checked_in --check_out_guest--> checked_out
confirmed  ─┐
checked_in ─┼─cancel_booking──> cancelled
confirmed  ─┼─modify_booking──> confirmed (dates changed, status unchanged)
checked_in ─┘
```

| Tool | Required starting state(s) | Rejected if reservation is |
|---|---|---|
| `check_in_guest` | `confirmed` | `checked_in`, `checked_out`, or `cancelled` |
| `check_out_guest` | `checked_in` | `confirmed` (never checked in), `checked_out`, or `cancelled` |
| `create_booking` | N/A — creates a new row | — |
| `modify_booking` | `confirmed` or `checked_in` | `checked_out` or `cancelled` (a finished or dead booking's dates can't change) |
| `cancel_booking` | `confirmed` or `checked_in` | `checked_out` (already finished) or already `cancelled` |

Every transition attempted from a state other than the one(s) listed above is rejected by the tool
itself, not by a DB constraint alone — each tool must check current status before writing
(FR-015).

## room_types (new in 003)

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `name` | text | e.g. "Standard Queen", "Deluxe King" |
| `bed_config` | text | |
| `max_occupancy` | int | |
| `sq_meters` | int | |

## rooms (new in 003)

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `room_type_id` | uuid FK → room_types.id | |
| `floor` | int | |
| `view_type` | text | |
| `occupancy_status` | text | e.g. `vacant`/`occupied` — set by check-in/check-out |
| `housekeeping_status` | text | e.g. `clean`/`needs_cleaning` — set by check-out (FR-017) |
| `operational_status` | text | `active`/`out_of_order` — added 2026-08-05 after review against real-world PMS schemas (source proposal §4 "why" note). Independent third axis, same pattern as the two status columns above. **Not yet in the DB** — 003 already shipped without it; needs its own migration (T016, `005_room_operational_status.sql`) before T017/T018 are written. T018's availability formula (`count(rooms of room_type_id) - count(overlapping reservations)`), shared with T017's `list_room_types`, MUST subtract `out_of_order` rooms from that count too, or an unsellable room still counts as available inventory. |
| `energy_mode` | text | column exists per source ERD; static default this phase — no sensor simulation (out of scope) |

## room_features (new in 003)

This is the amenities table — confirmed against the source proposal's own Phase 1 description,
"feature-tag table (view/amenities/accessible/smoking)" — not a placeholder for a separate
amenities concept.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `room_type_id` | uuid FK → room_types.id, nullable | type-level standard feature |
| `room_id` | uuid FK → rooms.id, nullable | instance-level override |
| `feature` | text | e.g. `accessible`, `smoking`, `city_view` |

Exactly one of `room_type_id`/`room_id` is expected to be set per row (type-level vs. instance-level
tag) — not DB-enforced this phase, kept simple per the source ERD's own modeling. Seeded with real
sample tags in migration 003 (spec.md Assumptions) — no tool this phase queries it, but it ships
populated rather than empty, since it's cheap to seed alongside `room_types`/`rooms` in the same
migration.

## Availability — two distinct computations, not one concept

Resolves analysis findings F1/B1: "availability" means different things at different moments, and
neither is backed by a stored table — both are computed from existing data.

| | **Reservation availability** (booking time) | **Room availability** (check-in time) |
|---|---|---|
| Used by | `create_booking` (FR-019) | `check_in_guest` (FR-016) |
| Question | Is any room of this *type* free for this *date range*? | Is a *specific room instance* physically free *right now*? |
| Computed from | `count(rooms of type) - count(overlapping active reservations of type)` — research.md §5 | `rooms.occupancy_status` for the specific instance being assigned |
| Can disagree? | Yes — a reservation can pass this check and still find no physically-free room at check-in (e.g. a lingering earlier guest); that's expected hotel behavior, not a contradiction |

## idempotency_keys (new in 003, supports FR-022)

| Column | Type | Notes |
|---|---|---|
| `key` | uuid, not null | generated by `concierge_agent` per write-tool call this phase (research.md §2) — the durable, write-ahead-queue-sourced version arrives in Phase 3 |
| `tool_name` | text, not null | which tool the key was used with |
| `result` | jsonb, not null | the exact `ToolResult` payload returned on first execution, replayed verbatim on a repeat call |
| `created_at` | timestamptz, not null | default `now()` |

**Primary key**: `(key, tool_name)` composite — the same key reused against a different tool is a
distinct, unrelated row, not a collision (research.md §2).

See research.md #2 for the full check-and-record pattern every Tier 2/3 tool in this phase follows
against this table.

## policy_chunks — unaffected

Untouched by this phase; captured as-is by migration 001 alongside the pre-split `guests` table.
