BEGIN;

-- 003 created idempotency_keys.key as uuid, but the LLM generates this value
-- itself and isn't reliable at producing syntactically valid UUID hex --
-- relax the column to a plain opaque text key (data-model.md, 2026-08-10).
-- Safe to re-run: text -> text is a no-op if this already happened.
ALTER TABLE idempotency_keys ALTER COLUMN key TYPE text USING key::text;

COMMIT;