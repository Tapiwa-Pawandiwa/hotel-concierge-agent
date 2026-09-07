# Quickstart: Guest Chat UI

## Prerequisites

- `specs/001-foundation` complete (it is — all 5 user stories independently functional).
- A GCP project with billing enabled, `gcloud` CLI authenticated (`gcloud auth login`), Cloud Run
  and Cloud Scheduler APIs enabled.
- The three existing secrets (`ANTHROPIC_API_KEY`, `SUPABASE_DB_URL`, `VOYAGE_API_KEY`) plus a new
  one (the reset endpoint's shared secret, any random string) added to Google Secret Manager.

## Local validation (before any deploy)

1. Run the agent locally as usual: `cd agent && adk api_server concierge_agent` (the API-server
   mode, not `adk run`'s CLI mode — this is what actually exposes `/run_sse` for the frontend to
   call).
2. Run the frontend locally: `cd web && npm run dev`, pointed at the local agent's URL
   (`http://localhost:8000`) via an env var, not the production Cloud Run URL.
3. Open `http://localhost:3000/chat`. Confirm: a message sends, the response streams in
   incrementally (not all at once), and a full booking conversation (identity → room browse → book
   → confirm) completes without a page reload — this is User Story 2's acceptance scenario, run
   through the UI for the first time rather than `adk run`'s CLI.
4. Send messages rapidly past the configured cap — confirm a `429` renders as a clear in-chat
   message, not a silent hang or a raw error (FR-010, User Story — rate limit).
5. Resize the browser to a mobile width (~375px) — confirm no horizontal scroll, no overlapping
   elements (User Story 3, SC-004).

## Production deploy

6. Deploy the agent (non-public): from the repo root,
   `adk deploy cloud_run --project=$PROJECT --region=$REGION --service_name=concierge-agent agent/concierge_agent`
   — answer "no" (or omit `--allow-unauthenticated`) when prompted about public access
   (`research.md` §3).
7. Grant the frontend's future Cloud Run service account `roles/run.invoker` on the agent service
   (exact command depends on the frontend service account name, resolved once it's created in the
   next step).
8. Deploy the frontend (public): from `web/`,
   `gcloud run deploy chat-ui --source=. --project=$PROJECT --region=$REGION --allow-unauthenticated --max-instances=1`
   (`research.md` §4/§5 — `--max-instances=1` matters for the rate limiter's correctness, not
   optional).
9. Set the agent's Cloud Run URL as an env var on the frontend service (`gcloud run services update
   chat-ui --set-env-vars=AGENT_URL=<url from step 6>`).
10. Set the shared reset secret and `DEMO_BASELINE_CUTOFF` (current timestamp, set once) as env
    vars/secrets on the agent service.
11. Create a Cloud Scheduler job hitting the agent's `/internal/reset-demo-data` with the shared
    secret header, on a schedule comfortably inside 24 hours (e.g. every 6 hours) — satisfies
    SC-007.

## Post-deploy validation (the real acceptance test)

12. From a device that has never touched this project, open the frontend's public Cloud Run URL
    directly (no VPN, no local network) and send a message with no prior setup — User Story 3,
    SC-001/SC-005.
13. Confirm the agent's own Cloud Run URL, hit directly (not through the frontend), returns
    `403`/`401` — proving it's genuinely non-public, not just "not linked anywhere."
14. Manually trigger the reset endpoint once (with the correct header) and confirm a
    demo-created reservation disappears while a seeded (pre-existing) reservation does not —
    proving the cutoff logic is scoped correctly before trusting it to run unattended on a
    schedule.
15. Full run-through of `specs/001-foundation`'s `quickstart.md` Stories 1-5, this time entirely
    through the public URL rather than `adk run`'s CLI — the real proof this milestone is done.
