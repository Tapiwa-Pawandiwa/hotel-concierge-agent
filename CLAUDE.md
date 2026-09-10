# Hotel Concierge + Operations Platform

AI-orchestrated hotel concierge and ops platform built on Google ADK + Claude, for two purposes at once: a hospitality-tech portfolio piece, and a hands-on way to learn RAG/agentic system design. Both purposes shape how work happens here — see **Operating mode** below before touching any code.

## Source of truth

- `docs/implementation_proposal.html` — the master design doc. Architecture, ER diagrams, tool inventory, migration SQL, Pydantic tool signatures, adapter ABCs, phased plan, risk register. If this file and anything I (Claude) say in conversation disagree, the file wins — flag the conflict instead of silently picking one.
- `docs/mycheckpoint.html` — evidence-based audit of what's actually running today (bugs R1-R8, real schema, real tech stack versions). Update cadence is defined in **Checkpoint audits** below — it's refreshed from verified running state, not every session and not from a design conversation alone.

## Repo layout (current, real)

```
agent/concierge_agent/     agent.py, tools.py — the one agent that exists today
agent/scripts/ingest.py    RAG ingestion script
data/                      guests.csv, hotel_bookings.csv (Kaggle source), policies/*.md, prep_bookings.py
docs/                      the two docs above
web/                       empty — one Next.js/Tailwind app, two surfaces: guest chat (`/chat`, this scope) and staff dashboard (`/dashboard`, Phase 6, later)
```

No `requirements.txt`/`pyproject.toml`, no committed migrations, no `seed/` directory yet — these are Phase 0/17.2/17.3 deliverables from the proposal, not built yet.

## Operating mode: worked-example (Project 1)

This is the standing instruction for every session, not a one-time preference. Supersedes an
earlier, stricter version of this section: this project is explicitly Project 1 of a portfolio-building learning arc, and unlike
prior domains (React Native), there's no existing pattern vocabulary for agent code or RAG
scripts to build from — guided discovery without seeing working code first is the *slow* path
here, not the rigorous one. Later projects in the arc are expected to shift back toward
self-directed writing as that vocabulary builds. This mode is specific to this project's stage,
not a permanent retreat from "guide, don't generate."

- **Persona: coding tutor and senior engineer.** My job is to teach RAG, AI agent architectures, and system design implementation through this project. That still means precise, actionable communication — just via worked examples now, not hints.
- **I provide complete, runnable code for every task — not hints, not pseudocode.** Every non-trivial line or block carries an inline comment explaining what it does. Every code block is followed by an explanation of how it fits the larger system — which primitive, which risk tier, which existing pattern it repeats — so the goal is pattern recognition and reuse next time, not blind paste.
- **I do not use my own file-editing tools on this project's application code** (`agent.py`, `tools.py`, migration files, tests, etc.). Code is delivered in my response; you place it, run it, and debug it yourself in Cursor/Claude Code. Integration and debugging stay your work even when the code doesn't.
- **After you confirm a task runs, I ask at least one comprehension-check question about the code before we move to the next task** — not a quiz to pass, just enough to confirm the pattern landed, not just the paste.
- Exception unchanged: scaffolding with no learning value (boilerplate config, `.gitignore`, formatting) is fine for me to just do directly.
- Reviews (when something breaks) should be specific: cite the line, name the failure class, explain why — don't just say "try this instead" without the reasoning.

## MVP scope & order

Portfolio/job priority, not a calendar countdown — sessions happen whenever there's time between
other commitments, so progress is tracked purely by what's checked off in `tasks.md`, never by a
day count or a "should be further along by now" comparison. Scope decision (not a default —
chosen explicitly over "thin slice across all 3 agents"): get `concierge_agent` fully working
end-to-end on the real schema, tested, demoable. `ops_agent`/`sales_agent`, the staff dashboard,
resilience/kill-switch, and the event-feasibility engine stay fully documented (already are in
`implementation_proposal.html`) but are **not** part of this scope — they're the next milestone
after, not squeezed into this one. Per-visitor state isolation is still deliberately deferred past
this scope — get it solid locally and tested first. **Reversed**: basic rate limiting is
now in scope for Milestone 3 (Guest chat UI), not deferred — the original deferral assumed the
agent stayed local; once it's genuinely public (this milestone's own goal, portfolio-linked), an
unauthenticated endpoint calling a real, metered Claude API needs at least basic abuse protection
before going live, not after. Scoped as "basic" deliberately — a simple per-IP/per-session request
cap, not a full guardrails system (that fuller system, alongside per-visitor state isolation, is
still Phase 3/`specs/004-resilience`, later).

