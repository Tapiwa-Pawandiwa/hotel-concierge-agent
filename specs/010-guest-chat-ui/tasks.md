# Tasks: Guest Chat UI

**Input**: Design documents from `/specs/010-guest-chat-ui/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md — all present.
GCP project (`hotel-concierge-507914`) created, billing linked, `gcloud` CLI installed/authenticated,
required APIs (Cloud Run, Cloud Scheduler, Secret Manager, Artifact Registry, Cloud Build) enabled —
all done and verified 2026-09-07, ahead of this task list.

**Tests**: Not requested — this feature's verification is the manual `quickstart.md` pass per story,
same convention as `specs/001-foundation`.

**Organization**: Grouped by user story (spec.md priorities: US1 = P1, US2 = P2, US3 = P3), each
independently testable per spec.md's own Independent Test criteria.

## Format: `[ID] [P?] [Story] Description`

- Per CLAUDE.md's Session loop and the constitution's Principle I: feature-code tasks are delivered
  as complete worked examples, placed/run/debugged by the human, with a comprehension-check question
  before the next task. Scaffolding tasks (T001-T002) are the constitution's explicit exception —
  boilerplate with no learning value, the agent does these directly.

---

## Phase 1: Setup

**Purpose**: Project scaffolding — no feature logic yet. Agent-executed directly (boilerplate exception).

- [x] T001 Scaffold `web/` via `npx create-next-app@latest` (TypeScript, Tailwind, App Router, no
      `src/` directory — matches `plan.md`'s Project Structure). Agent runs this directly.
- [x] T002 [P] Confirm the existing agent runs locally in API-server mode (`adk api_server
      concierge_agent`, not `adk run`'s CLI mode) and responds on `http://localhost:8000` — this is
      the mode that actually exposes `/run_sse` for the frontend to call (quickstart.md step 1).
      Agent verifies directly.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared plumbing every user story's chat flow depends on.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [x] T003 Implement the browser-side SSE stream reader in `web/lib/stream-client.ts` — takes a
      `session_id` and message text, `POST`s to `/api/chat`, and yields text chunks as they arrive
      from the response's `ReadableStream` (contracts/chat-api.md).
