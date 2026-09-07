# Contract: `POST /api/chat` (Next.js Route Handler, `web/app/api/chat/route.ts`)

The only HTTP endpoint the browser ever calls. Public (this is FR-005's public surface), rate-limited
per FR-010.

## Request

```
POST /api/chat
Content-Type: application/json

{
  "session_id": "9f1c2e3a-...-uuid",   // client-generated once per browser tab, reused every call
  "message": "I'd like to book a room for September 3rd to 5th"
}
```

## Response — success

`200 OK`, `Content-Type: text/event-stream` — the upstream agent's SSE stream, piped through
unchanged. Each event's `data:` payload is a JSON chunk of the assistant's in-progress or completed
response, per ADK's own `/run_sse` event shape (`research.md` §2). The client concatenates streamed
text chunks into the current assistant message as they arrive (FR-002).

A confirmation-gated tool call (Tier 3 — `modify_booking`/`cancel_booking`) surfaces as a normal
assistant message asking the guest to confirm, per FR-004's "handled entirely within the normal chat
flow" decision — no special event type the frontend needs to parse differently.

## Response — rate limited

`429 Too Many Requests`

```json
{ "error": "You're sending messages a bit fast — please wait a moment and try again." }
```

Satisfies FR-010's requirement that the guest sees a clear message, not a silent failure.

## Response — upstream agent unavailable

`502 Bad Gateway`

```json
{ "error": "The concierge is temporarily unavailable. Please try again in a moment." }
```

Satisfies FR-007.

## What this route does, server-side, per call

1. Check the rate limit for `session_id` (`research.md` §5) — return `429` immediately if exceeded, before touching the agent at all.
2. On this `session_id`'s first call, `POST` to the agent's `/apps/concierge_agent/users/{session_id}/sessions/{session_id}` to create the ADK session (`research.md` §2) — skipped on subsequent calls within the same session.
3. `POST` to the agent's `/run_sse` with `streaming: true` and the guest's message, using the agent's Cloud Run service-to-service identity (`research.md` §3) — the agent itself is not publicly reachable.
4. Stream the response back to the browser as it arrives.

---

# Contract: reset trigger endpoint (agent-side, new)

Not called by the browser or the Next.js app — called only by Cloud Scheduler, per `research.md` §6.

## Request

```
POST /internal/reset-demo-data
X-Reset-Secret: <value from Secret Manager, matched server-side>
```

## Response

`200 OK` — `{"status": "ok", "reservations_removed": <n>, "guests_removed": <n>}` on success.
`401 Unauthorized` if the header is missing or doesn't match — this is the only thing standing
between this endpoint and being an unauthenticated public write surface, so the check is mandatory,
not optional hardening.