| Order | Milestone | Phase / scope |
|---|---|---|
| 1 | Migrations 001 (baseline) + 002 (guests/reservations split) + 003 (room inventory), `requirements.txt`, row-count parity verified at each step | Phase 0+1+2 merged — full |
| 2 | `verify_guest_identity`, `check_in_guest`, `check_out_guest` (done), `list_room_types` (added after the original scope — resolves a room-discovery gap found during schema review), `search_guest_profiles`/`create_guest_profile`/`update_guest_profile` (added after the original scope — resolves a guest-onboarding gap: neither `create_booking` nor `verify_guest_identity` had a path for a guest with no prior `guest_id`/`booking_reference` — walk-in or first-time online), `assign_room` (added after the original scope — separates physical room allocation from booking and check-in), `products`/`product_prices`/`reservation_products` (added after the original scope — fixes a live bug: breakfast pricing was reading from an uncommitted `hotel_settings` key-value row instead of a real price catalogue), audit metadata (added after the original scope: `created_at`/`updated_at` added where a real gap existed — `guests`, `reservations`, `rooms` — plus lower-priority consistency additions on `room_types`/`room_features`, via one shared DB trigger; full table-by-table reasoning in `data-model.md`), `create_booking`, `modify_booking`/`cancel_booking`, `request_human_handoff` on `concierge_agent`, wired to the real schema | Phase 0+1+2 merged — full |
| 3 | Guest chat UI — `web/` app, `/chat` route, single chat surface calling ADK's `/run_sse` endpoint, **plus a live system-trace panel alongside the chat** (added after the original scope — see why-note below). No auth, no role selector — this is the guest-facing side only | New — wasn't previously scoped (the original 9-phase breakdown only ever scoped the *staff* dashboard, Phase 6). Tracked as `specs/010-guest-chat-ui` in the Spec-kit workflow table below, Short gate depth — still needs its own `specify`/`plan`/`tasks` pass when you reach it, not an assumption that `specs/001-foundation` already covers it |
| 4 | `menu_items`, `place_order`, `book_restaurant_table` — `menu_items` gains a beverage-covering `category` field and `RESTAURANT_RESERVATIONS` gains `special_requests` (documented in `implementation_proposal.html` §4 why-note; restaurant stays one merged concept, not split into multiple outlets — staff link via existing `staff.department`, capacity as a `hotel_settings` field, no real seat-availability logic until this milestone). Skip full billing/payment capture (guest bills, Stripe) — fast-follow, not needed for the core loop to feel real | Phase 5 — slice |
| 5 | Hand-written test pass, run *through the UI* now that it exists (a handful of real scenarios, not the full 15-20 suite yet) — fix what breaks | Testing |
| 6 | README, a short demo script/recording, confirm a fresh checkout runs clean | Polish |

**Milestones 3 and 4 swapped** — originally UI came after the F&B slice; reordered
because the goal shifted to "something live and visible on GitHub/portfolio soon," and F&B tools
add backend capability without anything to demo them through, while the UI is what actually makes
the project visible. F&B is now a fast-follow after the first live push, not a blocker to it — the
work itself is unchanged, only the order. Basic hosting (Cloud Run per §6/§9 research, still an
open decision on specifics) belongs inside Milestone 3 now too, not a separate later step, since
"live on the website" needs both the UI and somewhere for it to run.

**JANET brand UI shell, added after the original Milestone 3 scope — boilerplate, built
incrementally, a piece at a time across sessions rather than landed in one push.** The existing
`/chat` implementation (session-scoped SSE streaming against `/run_sse`, Tier 3 confirmation
handling, per-session rate limiting) already works end-to-end — this is a visual pass on top of
working functionality, not new backend scope. Six discrete, independently-checkable pieces, in a
sensible build order:
1. Brand theme tokens — the full espresso/ivory/champagne palette and Cormorant Garamond/Inter/
   JetBrains Mono type system in the **JANET design system** section below, replacing the default
   Tailwind-starter palette.
2. Logo integration — the real JANET mark, referenced from one shared place so it's reused
   everywhere it appears (sidebar, chat avatar) instead of duplicated per component.
3. Sidebar shell — persistent nav rail (Chat active; New conversation / My bookings / Hotel
   information visually present but inert — those need an auth/routing story that doesn't exist
   yet, not this pass).
4. "Staff — Coming soon" tab, disabled — the visible signal that the platform is bigger than one
   chat box, without claiming Phase 6 work that hasn't happened yet.
5. Branded empty-state greeting and a restyled input bar, replacing the generic starter chat shell.
6. Message bubble restyle to the brand palette.

Deliberately out of this pass, flagged rather than silently dropped: the room-type image cards and
the polished Confirm/Cancel button card both need the agent's structured tool results reaching the
UI, which `stream-client.ts` doesn't do yet (it only yields plain text) — that's real additional
work, tied to the live system-trace panel below, not a boilerplate styling task. Ordered ahead of
Phase 6 (staff dashboard) for the same reason as the trace panel: this is the guest-facing side,
visible on a portfolio now, not staff tooling with no audience yet.

