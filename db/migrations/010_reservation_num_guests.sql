BEGIN;

ALTER TABLE reservations ADD COLUMN IF NOT EXISTS num_guests integer;

-- Backfill from the original Kaggle-derived data where we can trace it --
-- adults + children only (not babies -- infants don't count against a
-- room's max_occupancy in real hotel practice, and room_types.max_occupancy
-- was seeded on that same assumption).
UPDATE reservations r
SET num_guests = COALESCE(glk.adults, 0) + COALESCE(glk.children, 0)
FROM guests_legacy_kaggle glk
WHERE r.booking_reference = 'BK-' || glk.guest_id
  AND r.num_guests IS NULL;

-- Anything else (bookings made through the agent itself, before this
-- migration) has no real historical party size to recover -- default to 1
-- rather than leave it null, same "backfill can't recover true history"
-- caveat as the audit-metadata migration (009).
UPDATE reservations SET num_guests = 1 WHERE num_guests IS NULL;

ALTER TABLE reservations ALTER COLUMN num_guests SET NOT NULL;
ALTER TABLE reservations ADD CONSTRAINT reservations_num_guests_positive CHECK (num_guests > 0);

COMMIT;
