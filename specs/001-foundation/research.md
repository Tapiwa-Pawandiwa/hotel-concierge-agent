# Phase 0 Research: Foundation, Room Inventory & Guest Lifecycle

## 1. Legacy reservation → room type backfill mapping

**Decision**: The 300-row seed data (`data/guests.csv`) contains exactly 8 distinct
`reserved_room_type` codes: `A`, `B`, `C`, `D`, `E`, `F`, `G`, `H`. Migration 003 seeds exactly 6
room types (per the source proposal's explicit "6 rows" count in §17.3, even though its own
illustrative JSON snippet only names 4) in a fixed creation order, and maps codes to types by
position with wraparound:

| Code | A | B | C | D | E | F | G | H |
|---|---|---|---|---|---|---|---|---|
| Room type (by creation order, 1-indexed, mod 6) | 1 | 2 | 3 | 4 | 5 | 6 | 1 | 2 |

No new column or mapping table — `reservations.room_type_id` is set directly from this fixed table
during backfill. Room instance count: 10 rooms per room type (60 total) — a concrete, documented
default for this "single-property, demo-scale" build, since the source proposal deliberately leaves
`rooms.json` generation unspecified ("a script assigns floor/view/feature combinations
programmatically... so count and distribution stay consistent if property size changes later").

**Rationale**: The Kaggle dataset's room type codes (`A`–`H`+) don't correspond to any real category
name, so no "correct" semantic mapping exists — any deterministic, reproducible assignment satisfies
FR-012 (every legacy reservation gets *a* room type) without inventing meaning that isn't there.
Fixed-lookup keeps the migration itself simple and auditable (same input always produces the same
output, satisfying the row-count/consistency check pattern already used in migration 002).

**Alternatives considered**: Leaving legacy `room_type_id` null and only requiring it for new
bookings — rejected because it would make ~300 of the demo's reservations un-checkable-in (FR-014
requires a room type to assign a room against), which defeats the point of merging Phase 1 in to
support Story 3 against realistic data, not just freshly created bookings.

## 2. Idempotency key enforcement

**Decision**: Add a small `idempotency_keys` table (`key uuid PRIMARY KEY`, `tool_name text`,
`result jsonb`, `created_at timestamptz`) shared across every Tier 2/3 write tool in this phase.
Each write tool checks for `(key, tool_name)` first; if found, replays the exact stored `result`
byte-for-byte without re-executing the write; if not found, performs the write and records both the
key and its resulting `ToolResult` payload in the same transaction. The same key reused against a
*different* `tool_name` is treated as a fresh, unrelated key — the table's primary key is the
`(key, tool_name)` pair, not `key` alone, so no cross-tool collision is possible or needs special
handling.

**Key source for this phase**: The write-ahead queue that would normally generate and durably
persist these keys client-side is Phase 3 (resilience) work, not built yet. Until then,
`concierge_agent` generates a fresh UUID4 itself immediately before each write-tool call within a
single turn. This protects against transport-level retries within one invocation attempt (e.g. an
ADK retry after a dropped response), not against a guest re-asking for the same action in a later,
separate turn — that stronger guarantee arrives with the real write-ahead queue in Phase 3.

**Rationale**: Constitution Principle VII requires idempotency on every Tier 2/3 write tool with no
exception, and this phase introduces five of them (`check_in_guest`, `check_out_guest`,
`create_booking`, `modify_booking`, `cancel_booking`). A single shared table avoids duplicating the
check-and-record pattern five different ways, and keeps the guarantee (FR-022, SC-007) enforceable
at the database layer rather than trusted to in-memory agent state that wouldn't survive a process
restart.

**Alternatives considered**: Per-table "last idempotency key" columns on `reservations` — rejected,
since it can't dedupe two different write *types* against the same reservation (e.g. a retried
check-in vs. a retried checkout) without one column per tool.

## 3. Migration file location

**Decision**: `db/migrations/`, repo root.