**Live system-trace panel, added after the original Milestone 3 scope.** A plain chat window
doesn't communicate that this is a real agentic system with real constraints, not a thin wrapper
around a model — that story only lands if the underlying mechanics are visible, not just the
conversation. `/chat` gets a second pane alongside the chat itself, rendering the actual tool-call
stream as it happens: which tool fired (`create_booking`, `verify_guest_identity`, ...), its risk
tier (T1/T2/T3, Constitution Principle III), the idempotency key generated for that call, and a
compact view of the real DB read/write result — not a mocked or staged view, the live trace of
what the agent actually did. Three specific things belong in it, each tied to a real project
primitive rather than invented for the demo: the RAG citation `retrieve_hotel_policy` actually
retrieved (source chunk + similarity score, proving grounded retrieval against `policy_chunks`,
not the model's own training knowledge); a proper confirmation card for Tier 3 actions
(`modify_booking`/`cancel_booking`) rendering ADK's `require_confirmation=True` HITL gate as a
real UI control instead of the raw `[HITL confirm]` CLI prompt (T030 already flagged this as
unacceptable guest-facing behavior); and the idempotency key itself, visible per write call, as
concrete evidence of the idempotency contract every Tier 2/3 tool already carries. Scoped as part
of `specs/010-guest-chat-ui` (same route, second pane, not a new surface) — not a staff-dashboard
feature and not gated behind Phase 6, since it reads the same tool-call stream the chat itself is
already driving. Surfaced via the `/chat?trace=true` route from the JANET design system's
Navigation architecture below, not a separate boolean toggle state — same segmented-control
component that later grows a Staff arm, not a one-off switch.

Milestones 1–2 were originally three separate rows (Phase 0 / Phase 1 / Phase 2), merged
mid-session because Phase 2's tool signatures (`verify_guest_identity`,
`check_in_guest`, `create_booking`, ...) depend on both Phase 0's `reservations` table and Phase
1's room inventory existing — building them separately would land intermediate states with
nothing demonstrable. See `specs/001-foundation/spec.md`'s `## Clarifications` section for the
full rationale.

**Two UI surfaces, two different times — don't conflate them.** The guest chat widget
(Milestone 3 above, chat pane + system-trace pane) and the staff dashboard (role selector, task
views, approval queue) are the same Next.js/Tailwind app decided in Section 15 of the proposal,
but different routes built at very different points: the chat widget is guest-facing and belongs
in *this* scope, since it's what actually gets shown on a portfolio site. The trace panel is part
of that same guest-facing route, not a preview of the staff dashboard — it renders the guest's own
conversation's tool calls back to whoever's watching the demo, it doesn't expose staff-only task
routing or approval queues. The staff dashboard itself can't be built yet regardless — it's the UI
for `ops_agent`/`sales_agent`, which don't exist yet (Phase 6, after this scope, per the table in
the Spec-kit workflow section below). If a task ever asks for "the dashboard" before Phase 6,
that's a scope-order violation — flag it rather than building it early.

This is the order things get built in, not a schedule for when — no day/date targets, no "behind
schedule" framing. The Session start protocol below reports progress against `tasks.md` only.
**Versioning over dates, going forward**: when a milestone boundary is actually reached, mark it
with a git tag (e.g. `v0.1-foundation-complete`) instead of a date in prose — a tag is a durable,
verifiable record pulled from the repo itself, where a date is a calendar entry that goes stale
the moment a session gets skipped and, worse, has already once caused real confusion for another
Claude instance reading these docs without shared context on "what day is it." Any future
"reversed"/"revisited" note in this file should cite the tag or milestone it happened relative to,
never a calendar date.

**Observability, evals/tests, and voice formatting gate multi-agent work — reordered ahead of
Phase 6.** Before `ops_agent`/`sales_agent` (multi-agent split, Phase 6 in the Spec-kit workflow
table below) gets started, three things land first, in this order:
1. **Observability** — the live system-trace panel (already scoped under Milestone 3 above,
   `specs/010-guest-chat-ui`) actually gets built, not just documented.
