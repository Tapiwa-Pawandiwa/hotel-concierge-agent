<!--
Sync Impact Report (latest: 2.0.0 → 2.0.1)
- Version change: 2.0.0 → 2.0.1
- Modified principles: I and X — removed "one-week deadline" / "MVP week" framing, replaced with
  "limited, non-continuous time available." Wording-only: neither principle's actual requirement
  changed, so PATCH per this file's own versioning policy. Rationale: calendar-day tracking
  (CLAUDE.md's old "Day N of 7") was producing false "behind schedule" pressure on days the human
  had no time for this project — CLAUDE.md now tracks order/progress only, no day binding, and
  the constitution's rationale text needed to match.
- Added sections: none
- Removed sections: none
- Follow-up TODOs: none new

---
Sync Impact Report (2.0.0, superseded above)
- Version change: 1.2.0 → 2.0.0
- Modified principles: I. Guide, Don't Generate → renamed I. Worked-Example Learning (Project 1
  Mode) — BACKWARD-INCOMPATIBLE redefinition. Previous text required implementation code to be
  written by the human, never generated wholesale by the agent. New text requires the opposite:
  the agent MUST provide complete, runnable, commented code for every task. Rationale: this
  project is Project 1 of a portfolio-building learning arc, and unlike prior domains the human
  has learned (React Native — learned by copying working patterns), there is no existing pattern
  vocabulary for agent code/RAG scripts to reason from; guided discovery without worked examples
  was measured (by the human, in-session) as too slow to be viable against the one-week deadline.
  This is a MAJOR bump per this file's own versioning policy, not a MINOR expansion — the prior
  rule is reversed, not extended.
- Added sections: none this pass
- Removed sections: none
- Templates requiring updates: .specify/templates/plan-template.md, .specify/templates/spec-template.md,
  .specify/templates/tasks-template.md — ⚠ still pending manual review from v1.0.0. This amendment
  makes that review more urgent: any Phase -1 gate language in those templates that assumes
  human-authored implementation (e.g. Article III-style "no code before the human writes tests")
  should be checked against Principle I's new text specifically.
- Follow-up TODOs: rate-limit mechanism, reset/isolation mechanism, and hosting target (Principle
  X) still undecided, unaffected by this amendment. Confirm at the start of Project 2 whether
  worked-example mode should persist or revert to guided-discovery, per Principle I's own closing
  sentence.
-->

# Hotel Concierge + Operations Platform Constitution

## Core Principles

### I. Worked-Example Learning (Project 1 Mode)
This project serves two purposes at once: a portfolio-grade system design and a hands-on
learning project — specifically Project 1 of a portfolio-building learning arc. The human has
learned adjacent domains before (React Native) by copying working patterns, not by discovering
code from hints alone; agent code and RAG scripts are a domain with no existing pattern vocabulary
to draw on, so guided discovery without seeing working examples first imposes too much cognitive
load to be viable given the limited, non-continuous time available for this project — sessions
happen around other commitments, not on a fixed daily schedule. The agent therefore MUST provide
complete, runnable code for every task, not hints or pseudocode. Every non-trivial line or block
MUST carry an inline comment explaining what it does, and every code block MUST be followed by an
explanation of how it fits the larger system — which primitive, which risk tier, which existing
pattern it repeats — so the goal is pattern recognition and reuse, not blind paste. The agent MUST
NOT use its own file-editing tools on the project's application code (`agent.py`, `tools.py`,
migrations, tests, etc.) — code is delivered in the response for the human to place, run, and
debug themselves, so integration and debugging remain the human's own work. After the human
confirms a task runs, the agent MUST ask at least one comprehension-check question before the next
task starts. Scaffolding with no learning value (boilerplate config, `.gitignore`, formatting)
remains exempt from all of the above — trivially fine for the agent to just do. This mode is
scoped to this project specifically; Project 2 onward in the same learning arc is expected to
shift back toward self-directed, guided-discovery writing as pattern vocabulary builds — confirm
this explicitly at that project's kickoff rather than assuming either mode by default.

### II. Four Primitives
Every entity in the system MUST be one of four shapes: a **Who** (Actor: Guest/StaffMember, or
Resource: Room/EventSpace/EquipmentInventoryItem/MenuItem), a **Request**, a **Financial** charge,
or a **Signal**. New features MUST extend these shapes rather than invent new ones. Rationale:
complexity is meant to grow in how many *kinds* of request and charge exist, never in the number
of moving parts underneath them.

### III. Risk Tiering (NON-NEGOTIABLE)
Every tool MUST be classified Tier 1 (read-only, autonomous), Tier 2 (write, logged and
reversible), or Tier 3 (money, dates, or a real booking — always human-confirmed before it
executes). No tool ships unclassified, and no Tier 3 tool executes without confirmation. No
exceptions.