**Rationale**: Migrations are database-level artifacts, not part of the `agent/` Python package —
every later phase's migration (004 onward per the proposal's own §17.2 manifest) belongs in the same
place regardless of which phase's code touches which agent. Keeps `agent/` scoped to what its own
`requirements.txt`/`.venv` actually needs.

**Alternatives considered**: `agent/scripts/migrations/`, next to the existing `ingest.py` — rejected
because migrations aren't agent-runtime concerns and future phases (billing, staff ops) won't
necessarily touch `concierge_agent`'s code at all.

## 4. Tier 3 confirmation mechanism

**Decision**: Use ADK's native `require_confirmation=True` tool flag for `modify_booking` and
`cancel_booking`, matching the proposal's own note on `modify_booking`'s Pydantic contract ("Tier 3
— uses ADK's native `require_confirmation=True` ...; a plain yes/no from a human is sufficient").

**Rationale**: The proposal explicitly distinguishes this "Shape 3" pattern (simple yes/no) from the
hand-rolled `pending_approvals` flow it says is only needed for `sales_agent`'s
`DatabaseSessionService` gap — that gap doesn't apply here, `concierge_agent`'s existing session
handling is unaffected.

**Alternatives considered**: Building a custom confirmation flow now — rejected as unnecessary
complexity; the native ADK mechanism is exactly what the source proposal already specifies for this
tool shape.

## 5. Booking-time availability computation

**Decision**: `create_booking` computes availability on demand, with no new table:

```sql
SELECT (SELECT count(*) FROM rooms WHERE room_type_id = :room_type_id)
     - (SELECT count(*) FROM reservations
        WHERE room_type_id = :room_type_id
          AND status IN ('confirmed', 'checked_in')
          AND check_in_date < :new_check_out
          AND check_out_date > :new_check_in) AS rooms_free;
```

Reject the booking if `rooms_free <= 0`. Half-open interval semantics (`check_in_date` inclusive,
`check_out_date` exclusive) give same-day-turnover behavior for free — a reservation checking out
on day X and a new one checking in on day X don't overlap, matching how real hotels handle
same-day turnover.

**Rationale**: Deterministic, matches the standard booking-site model the user asked for
(booking.com-style: search a date range, only book what's actually free for it). Computed from
existing tables (`reservations`, `rooms`) rather than a new `rate_calendar`-style availability
table — keeps this phase's schema additions to exactly what FR-011 already specifies, no
speculative new entity (constitution Principle IX). Explicitly distinct from `check_in_guest`'s
own availability check (FR-016), which tests a specific room instance's *current* physical
occupancy state, not a date-range reservation count — spec.md Assumptions makes this distinction
explicit now (resolves analysis findings F1/B1).

**Alternatives considered**: A persistent `rate_calendar`/availability-by-date table, precomputed —
rejected as exactly the kind of infrastructure the source proposal already scopes to a later phase
(`rate_calendar` appears in the proposal's own Phase 1 migration but was explicitly excluded from
this phase's `room_features`-adjacent scope in spec.md Assumptions); an on-demand `COUNT` query is
sufficient at this phase's data scale (single property, demo-sized reservation volume).

## 6. Dependency manifest scope

**Decision**: `agent/requirements.txt` lists direct, import-level dependencies only
(`google-adk`, `psycopg`, `pgvector`, `voyageai`, `python-dotenv`), each pinned to the exact version
currently installed in `agent/.venv`. Not a full `pip freeze` of the entire virtual environment.

**Rationale**: The current `.venv` is a kitchen-sink environment containing packages unrelated to the
agent runtime (Jupyter tooling, `kaggle`, `faker` — used only by the one-off
`data/prep_bookings.py` script, not by anything the agent imports). A full freeze would commit noise
and imply dependencies the agent doesn't actually have. Pinning direct imports exactly still
satisfies the Clarifications' exact-pin decision and SC-004 — pip's resolver fills in a compatible
transitive tree from those pins.

**Alternatives considered**: Full `pip freeze` (true lockfile-style reproducibility) — rejected as
disproportionate for a solo project at this scale; noted as a reasonable future upgrade (e.g.
`pip-compile`/`uv.lock`) if transitive drift ever actually causes a break, not built preemptively.