2. **Evals and tests** — two distinct things, both currently thin or undocumented, both pulled
   forward: automated unit tests against `agent/concierge_agent/tools.py` (pytest, no LLM in the
   loop — currently not scoped anywhere, `requirements.txt` has no test tooling at all yet), and
   the real eval suite (previously Phase 8 / `specs/009-eval-roi`, positioned *after* Phase 6 in
   the original proposal's phase numbering — pulled ahead of it here). Milestone 5's "hand-written
   test pass" above is a stopgap, not a substitute for either.
3. **Voice & response formatting** — the fix already specified in JANET voice & response
   formatting below (no markdown leaking as literal characters, no emoji, concise concierge tone).

Reasoning: adding a second agent multiplies the surface area that has to be trusted, and there's
no reliable way to tell whether a multi-agent handoff is working if there's not yet a way to
measure whether the single-agent system is working. Instrument and measure before scaling
complexity, not after. The proposal's original phase numbers stay as a reference index into
`implementation_proposal.html`'s content — not a build-order commitment — same principle already
established for the Milestone 3/4 swap above.

## JANET design system

Formalizes the guest-facing visual language: **quiet luxury, not generic SaaS luxury** — warm
ivory surfaces, espresso/near-black navigation, restrained bronze accents, editorial serif
typography, and very limited semantic colour. The reference point is an AMAN/Four Seasons digital
concierge, not a conventional chatbot. This is the concrete spec the "JANET brand UI shell"
checklist above builds against — reference it directly from Cursor while placing each piece,
rather than re-deriving colours/type per session.

**Key design principle, carried through the whole application:** JANET should not look like an AI
chatbot that happens to serve a hotel — it should look like the hotel's digital concierge, with
the AI infrastructure progressively revealed only once the guest enters System view. The guest UI
communicates luxury hospitality; the System UI communicates the actual agent engineering (HITL,
RAG, risk-tiering, observability) — that split is what makes the Guest/System toggle a real
portfolio differentiator, not a debug panel bolted on.

### Core colour system

| Token | Hex | Primary use |
|---|---|---|
| `janet-ink` | `#17130F` | Primary text, CTA buttons, icons |
| `espresso-950` | `#211A14` | Main sidebar / dark navigation |
| `espresso-900` | `#2C231B` | Sidebar hover, elevated dark surfaces |
| `walnut-800` | `#49392C` | Secondary luxury brown |
| `walnut-700` | `#625043` | Secondary text on dark backgrounds |
| `bronze-600` | `#8A6A45` | Brand accent, selected details |
| `champagne-500` | `#B69A72` | Logo accents, fine borders, premium details |
| `sand-300` | `#D8C8B3` | Borders / dividers / subtle controls |
| `sand-200` | `#E5D9C9` | Hover backgrounds |
| `linen-100` | `#F0E8DD` | Cards / assistant messages |
| `ivory-50` | `#F8F4ED` | Main application background |
| `cream-25` | `#FCFAF6` | Elevated cards / chat canvas |
| `white` | `#FFFFFF` | Select elevated surfaces |

`#F8F4ED` replaces ordinary SaaS grey as JANET's neutral canvas — not `#F5F5F5`, not blue-grey,
anywhere in the guest experience; even the neutrals stay warm. Primary brand combination:
**espresso `#211A14` + ivory `#F8F4ED` + champagne `#B69A72`**, with `#17130F` carrying the
high-contrast typography.

### Typography — two families, deliberately

The contrast between an editorial serif and a highly legible sans-serif is a major part of the
luxury effect, not incidental styling.

**Display/brand — Cormorant Garamond.** Wordmark, page titles, welcome statements ("Good
afternoon / How may I help you today?"), room names, major monetary values, editorial headings.

| Style | Size | Weight | Line height |
|---|---|---|---|
| Display XL | 48px | 500 | 52px |
| Display L | 40px | 500 | 44px |
| H1 | 36px | 500 | 42px |
| H2 | 28px | 500 | 34px |
| H3 | 22px | 600 | 28px |
| Card title | 18px | 600 | 24px |

**Interface/functional — Inter.** Everything requiring rapid scanning: chat messages, buttons,
navigation, form controls, dates, prices in tables, dashboard metrics, system traces, badges, tool
information.

| Style | Size | Weight | Line height |
|---|---|---|---|
| Body L | 16px | 400 | 26px |
| Body | 14px | 400 | 22px |
| Body S | 13px | 400 | 19px |
| Label | 12px | 500 | 16px |
| Button | 14px | 500 | 20px |
| Caption | 11px | 500 | 16px |

Avoid excessive bold — hierarchy comes from typography, whitespace, and contrast, not from making
everything 600–700 weight.

### Semantic colours — desaturated, not developer-dashboard bright

The system-trace panel needs colours for risk/system states, but bright dashboard colours would
clash with the rest of JANET, so every semantic colour here is muted.

| State | Background | Foreground | Usage |
|---|---|---|---|
| Success | `#E4ECE5` | `#35553B` | Confirmed booking |
| Warning | `#F3E7D4` | `#825C2D` | Pending / attention |
| Error | `#F1DEDA` | `#8B4038` | Failure / rate limit |
| Info | `#E3E8E8` | `#41595A` | Informational |
| Neutral | `#ECE7DF` | `#625B53` | Generic status |

**Risk tiers** (Constitution's T1/T2/T3, made visually distinctive rather than left as plain
badges):

- **T1 — Routine**: `#55715B` text on `#E4ECE5` — e.g. `list_room_types`
- **T2 — Controlled**: `#916B32` text on `#F3E7D4` — e.g. `create_quote`
- **T3 — Confirmation required**: `#91473D` text on `#F1DEDA` — e.g. `modify_booking`,
  `cancel_booking`

T3 should read as "human decision required," not as an alarming bright-red error state.

### Surface hierarchy

| Level | Hex | Use |
|---|---|---|
| 0 — Application canvas | `#F8F4ED` | Global background |
| 1 — Primary content | `#FCFAF6` | Chat canvas, dashboard content |
| 2 — Cards | `#FFFFFF` | Room cards, reservation cards, confirmation cards |
| 3 — Soft contextual surface | `#F0E8DD` | Assistant messages, secondary cards |
| 4 — Selected / hover | `#E5D9C9` | Navigation selection, subtle hover states |
| Dark surface | `#211A14` | Navigation / sidebar |
| Dark elevated | `#2C231B` | — |

### Borders & shadows

Very subtle borders, not conventional heavy SaaS shadows:

```css
--border-subtle: #E4D9CB;
--border-default: #D8C8B3;
--border-strong: #BBA78E;
```

Most cards: `border: 1px solid #E4D9CB;`

```css
/* standard elevation */
box-shadow:
  0 1px 2px rgba(33, 26, 20, 0.04),
  0 8px 24px rgba(33, 26, 20, 0.05);

/* modals only */
box-shadow: 0 20px 60px rgba(33, 26, 20, 0.14);
```

### Border-radius system

Slightly sharper than a generic mockup, deliberately:

```
XS      4px
Small   6px
Medium  8px
Large   12px   -- most cards
XL      16px   -- chat bubbles, major containers
Pill    999px  -- status badges and compact controls only
```

### Spacing system

4px base unit: `4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96px` (micro → xs → sm → md → lg → xl → 2xl
→ 3xl → 4xl). Guest interface uses generous spacing specifically: page horizontal padding
40–48px, major section spacing 48px, card padding 20–24px, chat message spacing 16px, sidebar
item spacing 8px, input internal padding 16px.

### Buttons

- **Primary** — espresso `#211A14` background, `#FCFAF6` text, hover `#34291F`. E.g. "Confirm
  booking."
- **Secondary** — `#F0E8DD` background, `#211A14` text, `#D8C8B3` border. E.g. "View details."
- **Tertiary** — transparent background, `#49392C` text. E.g. "None of these are me."
- **Destructive** — `#8B4038` background, `#FFFFFF` text — not bright red, and only surfaced at
  the actual final destructive action, not earlier in the flow.

### Guest chat message styling

**Reversed 2026-09-10** (live UI feedback, not a design-time decision): the original
"intentionally subtle" distinction — both bubbles near-identical warm neutrals — tested poorly
once actually built; not enough contrast to tell guest and JANET messages apart at a glance. Guest
messages now use the walnut brown token as a dark, high-contrast bubble instead of a second light
neutral. Still not the classic blue-user/grey-assistant convention — walnut is one of the app's
own brand tokens, not an arbitrary chat-app blue.

- **JANET message**: `#F0E8DD` background, `#211A14` text, 16px radius.
- **Guest message**: `#49392C` (walnut) background, `#FCFAF6` (cream) text, 16px radius.
- **JANET avatar**: the logo symbol inside a `#211A14` circle.

### Tier-3 confirmation card

Arguably the most carefully designed component in the system — it's the one place the HITL
architecture becomes visible to a guest, not just documented in the Constitution.

```
Background     #FCFAF6
Border         #B69A72
Top accent     #8A6A45
Heading        Cormorant Garamond, 22px
Body           Inter, 14px
Primary CTA    #211A14
```

A small **"T3 · Confirmation required"** badge sits above the heading — that's what visually
connects the guest-facing interaction to the risk-tier architecture underneath it, the same
connection the system-trace panel makes on the other side of the toggle.

### System trace typography

The trace panel is technical transparency, not part of the hospitality conversation — its
typography shifts deliberately. Inter for almost everything; **JetBrains Mono, 12–13px** only for
tool/call identifiers and raw data: tool names (`create_booking`, `verify_guest_identity`),
idempotency keys, JSON, request IDs, tool parameters, raw payloads.

Full type system across the app: **Cormorant Garamond** (luxury/editorial) → **Inter** (interface)
→ **JetBrains Mono** (agent/system internals) — the typography itself differentiates hotel
experience, application interface, and AI infrastructure as you move through the three surfaces.

### Staff dashboard — same system, not a separate one

No separate design system for Phase 6 — the staff dashboard stays unmistakably JANET, just more
information-dense:

```
                 JANET DESIGN SYSTEM
                        |
          +-------------+-------------+
          |             |             |
       GUEST          STAFF        SYSTEM
     Hospitality    Operations    Observability
          |             |             |
      Editorial      Dense UI       Technical
      imagery        tables         traces
      serif H1       metrics        monospace
```

Guest = hospitality-first (large serif headings, photography, whitespace). Staff =
operations-first (smaller typography, tighter spacing, tables, filters, KPIs). System =
engineering-first (monospace identifiers, trace trees, JSON inspection). All three read off the
same token set above — a stronger design concept than three pages that happen to share a brown
palette.

### Navigation architecture

Built as a segmented control, not a binary toggle, from the start — **Guest | Staff | System** is
the eventual shape, but only **Guest | System** is exposed during Milestone 3:

- Guest: `/chat`
- System: `/chat?trace=true`
- Staff (Phase 6, later): `/staff`

Architecting it as a segmented control now, even with one arm disabled, avoids redesigning
navigation when Phase 6 actually lands — same reasoning as the "Staff — Coming soon" tab already
in the MVP scope note above.

### Design tokens (CSS)

```css
:root {
  /* Brand */
  --janet-ink: #17130F;
  --janet-espresso: #211A14;
  --janet-espresso-elevated: #2C231B;
  --janet-walnut: #49392C;
  --janet-bronze: #8A6A45;
  --janet-champagne: #B69A72;

  /* Neutral */
  --janet-sand: #D8C8B3;
  --janet-sand-soft: #E5D9C9;
  --janet-linen: #F0E8DD;
  --janet-ivory: #F8F4ED;
  --janet-cream: #FCFAF6;
  --janet-white: #FFFFFF;

  /* Text */
  --text-primary: #17130F;
  --text-secondary: #625B53;
  --text-muted: #8A8178;
  --text-inverse: #FCFAF6;

  /* Borders */
  --border-subtle: #E4D9CB;
  --border-default: #D8C8B3;
  --border-strong: #BBA78E;

  /* Semantic */
  --success-bg: #E4ECE5;
  --success-text: #35553B;
  --warning-bg: #F3E7D4;
  --warning-text: #825C2D;
  --danger-bg: #F1DEDA;
  --danger-text: #8B4038;
  --info-bg: #E3E8E8;
  --info-text: #41595A;

  /* Typography */
  --font-display: "Cormorant Garamond", Georgia, serif;
  --font-ui: "Inter", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", monospace;

  /* Radius */
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --radius-pill: 999px;
}
```

## JANET voice & response formatting

Live-tested finding, not a design-time preference: `concierge_agent`'s replies currently read like
a generic AI assistant, not a hotel concierge, and worse, leak literal markdown syntax into the
chat — e.g. `**Ane**` shows up as literal asterisks, because `MessageBubble` renders plain text
(`whitespace-pre-wrap`, no markdown parser) and nothing in `agent.py`'s instruction string tells
the model to stop producing markdown in the first place. This is a fix to that instruction string,
not to the UI — the bubble rendering is already correct, the model's output needs to change to
match it. Belongs with `concierge_agent`'s existing instruction text (`specs/001-foundation`
scope), a separate track of work from the `web/` reskin above even though both land in the same
chat window.

**Rules, concrete enough to paste into the instruction string directly:**

1. **No markdown syntax** — no `**bold**`, no bullet or numbered lists, no headers. State things
   plainly in sentences; there is no renderer on the other end to turn `**` into bold, so it must
   never be produced.
2. **No emoji.** A luxury concierge doesn't communicate in emoji — this is the same "quiet
   luxury, not generic SaaS" restraint the design system already applies to colour, extended to
   voice.
3. **Em dashes used sparingly** — at most one per message, only where it earns its place. Strings
   of em-dash-joined clauses read as AI-generated, not as a person speaking.
4. **Short by default.** Routine turns (greetings, confirmations, simple answers) get 1-3
   sentences. Reserve length for genuinely multi-part information (e.g. presenting several room
   options), and even then, stay tight rather than exhaustive — the guest should be able to
   scan the reply, not have to read it closely.
5. **No filler openers.** Cut "I'm here to help you with anything you need," "Of course!," "Great
   question!" — answer, or ask the next question, directly.
6. **Warm, not chatty.** The register is an experienced concierge speaking in person, not a
   customer-support bot performing enthusiasm.

**Concrete before/after**, using the actual greeting that surfaced this:

> Before: "Hello! 👋 Welcome to Janet Hotel! My name is **Ane**, and I'm your concierge assistant.
> I'm here to help you with anything you need — whether that's booking a room, answering questions
> about our hotel policies, checking in or out, or just making your stay more comfortable. What
> can I help you with today?"
>
> After: "Good afternoon, and welcome to Janet. I'm Ane, your concierge. How may I help you
> today?"

One nuance worth carrying into the actual instruction rewrite: the chat UI's own empty state
already shows "Good afternoon / How may I help you today?" as a static headline (JANET design
system, Typography) before the guest sends anything — so the agent's first real reply doesn't need
to re-ask that question, it can go straight to being useful once the guest states what they want.

## Session start protocol

Every new session in this repo — before responding to anything else, including a greeting — do this first:

1. Find the active phase: check `specs/` in phase order (`001-foundation`, `004-resilience`, ...). The active phase is the lowest-numbered one whose `tasks.md` still has an unchecked `- [ ]` box. If a phase is fully checked off (`- [x]` throughout), move to the next number.
2. If the next phase in order has no `specs/00X-*/tasks.md` yet, that's the active state — say so, and name which spec-kit step is missing (`specify`, `clarify`, `plan`, `checklist`, or `tasks`), per the gate depth for that phase below.
3. If a `tasks.md` exists with an unchecked task, report: which phase, how many tasks are done vs. remaining, and the next unchecked, unblocked task by ID and name. No day count, no pace comparison — order and progress only.
4. Go straight into the Session loop below from there. Don't wait to be asked "where were we" — that question shouldn't need asking.

If no `specs/` directory exists at all yet, say that plainly and point back to the Development Workflow Gates: constitution first, then Phase 0's `specify`.

## Session loop

1. Confirmed by the Session start protocol above — the active, unblocked task.
2. I give the full worked example, in the Guidance format below — labeled, code included, no reasoning mixed into the instruction itself.
3. You place the code into the file yourself in Cursor/Claude Code, run it, and debug environment/execution issues as they come up. I don't touch your files.
4. I ask a quick comprehension-check question or two once it runs — confirming the pattern landed, not re-litigating the code.
5. Check the task off, move to the next. Don't batch multiple tasks before this — do it after each one, or gaps compound.

## Guidance format

Every task briefing (Session loop step 2) MUST hit all five of these, in order, clearly labeled — never prose that mixes instruction, code, and reasoning together in one block:

1. **INSTRUCTION.** One or two lines: what file, what it does. Nothing else in this line — no reasoning, no code.
2. **CODE.** The complete, runnable code for the task, inline comments on every non-trivial line/block explaining what it does.
3. **WHY THIS SHAPE.** How this code fits the larger system — which primitive (Who/Request/Financial/Signal), which risk tier, which existing pattern elsewhere in the codebase it repeats. This is the part that makes it reusable next time, not just working this time.
4. **DONE WHEN.** Acceptance criteria, quoted from `tasks.md` if it exists, not paraphrased into something softer.
5. **Hand-back.** Direct instruction to place it, run it, and report back — plus what I'll do with that report ("tell me the exact error if it doesn't run first try, don't just say 'it broke'").

If a briefing is missing any of these five, it isn't done — expand it rather than leaving something implicit.

The point of this loop is that something gets checked off every session, not that every session finishes a whole phase.

## Checkpoint audits (mycheckpoint.html)

`docs/mycheckpoint.html` is an audit, not a plan — it reflects only verified, running state, so it's not touched every session and never updated from a design conversation alone (that's what `implementation_proposal.html` is for).

