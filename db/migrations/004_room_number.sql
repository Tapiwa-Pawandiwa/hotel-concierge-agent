BEGIN;

ALTER TABLE rooms ADD COLUMN room_number text;

-- Backfill: floor number followed by a two-digit sequence within that floor,
-- e.g. "201", "202" -- a common real-world hotel numbering convention, and
-- deterministic so re-running against a fresh copy gives the same numbers.
WITH numbered AS (
    SELECT id, floor,
           row_number() OVER (PARTITION BY floor ORDER BY id) AS position_on_floor
    FROM rooms
)
UPDATE rooms
SET room_number = numbered.floor::text || lpad(numbered.position_on_floor::text, 2, '0')
FROM numbered
WHERE rooms.id = numbered.id;

ALTER TABLE rooms ALTER COLUMN room_number SET NOT NULL;
ALTER TABLE rooms ADD CONSTRAINT rooms_room_number_unique UNIQUE (room_number);

-- Confirms the backfill actxqually reached every row before committing.
DO $$
DECLARE
    still_null int;
BEGIN
    SELECT count(*) INTO still_null FROM rooms WHERE room_number IS NULL;
    IF still_null != 0 THEN
        RAISE EXCEPTION 'room_number backfill incomplete: % rooms still null', still_null;
    END IF;
END $$;

COMMIT;