import os
import psycopg
from dotenv import load_dotenv
from faker import Faker
from pathlib import Path

"""Regenerates room_features with a full, deterministic set of tags.

Run manually (not part of any migration): python agent/scripts/seed_room_features.py
Safe to re-run — it deletes and regenerates all room_features rows each time,
using a fixed Faker seed, so the output is identical every run.
"""

env_path = Path(__file__).resolve().parent.parent / "concierge_agent" / ".env"
load_dotenv(env_path)
conn = psycopg.connect(os.environ["SUPABASE_DB_URL"])

fake = Faker()
Faker.seed(42)  # fixed seed -- every run produces the exact same tags, same rooms

# Type-level standard: which room types get a bathtub vs. shower-only, and
# which get extra amenities. This is a deliberate category rule, not random --
# every room of a given type should have the same bathroom standard.
BATHTUB_TYPES = {"Deluxe Queen", "Deluxe King", "Executive Suite", "Presidential Suite"}
MINI_BAR_TYPES = {"Deluxe King", "Executive Suite", "Presidential Suite"}
SUITE_EXTRAS = {"Presidential Suite": ["butler_service", "balcony", "jacuzzi"]}

cur = conn.cursor()

# Wipe and regenerate rather than append -- this also removes the old
# 'city_view' row, which duplicated rooms.view_type and shouldn't have been
# a room_features tag in the first place.
cur.execute("DELETE FROM room_features")

cur.execute("SELECT id, name FROM room_types")
room_types = cur.fetchall()

for room_type_id, name in room_types:
   # Shower is the unstated baseline every room has -- only bathtub, the
    # extra, gets tagged. Untagged types implicitly mean "standard shower."
    if name in BATHTUB_TYPES:
        cur.execute(
            "INSERT INTO room_features (room_type_id, feature) VALUES (%s, %s)",
            (room_type_id, "bathtub"),
        )
    if name in MINI_BAR_TYPES:
        cur.execute(
            "INSERT INTO room_features (room_type_id, feature) VALUES (%s, %s)",
            (room_type_id, "mini_bar"),
        )
    for extra in SUITE_EXTRAS.get(name, []):
        cur.execute(
            "INSERT INTO room_features (room_type_id, feature) VALUES (%s, %s)",
            (room_type_id, extra),
        )

cur.execute("SELECT id, floor FROM rooms")
rooms = cur.fetchall()

for room_id, floor in rooms:
    # Independent probabilistic tags -- realistic hotel proportions, not an
    # even split. chance_of_getting_true is a percentage (0-100).
    if fake.boolean(chance_of_getting_true=8):
        cur.execute("INSERT INTO room_features (room_id, feature) VALUES (%s, %s)", (room_id, "accessible"))
    if fake.boolean(chance_of_getting_true=10):
        cur.execute("INSERT INTO room_features (room_id, feature) VALUES (%s, %s)", (room_id, "smoking"))
    if fake.boolean(chance_of_getting_true=15):
        cur.execute("INSERT INTO room_features (room_id, feature) VALUES (%s, %s)", (room_id, "corner_room"))
    if fake.boolean(chance_of_getting_true=15):
        cur.execute("INSERT INTO room_features (room_id, feature) VALUES (%s, %s)", (room_id, "quiet_room"))
    if fake.boolean(chance_of_getting_true=15):
        cur.execute("INSERT INTO room_features (room_id, feature) VALUES (%s, %s)", (room_id, "away_from_elevator"))
    # high_floor is deterministic, not a coin flip -- floors run 2-6, so 5/6
    # genuinely are the top two, not a random label.
    if floor >= 5:
        cur.execute("INSERT INTO room_features (room_id, feature) VALUES (%s, %s)", (room_id, "high_floor"))

conn.commit()

cur.execute("SELECT count(*) FROM room_features")
print(f"room_features regenerated: {cur.fetchone()[0]} rows")
cur.close()