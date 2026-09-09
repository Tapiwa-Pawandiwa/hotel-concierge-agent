# Research: Guest Chat UI

All decisions below are grounded in the actual `adk-python`/Cloud Run documentation (fetched
2026-09-03, not assumed), specifically because hosting was the one deliberately-open decision
carried in from `spec.md`'s Assumptions.

## 1. How the agent gets hosted

**Decision**: `adk deploy cloud_run --project=$PROJECT --region=$REGION agent/concierge_agent`, run
once from the repo root. No hand-written `Dockerfile`.

**Rationale**: This is ADK's own official one-command path — it packages the agent, builds the
container, pushes it to Artifact Registry, and deploys to Cloud Run in a single step. Confirmed
flags relevant here: `--service_name` (names the Cloud Run service), `--port` (defaults to 8000),
and secrets/env vars passed through via the standard `gcloud`-style `--set-env-vars`/`--set-secrets`
flags after `--`. This is the fastest real path to a working backend — writing a Dockerfile by hand
would be strictly slower for no benefit.

**Alternatives considered**: Hand-authored `Dockerfile` + `gcloud run deploy` — rejected, pure extra
work with no upside over the tool ADK ships specifically for this. A GKE/Compute Engine VM —
rejected outright, wrong scale for a portfolio demo and far slower to stand up.

## 2. How the deployed agent is actually called (session + streaming)

**Decision**: Two calls per new conversation, both server-to-server from the Next.js API route
(§4), never directly from the browser:

