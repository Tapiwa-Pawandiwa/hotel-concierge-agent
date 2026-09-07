# Implementation Plan: Guest Chat UI

**Branch**: `010-guest-chat-ui` | **Date**: 2026-09-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-guest-chat-ui/spec.md`

## Summary

A single guest-facing `/chat` route in the existing empty `web/` directory (Next.js/React + Tailwind,
per `docs/implementation_proposal.html` §15), streaming a live conversation against the already-built
and already-validated `concierge_agent` via ADK's SSE endpoint. Optimized for the shortest real path
to a genuinely public, hosted URL. Two constitution-mandated guardrails (Principle X) are in scope
alongside the UI itself: a basic per-visitor rate cap, and a scheduled reset of the public demo's
data — the smaller-scope alternative to full per-visitor isolation, chosen explicitly 2026-09-03 to
keep this milestone close to a pure UI+hosting task rather than reopening the whole `tools.py` layer.

## Technical Context

**Language/Version**: TypeScript (Next.js, frontend) + existing Python 3.14 (`agent/concierge_agent`, backend — unchanged, no language/version change to the already-shipped agent)

**Primary Dependencies**: Next.js + Tailwind CSS (frontend, per §15's resolved decision); `google-adk`'s built-in SSE server (backend, already present — `adk api_server` / equivalent, exposing `/run_sse` for the existing `root_agent`); a rate-limiting mechanism and a scheduled-reset mechanism, both resolved in `research.md`

**Storage**: Existing Supabase Postgres (unchanged schema for chat itself — conversation state is session-scoped only, per spec.md, no new table). The scheduled-reset mechanism needs a way to distinguish "seed/baseline" rows from "created during a public demo session" rows — resolved in `research.md`

**Testing**: Manual `quickstart.md` validation, consistent with `specs/001-foundation`'s approach (no automated suite yet, per `CLAUDE.md`)

**Target Platform**: Google Cloud Run (per `CLAUDE.md`'s §6/§9 note — resolved here, not left open)

**Project Type**: Web application — frontend (`web/`, new) + backend (`agent/concierge_agent`, already exists, deployed not rebuilt)

**Performance Goals**: SC-002 — assistant's streamed response begins appearing within 3 seconds of send, under normal conditions

**Constraints**: Principle X(a) — bounded LLM API cost via rate limiting; Principle X(b) — bounded cross-visitor data interference via scheduled reset (not eliminated, bounded to a 24h window per SC-007); Principle X(c) — trivially satisfied, no Stripe/payment code path exists in this codebase yet

**Scale/Scope**: Portfolio-demo scale — a handful to low dozens of concurrent visitors, not production traffic. One route (`/chat`), no additional pages this milestone.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Worked-Example Learning | **PASS** | All new `web/` application code and any `tools.py`/deployment-config changes still hand-delivered as worked examples per the Session loop — this phase's larger surface area (a full Next.js app, Dockerfile, Cloud Run config) doesn't change the rule, just the volume of tasks it applies to. |
| II. Four Primitives | **N/A** | No new domain entity. Session/demo-reset bookkeeping is operational scoping, same category as `idempotency_keys` — not a Who/Request/Financial/Signal. |
| III. Risk Tiering | **PASS** | No new tools; UI calls existing, already-tiered tools unchanged via the agent's SSE endpoint. |
| IV. Fixed Agent Topology | **PASS** | UI calls the existing `concierge_agent` only — no new agent, no new reasoning mode. |
| V. SQL-Only Data Layer | **PASS (design constraint carried into research)** | Rate limiting will default to an in-memory or Postgres-backed counter, not a new Redis/cache store, to avoid introducing a second datastore and stay fastest-path. Confirmed in `research.md`. |
| VI. Mocked-Adapter Boundary | **N/A** | Hosting is real infrastructure, not a mocked external system. |
| VII. Tool Contract & Idempotency | **PASS** | Unchanged — existing tools already compliant (verified live, `specs/001-foundation` T036). |
| VIII. Append-Only Billing | **N/A** | No billing surface touched by this feature. |
| IX. No Speculative Features | **PASS, actively enforced** | Scheduled reset chosen specifically to avoid over-building (full per-visitor isolation) ahead of the phase that actually needs it (`specs/004-resilience`). |
| X. Public Demo Guardrails | **PASS, this phase's core gate** | (a) rate limiting — FR-010, in scope. (b) scheduled reset — FR-011, in scope, chosen over full isolation 2026-09-03 (see spec.md Assumptions). (c) Stripe test-mode — trivially true, no payment code path exists. All three resolved before this plan proceeds, per Governance's requirement that a violation be documented and justified, not silently absorbed — here, no violation remains once (a)/(b)/(c) ship. |

### Post-design re-check (after Phase 1)

The §3 proxy-architecture decision in `research.md` (browser never calls the agent directly)
strengthens Principle X(a) beyond the original plan: the agent's own Cloud Run service is deployed
**non-public**, so the *only* thing genuinely exposed to unauthenticated internet traffic is the
rate-limited Next.js proxy route — there is no second, unprotected path to the metered LLM API that
could bypass FR-010. No new violations introduced by the Phase 1 design. Gate remains **PASS**.

## Project Structure

### Documentation (this feature)

```text
specs/010-guest-chat-ui/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks — not this command)
```

### Source Code (repository root)

```text
web/                              # NEW — currently empty placeholder
├── app/
│   ├── chat/
│   │   └── page.tsx              # the single /chat route
│   └── api/
│       └── chat/
│           └── route.ts          # NEW — thin server-side proxy into the agent's
│                                   # /run_sse, streaming the response straight through
├── components/
│   ├── ChatWindow.tsx            # message list + input, streaming render
│   └── MessageBubble.tsx
├── lib/
│   ├── stream-client.ts          # browser-side: reads the SSE stream from /api/chat
│   └── rate-limit.ts             # NEW — in-memory per-session request cap (FR-010)
├── package.json
├── next.config.js
└── tailwind.config.ts            # no Dockerfile — Cloud Run buildpacks handle this
                                    # (`gcloud run deploy --source=.`), confirmed in research.md

