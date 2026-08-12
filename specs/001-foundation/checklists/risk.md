# Risk Checklist: Foundation, Room Inventory & Guest Lifecycle

**Purpose**: Validate requirements quality in the four highest-risk areas of this merged phase before implementation starts — migration safety, identity-verification leak-proofing, reservation state-machine correctness, and idempotency-key contract completeness.
**Created**: 2026-08-05
**Feature**: [spec.md](../spec.md), [plan.md](../plan.md), [data-model.md](../data-model.md), [contracts/](../contracts/)

## Migration Correctness & Row-Count/Idempotency Safety

- [ ] CHK001 Is the absence of a row-count assertion for migration 001 explicitly justified as a baseline no-op, or could it mask an unnoticed pre-migration schema drift? [Clarity, contracts/migrations.md]
- [x] CHK002 Are the exact expected row counts for `room_types` and `rooms` specified as concrete numbers, rather than left as a `<seeded count>` placeholder? [Gap, contracts/migrations.md] — Resolved: 6 room types, 60 rooms (10/type), fixed in contracts/migrations.md and research.md §1.
- [x] CHK003 Is the legacy `reserved_room_type` → seeded-room-type mapping specified as a concrete, exhaustive lookup table, or only described conceptually ("e.g. code A → first type... wrapping")? [Ambiguity, research.md §1] — Resolved: fixed A–H → 1–6 (mod 6, wrapping) table in research.md §1, derived from the actual 8 codes present in `data/guests.csv`.
- [ ] CHK004 Are requirements defined for what happens if migration 003 fails after 001 and 002 have already succeeded — is manual intervention, retry, or rollback expected? [Gap]
- [ ] CHK005 Is re-run/idempotency behavior of the migration files themselves specified (can a partially-failed migration be safely retried), independent of the row-count abort behavior already covered? [Gap, Coverage]
- [ ] CHK006 Are retention or growth requirements specified for the `idempotency_keys` table, or is unbounded growth left undefined? [Gap, data-model.md]

## Guest-Identity-Verification: No Partial Match, No Information Leak

- [ ] CHK007 Is the "generic, not distinguishing which field was wrong" error requirement specific enough to rule out an implementation that returns different error text or codes for "booking reference not found" vs. "surname mismatch"? [Clarity, contracts/tools.md, Spec §FR-006]
- [ ] CHK008 Is the case/whitespace normalization rule for surname matching precisely defined (e.g., trim + case-fold), or left to interpretation? [Ambiguity, Spec Edge Cases]
- [ ] CHK009 Are response-time consistency requirements specified for `verify_guest_identity`, so a faster response on a partial match (e.g., valid booking reference, wrong surname) can't leak which field was correct? [Gap, Non-Functional]
- [ ] CHK010 Is the interaction between the per-conversation 3-attempt cap (FR-007a) and a guest starting a brand-new conversation specified — is the cap meant to be bypassable that way, or is that a gap? [Gap, Coverage, Spec §FR-007a]
- [ ] CHK011 Are audit/logging requirements defined for repeated failed verification attempts, or is monitoring for this left unspecified? [Gap]

## Reservation State-Machine Correctness

- [ ] CHK012 Are all invalid state transitions enumerated (e.g., `check_out_guest` on a `confirmed` reservation that was never checked in), or only the two called out in Spec Edge Cases (check-in on `cancelled`/`checked_out`)? [Completeness, Gap, Spec Edge Cases]
- [x] CHK013 Is the precondition state (or states) required for `cancel_booking` to succeed explicitly specified — e.g., is cancelling a `checked_in` reservation allowed, or only a `confirmed` one? [Gap, contracts/tools.md] — Resolved: `confirmed` or `checked_in` both allowed; `checked_out`/already-`cancelled` rejected. Full precondition table added to data-model.md.
- [x] CHK014 Is the precondition state required for `modify_booking` explicitly specified, mirroring the gap above? [Gap, contracts/tools.md] — Resolved: same table, same allowed states as `cancel_booking`.
- [ ] CHK015 Are concurrent-modification requirements specified for two simultaneous actions against the same reservation (e.g., a racing double check-in), or is single-actor access assumed without stating so? [Gap, Non-Functional]
- [x] CHK016 Does Spec §FR-019's availability requirement for `create_booking` explicitly state the same type-only (not per-date) availability scope that contracts/tools.md calls out, or could a reader of spec.md alone assume full date-range availability checking is required? [Consistency, Spec §FR-019, contracts/tools.md] — Resolved via `/speckit.analyze` (finding F1, 2026-08-05): this was a real conflict, not an acceptable scope limit as originally (incorrectly) deferred. Resolution went the other direction — FR-019 now requires real per-date availability (booking.com-style), and contracts/tools.md + tasks.md T016 were widened to match, not narrowed. See research.md §5, data-model.md's "Availability" section.

## Idempotency-Key Contract Completeness

- [x] CHK017 Is the replay behavior for a reused idempotency key specified precisely — must the exact original response be returned, or only an equivalent success result? [Clarity, Ambiguity, research.md §2] — Resolved: `idempotency_keys.result` (jsonb) stores the exact `ToolResult`, replayed byte-for-byte. Added to data-model.md.
- [x] CHK018 Is the required behavior specified for the same idempotency key being reused across two different tools (e.g., first used for `check_in_guest`, then `cancel_booking`), given `idempotency_keys.tool_name` implies this is distinguished? [Gap, Ambiguity, data-model.md] — Resolved: primary key is the `(key, tool_name)` pair, so cross-tool reuse is a distinct, unrelated row by design — no collision, no special-case handling needed.
- [x] CHK019 Is the source of the idempotency key value consistent between research.md (which attributes it to "the client's write-ahead queue," a Phase 3 component that doesn't exist yet) and this phase's actual tools, which must generate or receive keys without that queue in place? [Consistency, research.md §2] — Resolved: `concierge_agent` generates a fresh UUID4 itself this phase (protects transport-level retries within one invocation); the durable, cross-turn guarantee arrives with the real write-ahead queue in Phase 3. Documented explicitly in research.md §2.
- [ ] CHK020 Are all five write tools (`check_in_guest`, `check_out_guest`, `create_booking`, `modify_booking`, `cancel_booking`) confirmed to share identical idempotency-key semantics, or could any diverge without a stated reason? [Consistency, Spec §FR-022]

## Notes

- Check items off as completed: `[x]`
- These items test whether the **requirements** (spec.md/plan.md/data-model.md/contracts) are complete, clear, and consistent enough to implement against safely — not whether the eventual code works. Resolve `[Gap]`/`[Ambiguity]`/`[Consistency]` items by editing the referenced document, not by writing code first and hoping the gap doesn't matter.
- CHK002, CHK003, CHK013, CHK014, CHK017, and CHK019 (the highest-value gaps — places an implementer would otherwise have to guess) were resolved directly in research.md/data-model.md/contracts/ during this checklist pass, 2026-08-05.
- CHK016 was initially (incorrectly) deferred as an acceptable scope limit, then caught for real by `/speckit.analyze` (finding F1) and resolved properly the same day — see research.md §5, data-model.md's "Availability" section, and tasks.md T016/T024.
- Remaining open items (CHK001, CHK004–012, CHK015, CHK020) are reviewed and still genuinely acceptable scope limits for this phase, not blocking `/speckit.implement`.