### IV. Fixed Agent Topology
Agent count MUST track reasoning mode and trust boundary, not data domain. The topology is fixed
at three: `concierge_agent` (guest-facing), `ops_agent` (staff task routing/monitoring),
`sales_agent` (event feasibility, quotes, approval). New domains become tools inside one of these
three. A new agent is justified only when a domain introduces both a genuinely new reasoning mode
and a genuinely new trust boundary — the standard `sales_agent` itself had to meet.

### V. SQL-Only Data Layer
A single Postgres instance (via Supabase) with the `pgvector` extension serves both relational
data and vector-similarity search. No separate document store or dedicated vector database MAY be
introduced. Rationale: this system's relationships (guest → reservation → bill item → order) are
foreign-key-natural, and billing needs real ACID guarantees a document store doesn't provide for
free.

### VI. Mocked-Adapter Boundary
Every mocked external system (PMS/POS/ERP/WFM, sensors, locks) MUST implement one shared adapter
pattern and MUST live inside the application's own trust boundary. Only Anthropic Claude, Voyage
AI, and Stripe (test mode) MAY cross to a real third party with credentials. A production
integration later means writing a new adapter subclass, not touching any tool signature that
calls it.

### VII. Tool Contract & Idempotency
Every tool MUST return a `{status, data, error}` shape and MUST NOT raise an uncaught exception —
failures are structured data the model can react to, not stack traces. Every Tier 2/3 write tool
MUST accept an idempotency key, reusing the same key the client-side write-ahead queue generates,
so a replayed write after a reconnect cannot double-charge or double-book.

### VIII. Append-Only Billing
A posted charge in `bill_items` MUST NOT be `UPDATE`d. A correction MUST be a new offsetting row
(negative amount, same accounting code). Rationale: the ledger stays a true audit trail rather
than something that can quietly be edited after the fact.

### IX. No Speculative Features
Nothing MAY be built ahead of the phase that needs it. Structured loyalty systems, labor-law
compliance engines, and any `guest_preferences` structure beyond what's specified are explicit
scope exclusions, not oversights — re-adding them silently reverses a decision and requires a
constitution amendment, not a quiet schema change.

### X. Public Demo Guardrails
This system MUST NOT be deployed anywhere reachable by unauthenticated public traffic until three
things exist: (a) a rate limit or request budget per visitor/session — public traffic against the
Claude and Voyage APIs has real, unbounded cost with no guest login to attribute it to; (b) either
a scheduled state reset or per-visitor data isolation, so one visitor's check-in, booking, or
order cannot corrupt or become visible in another visitor's session; (c) confirmation that Stripe
stays test-mode only — no code path may expose real payment capture publicly, ever. This principle
states the requirement, not the implementation; the mechanism for each is an open decision (see
Section 15 of the proposal), but the gate itself is non-negotiable — it blocks the deploy step
specifically, not local development or the MVP build scope (`CLAUDE.md`).

## Source of Truth

`docs/implementation_proposal.html` is authoritative for architecture, ER diagrams, tool
signatures, migration SQL, and the phased plan. `docs/mycheckpoint.html` is authoritative for
current-state facts (live schema, known bugs R1–R8, real dependency versions). Where a
conversation and either file disagree, the file MUST win — the conflict is flagged for the human
to resolve, not silently resolved by the agent picking one side.

## Development Workflow Gates

Phase 0 (foundation/schema refactor) and Phase 7 (business events/feasibility — the newest and
most failure-prone path per the proposal's own eval notes) MUST run the full gate path:
`constitution → specify → clarify → plan → checklist → tasks → analyze → implement → converge`.
All other phases use the short path: `specify → plan → tasks → implement → converge`, with
`clarify` or `checklist` added only where a specific phase's card in the plan calls for it. Gate
depth is a velocity/rigor trade-off decided once per phase up front, not renegotiated mid-phase.

## Governance

This constitution supersedes any conflicting instruction given in conversation. Amendments
require: an explicit statement of what changed and why, a version bump per the rules below, and
an updated `Last Amended` date. Every `/speckit-plan` for a new phase MUST confirm the phase's
approach doesn't violate a principle above before proceeding; if it must, the violation is
documented and justified in that phase's plan, not silently absorbed.

**Versioning policy**: MAJOR — a principle is removed or redefined in a backward-incompatible
way. MINOR — a principle or section is added, or existing guidance is materially expanded.
PATCH — wording, typo, or non-semantic clarification.

**Version**: 2.0.1 | **Ratified**: 2026-08-05 | **Last Amended**: 2026-08-05
