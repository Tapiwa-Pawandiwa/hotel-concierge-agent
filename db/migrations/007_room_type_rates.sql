BEGIN;

-- create_booking needs a real nightly rate per room type to compute
-- total_price (T022/T026) -- this was applied live already; base_rate
-- values below match what's actually seeded on the live DB exactly.
ALTER TABLE room_types ADD COLUMN IF NOT EXISTS base_rate numeric;

UPDATE room_types SET base_rate = CASE name
    WHEN 'Standard Queen'     THEN 110.00
    WHEN 'Standard King'      THEN 120.00
    WHEN 'Deluxe Queen'       THEN 190.00
    WHEN 'Deluxe King'        THEN 175.00
    WHEN 'Executive Suite'    THEN 280.00
    WHEN 'Presidential Suite' THEN 550.00
END
WHERE base_rate IS NULL;

-- Fails loudly if a room type name doesn't match the CASE above, rather
-- than silently leaving base_rate NULL on some row.
ALTER TABLE room_types ALTER COLUMN base_rate SET NOT NULL;

COMMIT;
