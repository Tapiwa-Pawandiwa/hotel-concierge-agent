-- 003_rooms_inventory.sql
-- Adds room_types, rooms, room_features, idempotency_keys (data-model.md).
-- Seeds 6 room types / 60 rooms (10 per type), backfills reservations.room_type_id via the
-- fixed A-H -> 1-6 mapping in research.md #1, adds the FK constraints migration 002 left bare.
-- Excludes keycards, room_sensor_events, rate_calendar (spec.md Assumptions).
--
-- Room type names/bed_config/sq_meters/view_type/feature values below are authored demo seed
-- data, not spec-derived facts -- flagged here since everything else in this migration (table
-- shapes, the A-H mapping, row counts) comes directly from research.md/data-model.md.

BEGIN;

CREATE TABLE room_types (
    id             uuid PRIMARY KEY,
    name            text NOT NULL,
    bed_config       text,
    max_occupancy     int,
    sq_meters          int
);

-- Fixed ids (not gen_random_uuid()) so the A-H legacy-code backfill below can reference them
-- directly, deterministically, without relying on INSERT-order/RETURNING-order assumptions.
INSERT INTO room_types (id, name, bed_config, max_occupancy, sq_meters) VALUES
    ('00000000-0000-0000-0000-000000000001', 'Standard Queen',     '1 Queen',          2, 24),
    ('00000000-0000-0000-0000-000000000002', 'Standard King',      '1 King',           2, 24),
    ('00000000-0000-0000-0000-000000000003', 'Deluxe Queen',       '2 Queen',          4, 32),
    ('00000000-0000-0000-0000-000000000004', 'Deluxe King',        '1 King + Sofa',    3, 32),
    ('00000000-0000-0000-0000-000000000005', 'Executive Suite',    '1 King + Living',  3, 45),
    ('00000000-0000-0000-0000-000000000006', 'Presidential Suite', '1 King + Living',  4, 70);

CREATE TABLE rooms (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    room_type_id          uuid NOT NULL REFERENCES room_types(id) ON DELETE RESTRICT,
    floor                   int,
    view_type                text,
    occupancy_status           text NOT NULL DEFAULT 'vacant',
    housekeeping_status         text NOT NULL DEFAULT 'clean',
    energy_mode                   text NOT NULL DEFAULT 'normal'
);

-- 10 rooms per type = 60 total. Floors/views cycle deterministically -- flavor data.
INSERT INTO rooms (room_type_id, floor, view_type)
SELECT rt.id,
       2 + ((n - 1) % 5),
       (ARRAY['city','garden','pool','ocean','courtyard'])[1 + ((n - 1) % 5)]
FROM room_types rt
CROSS JOIN generate_series(1, 10) AS n;

CREATE TABLE room_features (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    room_type_id    uuid REFERENCES room_types(id) ON DELETE CASCADE,
    room_id          uuid REFERENCES rooms(id) ON DELETE CASCADE,
    feature           text NOT NULL,
    CONSTRAINT room_features_one_target CHECK (
        (room_type_id IS NOT NULL AND room_id IS NULL) OR
        (room_type_id IS NULL AND room_id IS NOT NULL)
    )
);

-- Type-level tags (a handful, per spec.md Assumptions -- not exhaustive)
INSERT INTO room_features (room_type_id, feature)
SELECT id, 'city_view' FROM room_types WHERE name = 'Standard Queen'
UNION ALL
SELECT id, 'mini_bar' FROM room_types WHERE name = 'Executive Suite'
UNION ALL
SELECT id, 'mini_bar' FROM room_types WHERE name = 'Presidential Suite'
UNION ALL
SELECT id, 'butler_service' FROM room_types WHERE name = 'Presidential Suite';

-- Instance-level tags (a handful of specific rooms)
INSERT INTO room_features (room_id, feature)
SELECT id, 'accessible' FROM rooms ORDER BY id LIMIT 3;

INSERT INTO room_features (room_id, feature)
SELECT id, 'smoking' FROM rooms ORDER BY id OFFSET 3 LIMIT 2;

CREATE TABLE idempotency_keys (
    key         uuid NOT NULL,
    tool_name    text NOT NULL,
    result        jsonb,
    created_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (key, tool_name)
);

-- Backfill reservations.room_type_id via the fixed A-H -> 1-6 mapping (research.md #1).
-- reserved_room_type lives on guests_legacy_kaggle (renamed off guests in 002); join back
-- through guests.legacy_guest_id to reach it.
UPDATE reservations r
SET room_type_id = CASE gl.reserved_room_type
    WHEN 'A' THEN '00000000-0000-0000-0000-000000000001'
    WHEN 'B' THEN '00000000-0000-0000-0000-000000000002'
    WHEN 'C' THEN '00000000-0000-0000-0000-000000000003'
    WHEN 'D' THEN '00000000-0000-0000-0000-000000000004'
    WHEN 'E' THEN '00000000-0000-0000-0000-000000000005'
    WHEN 'F' THEN '00000000-0000-0000-0000-000000000006'
    WHEN 'G' THEN '00000000-0000-0000-0000-000000000001'
    WHEN 'H' THEN '00000000-0000-0000-0000-000000000002'
END::uuid
FROM guests g
JOIN guests_legacy_kaggle gl ON gl.guest_id = g.legacy_guest_id
WHERE r.guest_id = g.id;

ALTER TABLE reservations
    ADD CONSTRAINT reservations_room_type_id_fkey FOREIGN KEY (room_type_id) REFERENCES room_types(id),
    ADD CONSTRAINT reservations_room_id_fkey FOREIGN KEY (room_id) REFERENCES rooms(id);

-- Row-count assertions (FR-013) -- abort the whole transaction on mismatch.
DO $$
DECLARE
    rt_count int; room_count int; null_type_count int;
BEGIN
    SELECT count(*) INTO rt_count FROM room_types;
    SELECT count(*) INTO room_count FROM rooms;
    SELECT count(*) INTO null_type_count FROM reservations WHERE room_type_id IS NULL;
    IF rt_count != 6 THEN
        RAISE EXCEPTION 'room_types count wrong: expected 6, got %', rt_count;
    END IF;
    IF room_count != 60 THEN
        RAISE EXCEPTION 'rooms count wrong: expected 60, got %', room_count;
    END IF;
    IF null_type_count != 0 THEN
        RAISE EXCEPTION 'reservations missing room_type_id on % rows', null_type_count;
    END IF;
END $$;

COMMIT;
