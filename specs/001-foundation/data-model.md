# Data Model: Foundation, Room Inventory & Guest Lifecycle

Source: `docs/implementation_proposal.html` §4 (ERD, "Guest identity, rooms & stay lifecycle") and
§17.2 (migration manifest). Column lists here are the subset this phase actually creates/touches —
full attribute lists live in the source doc; nothing here contradicts it.

**Migration-number collision, unresolved — flagging rather than guessing.** This
file names three migrations that don't exist in `db/migrations/` (real files stop at `004`):
`005_idempotency_key_as_text.sql` (below, `idempotency_keys.key`), `005_room_operational_status.sql`
(below, `rooms.operational_status`), and `006_room_type_rates.sql` (below, `room_types.base_rate`).
Two different changes both claim `005`. All three were evidently applied directly against the live
Supabase DB, uncommitted — the same schema-drift pattern already flagged for `operational_status`
and `hotel_settings`, now a recurring habit rather than a one-off. Needs the human to confirm what
was actually applied and in what real order before these get written as real, committed migration
files with non-colliding numbers — I'm not guessing an order I can't verify from the DB itself. The
new audit-timestamps work below is provisionally called migration `007`, on the assumption `005`
and `006` resolve to one migration each; treat that number as provisional until the collision above
is sorted out.

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
| `updated_at` | timestamptz, not null | default `now()`, kept current by the shared `set_updated_at()` trigger (migration 007, provisional) — a real gap until now: `update_guest_profile` (T021, already implemented) mutates existing rows with nothing recording when |

**Validation**: `legacy_guest_id` uniqueness enforced by the migration (FR-003's row-count check
catches a collision indirectly; the constraint itself is the hard stop).

**Guest Profile Management (T018–T020, added after the original scope)**: this table isn't only populated by the
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
| `room_id` | uuid FK → rooms.id | null until `assign_room` runs (later clarification) — may happen any time after booking, not tied to check-in. Mutable until check-in, not a permanent lock. |
| `check_in_date` | date, not null | |
| `check_out_date` | date, not null | `CHECK (check_out_date > check_in_date)` |
| `adr` | numeric(10,2) | |
| `status` | text, not null, default `'confirmed'` | `CHECK (status IN ('confirmed','checked_in','checked_out','cancelled'))` |
| `created_at` | timestamptz, not null, default `now()` | **missing until this migration** — 002 gave `guests` this column but not `reservations`; caught during the audit-metadata review |
| `updated_at` | timestamptz, not null, default `now()` | kept current by a `BEFORE UPDATE` trigger (see below), not by each write tool setting it explicitly |

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
| `assign_room` | `confirmed` | `checked_in`, `checked_out`, or `cancelled` — a room isn't (re)assigned to a stay that's already active or over |
| `check_in_guest` | `confirmed`, with `room_id` already set by `assign_room` | `checked_in`, `checked_out`, `cancelled`, or `confirmed` with no room assigned yet (distinct rejection reason — the agent should call `assign_room` first, not retry) |
| `check_out_guest` | `checked_in` | `confirmed` (never checked in), `checked_out`, or `cancelled` |
| `create_booking` | N/A — creates a new row | — |
| `modify_booking` | `confirmed` or `checked_in` | `checked_out` or `cancelled` (a finished or dead booking's dates can't change) |
| `cancel_booking` | `confirmed` or `checked_in` | `checked_out` (already finished) or already `cancelled` |

Every transition attempted from a state other than the one(s) listed above is rejected by the tool
itself, not by a DB constraint alone — each tool must check current status before writing
(FR-015).

**`breakfast_included` (added directly in code, never in this table — should be dropped)**: the
live `create_booking` writes a bare `breakfast_included` boolean onto this table and prices it from
a `hotel_settings` key-value row. Both are wrong for the reasons in `products`/`product_prices`/
`reservation_products` below — replace the column with rows in `reservation_products` instead of
keeping it alongside as a second, competing source of truth.

## products, product_prices, reservation_products (new, added after the original scope)

