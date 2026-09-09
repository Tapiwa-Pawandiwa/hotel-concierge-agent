# Feature Specification: Guest Chat UI

**Feature Branch**: `010-guest-chat-ui`

**Created**: 2026-09-03

**Status**: Draft

**Input**: User description: "Guest chat UI — Milestone 3 in CLAUDE.md's MVP scope & order table (swapped ahead of F&B on 2026-08-12/2026-08-27 so there's something live and demoable sooner). A single guest-facing chat surface in the existing empty `web/` directory, one route, calling the already-running `concierge_agent`'s streaming endpoint to have a real conversation with the agent that specs/001-foundation just built end-to-end. No auth, no role selector — guest-facing only. Basic hosting so the thing is actually live on the internet, not just local; exact hosting configuration is an open decision for the planning phase. Out of scope: staff dashboard, F&B tools, rate limiting / per-visitor isolation."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Have a live conversation with the concierge (Priority: P1)

A visitor arrives at the chat page and exchanges messages with the hotel concierge assistant in real time — typing a question or request and watching the assistant's reply appear as it's produced, the way a modern chat product behaves, rather than staring at a blank screen until a full answer arrives at once.

**Why this priority**: This is the entire point of the feature. Without a working, responsive live conversation, there is nothing to demonstrate.

**Independent Test**: Open the chat page, send a simple message (e.g. a policy question), and confirm a response appears and streams in visibly rather than popping in all at once after a long pause.

**Acceptance Scenarios**:

1. **Given** a visitor has just opened the chat page, **When** they type a message and send it, **Then** the assistant's reply begins appearing within a few seconds and continues to fill in as it's generated.
2. **Given** a conversation already has several exchanged messages, **When** the visitor sends another message, **Then** the new exchange appends below the existing history without losing or reordering what came before.

---

### User Story 2 - Complete a real task end-to-end without leaving the page (Priority: P2)

A visitor uses the chat to actually accomplish something — verifying their identity, browsing rooms, creating or changing a booking, checking in — the same guest-lifecycle capabilities already built and validated in the underlying agent, entirely through this one page.

**Why this priority**: A chat window that can only make small talk isn't a demonstration of the system; the value is in showing the same booking/identity/check-in flows already proven to work, now reachable by a real visitor.

**Independent Test**: Run a full booking conversation (identity or new-guest resolution, room selection, confirmation) start to finish in the chat UI, with no manual page reload required at any point, including when the assistant asks for explicit confirmation before a change or cancellation.

**Acceptance Scenarios**:

1. **Given** a visitor is mid-conversation, **When** the assistant proposes an action that requires explicit confirmation (e.g. cancelling a booking), **Then** that confirmation request appears clearly as part of the conversation, and the visitor's next reply is understood as their confirmation or decline.
2. **Given** a visitor completes a booking, **When** they continue chatting afterward, **Then** the assistant retains the context of what was just booked without the visitor needing to repeat themselves.

---

### User Story 3 - Reach the chat with zero setup (Priority: P3)

A first-time visitor — someone reviewing this as a portfolio piece, not someone who has been onboarded — opens a public web address and is immediately able to start chatting, with no account creation, login, install step, or prior configuration.

**Why this priority**: The stated purpose of moving this milestone ahead of F&B is to have something live and demoable as soon as possible; a chat that only runs on the builder's own machine doesn't satisfy that.

**Independent Test**: From a device that has never touched this project before, open the public URL and send a message without performing any setup step first.

**Acceptance Scenarios**:

1. **Given** a visitor has never interacted with this system before, **When** they open the chat page's public URL, **Then** they can send a message immediately, with no signup, login, or role selection presented.
2. **Given** the page is loaded on a phone-sized browser window, **When** the visitor uses the chat, **Then** the layout remains usable — no overlapping text, no horizontal scrolling required to read a message.

---

### User Story 4 - See the agent's real mechanics at work (Priority: P4)

Someone evaluating this as a portfolio/engineering artifact — not a hotel guest — can switch into a
"System" view alongside the same conversation and see real, per-tool-call detail as it happens:
which tool fired, its risk tier, the idempotency key used for a write action, and the actual policy
citation a RAG lookup returned. This is what proves the system is a real agentic architecture with
real constraints, not a thin chat wrapper around a language model.

**Why this priority**: Doesn't change whether the guest-facing chat itself works — US1-US3 already
cover that entirely. This is an additive transparency layer for evaluators/recruiters, valuable for
the project's dual portfolio/learning purpose but strictly on top of an already-functioning chat.

**Independent Test**: Open `/chat?trace=true`, ask a policy question (triggers
`retrieve_hotel_policy`) and separately trigger a Tier 3 action (modify or cancel a booking).
Confirm the trace pane shows the real tool name, risk-tier badge, idempotency key (for the write
action), and the actual retrieved policy chunk + source file (for the policy question) — matching
what genuinely happened, not placeholder data.

