# Feature Specification: Foundation, Room Inventory & Guest Lifecycle

**Feature Branch**: `001-foundation`

**Created**: 2026-08-05

**Status**: Draft

**Input**: User description: "Merge Phase 0 (Foundation), Phase 1 (Room & inventory foundation), and
Phase 2 (Check-in, kiosk mode & guest lifecycle) from docs/implementation_proposal.html into one
phase, since all three are guest-related and Phase 2's tools are unusable without Phase 0's
reservations table and Phase 1's room inventory both existing first."

## Clarifications

### Session 2026-08-05

- Q: Should the identity-check tool limit repeated failed match attempts within a single conversation? → A: Cap at 3 failed attempts per conversation, then redirect to front desk (session-scoped guardrail, not part of the `verify_guest_identity` tool's own data contract — see Assumptions)
- Q: Should the committed dependency manifest pin exact package versions, or allow flexible ranges? → A: Exact pins (`package==1.2.3`). Containerization (Docker) considered and explicitly deferred — no deployment target exists yet to containerize for (R7), and building it now would be speculative per the constitution's No Speculative Features principle.
- Q: Should this phase build the full `verify_guest_identity`/check-in/booking tool set (originally Phase 2), or only the "basic access control" fix (originally Phase 0)? → A: Merge all three phases (Foundation + Room Inventory + Guest Lifecycle) into this one — see rationale below.
- Q: With the merge, should check-in/booking tools assign a real room, or run without one for now? → A: Merge Phase 1 (room inventory) in too, so `check_in_guest` can assign a real room from day one instead of operating against null room columns.

### Session 2026-08-05 (analyze remediation)

- Q: Should `create_booking` check real per-date room availability, or just that the room type exists at all? → A: Real per-date availability, modeled on standard hotel-booking-site behavior (booking.com-style) — a guest can only create a booking for a room type that has at least one room free for the *entire requested date range*, computed deterministically from existing active reservations. Resolves FR-019 to match this exactly (previously conflicted with a narrower reading in contracts.md/tasks.md, flagged as checklist CHK016 and analysis finding F1).
- Q: Is "availability" the same concept at booking time and check-in time? → A: No — two distinct, deliberately different checks. **Reservation availability** (booking time, `create_booking`): is there at least one room of this type not already reserved by an active reservation overlapping these dates? **Room availability** (check-in time, `check_in_guest`): is a *specific* room instance physically free right now? A reservation can pass the first check and still hit the second (e.g. a lingering earlier guest) — that's expected hotel behavior, not a bug, and `check_in_guest`'s existing FR-016 already handles it gracefully.
- Q: Should `room_features` be seeded with real data this phase even though no tool queries it yet? → A: Yes — confirmed from the source proposal itself (§9 Phase 1 line: "feature-tag table (view/amenities/accessible/smoking)") that this *is* the amenities table, not a placeholder for one. Cheap to seed now alongside `room_types`/`rooms`; avoids a future re-migration just to add data to an already-existing table.

**Why merged**: The original phased plan (`implementation_proposal.html` §9) sequenced these as
Phase 0 → Phase 1 → Phase 2, each blocking the next: Phase 2's tool signatures
(`verify_guest_identity`, `check_in_guest`, `create_booking`, `modify_booking`) are written against
the `reservations` table Phase 0 introduces, and real check-in requires an actual room to assign,
which only exists once Phase 1's `room_types`/`rooms` tables exist. Building them as one phase
avoids landing intermediate states that can't be demonstrated end-to-end (e.g. a reservations table
with no rooms to point at, or a verified identity with no lifecycle to act on). This phase keeps the
full constitution gate path (`specify → clarify → plan → checklist → tasks → analyze → implement →
converge`) throughout, since it's now the single blocking foundation everything else depends on.

