BEGIN;

-- Personal multi-room bookings (a guest booking several rooms themselves)
-- -- deliberately NOT the same concept as reservations.group_booking_id,
-- which is reserved for the formal corporate/event group-block case
-- (FK to event_bookings, arriving in Phase 7). This table gets a real FK
-- from day one since it doesn't need to defer one.
--
-- updated_at included even though no tool mutates this table yet -- a
-- real hotel operation (correcting the primary contact on a party) is
-- realistic future need, not a speculative one, and retrofitting an
-- audit column later would mean a throwaway migration just for this.
CREATE TABLE booking_parties (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    primary_guest_id  uuid NOT NULL REFERENCES guests(id),
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);

-- Reuses the shared trigger function from migration 009 -- same function,
-- one more table wired to it, not a new copy of the same logic.
CREATE TRIGGER booking_parties_set_updated_at
BEFORE UPDATE ON booking_parties
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

ALTER TABLE reservations ADD COLUMN booking_party_id uuid REFERENCES booking_parties(id);

COMMIT;