- [x] T004 Implement `web/app/api/chat/route.ts` (local-dev version, calling `http://localhost:8000`
      directly, no rate limiting yet — that's US3/T012) — per contracts/chat-api.md: on a session's
      first call, `POST /apps/concierge_agent/users/{session_id}/sessions/{session_id}` to create
      the ADK session, then `POST /run_sse` with `streaming: true`, piping the SSE response straight
      back to the browser (research.md §2/§3).

**Checkpoint**: A `curl`/direct call to `/api/chat` returns a real streamed response from the local
agent. No UI yet — this phase proves the plumbing, US1 builds the UI on top of it.

---

## Phase 3: User Story 1 - Have a live conversation with the concierge (Priority: P1) 🎯 MVP

**Goal**: A visitor can open `/chat` and exchange streaming messages with the concierge agent.

**Independent Test**: Open the chat page, send a message, confirm the response streams in visibly
rather than appearing all at once (spec.md US1 Acceptance Scenarios).

### Implementation for User Story 1

- [x] T005 [US1] Create `web/components/MessageBubble.tsx` — renders one message (`role`, `text`,
      per data-model.md), styled distinctly for `"user"` vs `"assistant"`.
- [x] T006 [US1] Create `web/components/ChatWindow.tsx` — message list (auto-scrolling to the latest)
      + text input + send button; on send, calls `stream-client.ts` (T003) and appends streamed
      chunks to the current assistant message in React state as they arrive (FR-002).
- [x] T007 [US1] Create `web/app/chat/page.tsx` — the `/chat` route; generates a `session_id` (UUID)
      once per page load via `crypto.randomUUID()`, held in component state only (FR-009 — never
      written to `localStorage`/cookies), renders `ChatWindow`.
- [x] T008 [US1] Manually validate US1's acceptance scenarios from spec.md against the local dev
      server (`npm run dev` + local `adk api_server`) — quickstart.md steps 2-3.

**Checkpoint**: US1 fully functional locally — this is the demoable core.

---

## Phase 4: User Story 2 - Complete a real task end-to-end (Priority: P2)

**Goal**: A full booking/identity/check-in conversation completes entirely through the chat UI.

**Independent Test**: Run a full booking conversation (identity or new-guest resolution, room
selection, confirmation) start to finish in the UI, no manual reload (spec.md US2).

### Implementation for User Story 2

- [x] T009 [US2] Handle unusually long assistant responses in `ChatWindow.tsx` (e.g. a full room-type
      list) — confirm the message list scrolls correctly and the input stays reachable rather than
      being pushed off-screen (spec.md Edge Cases).
- [x] T010 [US2] Add a clear inline error state to `ChatWindow.tsx` for when `/api/chat` returns
      non-200 (network drop, agent unreachable) — FR-007, contracts/chat-api.md's 502 case.
- [x] T011 [US2] Manually validate US2's acceptance scenarios end-to-end through the local UI — a
      full booking including a confirmation-gated action (modify or cancel), confirming the
      confirmation prompt renders as a normal message and the guest's next reply is treated as the
      answer (FR-004) — quickstart.md step 3.

**Checkpoint**: US1 + US2 both functional locally — the whole guest lifecycle works through the browser.

---

## Phase 5: User Story 3 - Reach the chat with zero setup, publicly, safely (Priority: P3)

**Goal**: The chat is live at a public URL, with the two constitution-mandated guardrails in place.

**Independent Test**: From a device that's never touched this project, open the public URL and chat
with no setup (spec.md US3); rate limit and scheduled reset both verifiably work (FR-010, FR-011).

### Implementation for User Story 3

- [x] T012 [US3] Implement `web/lib/rate-limit.ts` — in-memory `Map<sessionId, {count, windowStart}>`,
      e.g. 20 messages / 5 minutes per session (research.md §5); wire it into
      `web/app/api/chat/route.ts` as the first check, returning `429` with the message from
      contracts/chat-api.md before any call to the agent.
- [x] T013 [US3] Responsive pass on `web/app/chat/page.tsx`/`ChatWindow.tsx` — confirm usable at
      ~375px width, no horizontal scroll, no overlapping elements (FR-008, SC-004).
- [x] T014 [US3] Implement `agent/scripts/reset_demo_data.py` as a **standalone script** — revised
      2026-09-09, no HTTP route needed: `adk deploy cloud_run` only accepts a plain agent directory
      (confirmed via `--help`, no custom-route hook), and a Cloud Run Job is the correct GCP
      primitive for a scheduled batch task anyway (research.md §6). Deletes `reservations` created
      after `DEMO_BASELINE_CUTOFF` (`reservation_products` cascades automatically — confirmed via the
      live FK's `ON DELETE CASCADE`); deletes `guests` with `legacy_guest_id IS NULL` created after
      that same cutoff; resets every `rooms` row's occupancy/housekeeping to defaults; deletes
      now-orphaned `booking_parties` rows.
- [x] T015 [US3] Deploy the agent (non-public): `adk deploy cloud_run --project=hotel-concierge-507914
      --region=<region> --service_name=concierge-agent agent/concierge_agent`, declining public
      access (quickstart.md step 6). Human runs this — needs interactive confirmation and their own
      deploy-time judgment call on region.
- [x] T016 [US3] Create the three secrets in Secret Manager (`ANTHROPIC_API_KEY`, `SUPABASE_DB_URL`,
      `VOYAGE_API_KEY`) and grant the agent service access (quickstart.md step 10 — no reset secret
      needed, revised 2026-09-09). Human runs this — secret values shouldn't pass through the
      agent's own context.
- [x] T017 [US3] Update `web/app/api/chat/route.ts` to call the deployed agent's Cloud Run URL
      (via an `AGENT_URL` env var) instead of `localhost:8000`, using Cloud Run's service-to-service
      identity token for auth (research.md §3) rather than a public call.
- [x] T018 [US3] Grant the frontend Cloud Run service's identity `roles/run.invoker` on the agent
      service (quickstart.md step 7) — human runs this, after both services exist.
- [x] T019 [US3] Deploy the frontend (public): `gcloud run deploy chat-ui --source=web
      --project=hotel-concierge-507914 --region=<region> --allow-unauthenticated --max-instances=1`
      (quickstart.md step 8 — `--max-instances=1` is load-bearing for T012's rate limiter, not
      optional). Human runs this.
- [ ] T020 [US3] Deploy `reset_demo_data.py` as its own Cloud Run Job, then create a Cloud Scheduler
      job that invokes that Job's execution directly via the Cloud Run Admin API (IAM-authenticated,
      no shared secret — quickstart.md step 10-11, revised 2026-09-09) on a fixed cadence (e.g.
      every 6 hours). Human runs this.
- [ ] T021 [US3] Post-deploy validation per quickstart.md steps 12-15: public URL reachable with zero
      setup from an unfamiliar device; the agent's own Cloud Run URL confirmed non-public
      (401/403 on direct hit); reset endpoint manually triggered once and confirmed to remove a
      demo-created reservation while leaving seeded ones untouched; full `specs/001-foundation`
      quickstart Stories 1-5 re-run through the public URL.
- [x] T022 [US3] Found live during T015/T016's own verification, not from a hand-written test:
      the first successful `adk deploy cloud_run` produced a container that crashes on the *first*
      real conversation (`/run_sse`) with `ImportError: LiteLLM support requires: pip install
      google-adk[extensions]` — confirmed via `gcloud logging read` against the live Cloud Run
      revision, not guessed. Root cause: `adk deploy cloud_run` looks for `requirements.txt`
      *inside the agent's own source folder* (`agent/concierge_agent/requirements.txt`) — confirmed
      directly in `cli_deploy.py` — not at `agent/requirements.txt`, this project's convention since
      T002. Since that file didn't exist where ADK expects it, the deployed container had *none* of
      our real dependencies (not just missing `[extensions]` — `psycopg`, `pgvector`, `voyageai`
      too), and only appeared to work because agent module loading is lazy: `/list-apps` never
      imports `tools.py`, only an actual `/run_sse` call does. Fixed by adding
      `agent/concierge_agent/requirements.txt` (same content as `agent/requirements.txt`, kept in
      sync manually — duplicated only because ADK's tool hardcodes this exact location, not a new
      convention). Requires a redeploy (same command as T015) to actually take effect.

**Checkpoint**: All three user stories independently functional — the chat is live, public, rate-limited, and self-resetting.

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)**: sequential, both block every story.
- **US1 (Phase 3)**: depends only on Foundational. The demoable MVP.
- **US2 (Phase 4)**: depends on US1 (reuses `ChatWindow.tsx`) — no new plumbing, mostly validation + two small robustness fixes.
- **US3 (Phase 5)**: depends on US1 (deploys what US1/US2 built) — independent of US2's specific fixes, could run in parallel with US2 if desired, but sequenced last here since public exposure without a working core conversation isn't useful.
- T015-T020 are human-run (real GCP account actions, interactive prompts, deploy-time judgment calls) — not code the agent places.

## Implementation Strategy

**MVP first**: Phase 1 → Phase 2 → Phase 3 (US1). Stop and validate locally — this alone is demoable.
**Then**: US2 (robustness + full-flow validation, still local) → US3 (guardrails + real public deploy).
Matches spec.md's own priority ordering exactly — nothing here reorders it for convenience.