**Scope still explicitly excluded** (unchanged from the original per-phase boundaries): keycards,
`room_sensor_events`, `rate_calendar`, and simulated energy-mode sensing (flavor, not core to the
demo — real hotel data model exists in the source doc but isn't built this phase); kiosk mode as a
distinct UI (it's a deployment context per the proposal, not a new tool); menu/ordering/billing;
`ops_agent`/`sales_agent`; the staff dashboard; resilience/kill-switch; and any real
`staff_tasks`-backed routing behind `request_human_handoff` (that system doesn't exist until
Phase 4/Milestone 4 — this phase's handoff tool is a minimal stand-in, not the full routing engine).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Guest proves who they are before the agent shares their details (Priority: P1)

A guest chatting with the concierge agent asks a question that requires the agent to know who they
are. Today the agent accepts a bare `guest_id` and hands back that guest's full profile — no check
that the person asking is actually that guest. This story replaces that with a real identity check:
the guest supplies their booking reference and surname (not a guessable sequential ID) before the
agent discloses anything.

**Why this priority**: Closes the data-leak risk (R2) that makes the current tool unsafe to run at
all, and every other story in this phase (checking in, booking, modifying a stay) needs a verified
identity as its starting point.

**Independent Test**: Ask the concierge agent guest-specific questions with (a) correct booking
reference + surname and (b) incorrect/mismatched values, and confirm profile data is returned only
for (a).

**Acceptance Scenarios**:

1. **Given** a guest who supplies their correct booking reference and surname, **When** they ask a
   guest-specific question, **Then** the agent returns their reservation details.
2. **Given** a guest who supplies a booking reference and surname that don't belong to the same
   reservation, **When** they ask a guest-specific question, **Then** the agent returns no profile
   or reservation data and does not indicate which of the two values was wrong.
3. **Given** a guest who supplies only one identifying value, **When** they ask a guest-specific
   question, **Then** the agent asks for the missing value rather than guessing or partially
   matching.
4. **Given** a guest who has failed to verify their identity 3 times in the current conversation,
   **When** they attempt a 4th time, **Then** the agent stops attempting verification and directs
   them to contact the front desk instead of accepting further attempts.

---

### User Story 2 - The live database schema is captured as committed, versioned migrations (Priority: P1)

Today the schema that actually exists in Supabase lives nowhere in the repository. This story
commits it as a first migration (an unchanged baseline capture), a second migration that splits the
flat `guests` table into `guests` (identity) + `reservations` (owns `booking_reference`), and a
third migration that adds the room inventory (`room_types`, `rooms`, `room_features`) every
lifecycle tool in this phase depends on — preserving every existing row throughout.

**Why this priority**: Every other story in this phase is built on top of this one; getting the
split or the inventory model wrong here compounds into every later phase's migrations too.

**Independent Test**: Run all three migrations against a copy of the current database and confirm
row counts match the pre-migration count exactly, with a working room catalogue in place afterward.

**Acceptance Scenarios**:

1. **Given** the current live `guests` table with 300 rows, **When** migration 001 is applied,
   **Then** the schema is unchanged and all 300 rows remain exactly as they were.
2. **Given** the post-001 database, **When** migration 002 is applied, **Then** the new `guests`
   table has exactly 300 rows and the new `reservations` table has exactly 300 rows, each linked to
   the correct guest.
3. **Given** the post-002 database, **When** migration 003 is applied, **Then** a fixed catalogue of
   room types and room instances exists, and every reservation has a room type assigned (backfilled
   for existing rows, required going forward for new ones).
4. **Given** any of these three migrations running against a database where the resulting row counts
   would not match expectations, **When** the migration executes, **Then** it fails loudly and
   leaves no partially-applied change.

---

### User Story 3 - A verified guest can check in and check out (Priority: P2)

Once a guest's identity is verified (Story 1) and a real room exists to assign (Story 2), the agent
can move their reservation through its actual stay lifecycle: check them into a specific room on
arrival, and check them out and release the room when they leave.

**Why this priority**: This is the core "the agent actually does something for a real stay" loop —
higher guest-facing value than booking mechanics, but depends on identity verification and room
inventory both existing first.

**Independent Test**: Verify a guest's identity, check them in, confirm a room is now assigned and
occupied, check them out, confirm the room is released for housekeeping.

**Acceptance Scenarios**:

1. **Given** a verified guest with a `confirmed` reservation and an available room of their booked
   type, **When** the agent checks them in, **Then** the reservation status becomes `checked_in`
   and a specific room is assigned to them.
2. **Given** a verified guest whose reservation is already `checked_in`, **When** check-in is
   attempted again, **Then** the agent does not create a duplicate check-in or reassign a different
   room.
3. **Given** no room of the booked type is currently available, **When** check-in is attempted,
   **Then** the agent reports the room isn't ready rather than assigning an incorrect room type.
4. **Given** a verified guest who is `checked_in`, **When** the agent checks them out, **Then** the
   reservation status becomes `checked_out` and the room is marked as needing housekeeping before
   its next assignment.

---

### User Story 4 - A guest can book, modify, or cancel a stay (Priority: P3)

A guest (existing or new) can ask the concierge to create a new reservation against the room
catalogue, or change the dates or cancel an existing one. Date changes and cancellations are
consequential enough that they always get a human yes/no before they take effect.

**Why this priority**: Extends the lifecycle beyond stays that already exist in the migrated data —
needed for the demo to show a booking created live, not just pre-loaded ones — but the read/identity
and check-in/out loops (Stories 1 and 3) demonstrate the core value on their own first.

**Independent Test**: Create a new booking end-to-end via the agent, then modify its dates, then
cancel it, confirming each step requires explicit confirmation before the change is committed.

**Acceptance Scenarios**:

1. **Given** a room type with availability and valid stay dates, **When** a guest asks to book a
   stay, **Then** a new reservation is created with a booking reference returned to the guest.
2. **Given** an existing reservation, **When** a guest asks to change its dates, **Then** the agent
   confirms the change with the guest before committing it, and rejects a new date range where
   checkout would not be after check-in.
3. **Given** an existing reservation, **When** a guest asks to cancel it, **Then** the agent confirms
   the cancellation with the guest before committing it.
4. **Given** a modify or cancel request that has not yet been confirmed, **When** the guest does not
   confirm, **Then** the reservation is left unchanged.

---

### User Story 5 - A guest can ask for a human when the agent can't help (Priority: P4)

Some requests are outside what the concierge agent can or should resolve on its own. The guest can
ask to speak to a person, and the agent acknowledges the request and surfaces it rather than looping
or refusing silently.

**Why this priority**: An escape hatch, not a core demo path — lowest priority of the five stories,
included because leaving guests stuck with no way out is a worse experience than a minimal handoff.

**Independent Test**: Ask the agent for a human, and confirm it acknowledges the escalation clearly
rather than continuing to try to resolve the request itself or giving a dead-end response.

**Acceptance Scenarios**:

1. **Given** a guest who asks to speak with a staff member, **When** the request is made, **Then**
   the agent confirms the escalation was received and sets expectations for what happens next.

---

### Edge Cases

- What happens when a guest supplies identifying details in a different case or with extra
  whitespace? Matching must not be case- or whitespace-sensitive in a way that causes false
  rejections.
- What happens when the same surname matches multiple reservations? The booking reference is what
  disambiguates — a surname alone must never be sufficient to return data.
- What happens when migration 002 encounters a `guests` row whose `guest_name` doesn't split cleanly
  into first/last? Must not silently drop or mis-split the row.
- What happens when a legacy `guest_id` collides with an existing `legacy_guest_id` during backfill?
  The unique constraint must catch it.
- What happens when the identity tool is called with well-formed but entirely fabricated details?
  Must return a clean not-found result, not an error or exception.
- What happens to the 300 existing (Kaggle-derived) reservations, which have no real room instance
  on file? Migration 003 must give each one a room type (deterministically mapped from the existing
  data) so every legacy reservation is checkable-in like any other; a specific room instance is only
  assigned at check-in time, not backfilled retroactively.
- What happens when check-in is attempted on a `cancelled` or `checked_out` reservation? Must be
  rejected, not silently transitioned.
- What happens when a booking is requested for a room type with zero rooms free across the entire
  requested date range (per FR-019's overlap computation)? Must be reported to the guest as
  unavailable, not booked anyway — mirrors real hotel-booking-site behavior (you cannot book what
  isn't available for your dates).
- What happens when a booking's requested check-in date equals another active reservation's
  check-out date for the same room type (same-day turnover)? Not a conflict — the departing
  reservation's date range does not extend into its checkout day.
- What happens when `modify_booking`/`cancel_booking` is called twice with the same idempotency key
  (e.g. a retried request after a dropped connection)? Must not double-apply the change.

## Requirements *(mandatory)*

### Functional Requirements

**Schema & migrations**

- **FR-001**: System MUST have a committed migration (`001_initial_schema.sql`) that captures the
  currently-live database schema exactly as-is.
- **FR-002**: System MUST have a committed migration (`002_refactor_guests_reservations.sql`) that
  splits the flat `guests` table into `guests` (identity only) and `reservations` (one row per
  existing booking), backfilling from the pre-split data.
- **FR-003**: Migration 002 MUST verify that post-split `guests` and `reservations` row counts both
  exactly equal the original `guests` row count, and MUST abort without a partial change if they
  don't match.
- **FR-004**: System MUST retain a traceable link from each new guest identity row back to its
  original guest identifier.
- **FR-011**: System MUST have a committed migration (`003_rooms_inventory.sql`) that adds a room
  type catalogue, individual room instances linked to a type, and a room-feature tagging table.
- **FR-012**: Migration 003 MUST backfill a room type onto every existing reservation via a
  deterministic mapping from the legacy data, so no pre-existing reservation is left without a room
  type; it MUST NOT assign a specific room instance during backfill.
- **FR-013**: Migration 003 MUST verify expected row counts (room types, rooms, and reservations
  with a non-null room type) before completing, and MUST abort without a partial change if they
  don't match.

**Guest identity verification**

- **FR-005**: System MUST provide a guest-identity-verification tool that accepts a booking
  reference and surname and returns guest/reservation data only when both match the same
  reservation record.
- **FR-006**: The verification tool MUST NOT reveal which supplied value (if any) was incorrect.
- **FR-007**: The verification tool MUST NOT return partial or best-guess matches under any
  circumstance.
- **FR-007a**: The agent MUST stop attempting identity verification after 3 failed attempts within a
  single conversation and MUST direct the guest to contact the front desk, without persisting any
  lockout state beyond that conversation.
- **FR-010**: The previous unauthenticated lookup tool (`lookup_guest_profile` as currently
  implemented) MUST be removed or fully replaced — it MUST NOT remain callable by the agent once the
  verification tool ships.

**Guest lifecycle**

- **FR-014**: System MUST provide a tool that checks a verified guest into a specific, available room
  matching their reservation's room type, transitioning the reservation to a checked-in state.
- **FR-015**: The check-in tool MUST reject check-in attempts against a reservation that is not
  currently in a checkable state (e.g. already checked in, checked out, or cancelled).
- **FR-016**: The check-in tool MUST report unavailability rather than assigning a room of the wrong
  type when no room of the reserved type is currently available.
- **FR-017**: System MUST provide a tool that checks a checked-in guest out, transitioning the
  reservation to a checked-out state and marking their room as needing housekeeping before its next
  assignment.
- **FR-018**: System MUST provide a tool that creates a new reservation against the room catalogue
  given a room type and valid stay dates, returning a booking reference.
- **FR-019**: The booking-creation tool MUST reject date ranges where checkout is not after check-in.
  It MUST also reject a booking when no room of the requested type is free for the *entire*
  requested date range — computed deterministically as: `(total rooms of that type) minus (active
  reservations of that type whose dates overlap the request)` must be greater than zero, where
  "active" means status `confirmed` or `checked_in` (a `cancelled` or `checked_out` reservation
  never holds a room against future dates), and "overlap" uses standard same-day-turnover semantics
  (a reservation checking out the same day a new one checks in does not count as a conflict). This
  is a distinct check from FR-016's check-in-time room availability — see Assumptions.
- **FR-020**: System MUST provide tools to change an existing reservation's dates or cancel it, both
  of which MUST require explicit human confirmation before the change is committed, and MUST leave
  the reservation unchanged if confirmation is not given.
- **FR-021**: System MUST provide a minimal human-handoff tool that acknowledges a guest's request to
  speak with staff and confirms the escalation was received.
- **FR-022**: Every write tool introduced in this phase (check-in, check-out, create/modify/cancel
  booking) MUST accept an idempotency key and MUST NOT double-apply a change when called twice with
  the same key.

**Tool contract**

- **FR-008**: Every tool introduced or touched in this phase MUST return a `{status, data, error}`
  result shape and MUST NOT raise an uncaught exception.

**Environment**

- **FR-009**: System MUST have a committed dependency manifest listing the packages the agent
  actually requires to run, with each package pinned to the exact version currently in use.

### Key Entities *(include if feature involves data)*

- **Guest**: A person's identity — name, contact details, traits that persist across stays.
- **Reservation**: A single booking — stay dates, rate, status, room type, assigned room (once
  checked in), and a booking reference — belonging to exactly one Guest.
- **Room Type**: A bookable category of room (e.g. Standard Queen, Deluxe King) with occupancy and
  size characteristics; what a reservation is made against.
- **Room**: A specific physical room instance belonging to a Room Type, with its own floor, view,
  occupancy status, and housekeeping status; what a reservation is assigned to at check-in.
- **Room Feature**: A tag (view, amenity, accessibility, smoking) attached to a Room Type or a
  specific Room instance.
- **Policy Chunk**: Existing entity, unaffected by this phase.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A guest supplying correct identifying details receives their reservation information
  in a single exchange, with no follow-up clarification needed.
- **SC-002**: In testing, guests supplying incorrect, mismatched, or incomplete identifying details
  are denied profile/reservation data 100% of the time.
- **SC-002a**: No conversation is allowed more than 3 identity-verification attempts before being
  redirected to the front desk.
- **SC-003**: Post-migration guest, reservation, and room-inventory row counts match expectations
  exactly, verified automatically as part of each migration.
- **SC-004**: A contributor can go from a freshly cloned repository to a running agent using only the
  committed dependency manifest, with no undocumented manual installation steps.
- **SC-005**: A guest can complete check-in and check-out for an existing reservation through the
  agent in a single conversation each, ending with correct reservation and room state.
- **SC-006**: A guest can create a new booking, then modify or cancel it, entirely through
  conversation with the agent, with every date/cancellation change requiring an explicit
  confirmation step before it takes effect.
- **SC-007**: No write action introduced in this phase can be double-applied by retrying the same
  request, verified by replaying an identical request and confirming no duplicate state change.

## Assumptions

- No password- or OTP-based authentication system exists at this phase; identity verification uses
  knowledge-based matching (booking reference + surname), matching the proposal's
  `verify_guest_identity(booking_reference, surname)` tool contract exactly.
- The session-scoped 3-attempt cap on failed identity verification (FR-007a) is an addition on top
  of the base `verify_guest_identity` tool contract from the source proposal — implemented as a
  conversation-level guardrail in the agent's behavior, not a change to the tool's own data contract
  or a persistent account-lockout system.
- The 300 synthetic guest/booking rows are the only pre-existing guest data; new bookings created via
  this phase's tools add to, rather than replace, that seed data.
- Legacy reservations' room type is backfilled deterministically from the existing Kaggle-derived
  `reserved_room_type` codes; specific room assignment happens only at check-in time for every
  reservation, legacy or new, consistent with how a real hotel assigns rooms on arrival rather than
  at booking time.
- Migrations are applied manually against the Supabase instance for this phase; no automated
  migration-runner or CI pipeline is introduced.
- `request_human_handoff` in this phase is a minimal acknowledgment only — it does not integrate with
  a real staff task-routing system, since that system (`staff_tasks`) doesn't exist until
  Phase 4/Milestone 4 per the proposal's phased plan.
- Keycards, room sensor events, rate calendar, and simulated energy-mode sensing are out of scope for
  this phase's room inventory migration, even though they appear in the same migration file in the
  source proposal — they add no value to the guest-lifecycle demo this phase targets.
- Containerization (Docker) is out of scope for this phase — no deployment target exists yet to
  containerize for, and a pinned dependency manifest is sufficient to satisfy SC-004 on its own.
- "Availability" means two deliberately different things in this spec, not one term reused loosely:
  **reservation availability** (FR-019, booking time — is any room of this type free for these
  dates, computed from active reservation date-overlap) and **room availability** (FR-016, check-in
  time — is a specific room instance physically free right now). No date-overlap calendar table is
  introduced to support this — it's computed on demand from `reservations` and `rooms`, keeping this
  phase SQL-only with no new entity beyond what FR-011 already specifies.
- `room_features` is seeded with real sample tags (a handful of type-level and instance-level
  view/amenity/accessible/smoking entries) in migration 003, even though no tool in this phase reads
  them — confirmed against the source proposal's own description of this table as the amenities
  table, not a placeholder for a separate one.
