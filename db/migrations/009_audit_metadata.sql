BEGIN; 
-- live gaps: reservations/rooms are missing both columns entirely,
-- guests is missing updated_at. Existing rows get this migration's apply
-- time as created_at -- their true original creation time isn't
-- recoverable from what's in the DB today (data-model.md caveat).

ALTER TABLE guests ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now()
ALTER TABLE reservations ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE reservations ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now()
ALTER TABLE rooms ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now()
ALTER TABLE rooms ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now()
ALTER TABLE room_types    ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE room_features ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS guests_set_updated_at ON guests;
CREATE TRIGGER guests_set_updated_at
BEFORE UPDATE ON guests
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS reservations_set_updated_at ON reservations;
CREATE TRIGGER reservations_set_updated_at
BEFORE UPDATE ON reservations
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS rooms_set_updated_at ON rooms;
CREATE TRIGGER rooms_set_updated_at
BEFORE UPDATE ON rooms
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMIT;