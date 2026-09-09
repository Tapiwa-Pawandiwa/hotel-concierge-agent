import os
from datetime import datetime, timezone
from pathlib import Path
import psycopg
from dotenv import load_dotenv

"""Resets the public demo's data back to a known-good baseline.

Run manually for local testing (python agent/scripts/reset_demo_data.py),
or on a schedule as a Cloud Run Job triggered by Cloud Scheduler
(research.md §6, revised 2026-09-09) -- deliberately a standalone script,
not an HTTP route: there's no public port to secure this way, since IAM
(the Job's own service account) is the real security boundary instead of
an app-level secret.

DEMO_BASELINE_CUTOFF must be a fixed ISO timestamp env var -- everything
created after it is treated as public-demo traffic and removed; anything
before it (the original 300 seeded reservations/guests) is never touched.
"""


env_path = Path(__file__).resolve().parent.parent / "concierge_agent" / ".env"
load_dotenv(env_path)  # no-op in Cloud Run, where env vars are injected directly


cutoff = os.environ["DEMO_BASELINE_CUTOFF"]

conn = psycopg.connect(os.environ["SUPABASE_DB_URL"])
cur = conn.cursor()

# reservation_products cascades automatically (ON DELETE CASCADE, confirmed
# live) -- deleting reservations is enough, no separate delete needed.
cur.execute("DELETE FROM reservations WHERE created_at > %s", (cutoff,))
reservations_removed = cur.rowcount

# Never touch the original 300 seeded guests -- they all have a
# legacy_guest_id; a demo-created profile always has it NULL.
cur.execute(
    "DELETE FROM guests WHERE created_at > %s AND legacy_guest_id IS NULL",
    (cutoff,),
)
guests_removed = cur.rowcount

# Orphaned booking_parties (every reservation that referenced them was
# just deleted above) -- nothing else points at them, safe to clean up.
cur.execute(
    """
    DELETE FROM booking_parties bp
    WHERE NOT EXISTS (
        SELECT 1 FROM reservations r WHERE r.booking_party_id = bp.id
    )
    """
)
parties_removed = cur.rowcount

# Rooms are shared physical inventory, never "demo-created" -- just reset
# every room's live state back to its default, unconditionally.
cur.execute(
    "UPDATE rooms SET occupancy_status = 'vacant', housekeeping_status = 'clean'"
)
rooms_reset = cur.rowcount

conn.commit()

print(
    f"[{datetime.now(timezone.utc).isoformat()}] Demo reset complete: "
    f"{reservations_removed} reservations removed, {guests_removed} guests removed, "
    f"{parties_removed} orphaned booking parties removed, {rooms_reset} rooms reset."
)