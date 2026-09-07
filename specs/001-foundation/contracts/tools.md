# Tool Contracts: concierge_agent additions/changes

Every tool below returns the constitution's universal shape (Principle VII) — reproduced once here,
not repeated per tool:

```python
class ToolResult(BaseModel):
    status: Literal["ok", "error", "pending_confirmation"]
    data: dict | None = None
    error: str | None = None
```

Never raise. A database failure, a not-found result, and a business-rule rejection (e.g. "no rooms
available") are all `status="error"` with a message in `error` — not an exception.

Every write tool below (Tier 2/3) checks `idempotency_keys` for `(idempotency_key, tool_name)`
before acting; on a match it returns the stored `result` payload byte-for-byte rather than
re-deriving a fresh response (research.md §2, data-model.md). Required starting reservation state
per tool is the precondition table in data-model.md's "State transitions" section — not repeated
per tool below.

---

## verify_guest_identity — Tier 1, read-only, autonomous

```python
def verify_guest_identity(booking_reference: str, surname: str) -> ToolResult:
```

- Matches source proposal's Pydantic contract exactly (§11).
- `status="ok"`, `data={guest_id, verified: true, reservation_status}` on match.
- `status="error"` (generic, not distinguishing which field was wrong — FR-006) on any non-match.
- Agent-level guardrail (not part of this function's contract): stop calling this tool after 3
  failed results in one conversation; redirect to front desk instead (FR-007a).
- Replaces `lookup_guest_profile` entirely (FR-010) — that function and its registration in
  `agent.py` are removed, not deprecated alongside.

## assign_room — Tier 2, write, idempotent, logged/reversible

```python
def assign_room(
    idempotency_key: UUID,
    booking_reference: str,
    room_id: UUID | None = None,
    desired_features: list[str] | None = None,
) -> ToolResult:
```

- New 2026-08-12 — separates physical room allocation from both booking and check-in (see
  `spec.md` Clarifications, Session 2026-08-12).
- Precondition: reservation `status = 'confirmed'`.
- If `room_id` given: validates it belongs to the reservation's `room_type_id`, is
  `operational_status = 'active'`, and isn't already the `room_id` of a different active
  reservation with overlapping dates.
- If `room_id` omitted: searches rooms of the reservation's `room_type_id` not already assigned to
  another overlapping active reservation, optionally filtered by `desired_features` against
  `room_features`; assigns the first match.
- Effect: sets `reservations.room_id`. Does **not** touch `rooms.occupancy_status` — assignment is
  not occupancy.
- Mutable, not a one-time lock: calling it again on the same reservation reassigns a different
  room rather than erroring.

## check_in_guest — Tier 2, write, idempotent, logged/reversible

```python
def check_in_guest(
    idempotency_key: UUID,
    booking_reference: str,
) -> ToolResult:
```

- **Revised 2026-08-12**: no longer searches for a room itself — that's `assign_room`'s job now.
- Preconditions: reservation exists, `status = 'confirmed'`, **and `room_id` already set** (via a
  prior `assign_room` call). Rejects with a distinct error if `room_id` is `NULL`, telling the
  caller to run `assign_room` first, rather than silently picking a room.
- Also validates the *already-assigned* room is currently `occupancy_status = 'vacant'` and
  `operational_status = 'active'` — this is where a holdover guest or an out-of-order room still
  surfaces, just as a rejection instead of a silent reassignment.
- Effect: sets `reservations.status = 'checked_in'`, sets `rooms.occupancy_status = 'occupied'`.
- Rejections (`status="error"`): reservation not found; reservation not in `confirmed` state
  (FR-015); no room assigned yet; assigned room not currently ready.
- Idempotent replay of the same key returns the original result without re-running the state change.

## check_out_guest — Tier 2, write, idempotent, logged/reversible

```python
def check_out_guest(idempotency_key: UUID, booking_reference: str) -> ToolResult:
```

- Precondition: reservation `status = 'checked_in'`.
- Effect: sets `reservations.status = 'checked_out'`, sets
  `rooms.housekeeping_status = 'needs_cleaning'`, `rooms.occupancy_status = 'vacant'`.
- Rejection: reservation not found or not currently checked in.

## create_booking — Tier 2, write, idempotent, logged/reversible

```python
def create_booking(
    idempotency_key: UUID,
    guest_id: UUID,
    room_type_id: UUID,
    check_in_date: date,
    check_out_date: date,
) -> ToolResult:
```

- Preconditions: `check_out_date > check_in_date`; at least one room of `room_type_id` is free for
  the *entire* requested date range, computed as `count(rooms of type) - count(overlapping active
  reservations of that type)` (FR-019; research.md §5; data-model.md's "Availability" section).
  Distinct from `check_in_guest`'s room-instance-level availability check — see data-model.md.
- Effect: inserts a new `reservations` row with a generated `booking_reference`,
  `status = 'confirmed'`.
- Returns `data={booking_reference}` on success.

## modify_booking — Tier 3, confirmation-gated

```python
def modify_booking(
    idempotency_key: UUID,
    booking_reference: str,
    new_check_in: date | None,
    new_check_out: date | None,
) -> ToolResult:
```

- Matches source proposal's signature (§11) plus the constitution's mandatory `idempotency_key`
  (not shown in the proposal's illustrative snippet, but required by Principle VII with no
  exception).
- ADK `require_confirmation=True` (research.md #4) — the tool only executes after an explicit human
  yes; a "no" or timeout leaves the reservation unchanged (FR-020).
- Rejects a resulting date range that fails `check_out_date > check_in_date`.

## cancel_booking — Tier 3, confirmation-gated

```python
def cancel_booking(idempotency_key: UUID, booking_reference: str) -> ToolResult:
```

- Same confirmation pattern as `modify_booking`. Sets `status = 'cancelled'`.

## request_human_handoff — Tier 1, minimal acknowledgment

```python
def request_human_handoff(reason: str | None = None) -> ToolResult:
```

- No persistence to a real staff-routing system this phase (`staff_tasks` doesn't exist until
  Phase 4 — Assumptions in spec.md). `status="ok"` with a `data={acknowledged: true}` response the
  agent surfaces to the guest as "a staff member has been notified" or equivalent (FR-021).
- Read-only from the schema's perspective (no table write), consistent with its Tier 1
  classification in the source proposal's tool inventory (§11).