Trigger: whenever a `tasks.md` phase Checkpoint is reached (the "Checkpoint: ... functional" line that follows a user story's tasks) and its acceptance scenarios have actually passed, re-read the live repo — migrations actually applied, current `agent/concierge_agent/tools.py`/`agent.py`, `agent/requirements.txt` — and update `mycheckpoint.html`'s schema/bug-list/dependency tables to match what's really there. If one of R1-R8 has been fixed, mark it fixed. If the schema or a dependency version has moved since the last audit, update it. Source the update from the actual files, never from what `tasks.md` or a conversation says *should* be true by now.

Multiple small changes between Checkpoints don't each trigger a refresh — batching to the Checkpoint boundary keeps the audit meaningful (a real "here's what's demoable right now" snapshot) instead of a diff-by-diff log.

## Spec-kit workflow

This project uses [spec-kit](https://github.com/github/spec-kit) for the spec → plan → tasks → implement pipeline, adapted for the worked-example operating mode above: `/speckit.implement` is **not** run as an autonomous batch step here — I never use my own tools to write into the repo. Treat `tasks.md` as the session-loop backlog instead: I hand over each task as a full worked example, you place and run it yourself, one task at a time, per the loop above.

**One-time setup** (run in your own terminal — this sandbox's network is locked to an allowlist and can't reach PyPI/GitHub to install it for you):

```bash
uv tool install specify-cli
cd /Users/tapiwa/Desktop/Projects/hotel-concierge-agent
specify init . --integration claude --script sh
```

Then run `/speckit.constitution` once, pasting the principles block below as the argument.

**Gate depth per phase** — the full 9-gate path (`constitution → specify → clarify → plan → checklist → tasks → analyze → implement → converge`) is overkill for a solo build; using it everywhere would cost more velocity than it buys rigor. Full gates only where ambiguity is genuinely high; short path (`specify → plan → tasks → [guided implement] → converge`) everywhere else.

| Phase (proposal §9) | `specs/` directory | Gate depth |
|---|---|---|
| 0+1+2 — Foundation, room inventory & guest lifecycle (merged — see `specs/001-foundation/spec.md` Clarifications) | `specs/001-foundation` | **Full** — blocking gate, wrong here is expensive everywhere downstream |
| New — Guest chat UI (`web/` app, `/chat` route; not a proposal phase — added after the original scope, see MVP scope & order Milestone 3) | `specs/010-guest-chat-ui` | Short — no money math, no novel trust-boundary pattern, just one route wired to an existing ADK endpoint |
| 3 — Resilience & kill switch | `specs/004-resilience` | Short + `/speckit.clarify` (novel pattern, worth one clarify pass) |
| 4 — Staff ops & continuity | `specs/005-staff-ops` | Short |
| 5 — Ordering, F&B & billing | `specs/006-fnb-billing` | Short + `/speckit.checklist` (money math, worth the extra check) |
| 6 — Multi-agent split & dashboard | `specs/007-agent-split-dashboard` | Short |
| 7 — Business events, experiences, pricing | `specs/008-business-events` | **Full** — newest, most failure-prone path (proposal §9 Phase 8 eval notes) |
| 8 — Cost tracking, eval, ROI | `specs/009-eval-roi` | Short |
| 9 — Voice | not yet scoped | deferred |

**Phase 8 (eval/ROI) now precedes Phase 6 (multi-agent split & dashboard) in actual build order**,
despite the table's numbering — see the "Observability, evals/tests, and voice formatting gate
multi-agent work" note in MVP scope & order above. The numbers below are a reference index into
`implementation_proposal.html`'s phase content, not a commitment to build them in that order.

`/speckit.specify` and `/speckit.plan` for each phase should draw directly on `implementation_proposal.html` — the ER diagrams, tool signatures, and migration SQL in §4/§11/§17 are already-decided requirements, not things for spec-kit to (re)discover from scratch. Feed them in as context rather than starting each phase from a blank feature description.

## Constitution (paste into `/speckit.constitution`)

```
This hotel concierge platform serves two purposes: a portfolio-grade system
design and a hands-on learning project — Project 1 of a learning arc, run in
worked-example mode: the agent provides complete, commented, runnable code
for every task rather than hints, explains how each piece fits the larger
system, and never edits the project's files directly — the human places,
runs, and debugs the code themselves. Later projects in the arc shift back
toward self-directed writing as pattern vocabulary builds.

Four primitives: every entity is a Who (Actor: Guest/StaffMember, or
Resource: Room/EventSpace/EquipmentInventoryItem/MenuItem), a Request, a
Financial charge, or a Signal. New features extend these shapes, they don't
invent new ones.

Risk tiering is mandatory: every tool is Tier 1 (read-only, autonomous),
Tier 2 (write, logged and reversible), or Tier 3 (money, dates, or a real
booking — always human-confirmed before it executes). No exceptions.

Agent topology is fixed at three: concierge_agent (guest-facing),
ops_agent (staff task routing/monitoring), sales_agent (event feasibility,
quotes, approval). New domains become tools inside one of these three, not
new agents — unless they introduce a genuinely new reasoning mode and a
genuinely new trust boundary, the way sales_agent did.

SQL only: single Postgres + pgvector. No separate document or vector
database.

Every mocked external system (PMS/POS/ERP/WFM, sensors, locks) implements
one shared adapter pattern and lives inside the app's own trust boundary.
Only Anthropic Claude, Voyage AI, and Stripe (test mode) are real third
parties.

Every tool returns a {status, data, error} shape and never raises. Every
Tier 2/3 write tool takes an idempotency key.

Billing is append-only. A correction is a new offsetting row, never an
UPDATE to a posted charge.

No speculative features: nothing is built ahead of the phase that needs
it. No structured loyalty system, no labor-law compliance engine, no
guest_preferences table beyond what's specified — these were explicit
scope decisions, not oversights.
```
