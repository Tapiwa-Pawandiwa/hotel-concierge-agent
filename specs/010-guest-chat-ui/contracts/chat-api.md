# Contract: `POST /api/chat` (Next.js Route Handler, `web/app/api/chat/route.ts`)

The only HTTP endpoint the browser ever calls. Public (this is FR-005's public surface), rate-limited
per FR-010.

## Request

Exactly one of `message` or `confirmation` is present per call — never both:

```
POST /api/chat
Content-Type: application/json

{
  "session_id": "9f1c2e3a-...-uuid",   // client-generated once per browser tab, reused every call
  "message": "I'd like to book a room for September 3rd to 5th"
}
```

Or, answering a pending Tier 3 confirmation (already implemented; documented here 2026-09-10 —
this contract previously omitted it):

```
POST /api/chat
Content-Type: application/json

{
  "session_id": "9f1c2e3a-...-uuid",
  "confirmation": { "id": "toolu_01DPM5XBAxVR6cjtMfGgdiFy", "confirmed": true }
}
```

## Response — success

`200 OK`, `Content-Type: text/event-stream` — the upstream agent's SSE stream, piped through
unchanged. Each event's `data:` payload is a JSON chunk of the assistant's in-progress or completed
response, per ADK's own `/run_sse` event shape (`research.md` §2). The client concatenates streamed
text chunks into the current assistant message as they arrive (FR-002).

A confirmation-gated tool call (Tier 3 — `modify_booking`/`cancel_booking`) still surfaces its ask as
part of the normal assistant message text (FR-004) — the underlying protocol is unchanged. What
changed 2026-09-10 (FR-014, User Story 4): the frontend now renders that moment as a real Confirm/
Cancel button pair instead of asking the guest to type "yes"/"no" — the buttons call this same
endpoint with the `confirmation` request shape above, they don't require a new route.

**Trace data (User Story 4, `/chat?trace=true` only)**: this endpoint's response body is unchanged —
the trace pane is a client-side concern, built by having `stream-client.ts` read *more* of the same
SSE stream it already receives (`research.md` §8), not a second response format. Specifically, a
`functionResponse` part on a `role:"user"` event (previously discarded entirely) carries the tool's
real `{status, data/matches, error}` result, joinable to its originating `functionCall` by shared
`id`.

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

# Not an HTTP contract: scheduled reset (revised 2026-09-09)

`agent/scripts/reset_demo_data.py` is a standalone script, not an HTTP route — there is no request/
response contract here at all. It runs as a **Cloud Run Job**, triggered by Cloud Scheduler calling
the Cloud Run Admin API directly (`.../jobs/reset-demo-data:run`, OAuth-authenticated), per
`research.md` §6. Never called by the browser, the Next.js app, or any public endpoint — this is
what closes the gap the original shared-secret HTTP design was working around: there's no public
port to secure at all, because there's no public port.
