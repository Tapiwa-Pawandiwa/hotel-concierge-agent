# Migration Contracts

Three migration files, applied in order against the live Supabase database. Each is a single
transaction; each ends with a row-count assertion that raises (aborting the transaction, leaving no
partial change) if expectations aren't met. Full DDL is written by the human during `tasks.md`
execution, drawing on `docs/implementation_proposal.html` §4/§17.2, which already contains complete
SQL for 001 and 002 — 003 is newly specified here since the proposal's own §17.2 table only names
what 003 adds, not its DDL.

## db/migrations/001_initial_schema.sql

**Intent**: Baseline capture only. Commits the schema exactly as it lives in Supabase today
(`guests` flat table, `policy_chunks` with its `pgvector` HNSW index) — closes R5. No structural
change.

**Row-count assertion**: N/A (nothing changes; nothing to assert beyond "it ran without error").

## db/migrations/002_refactor_guests_reservations.sql

**Intent**: Split flat `guests` into `guests` (identity) + `reservations`. Full DDL and backfill
logic already written in the source proposal (§4) — reproduce verbatim, don't re-derive.

**Row-count assertion**: `count(guests_old) == count(guests_new) == count(reservations)` (FR-003) —
already specified as a `DO $$ ... RAISE EXCEPTION` block in the source proposal; reuse it.

## db/migrations/003_rooms_inventory.sql

**Intent**: Add `room_types`, `rooms`, `room_features`, and `idempotency_keys` (research.md #2).
Seed exactly 6 room types, 10 rooms per type (60 rooms total — research.md #1), and a handful of
real `room_features` tags (type-level and instance-level view/amenity/accessible/smoking entries —
this is the amenities table per the source proposal, not a placeholder; seeded even though no tool
this phase queries it, per spec.md Assumptions). Backfill
`reservations.room_type_id` on every existing row via the fixed A–H code-to-type mapping table in
research.md #1. Add the FK constraints on `reservations.room_type_id`/`room_id` that migration 002
left as bare `uuid` columns (per the source proposal's own note that 003 onward "adds FKs the prior
migration left as bare uuid columns").

Explicitly excluded from this file despite appearing in the source proposal's same-named migration:
`keycards`, `room_sensor_events`, `rate_calendar` (spec.md Assumptions — flavor, not needed for this
phase's demo).

**Row-count assertion**: `count(room_types) == 6`, `count(rooms) == 60`, and
`count(reservations WHERE room_type_id IS NOT NULL) == count(reservations)` (every reservation has a
room type after backfill — FR-013).