Fixes a real bug, not a hypothetical gap: `create_booking` was found querying
`hotel_settings WHERE key = 'breakfast_rate_per_day'` for a price, with no committed migration
behind `hotel_settings` and a separate live bug where the resulting `total_price` was referenced
but never computed. See `docs/implementation_proposal.html` §1/§4 why-notes for the full reasoning
(external-critique validation, Principle II mapping — this generalizes the existing `MenuItem`
Resource primitive, it isn't a new one).

| Table | Column | Type | Notes |
|---|---|---|---|
| `products` | `id` | uuid PK | |
| | `code` | text, unique | e.g. `BREAKFAST` |
| | `name` | text | e.g. "Breakfast Buffet" |
| | `category` | text | free text this phase — e.g. `food_beverage`; not a normalized lookup table, only one product exists yet |
| | `active` | bool, default `true` | |
| | `created_at` | timestamptz, not null, default `now()` | when this product was added to the catalogue |
| `product_prices` | `id` | uuid PK | |
| | `product_id` | uuid FK → products.id | |
| | `amount` | numeric(10,2) | |
| | `pricing_basis` | text | `PER_NIGHT` is the only value actually exercised this phase (matches current per-night breakfast behavior); `PER_PERSON`, `PER_STAY`, `PER_ITEM` are valid text values, documented for when dinner/half-board additions need them, not built now |
| | `valid_from` | date | |
| | `valid_to` | date, nullable | `NULL` = currently in effect |
| | `created_at` | timestamptz, not null, default `now()` | when this price row was entered — distinct from `valid_from` (when it takes effect) |
| `reservation_products` | `id` | uuid PK | |
| | `reservation_id` | text FK → reservations.booking_reference | |
| | `product_id` | uuid FK → products.id | |
| | `quantity` | int | e.g. number of nights, for a `PER_NIGHT` product |
| | `unit_price` | numeric(10,2) | **snapshotted** from `product_prices` at booking time — not a live join, so a later catalogue price change never retroactively reprices a past booking |
| | `pricing_basis` | text | also snapshotted, same reasoning |
| | `line_total` | numeric(10,2) | `unit_price * quantity`, stored rather than recomputed, same append-only-ledger spirit as `bill_items` (Principle VIII) even though this isn't itself a posted charge |
| | `created_at` | timestamptz, not null, default `now()` | when this add-on was purchased. No `updated_at` — these rows are meant to be immutable snapshots, not edited in place, same append-only spirit as `bill_items` |

**Audit metadata, all three tables (from the audit-metadata review):** `products`/`product_prices` also get
`created_at` (default `now()`) — cheap now since these tables don't exist yet (T025/migration 006),
so it's one column list, not a later `ALTER TABLE`. Note `product_prices.valid_from` answers a
different question than `created_at` would (when the price takes effect vs. when the row was
entered) — both are kept, neither replaces the other. None of the three get `updated_at`: catalogue
rows get superseded by a new `product_prices` row (Principle VIII spirit — a price change is a new
row, not an edit), and `reservation_products` rows are immutable snapshots by design.

**Scoped smaller than the full external critique, deliberately (Principle IX):** no `rate_plans`/
`rate_plan_components` this phase — half-board/full-board stays room rate (`adr`, unchanged,
room-revenue-only) plus `reservation_products` line items summed on top, not a commercially
repriced bundle. `adr` staying room-only is a useful side effect: it keeps meaning what a real ADR
metric should mean, now that breakfast isn't smushed into it.

## room_types (new in 003)

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `name` | text | e.g. "Standard Queen", "Deluxe King" |
| `bed_config` | text | |
| `max_occupancy` | int | |
| `sq_meters` | int | |
| `base_rate` | numeric(10,2), not null | flat, not date-varying (`rate_calendar` stays excluded this phase — spec.md Assumptions). Live via a migration claiming the number `006` (collision flagged above — real number TBD). Researched against real French/Swiss mid-to-upper 4-star pricing (2026). |
| `created_at` | timestamptz, not null, default `now()` | added in the audit-metadata review (migration 007, provisional) — low urgency (this table is seeded once, rarely mutated after), added for consistency, not because of a live gap the way `guests`/`rooms` had one |

## rooms (new in 003)

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `room_type_id` | uuid FK → room_types.id | |
| `room_number` | text, not null, unique | e.g. "204" — added after live testing showed `check_in_guest` had no human-readable identifier to give a guest. Live via `004_room_number.sql`. |
| `floor` | int | |
| `view_type` | text | |
| `occupancy_status` | text | e.g. `vacant`/`occupied` — set by check-in/check-out |
| `housekeeping_status` | text | e.g. `clean`/`needs_cleaning` — set by check-out (FR-017) |
| `operational_status` | text | `active`/`out_of_order` — added after review against real-world PMS schemas (source proposal §4 "why" note). Independent third axis, same pattern as the two status columns above. Live via a migration claiming the number `005` (collision flagged above — real number TBD, T016). `list_room_types`/`create_booking`'s shared availability formula excludes `out_of_order` rooms, or an unsellable room would still count as available inventory. |
| `energy_mode` | text | column exists per source ERD; static default this phase — no sensor simulation (out of scope) |
| `created_at` | timestamptz, not null, default `now()` | added in the audit-metadata review (migration 007, provisional) |
| `updated_at` | timestamptz, not null, default `now()` | kept current by the shared `set_updated_at()` trigger — a real gap until now: `occupancy_status`/`housekeeping_status`/`operational_status` all change constantly (check-in/out cycles, out-of-order toggling) and nothing recorded when |

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
| `created_at` | timestamptz, not null, default `now()` | added in the audit-metadata review (migration 007, provisional) — low urgency, same reasoning as `room_types.created_at` |

Exactly one of `room_type_id`/`room_id` is expected to be set per row (type-level vs. instance-level
tag) — not DB-enforced this phase, kept simple per the source ERD's own modeling. Seeded with real
sample tags in migration 003 (spec.md Assumptions) — no tool this phase queries it, but it ships
populated rather than empty, since it's cheap to seed alongside `room_types`/`rooms` in the same
migration.

## Availability — three distinct concepts, not one, across three tools

Resolves analysis findings F1/B1, refined with the addition of `assign_room`:
"availability" means something different at each of booking, assignment, and check-in, and none of
it is backed by a stored table — all three are computed from existing data.

| | **Reservation availability** (booking time) | **Assignment eligibility** (assign-time) | **Room readiness** (check-in time) |
|---|---|---|---|
| Used by | `create_booking` (FR-019) | `assign_room` (later clarification) | `check_in_guest` (FR-016) |
| Question | Is any room of this *type* free for this *date range*? | Which specific room of this type is currently unassigned to another active reservation (and matches any requested features)? | Is the *already-assigned* room physically vacant (and, once `operational_status` exists, `active`) *right now*? |
| Computed from | `count(rooms of type, operational_status='active') - count(overlapping active reservations of type)` — research.md §5 | `rooms` of the reservation's `room_type_id` not already set as another active reservation's `room_id`, optionally filtered by `room_features` | `rooms.occupancy_status`/`operational_status` for the one room already on `reservations.room_id` |
| Can disagree with the prior stage? | — | Yes — a room type can have free inventory yet momentarily have no room assignable if all instances are already assigned to other confirmed stays for overlapping dates | Yes — an assigned room can still be occupied by a holdover guest or `out_of_order` at the actual check-in moment; `check_in_guest` rejects rather than silently swapping rooms, so the agent can call `assign_room` again for a different room |

## Audit metadata review (migration 007, provisional number)

Triggered by "the schema for reservations doesn't include valuable metadata like modified date or
created date" — reviewed across every table, not just `reservations`, per "we need valuable
metadata for all tables." Split three ways, not a blanket add-everywhere:

- **Real, live gaps** (a write tool already mutates the table with nothing recording when):
  `reservations` (missing both), `guests` (missing `updated_at`), `rooms` (missing both).
- **Lower priority, added for consistency, not urgency** (seeded once, rarely mutated after):
  `room_types`, `room_features` — `created_at` only.
- **Already adequate or intentionally excluded**: `idempotency_keys` (has `created_at`, correctly
  no `updated_at` — write-once by design); `product_prices` (has `valid_from`/`valid_to`, a more
  precise temporal concept than a generic timestamp — `created_at` added alongside, not instead);
  `reservation_products` (append-only snapshot, `created_at` only); `policy_chunks` (regenerated
  wholesale by the ingest script, not mutated row by row — a timestamp here describes the last
  ingest run, better logged by that job than added as schema, so deliberately skipped).

**Mechanism**: one shared trigger function, reused across every table that needs `updated_at`
(`guests`, `reservations`, `rooms`) rather than three copies of the same logic — the same
per-callsite-drift failure class as the duplicate `create_booking` definition (§11 code-review
note), closed at the DB level instead of trusted to every write tool remembering it:

```sql
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- then, per table:
CREATE TRIGGER <table>_set_updated_at
BEFORE UPDATE ON <table>
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
```

**Caveat**: backfilled/pre-existing rows get this migration's apply time as `created_at`, not their
true original creation time, which isn't recoverable from what's in the DB today.

## idempotency_keys (new in 003, supports FR-022)

| Column | Type | Notes |
|---|---|---|
| `key` | text, not null | relaxed from `uuid` (migration `005_idempotency_key_as_text.sql`) — the LLM generates this value itself and isn't reliable at producing syntactically valid UUID hex; the column never needed real UUID typing, it's just an opaque lookup key. Generated by `concierge_agent` per write-tool call this phase (research.md §2) — the durable, write-ahead-queue-sourced version arrives in Phase 3 |
| `tool_name` | text, not null | which tool the key was used with |
| `result` | jsonb, not null | the exact `ToolResult` payload returned on first execution, replayed verbatim on a repeat call |
| `created_at` | timestamptz, not null | default `now()` |

**Primary key**: `(key, tool_name)` composite — the same key reused against a different tool is a
distinct, unrelated row, not a collision (research.md §2).

See research.md #2 for the full check-and-record pattern every Tier 2/3 tool in this phase follows
against this table.

## policy_chunks — unaffected

Untouched by this phase; captured as-is by migration 001 alongside the pre-split `guests` table.