**Acceptance Scenarios**:

1. **Given** a visitor is on `/chat?trace=true` and asks a policy question, **When** the agent calls `retrieve_hotel_policy`, **Then** the trace pane shows the exact source file and matched text the tool actually returned.
2. **Given** a visitor triggers a Tier 3 action, **When** the agent calls that tool, **Then** the trace pane shows a "T3" risk-tier badge and the real idempotency key generated for that call, and the guest-facing side shows a real Confirm/Cancel button pair instead of a plain-text yes/no prompt.
3. **Given** a visitor is on the plain `/chat` route (trace not requested), **When** they use the chat normally, **Then** no trace UI appears and the experience is identical to before this story existed.

---

### Edge Cases

- What happens when the visitor sends a new message while the assistant is still generating its response to the previous one?
- How does the interface behave if the underlying agent service is temporarily unreachable or returns an error mid-response?
- What happens if the visitor's connection drops partway through a streamed response — does the partial message stay visible, and can they retry?
- How is an unusually long assistant response (e.g. a full list of room options with descriptions) displayed without breaking the page layout or requiring excessive scrolling to reach the input box?
- What happens if the visitor submits an empty message, or pastes a very large block of text?
- What does the trace pane show when a tool call fails (`safe_tool`'s error path) — silently nothing, or a visible failure entry?
- What does the trace pane show when a guest declines a Tier 3 confirmation via the new button UI?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST let a visitor send a text message and receive the concierge agent's response within the same conversation, with no account creation or login required.
- **FR-002**: The system MUST display the assistant's response incrementally as it is generated, rather than only after the full response is complete.
- **FR-003**: The system MUST preserve the full message history within the visitor's current browser session so they can scroll back through everything already said.
- **FR-004**: When the assistant proposes an action that requires the guest's explicit confirmation (e.g. changing or cancelling a booking), the interface MUST present that confirmation request clearly as part of the conversation and treat the guest's next reply as their confirmation or decline.
- **FR-005**: The chat surface MUST be reachable at a single, publicly accessible web address that requires no prior setup by the visitor.
- **FR-006**: The system MUST NOT expose any interface element for staff-only actions — task routing, approval queues, or role selection — on this surface.
- **FR-007**: If the assistant is unavailable, or a message fails to send, the interface MUST show the visitor a clear indication of the failure rather than leaving the request hanging with no feedback.
- **FR-008**: The interface MUST remain usable on both desktop-sized and mobile-sized browser windows.
- **FR-009**: The system MUST NOT persist a visitor's conversation or identity beyond their current browser session — there is no login, so nothing ties a return visit back to a prior one.
- **FR-010**: The system MUST apply a basic request-rate cap (per visitor) to protect against runaway usage against the underlying, metered LLM API — reversed into scope 2026-09-03 once the feature's own goal (public, portfolio-linked hosting) made an uncapped public endpoint a real cost risk, not a hypothetical one. A visitor who exceeds the cap MUST see a clear message explaining they've sent too many messages too quickly, not a silent failure or generic error.
- **FR-011**: The system MUST periodically reset the public demo's data (reservations, guest profiles created by public visitors, room state) back to a known-good seed state, on a fixed schedule — the constitution's Principle X (Public Demo Guardrails) requires either this or full per-visitor data isolation before any public deployment; scheduled reset is the one chosen for this milestone (2026-09-03) as the smaller-scope option. Full per-visitor isolation remains explicitly deferred to `specs/004-resilience`.
- **FR-012** (added 2026-09-10, User Story 4): The system MUST provide a `/chat?trace=true` view that renders, for each tool call the agent makes during the conversation, the tool's name, its risk tier (T1/T2/T3), and — for Tier 2/3 write calls — the idempotency key used for that call.
- **FR-013** (added 2026-09-10, User Story 4): For any call to `retrieve_hotel_policy`, the trace view MUST show the actual source document, matched text, and a similarity/relevance score the tool returned — not a mocked or pre-staged example. `retrieve_hotel_policy` does not currently compute or return a score (confirmed live, `research.md` §8); this requires a small `agent/concierge_agent/tools.py` change, not just a frontend one.
- **FR-014** (added 2026-09-10, User Story 4): When the agent raises a Tier 3 confirmation request, the guest-facing chat — on both `/chat` and `/chat?trace=true` — MUST render a real Confirm/Cancel button pair instead of requiring the guest to type a raw "yes"/"no" reply. This supersedes FR-004's original "handled entirely as normal chat text" framing for the confirmation *control* itself; the underlying request/response protocol (already implemented) is unchanged.
- **FR-015** (added 2026-09-10, User Story 4): The plain `/chat` route (trace not requested) MUST behave exactly as it did before User Story 4 — no trace UI, no change to the guest-facing conversation itself, other than the FR-014 button change which applies to both routes.

### Key Entities

- **Conversation (session-scoped)**: The ordered sequence of messages exchanged between one visitor and the concierge agent during their current visit. Not tied to any visitor identity beyond the browser session, and not retrievable after that session ends.
- **Message**: A single turn within a conversation — either the visitor's submitted text, or the assistant's response (which may arrive incrementally), including any confirmation prompt the assistant raises before a guarded action.
- **Tool Call (trace-only, ephemeral, added 2026-09-10)**: One tool invocation within the current conversation — its name, risk tier, arguments (including idempotency key when present), and eventual result (or failure). Never persisted; exists only in the browser's in-memory trace for the current session, discarded when the tab closes — same lifetime as Conversation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time visitor can open the page and send their first message within 10 seconds of arriving, with no signup or login step in the way.
- **SC-002**: The assistant's response begins appearing within 3 seconds of the visitor sending a message, under normal conditions.
- **SC-003**: A visitor can complete a full booking conversation — identity or profile resolution, room selection, and confirmation — start to finish without the page requiring a manual reload.
- **SC-004**: The page renders usably on a mobile-width screen (approximately 375px wide) with no horizontal scrolling and no overlapping elements.
- **SC-005**: The chat surface is reachable from a public URL with zero local setup steps required by the visitor.
- **SC-006**: A visitor sending messages at a normal conversational pace never encounters the rate limit; only clearly abnormal, rapid-fire usage does.
- **SC-007**: The public demo's data returns to a known-good state at least once every 24 hours, bounding how long any cross-visitor data interference from one visitor's actions can persist.
- **SC-008** (added 2026-09-10, User Story 4): On `/chat?trace=true`, every tool call the agent makes during a conversation appears in the trace pane within the same few seconds the guest sees the agent's own reply — not delayed, not batched at the end.
- **SC-009** (added 2026-09-10, User Story 4): The Tier 3 confirmation control (Confirm/Cancel buttons) is visually distinguishable from a normal message bubble in 100% of manual test runs — a reviewer glancing at the transcript can tell exactly where a guarded action was confirmed.

## Assumptions

- No user accounts or authentication for this feature, per `CLAUDE.md`'s explicit scope decision — a returning guest simply starts a fresh conversation and verifies their identity conversationally (as the agent already does today), rather than logging in.
- Conversation history is scoped to the current browser session only; it is not expected to persist across a browser restart or be retrievable in a later visit.
- Confirmation-gated actions (e.g. modifying or cancelling a booking) are handled entirely within the normal chat flow — the guest's next typed reply serves as their confirmation or decline, consistent with how the underlying agent already handles this conversationally today.
- Hosting and deployment specifics (where this runs, what is containerized, how secrets are handled) are a planning-phase decision, not resolved by this specification — `CLAUDE.md` explicitly notes this remains "an open decision on specifics."
- Basic per-visitor rate limiting AND a scheduled public-demo data reset are both in scope for this feature (2026-09-03 — see `CLAUDE.md`), together satisfying the constitution's Principle X gate on public deployment. Full per-visitor *state isolation* and a fuller abuse-protection/guardrails system remain out of scope, deferred to `specs/004-resilience`. Between resets, a public visitor can in principle still see or act on another visitor's demo data (e.g. a guessed booking reference) — accepted as a bounded, small-window risk for a portfolio demo, not eliminated entirely.
- The staff dashboard, role selection, and any staff/ops/sales-agent-facing views are entirely out of scope; this specification covers only the guest-facing surface.
- F&B ordering and table-booking capabilities are out of scope for this feature — they belong to the next milestone and are not required for this chat surface to be considered complete.
- **Added 2026-09-10 (User Story 4)**: Risk tier (T1/T2/T3) is not present anywhere in the ADK SSE stream — it is a static classification that must be maintained as a small lookup table in the frontend (tool name → tier), kept in sync by hand with the constitution's own tiering and `agent.py`'s actual `require_confirmation=True` wiring. Not derived at runtime, and not automatically kept correct if a tool's tier changes without a matching frontend update.
- **Added 2026-09-10 (User Story 4)**: `functionResponse` events (a tool's actual return value) arrive on SSE events with `content.role === "user"`, not `"model"` — confirmed via a live raw-SSE probe against the running agent. `stream-client.ts`'s current role filter discards every tool result today; User Story 4 requires loosening that filter, not just adding new event types on top of it.
- **Added 2026-09-10 (User Story 4)**: Room-type image cards (guest-facing visual room browsing) and the "Staff — Coming soon" sidebar tab predate this story and are tracked separately in `CLAUDE.md`'s JANET UI shell checklist; only the trace panel, the risk/idempotency/citation display, and the Tier 3 confirmation button are in this story's scope.