agent/                             # EXISTING — concierge_agent unchanged this phase
├── concierge_agent/               # unchanged
└── scripts/
    └── reset_demo_data.py        # NEW — scheduled reset (FR-011), truncates/reseeds
                                    # public-demo rows back to the known-good baseline
                                    # (no Dockerfile either — `adk deploy cloud_run` builds
                                    # and deploys the container in one step)
```

**Structure Decision**: Two Cloud Run services, not one — the Next.js frontend (`web/`) and the
existing Python ADK agent (`agent/`) deploy separately, each via its platform's own one-command
deploy path (`gcloud run deploy --source=.` for Next.js, `adk deploy cloud_run` for the agent) —
neither needs a hand-written `Dockerfile`, both use Cloud Run's automatic buildpacks/build step.
Rejected a single combined container: the agent already runs as its own ADK-served process today,
unchanged since `specs/001-foundation`, and merging it into one container with a Node.js frontend
would mean rebuilding how it's served — real, unnecessary work against the "fastest path to live"
goal.

Revised from an earlier draft of this plan: the browser does **not** call the agent's Cloud Run URL
directly. Instead, `web/app/api/chat/route.ts` is a thin Next.js server-side route that (1) applies
the per-session rate cap (FR-010) before doing anything else, then (2) calls the agent's `/run_sse`
endpoint server-to-server and streams the response straight back to the browser. This one design
choice resolves three things at once: no CORS configuration needed on the agent (the browser only
ever talks to the Next.js origin), rate limiting has one clear enforcement point instead of needing
to live inside the agent itself, and the agent's Cloud Run service can stay **non-public**
(`--no-allow-unauthenticated`, the default) — only the Next.js service's own Cloud Run identity is
granted `roles/run.invoker` on it, which is meaningfully more secure than exposing the agent
directly to the public internet. `reset_demo_data.py` is a new script under the existing
`agent/scripts/` directory (same location as `ingest.py`/`seed_room_features.py`), invoked on a
schedule by Cloud Scheduler hitting a small trigger endpoint added to the agent — not a new
standalone service.

## Complexity Tracking

No unjustified violations — every Constitution Check row above is PASS or N/A. The one principle
this phase actively negotiates (X — Public Demo Guardrails) is satisfied via the smaller-scope
option the constitution itself offers (scheduled reset vs. full isolation), not an exception to it.
