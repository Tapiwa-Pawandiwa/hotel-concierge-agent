-- 002_refactor_guests_reservations.sql
-- Splits flat guests into guests (identity) + reservations (owns booking_reference).
-- Source: docs/implementation_proposal.html lines 1256-1343, reproduced verbatim except:
-- 1) arrival_date_day -> arrival_date_day_of_month (real live column name, confirmed via
--    direct schema introspection during T003).
-- 2) checkout date now uses (stays_in_weekend_nights + stays_in_week_nights), not lead_time.
--    Proposal bug: lead_time is days between booking and arrival (Kaggle dataset semantics),
--    not length of stay -- using it as nights-stayed produced check_out_date = check_in_date
--    for the 15 rows where lead_time = 0, violating reservations_dates_valid. Confirmed via
--    live query: 2 of 300 rows also have 0 total nights in stays_in_weekend/week_nights, so
--    GREATEST(...,1) floors every stay at 1 night rather than silently dropping those rows.

BEGIN;

CREATE TABLE guests_new (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    legacy_guest_id        text UNIQUE,
    first_name             text NOT NULL,
    last_name               text NOT NULL,
    email                   text,
    phone                   text,
    country_code            text,
    preferred_language      text,
    stripe_customer_id      text,
    accessibility_flags     text[] DEFAULT '{}',
    dietary_flags           text[] DEFAULT '{}',
    created_at               timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE reservations (
    booking_reference    text PRIMARY KEY,
    guest_id              uuid NOT NULL REFERENCES guests_new(id) ON DELETE RESTRICT,
    room_type_id           uuid,
    room_id                 uuid,
    group_booking_id         uuid,
    check_in_date            date NOT NULL,
    check_out_date           date NOT NULL,
    adr                      numeric(10,2),
    status                    text NOT NULL DEFAULT 'confirmed'
        CHECK (status IN ('confirmed','checked_in','checked_out','cancelled')),
    CONSTRAINT reservations_dates_valid CHECK (check_out_date > check_in_date)
);

INSERT INTO guests_new (legacy_guest_id, first_name, last_name, email, country_code, created_at)
SELECT
    guest_id,
    split_part(guest_name, ' ', 1),
    NULLIF(substring(guest_name FROM position(' ' IN guest_name) + 1), ''),
    guest_email,
    country,
    now()
FROM guests;

INSERT INTO reservations (booking_reference, guest_id, check_in_date, check_out_date, adr, status)
SELECT
    'BK-' || g.guest_id,
    gn.id,
    make_date(g.arrival_date_year,
              extract(month FROM to_date(g.arrival_date_month, 'Month'))::int,
              g.arrival_date_day_of_month),
    make_date(g.arrival_date_year,
              extract(month FROM to_date(g.arrival_date_month, 'Month'))::int,
              g.arrival_date_day_of_month)
        + make_interval(days => GREATEST(g.stays_in_weekend_nights + g.stays_in_week_nights, 1)),
    g.adr,
    'confirmed'
FROM guests g
JOIN guests_new gn ON gn.legacy_guest_id = g.guest_id;

DO $$
DECLARE
    old_count int; new_guest_count int; new_resv_count int;
BEGIN
    SELECT count(*) INTO old_count FROM guests;
    SELECT count(*) INTO new_guest_count FROM guests_new;
    SELECT count(*) INTO new_resv_count FROM reservations;
    IF old_count != new_guest_count OR old_count != new_resv_count THEN
        RAISE EXCEPTION 'Row-count mismatch: guests=%, guests_new=%, reservations=%',
            old_count, new_guest_count, new_resv_count;
    END IF;
END $$;

ALTER TABLE guests RENAME TO guests_legacy_kaggle;
ALTER TABLE guests_new RENAME TO guests;

COMMIT;
