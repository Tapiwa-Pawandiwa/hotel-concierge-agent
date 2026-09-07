BEGIN;

-- Replaces the hotel_settings key-value breakfast price with a real
-- catalogue (T025, data-model.md "products, product_prices,
-- reservation_products"). hotel_settings.breakfast_rate_per_day is
-- retired as a price source -- not touched here, since hotel_settings
-- itself may still hold genuine operational config elsewhere.

CREATE TABLE IF NOT EXISTS products (
    id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code     text NOT NULL UNIQUE,
    name     text NOT NULL,
    category text,
    active   boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS product_prices (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id    uuid NOT NULL REFERENCES products(id),
    amount        numeric NOT NULL,
    pricing_basis text NOT NULL,
    valid_from    date NOT NULL DEFAULT CURRENT_DATE,
    valid_to      date
);

-- reservation_id is text, not uuid, because reservations' own primary key
-- is booking_reference (text) -- matches the FK type it points to.
CREATE TABLE IF NOT EXISTS reservation_products (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reservation_id text NOT NULL REFERENCES reservations(booking_reference),
    product_id     uuid NOT NULL REFERENCES products(id),
    quantity       integer NOT NULL,
    unit_price     numeric NOT NULL,
    pricing_basis  text NOT NULL,
    line_total     numeric NOT NULL
);

-- Seed BREAKFAST at the exact price/date it was actually first priced at
-- live, so this migration doesn't silently reprice it on a fresh DB.
INSERT INTO products (code, name, category)
SELECT 'BREAKFAST', 'Breakfast Buffet', 'food_beverage'
WHERE NOT EXISTS (SELECT 1 FROM products WHERE code = 'BREAKFAST');

INSERT INTO product_prices (product_id, amount, pricing_basis, valid_from)
SELECT p.id, 22.00, 'PER_NIGHT', DATE '2026-08-14'
FROM products p
WHERE p.code = 'BREAKFAST'
  AND NOT EXISTS (SELECT 1 FROM product_prices pp WHERE pp.product_id = p.id);

COMMIT;