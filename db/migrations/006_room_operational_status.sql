BEGIN;

-- Same pattern as occupancy_status/housekeeping_status: adds the
-- active/out_of_order flag assign_room/create_booking need to exclude
-- out-of-order rooms from availability (T016, source proposal §4).
-- NOT NULL DEFAULT on an ADD COLUMN backfills every existing row in the
-- same statement -- no separate UPDATE needed.
ALTER TABLE rooms ADD COLUMN IF NOT EXISTS operational_status text NOT NULL DEFAULT 'active';

-- Confirms the backfill actually reached every row before committing,
-- same assertion pattern as 004_room_number.sql.
DO $$
DECLARE still_null int;
BEGIN
    SELECT count(*) INTO still_null FROM rooms WHERE operational_status IS NULL;
    IF still_null != 0 THEN
        RAISE EXCEPTION 'operational_status backfill incomplete: % rooms still null', still_null;
    END IF;
END $$;

COMMIT;