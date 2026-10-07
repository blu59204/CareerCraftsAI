-- Destructive rollback: export encrypted vault rows before intentionally using.
BEGIN;
DROP TABLE IF EXISTS portal_credentials;
COMMIT;
