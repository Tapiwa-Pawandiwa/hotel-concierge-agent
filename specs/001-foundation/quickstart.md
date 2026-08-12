# Quickstart: Validating Foundation, Room Inventory & Guest Lifecycle

Manual validation steps per user story — run these against a scratch/dev Supabase project, not
production data, since migration 002/003 rewrite the guest table. No automated suite exists yet
(this phase's Testing section is by hand; the dedicated testing day comes later per CLAUDE.md's
MVP week table).

## Prerequisites

- Migrations 001, 002, 003 applied in order (`db/migrations/*.sql`) against a fresh copy of the
  current Supabase schema.
- `agent/requirements.txt` installed into a clean virtual environment.
- `agent/.env` populated with `SUPABASE_DB_URL` and `VOYAGE_API_KEY` (existing convention, unchanged
  this phase).
- Agent started via `adk run` or `adk web` from `agent/`.

## Story 2 check first — schema & migrations (do this before anything else)

```sql
-- After 001: no-op check, schema matches pre-migration inspection
-- After 002:
SELECT count(*) FROM guests;        -- expect 300
SELECT count(*) FROM reservations;  -- expect 300
-- After 003:
SELECT count(*) FROM room_types;                                   -- expect seeded count
SELECT count(*) FROM rooms;                                        -- expect seeded count
SELECT count(*) FROM reservations WHERE room_type_id IS NOT NULL;  -- expect 300
```

If any of these mismatch, the migration's own row-count assertion should already have aborted it —
this is a manual double-check, not the primary safety net.

## Story 1 — identity verification

1. Pick a known reservation's `booking_reference` and the guest's surname from the post-migration
   `guests`/`reservations` tables.
2. In a chat with the agent, ask a guest-specific question supplying both correctly. Expect
   reservation details back.
3. Repeat with a surname that belongs to a *different* reservation than the booking reference
   supplied. Expect a generic "couldn't verify" response, not a partial match.
4. Repeat supplying only the booking reference. Expect the agent to ask for the surname, not guess.
5. Deliberately fail verification 3 times in one conversation, then try a 4th. Expect the agent to
   stop and direct you to the front desk rather than accepting a 4th attempt.

## Story 3 — check-in / check-out

1. Verify identity for a `confirmed` reservation with an available room of its type.
2. Ask the agent to check you in. Expect confirmation and a specific room reference back; check
   `reservations.status = 'checked_in'` and `rooms.occupancy_status = 'occupied'` in the DB.
3. Ask to check in again. Expect no duplicate action or room reassignment.
4. Ask to check out. Expect `reservations.status = 'checked_out'` and
   `rooms.housekeeping_status = 'needs_cleaning'`.

### Idempotency replay (SC-007, T024)

5. Call `check_in_guest` directly (not through a fresh agent turn) twice with the exact same
   `idempotency_key` value. Expect the second call to return the first call's stored result
   verbatim, and confirm in the DB that no second state change occurred (room not reassigned,
   status unchanged by the replay).
6. Repeat with `check_out_guest`.

## Story 4 — booking creation, modification, cancellation

1. Ask the agent to book a stay for a known guest against an existing room type and valid dates.
   Expect a new `booking_reference` returned and a corresponding `reservations` row.
2. Ask to change that booking's dates. Expect the agent to ask for explicit confirmation before
   committing — verify the DB is unchanged until you confirm.
3. Ask to cancel the booking. Same confirmation-before-commit check.
4. Start a modify/cancel request and decline the confirmation. Verify the reservation is unchanged.

### Real per-date availability (FR-019)

5. Pick a room type with exactly `N` rooms. Create `N` active (`confirmed`) bookings against it for
   the same overlapping date range. Attempt one more booking for that type, overlapping dates.
   Expect rejection — no room free for the full requested range.
6. Book a stay that starts on the exact day one of those `N` reservations checks out. Expect this to
   succeed (same-day turnover is not a conflict, per FR-019's half-open interval semantics).
7. Cancel one of the `N` active reservations, then retry the rejected booking from step 5 for the
   same dates. Expect it to now succeed.

### Idempotency replay (SC-007, T024)

8. Call `create_booking` directly twice with the exact same `idempotency_key`. Expect the second
   call to return the first call's stored result verbatim with no second `reservations` row created.
9. Repeat with `modify_booking` and `cancel_booking`.

## Story 5 — human handoff

1. Ask the agent to speak to a staff member. Expect an explicit acknowledgment, not a dead end or a
   continued attempt to resolve the original request itself.

## Environment reproducibility (Story "requirements.txt")

1. Create a brand-new empty virtual environment.
2. `pip install -r agent/requirements.txt`.
3. Start the agent (`adk run` from `agent/`). Expect no `ImportError`/missing-package failure.