1. `POST /apps/{app_name}/users/{user_id}/sessions/{session_id}` — creates the session. `app_name`
   is the agent's directory name (`concierge_agent`); `user_id`/`session_id` are a single random
   UUID generated client-side on first page load and reused for the rest of that browser tab's
   life (matches spec.md's "session-scoped, no persistence across restart" requirement exactly —
   ADK's own session concept **is** the browser-session concept here, not a separate thing to build).
2. `POST /run_sse` — body `{"app_name", "user_id", "session_id", "new_message": {"role": "user",
   "parts": [{"text": "..."}]}, "streaming": true}` — returns the actual server-sent-event stream.

**Rationale**: These are the real, documented endpoints an `adk deploy cloud_run` service exposes —
not invented. Streaming via SSE is a natural fit for `fetch` + `ReadableStream` in a Next.js Route
Handler, which can pipe the upstream SSE body straight through to the browser response.

**Alternatives considered**: Polling a non-streaming `/run` endpoint — rejected, directly violates
FR-002/SC-002 (response must appear incrementally, within 3 seconds).

## 3. Frontend ↔ backend integration shape

**Decision**: The browser never calls the agent's Cloud Run URL directly. `web/app/api/chat/route.ts`
is a thin Next.js Route Handler that (a) checks the rate limit (§5) first, (b) calls the two agent
endpoints from §2 server-side, and (c) streams the SSE response back to the browser unchanged.

**Rationale**: This single design choice resolves three separate problems at once, discovered while
researching rather than assumed upfront (an earlier draft of this plan had the browser calling the
agent directly): (1) no CORS configuration needed on the agent at all — the browser only ever talks
to the Next.js origin; (2) the rate cap has exactly one enforcement point, not something that has to
live inside the agent itself; (3) the agent's Cloud Run service can be deployed **non-public**
(`--no-allow-unauthenticated`, Cloud Run's own default) with only the frontend's Cloud Run service
identity granted `roles/run.invoker` on it — meaningfully more secure than putting the agent
directly on the open internet, and costs essentially nothing extra to build.

**Alternatives considered**: Direct browser → agent SSE connection with `--allow_origins` CORS
config (ADK does support this via a real flag) — rejected once the proxy route turned out to solve
CORS, rate limiting, and public exposure together for roughly the same amount of code.

## 4. Frontend hosting

**Decision**: `gcloud run deploy --source=. --allow-unauthenticated` from `web/`, using Cloud Run's
buildpacks (no hand-written `Dockerfile`). The frontend's Cloud Run service is set to
`--max-instances=1` — see §5 for why this matters.

**Rationale**: Confirmed as a real, documented, single-command deploy path for a Next.js app; Cloud
Run's buildpacks detect and build it automatically. `--allow-unauthenticated` is required here since
this is the actual public-facing surface (unlike the agent, which stays private per §3).

**Alternatives considered**: Vercel (Next.js's own platform) — genuinely simpler for the frontend
alone, but rejected because it would split hosting across two providers and complicate the
service-to-service auth from §3 (Cloud Run's automatic identity-token auth between its own services
doesn't apply across providers); staying on Cloud Run for both keeps the auth story in §3 simple.

## 5. Rate limiting mechanism (FR-010)

**Decision**: A plain in-memory `Map<sessionId, {count, windowStart}>` inside the Next.js API route
(`web/lib/rate-limit.ts`), enforcing something like 20 messages per 5-minute window per session —
exact numbers are a tasks-phase tuning detail, not a plan-phase decision. The frontend Cloud Run
service is deployed with `--max-instances=1` specifically so this in-memory counter stays
authoritative — with more than one instance, requests would round-robin across processes with
independent counters, silently raising the effective limit.

**Rationale**: Directly satisfies the Constitution Check's Principle V note: no new datastore
(Redis, etc.) is introduced, keeping this a pure "SQL-only or nothing" system. `--max-instances=1`
is an explicit, deliberate, and cheap way to make an otherwise-fragile in-memory approach actually
correct, appropriate for the portfolio-demo scale in Technical Context (a handful to low dozens of
concurrent visitors, not production traffic) — this is the "basic" rate limiter FR-010 asks for, not
the fuller guardrails system deferred to `specs/004-resilience`.

**Alternatives considered**: Postgres-backed counter table — rejected as unnecessary extra
schema/writes for a cap this simple; Redis/Upstash — rejected, a new datastore for something this
small is disproportionate and works against "fastest path to live."

## 6. Scheduled public-demo data reset (FR-011)

**Decision, revised 2026-09-09**: A new standalone script, `agent/scripts/reset_demo_data.py`,
deployed as its own **Cloud Run Job** (not a route on the agent's own service) —
`gcloud run jobs deploy reset-demo-data --source=agent --command=python --args=scripts/reset_demo_data.py`.
Cloud Scheduler triggers the job execution directly against the Cloud Run Admin API
(`POST https://run.googleapis.com/v2/projects/{project}/locations/{region}/jobs/reset-demo-data:run`),
authenticated via `--oauth-service-account-email` — a real IAM-authenticated call, not a public HTTP
endpoint at all. (Original design in this section called for a shared-secret HTTP route added to the
agent's own FastAPI app — corrected once `adk deploy cloud_run` was confirmed to only accept a plain
agent directory, no hook for a custom route; Cloud Run Jobs is the right-sized GCP primitive for a
run-to-completion scheduled task anyway, not a retrofit.) The reset logic itself reuses schema that
already exists — **no new column needed**: `guests.created_at`/`reservations.created_at` (T027)
already distinguish the original 300 seeded rows from anything created afterward. Concretely: delete
`reservations` with `created_at` after a fixed baseline cutoff timestamp (`reservation_products`
cascades automatically — confirmed via the live FK's `ON DELETE CASCADE`); delete `guests` with
`created_at` after that same cutoff **and** `legacy_guest_id IS NULL` (never touch the seeded 300,
which all have a `legacy_guest_id`); reset every `rooms` row's `occupancy_status`/
`housekeeping_status` back to their defaults; delete now-orphaned `booking_parties` rows.

**Rationale**: A Cloud Run Job is a run-to-completion container invoked on demand or on a schedule —
exactly what a periodic batch script needs, with no persistent server, no public port, and no
custom-secret-header security to get right, since IAM (the OAuth service account) is the real
security boundary. Reusing the audit-metadata columns already shipped this session avoids a new
migration entirely — the smallest-scope option available, matching why scheduled reset was chosen
over full isolation in the first place.

**Alternatives considered**: A full point-in-time DB restore/snapshot on schedule — rejected,
Supabase-managed restore is a heavier, slower mechanism than a targeted delete for this narrow a
need. A `demo_session_id` column (the mechanism full isolation would have needed) — explicitly
rejected earlier in this planning session precisely to avoid the larger scope.

## 7. Secrets

**Decision**: `ANTHROPIC_API_KEY`, `SUPABASE_DB_URL`, `VOYAGE_API_KEY`, and the reset endpoint's
shared secret all live in Google Secret Manager, granted to each Cloud Run service's runtime service
account, passed via `--set-secrets` at deploy time. Never committed, never baked into either
container image.

**Rationale**: This is the documented, standard pattern for `adk deploy cloud_run` and Cloud Run
generally — confirmed via the official docs, not assumed. Matches this project's existing local
convention (`.env`, gitignored) with the equivalent production mechanism.

**Alternatives considered**: Plain `--set-env-vars` with secrets inline — rejected, defeats the
point of a secret manager and each of these three keys already has real cost/access exposure if
leaked (Anthropic API billing, DB credentials).

## 8. Trace panel data source (added 2026-09-10, User Story 4)

**Decision**: Loosen `stream-client.ts`'s event filter from "skip anything where `role !== 'model'`"
to also process `role === "user"` events carrying a `functionResponse` part, and start reading
`functionCall` parts for every tool name (not just `adk_request_confirmation`, which is all it reads
today). Pair each `functionCall`/`functionResponse` by their shared `id` field into one trace entry:
`{toolName, args, riskTier, result}`.

**Rationale**: Grounded in a live raw-SSE probe against the actual running local agent (not assumed)
— asked "What time is check-in and check-out?" to trigger `retrieve_hotel_policy`, captured the full
event stream. Findings:

- The `functionCall` part (tool name + args, including any `idempotency_key` argument on write
  tools) arrives on a `role:"model"`, `partial:false` event — already passes the existing role
  filter today, it's just never read for anything besides the one hardcoded confirmation-tool name.
- The `functionResponse` part (the tool's actual `{status, data/matches, error}` return value)
  arrives on a **separate event with `role:"user"`** — the current filter silently discards every
  one of these. This is the real gap behind `CLAUDE.md`'s "flag rather than silently drop" note
  about the trace panel.
- Both parts share the same `id` (e.g. `toolu_01DPM5XBAxVR6cjtMfGgdiFy`, generated by the model) —
  the correct join key for pairing a call with its eventual result.
- Risk tier is not present anywhere in the stream at all — confirmed absent from every event field
  in the capture. It has no runtime source; it must be a static `TOOL_RISK_TIERS` table maintained
  by hand in the frontend.
- `retrieve_hotel_policy`'s actual live return value was
  `{"status":"success","matches":[{"source":"checkin_checkout.md","text":"..."}]}` — no
  similarity/relevance score field at all. Showing one (per `CLAUDE.md`'s "source chunk + similarity
  score" description) requires selecting and returning the pgvector cosine distance
  (`embedding <=> %s::vector`) alongside each match in `tools.py` — real application-code work, not
  a UI-only change.

**Alternatives considered**: A second, non-SSE polling endpoint dedicated to trace data — rejected;
the data already exists in the one stream the UI already consumes, so a second endpoint would be
duplicate plumbing for data already in hand.
