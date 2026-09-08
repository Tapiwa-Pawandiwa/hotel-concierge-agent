# Tasks: Foundation, Room Inventory & Guest Lifecycle

**Input**: Design documents from `/specs/001-foundation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md — all present

**Tests**: Not requested in spec.md; this phase's verification is the manual `quickstart.md` pass per
story, per CLAUDE.md's MVP scope & order (automated pytest suite is a later, dedicated Testing
milestone).

**Organization**: Tasks are grouped by user story (spec.md priorities: US1/US2 = P1, US3 = P2,
US4 = P3, US5 = P4) so each can be implemented and validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Per CLAUDE.md's Session loop and the constitution's Principle I (Worked-Example Learning): the
  agent delivers each task as a complete worked example, the human places/runs/debugs it, and the
  agent asks a comprehension-check question before the next task starts. Don't batch multiple
  tasks before that check.

## Path Conventions

Per plan.md's Structure Decision: migrations in repo-root `db/migrations/`, dependency manifest and
agent code under `agent/`.

---

## Phase 1: Setup

**Purpose**: Environment and directory scaffolding — no schema or tool logic yet.

- [x] T001 [P] Create `db/migrations/` directory at repo root
- [x] T002 [P] Create `agent/requirements.txt` listing `google-adk`, `psycopg`, `pgvector`,
      `voyageai`, `python-dotenv`, each pinned to the exact version currently installed in
      `agent/.venv` (FR-009; research.md §5 — direct imports only, not a full `pip freeze`).
      Also includes `psycopg-binary==3.3.4`, one step beyond research.md §5's "direct imports
      only" rule — not imported by name in `tools.py`, but `psycopg` needs its C/binary backend to
      work without a local `libpq`/build toolchain, and it's already present in `agent/.venv`. Left
      out `psycopg2-binary` (confirmed unused — no `import psycopg2` anywhere in the codebase).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The schema every user story depends on, plus the shared idempotency mechanism every
write tool (US3/US4) needs. This phase's own completion criteria *are* User Story 2's acceptance
scenarios — there's no separate "US2 phase" later.

**⚠️ CRITICAL**: No user story work (US1/US3/US4/US5) can begin until this phase is complete.

- [x] T003 Write `db/migrations/001_initial_schema.sql` — baseline capture of the currently-live
      schema (`guests` flat table, `policy_chunks` with its `pgvector` HNSW index), verbatim per
      `docs/implementation_proposal.html` §4. No structural change (FR-001). Apply to a scratch/dev
      Supabase project; confirm schema unchanged (US2 Acceptance Scenario 1).
- [x] T004 Write `db/migrations/002_refactor_guests_reservations.sql` — split `guests` into `guests`
      (identity) + `reservations`, backfilling all 300 rows, with the row-count assertion
      (`old_count == new_guest_count == new_resv_count`) from the source proposal's `DO $$` block
      reproduced verbatim (FR-002, FR-003, FR-004). Apply on top of T003; confirm both new tables
      have exactly 300 rows each (US2 Acceptance Scenario 2).
- [x] T005 Write `db/migrations/003_rooms_inventory.sql` — add `room_types` (6 seeded rows),
      `rooms` (60 seeded rows, 10 per type), `room_features` (seeded with real sample
      view/amenity/accessible/smoking tags, type- and instance-level — this is the amenities table
      per the source proposal, not a placeholder; spec.md Assumptions), and `idempotency_keys`
      (`key`, `tool_name` composite PK, `result` jsonb, `created_at` — data-model.md); backfill
      `reservations.room_type_id` on all 300 existing rows via the fixed A–H → 1–6 mapping table in
      research.md §1; add the FK constraints on `reservations.room_type_id`/`room_id` left bare by
      002 (FR-011, FR-012). Include the row-count assertion (`room_types = 6`, `rooms = 60`,
      every reservation has a non-null `room_type_id` — FR-013). Explicitly exclude `keycards`,
      `room_sensor_events`, `rate_calendar` (spec.md Assumptions). Apply on top of T004; confirm
      counts (US2 Acceptance Scenario 3).
- [x] T006 Run every query in `quickstart.md`'s "Story 2 check first" section against the
      post-T005 database and confirm all five counts match exactly (SC-003; also exercises US2
      Acceptance Scenario 4 — deliberately introduce a mismatch on a throwaway copy first to
      confirm the assertions actually abort the transaction, then discard that copy).
- [x] T007 Implement a shared idempotency check-and-record helper in
      `agent/concierge_agent/tools.py` — given `(key, tool_name)`, looks up `idempotency_keys`;
      returns the stored `result` verbatim on a hit; on a miss, the caller performs its write and
      the helper records `(key, tool_name, result)` in the same transaction (FR-022; research.md
      §2). Every write tool in US3/US4 calls this helper — implement it once here, not per tool.

**Checkpoint**: Foundation ready — schema exists, row counts verified, idempotency mechanism in
place. User Story 2 is fully satisfied by this phase alone.

---

## Phase 3: User Story 1 - Guest proves who they are (Priority: P1) 🎯 MVP

**Goal**: Replace the broken, unauthenticated `lookup_guest_profile` with a real identity check
(booking reference + surname) before the agent discloses anything guest-specific.

**Independent Test**: Ask the agent guest-specific questions with correct vs. incorrect/incomplete
identifying details (quickstart.md "Story 1"); confirm data is returned only on a full, correct
match, and that a 4th attempt after 3 failures is refused.

### Implementation for User Story 1

- [x] T008 [US1] Remove `lookup_guest_profile` entirely from `agent/concierge_agent/tools.py` and
      its registration/reference in `agent/concierge_agent/agent.py` (FR-010) — it must not remain
      callable once T009 ships.
- [x] T009 [US1] Implement `verify_guest_identity(booking_reference: str, surname: str) -> ToolResult`
      in `agent/concierge_agent/tools.py` per `contracts/tools.md` — case/whitespace-insensitive
      surname match, both values must match the *same* reservation, generic `status="error"` on any
      non-match without indicating which field was wrong (FR-005, FR-006, FR-007).
- [x] T010 [US1] Register `verify_guest_identity` in `agent/concierge_agent/agent.py`; rewrite the
      agent's instruction text so it calls this tool before answering any guest-specific question,
      asks for a missing value rather than guessing, and — after 3 failed verification results in
      one conversation — stops attempting verification and tells the guest to contact the front desk
      (FR-007a). This cap is conversation-level agent behavior, not part of the tool's own contract.
- [x] T011 [US1] Manually validate all 4 acceptance scenarios in `quickstart.md`'s "Story 1" section.

**Checkpoint**: User Story 1 fully functional and independently testable — this is the demoable MVP.

---

## Phase 4: User Story 3 - Guest checks in and checks out (Priority: P2)

**Goal**: A verified guest can be checked into a specific available room and later checked out, with
the room correctly released for housekeeping.

**Independent Test**: Verify identity, check in, confirm a room is assigned and occupied, check out,
confirm the room is released (quickstart.md "Story 3").

### Implementation for User Story 3

- [x] T012 [US3] Implement `check_in_guest(idempotency_key: UUID, booking_reference: str) -> ToolResult`
      in `agent/concierge_agent/tools.py`, using the T007 helper. Precondition: reservation status
      `confirmed` (data-model.md precondition table); assigns an available room of the reservation's
      `room_type_id`, sets `reservations.status = 'checked_in'` and
      `rooms.occupancy_status = 'occupied'`. Rejects (structured error, not exception) if the
      reservation isn't found, isn't `confirmed`, or no room of the required type is available
      (FR-014, FR-015, FR-016).
- [x] T013 [US3] Implement `check_out_guest(idempotency_key: UUID, booking_reference: str) -> ToolResult`
      in `agent/concierge_agent/tools.py`, using the T007 helper. Precondition: reservation status
      `checked_in`; sets `status = 'checked_out'`, `rooms.housekeeping_status = 'needs_cleaning'`,
      `rooms.occupancy_status = 'vacant'` (FR-017).
- [x] T014 [US3] Register both tools in `agent/concierge_agent/agent.py`; update instruction text so
      the agent only offers check-in/check-out after identity verification (US1) has succeeded.
- [x] T015 [US3] Manually validate all 4 acceptance scenarios in `quickstart.md`'s "Story 3" section.

**Checkpoint**: User Stories 1, 2, and 3 all independently functional.

---

## Phase 5: User Story 4 - Guest books, modifies, or cancels a stay (Priority: P3)

**Goal**: A guest can create a new reservation against the room catalogue, and change dates or
cancel an existing one — the latter two always confirmation-gated. Every booking also needs a
resolved guest identity behind it: an existing profile found by search, or a new one created on
the spot — not assumed to already exist the way `create_booking`'s `guest_id` parameter originally
implied (source proposal §11 "why" note — see Guest Profile Management below).

**Independent Test**: Search for a guest profile, confirm a no-match creates a new one and a match
reuses the existing one; create a booking end-to-end against the resolved `guest_id`; modify its
dates; cancel it — confirming each date-change/cancellation requires explicit confirmation before
it commits (quickstart.md "Story 4", extended).

### Implementation for User Story 4

- [x] T016 [US4] Write a migration adding `operational_status` text to `rooms`
      (`active`/`out_of_order`, default `active`), same pattern as
      `occupancy_status`/`housekeeping_status`. Apply on top of 004; confirm all existing rows
      default to `active` (data-model.md, source proposal §4 "why" note).
      **Number collision**: this was going to be `005_room_operational_status.sql`,
      but `data-model.md` also references an uncommitted `005_idempotency_key_as_text.sql` already
      applied live — confirm with the human which was actually applied and in what order before
      writing this file, don't assume `005` is free.
- [x] T017 [US4] Implement `assign_room(idempotency_key, booking_reference, room_id=None,
      desired_features=None) -> ToolResult` in `agent/concierge_agent/tools.py`, using the T007
      helper (later clarification — new tool, separates physical room allocation from both
      booking and check-in). Precondition: reservation status `confirmed`. If `room_id` given,
      validates it belongs to the reservation's `room_type_id`, is `operational_status = 'active'`,
      and isn't already the assigned `room_id` of a *different* active reservation overlapping
      dates; rejects otherwise. If `room_id` omitted, searches rooms of the reservation's
      `room_type_id` not already assigned to another overlapping active reservation, optionally
      filtered by `desired_features` matching that room's `room_features` tags; assigns the first
      match. Sets `reservations.room_id` — does NOT touch `rooms.occupancy_status` (that's
      check-in's job, per the later clarification: assignment ≠ occupancy). Mutable — calling
      it again on the same reservation reassigns a different room, it doesn't error.
      **Also revises `check_in_guest` (shipped in T014)**: removes its internal room-search entirely;
      it now requires `reservations.room_id` already set (rejects with a distinct "no room assigned
      — call assign_room first" error if `NULL`), and validates the *already-assigned* room's
      `occupancy_status = 'vacant'` (and `operational_status = 'active'`) before completing check-in,
      rather than searching for and picking any vacant room of the right type itself.
- [x] T018 [US4] Implement `list_room_types(check_in_date, check_out_date) -> ToolResult` in
      `agent/concierge_agent/tools.py`. Tier 1, read-only, no confirmation. Returns every room
      type's `bed_config`/`max_occupancy`/`sq_meters`/`room_features.feature` list plus real
      per-date availability for the requested range — same counting logic T022 uses
      (`count(rooms of room_type_id, operational_status = 'active') - count(overlapping
      reservations)`), factored into a shared helper both tools call rather than duplicated.
      Resolves natural-language room requests ("a suite with a couch") via the model's own
      reasoning over the returned list, not a structured filter parameter (source proposal §4/§11
      "why" note — this is the tool that closes the gap between what a guest describes
      and the `room_type_id` `create_booking` needs).

#### Guest Profile Management (new, added after the original scope)

The person (`guests` — a **Who**, Principle II) and the stay (`reservations` — a **Request**) are
separate primitives and separate writes, matching how hotels actually run this: a profile can
exist with zero stays attached, and the standard flow always searches for an existing profile
before creating a new one — whether the guest is at a kiosk, on the phone, or booking online. This
sits ahead of `create_booking` in the flow, not inside it. No schema change needed: `guests` and
its `legacy_guest_id` column already exist from migration 002, and that column is nullable with no
`NOT NULL` constraint, so new profiles can leave it `NULL` (Postgres `UNIQUE` already permits
multiple `NULL`s).

- [x] T019 [US4] Implement `search_guest_profiles(first_name=None, last_name=None, email=None,
      phone=None) -> ToolResult` in `agent/concierge_agent/tools.py`. Tier 1, read-only, no
      confirmation. Matches on exact case-insensitive `email` or `phone` if given, else `ILIKE` on
      `first_name`/`last_name`; returns up to 5 candidate `guests` rows (`guest_id`, `first_name`,
      `last_name`, `email`, `phone`). No scoring/confidence engine — deliberately declined
      (Cloudbeds' 90%+ match-confidence engine, OPERA's auto-merge rules are real-world references,
      not requirements here) as speculative for this phase; the model presents candidates
      conversationally and lets the guest confirm — the same pattern `list_room_types` already uses
      to resolve "a suite with a couch" over a returned list instead of a structured filter.
- [x] T020 [US4] Implement `create_guest_profile(idempotency_key, first_name, last_name, email=None,
      phone=None, country=None) -> ToolResult` in `agent/concierge_agent/tools.py`, using the T007
      helper. Tier 2 — write, logged, reversible; no human confirmation required (same tier as
      `check_in_guest`/`check_out_guest` — a profile alone carries no money or dates). Inserts a new
      `guests` row with `legacy_guest_id = NULL` and returns the new `guest_id`. Does not itself
      check for duplicates — relies on the agent having called T019 first, per its instruction text
      (T025); no DB-level dedupe/merge this phase, matching the "search upfront, no automatic merge"
      decision.
- [x] T021 [US4] Implement `update_guest_profile(idempotency_key, guest_id, first_name=None,
      last_name=None, email=None, phone=None, country=None) -> ToolResult` in
      `agent/concierge_agent/tools.py`, using the T007 helper. Tier 2, same reasoning as T020 — only
      the supplied fields are updated (partial update, not full overwrite); rejects if `guest_id`
      doesn't exist.

#### Booking, resumed

- [x] T022 [US4] Implement `create_booking(idempotency_key, guest_id, room_type_id, check_in_date,
      check_out_date) -> ToolResult` in `agent/concierge_agent/tools.py`, using the T007 helper.
      Rejects `check_out_date <= check_in_date`. Computes real per-date reservation availability
      (research.md §5), now excluding `out_of_order` rooms per T016: `count(rooms of room_type_id,
      operational_status = 'active') - count(reservations of that type with status IN
      ('confirmed','checked_in') whose date range overlaps the request)`; rejects if that count is
      `<= 0` — modeled deterministically on standard hotel-booking-site behavior, not just a "does
      this room type exist" check (FR-018, FR-019). Generates a new `booking_reference`, inserts
      with `status = 'confirmed'` only once availability is confirmed. `guest_id` is now always a
      resolved value — from T019/T020 for a new guest, or T009's `verify_guest_identity` for a
      returning guest citing an existing reservation; `create_booking` itself takes no new
      parameters, only its precondition changed, from assumed to explicit.
- [x] T023 [US4] Implement `modify_booking(idempotency_key, booking_reference, new_check_in,
      new_check_out) -> ToolResult` in `agent/concierge_agent/tools.py` using ADK's native
      `require_confirmation=True` (research.md §4). Precondition: reservation status `confirmed` or
      `checked_in` (data-model.md precondition table); rejects a resulting range where checkout
      isn't after check-in; leaves the reservation unchanged if not confirmed (FR-020).
- [x] T024 [US4] Implement `cancel_booking(idempotency_key, booking_reference) -> ToolResult` in
      `agent/concierge_agent/tools.py`, same `require_confirmation=True` pattern and precondition
      states as T023; sets `status = 'cancelled'` only after confirmation (FR-020).

#### Products & pricing — fixes a live bug, not new scope (added after the original scope)

Code review found the shipped `create_booking` pricing breakfast from
`SELECT value FROM hotel_settings WHERE key = 'breakfast_rate_per_day'` — an uncommitted table used
as a catalogue price source — plus a separate bug where the returned `total_price` is referenced
but never computed (`NameError` on every real call). See `data-model.md`'s new
`products`/`product_prices`/`reservation_products` section and
`docs/implementation_proposal.html` §1/§4 why-notes for the full design reasoning.

- [x] T025 [US4] Write a migration adding `products`, `product_prices`, `reservation_products` per
      `data-model.md` (each including `created_at`). Seed `products`/`product_prices` with one row
      (`BREAKFAST`, `PER_NIGHT`, matching whatever `breakfast_rate_per_day` was actually set to in
      `hotel_settings`, so the price doesn't silently change under this migration). Do **not** carry
      `hotel_settings` forward as a price source for anything — it's still fine for genuine
      operational config (`check_in_time`, `timezone`, restaurant `capacity`), just not prices. Apply
      on top of T016. **Number collision**: this was going to be
      `006_products_pricing.sql`, but `data-model.md` also references an uncommitted
      `006_room_type_rates.sql` (`room_types.base_rate`) already applied live — same confirmation
      needed as T016 before this gets a real filename.
- [x] T026 [US4] Rework `create_booking` in `agent/concierge_agent/tools.py`: delete the duplicate,
      earlier `create_booking` definition entirely (two functions of the same name currently exist —
      Python silently keeps only the later one, so the first is dead code and the second, worse one
      is what actually runs). Replace the `hotel_settings` breakfast lookup with a `product_prices`
      read (current applicable row for `BREAKFAST`, `valid_to IS NULL` or covers today) and, on
      success, insert a matching `reservation_products` row with `unit_price`/`pricing_basis`
      snapshotted from that read — not a live join, per `data-model.md`'s reasoning. Drop
      `reservations.breakfast_included` from the insert; `reservation_products` is now the source of
      truth. Fix the undefined `total_price` (compute it: `(base_rate * nights) + breakfast_total`,
      restored from the dead first definition rather than reinvented). Uses the T007 helper, same as
      before.
#### Audit metadata — every table reviewed, not just reservations (added after the original scope)

Triggered directly: "the schema for reservations doesn't include valuable metadata like modified
date or created date," then broadened to "we need valuable metadata for all tables, please review
your logic, and discuss with me." Full table-by-table split lives in `data-model.md`'s new "Audit
metadata review" section — real live gaps (`guests`, `reservations`, `rooms`), lower-priority
consistency additions (`room_types`, `room_features`), and tables deliberately left alone
(`idempotency_keys`, `product_prices`, `reservation_products`, `policy_chunks`), each with its own
reasoning, not a blanket add-everywhere pass.

- [x] T027 [US4] Write a migration adding: `guests.updated_at`; `reservations.created_at` and
      `.updated_at`; `rooms.created_at` and `.updated_at`; `room_types.created_at`;
      `room_features.created_at`. Also create one shared `set_updated_at()` trigger function (full
      SQL in `data-model.md`) and attach it via a separate `CREATE TRIGGER ... BEFORE UPDATE` on
      `guests`, `reservations`, and `rooms` — one function, three triggers, not three copies of the
      same logic. **Number collision**: provisionally `007`, contingent on T016/T025 resolving to
      real, non-colliding numbers first — confirm the full real sequence with the human before
      writing this file.
- [x] T028 [US4] Register all eight tools (`assign_room`, `list_room_types`,
      `search_guest_profiles`, `create_guest_profile`, `update_guest_profile`, `create_booking`,
      `modify_booking`, `cancel_booking`) in `agent/concierge_agent/agent.py`; update instruction
      text so the agent always searches for a guest profile before creating one, only creates one
      on a confirmed no-match, calls `assign_room` before offering check-in whenever a reservation
      has no `room_id` yet (and again if `check_in_guest` rejects with the "no room assigned"
      error), and explains the confirmation step to the guest before `modify_booking`/
      `cancel_booking` fire. Also fix the truncated/garbled sentences already in the instruction
      string (e.g. "assign_room, cr\ncreate_guest_profile" and "wait for th\nsystem commits it") —
      found on code review, likely a paste accident, not a deliberate abbreviation.
- [x] T029 [US4] Manually validate all 4 acceptance scenarios in `quickstart.md`'s "Story 4" section,
      plus three new ones: ask for a room type matching a described preference (e.g. "a suite with a
      couch") before booking, confirming `list_room_types` resolves it correctly; run the same guest
      through the profile flow twice with matching contact details, confirming the second pass reuses
      the existing `guest_id` instead of creating a duplicate; and book with breakfast added,
      confirming the response includes a real `total_price` and a `reservation_products` row exists
      with the snapshotted price.

#### Found via live testing, added after T026/T028 — not part of their original scope

- [ ] T030 [US4] Two related fixes, both needed together: (1) In `agent/concierge_agent/agent.py`'s
      instruction string, inject the real current date (e.g. an f-string with
      `datetime.date.today().isoformat()` at agent-construction time) so the "DATES" section has
      something to reason "past" vs. "future" against — live-tested and confirmed the agent asks "And
      which year, 2024 or 2025?" because nothing in its instructions currently tells it what today is.
      (2) In `agent/concierge_agent/tools.py`'s `create_booking`, add a guard rejecting
      `check_in_date` before today, alongside the existing `check_out_date <= check_in_date` check —
      defense-in-depth so a past booking can't be created even if (1) somehow fails or gets bypassed.
- [ ] T031 [US4] Fix a PII-disclosure gap in the guest-profile-match flow — same failure class as R1's
      original `lookup_guest_profile` finding (any requester gets a matched profile's PII), just in a
      new tool: live-tested and the agent reads the *stored* email/phone back to the guest to confirm
      a `search_guest_profiles` match (e.g. "the profile has the email suzannesmith@example.org on
      file — is this you?"), disclosing another guest's contact details to whoever's chatting if
      names collide or a wrong match gets read back. Fix in `agent.py`'s instruction text only (no
      tool signature change needed): never recite a candidate's stored `email`/`phone` to the guest —
      reference candidates by name only, and if disambiguation is genuinely needed, ask the guest to
      state their own contact detail and silently check it against the candidate rather than
      displaying what's on file.
- [x] T039 [US4] Party size is never collected or enforced — live-tested across several full booking
      conversations and the agent never once asked how many guests are staying, despite
      `room_types.max_occupancy` already existing in the schema and already being returned by
      `list_room_types`. Three parts: (1) migration `010_reservation_num_guests.sql` adding
      `reservations.num_guests` (int, backfilled from `guests_legacy_kaggle.adults + children` for
      the original 300 via `booking_reference = 'BK-' || guest_id`, `1` for any other existing row,
      then set `NOT NULL`); (2) `create_booking` in `tools.py` gains a required `num_guests: int`
      parameter, validated against the chosen room type's `max_occupancy` (reject with a clear error
      if `num_guests` is below 1 or exceeds it — same "reject with a structured error" pattern as the
      availability check, not a silent clamp), and stores it on insert; (3) `agent.py`'s "NEW
      BOOKINGS" instruction updated so asking for party size is a required step alongside dates, up
      front — not optional, not inferred — and the agent uses it (with `list_room_types`'s
      `max_occupancy` already in the response) to steer its own room-type recommendations, same
      natural-language-reasoning pattern as "a suite with a couch" rather than a new structured filter
      parameter.
- [x] T040 [US4] Multi-room bookings under one guest request create fully unlinked reservations —
      live-tested (Sherlock Holmes, 2 rooms; Dwayne Hayes, 9 rooms) and each room got its own
      `booking_reference` with no relationship between them, so staff have no way to see "this is one
      group" rather than unrelated strangers who share a name. Real PMS practice (Opera/Cloudbeds/
      Mews) keeps one reservation row per physical room (different occupants/times/charges per room
      stays correct) but ties them together for staff via a shared identifier — **revised
      2026-09-08 after checking `implementation_proposal.html`**: `reservations.group_booking_id`
      (already in the schema since migration 002) is NOT that identifier — it's explicitly documented
      (source proposal §8/§Phase-7 schema note) as reserved for the *formal corporate/event* group-
      block case, FK'd to `event_bookings` once Phase 7 (`specs/008-business-events`) builds it.
      Reusing it here would misuse a column reserved for a different concept and collide with that
      future FK. Confirmed via research this is a real, standard distinction in hotel systems
      (industry "group booking" = wedding/corporate block; a guest's own multi-room request is a
      separate, simpler concept) — not inventing a false split.

      Corrected design: a genuinely new, small parent table, not a bare UUID column (unlike
      `group_booking_id`, which deferred its FK to Phase 7 deliberately — this one doesn't need to
      defer, so it gets a real FK from day one):
      ```sql
      CREATE TABLE booking_parties (
          id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          primary_guest_id  uuid NOT NULL REFERENCES guests(id),
          created_at        timestamptz NOT NULL DEFAULT now()
      );
      ALTER TABLE reservations ADD COLUMN booking_party_id uuid REFERENCES booking_parties(id);
      ```
      New tool `create_booking_party(idempotency_key, primary_guest_id) -> {booking_party_id}`
      (Tier 2, same shape as `create_guest_profile`). `create_booking` gains an optional
      `booking_party_id: str | None = None` parameter, stored on insert, `NULL` for a normal
      single-room booking (backward compatible). `agent.py` instruction text: when booking more than
      one room for the same request, call `create_booking_party` ONCE first, then pass the real
      returned `booking_party_id` to every `create_booking` call in that batch — a real FK, so an
      invented ID would fail loudly rather than silently, unlike the self-generated-UUID pattern
      `idempotency_key` uses. Explicitly out of scope, per `CLAUDE.md`'s billing deferral: combined/
      master payment across a party — no `bill_items`/payment table exists yet, that's
      `specs/006-fnb-billing`, later. This task only makes staff able to see the party as one unit,
      not pay for it as one unit.

**Checkpoint**: User Stories 1–4 all independently functional.

---

## Phase 6: User Story 5 - Guest asks for a human (Priority: P4)

**Goal**: A guest asking for staff help gets a clear acknowledgment rather than a dead end.

**Independent Test**: Ask the agent for a human; confirm an explicit escalation acknowledgment
(quickstart.md "Story 5").

### Implementation for User Story 5

- [ ] T032 [US5] Implement `request_human_handoff(reason: str | None = None) -> ToolResult` in
      `agent/concierge_agent/tools.py` — minimal acknowledgment only, no `staff_tasks` persistence
      this phase (spec.md Assumptions; FR-021).
- [ ] T033 [US5] Register the tool in `agent/concierge_agent/agent.py`; update instruction text so
      the agent offers this path when it can't resolve a request itself.
- [ ] T034 [US5] Manually validate the acceptance scenario in `quickstart.md`'s "Story 5" section.

**Checkpoint**: All five user stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Verify the requirements that cut across every story rather than belonging to one.

- [x] T035 Verify SC-007 by its own stated method — replay: call each of the eight write tools
      (`check_in_guest`, `check_out_guest`, `assign_room`, `create_guest_profile`,
      `update_guest_profile`, `create_booking`, `modify_booking`, `cancel_booking`) twice with the
      *same* `idempotency_key`, and confirm the second call returns the first call's stored
      `result` verbatim with no second state change in the database (quickstart.md's new
      "Idempotency replay" steps under Stories 3 and 4). Implementation existing (T007) alone
      doesn't satisfy SC-007 — this task is the verification the criterion itself specifies.
- [x] T036 [P] Audit every tool touched or added this phase (`verify_guest_identity`,
      `check_in_guest`, `check_out_guest`, `assign_room`, `list_room_types`,
      `search_guest_profiles`, `create_guest_profile`, `update_guest_profile`, `create_booking`,
      `modify_booking`, `cancel_booking`, `request_human_handoff`) in
      `agent/concierge_agent/tools.py` for FR-008
      compliance — `{status, data, error}` return shape, zero uncaught exceptions, including on a
      dropped DB connection.
- [x] T037 Fresh-environment check: new empty virtual environment, `pip install -r
      agent/requirements.txt`, `adk run` from `agent/` starts with no `ImportError`/missing-package
      failure (SC-004; quickstart.md final section).
- [ ] T038 Full end-to-end `quickstart.md` pass across all 5 stories in one sitting, against a
      freshly re-migrated scratch database, before marking this phase complete.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS every user story. Also independently
  satisfies User Story 2 in full.
- **User Story 1 (Phase 3)**: Depends only on Foundational. No dependency on US3/US4/US5.
- **User Story 3 (Phase 4)**: Depends on Foundational (rooms) and, functionally, on US1 (a guest
  must be verified before check-in makes sense) — build after US1, even though its tools don't
  literally import anything from US1's code.
- **User Story 4 (Phase 5)**: Depends on Foundational; functionally follows US1 for the same reason
  as US3.
- **User Story 5 (Phase 6)**: Depends on nothing but Foundational — could be built any time after
  Phase 2, sequenced last here only because it's lowest priority (P4).
- **Polish (Phase 7)**: Depends on every story you choose to include being complete.

### Parallel Opportunities

- T001/T002 (Setup) — different files, run together.
- T003/T004/T005 (migrations) are **not** parallel — each depends on the schema state the previous
  one leaves behind.
- Once Foundational (Phase 2) is done, US1 and US5 have no cross-story dependency and could be built
  in either order or concurrently by different people; US3 and US4 are best sequenced after US1 given
  the identity-verification precondition, even though nothing enforces that in code.
- T036 (Polish audit) has no file dependency on T035/T037/T038 and can run in parallel with them.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup) → Phase 2 (Foundational — also completes US2) → Phase 3 (US1).
2. **Stop and validate**: `quickstart.md` Story 1, by hand.
3. This alone is a demoable MVP: real schema, real identity verification, the R1/R2 bugs closed.

### Incremental Delivery

Phase 2 → US1 (demo) → US3 (demo) → US4 (demo) → US5 (demo) → Phase 7 (polish). Each checkpoint
above is a real stopping point — per CLAUDE.md's Session loop, review after each task, not after a
whole phase.

---

## Notes

- Every task shares two files (`agent/concierge_agent/tools.py`, `agent/concierge_agent/agent.py`)
  more than a typical multi-file project would — that's why so few tasks carry a `[P]` marker.
  Real, not accidental: this is still a two-file agent implementation at this phase's scale.
- Per the constitution's Principle I (Worked-Example Learning, Project 1 Mode) and CLAUDE.md's
  Session loop: the agent provides complete, commented code for every task; the human places, runs,
  and debugs it, and confirms it against that task's cited FR/acceptance criteria before the next
  task starts.
