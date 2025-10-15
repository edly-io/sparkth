-- This file should undo anything in `up.sql`
DROP INDEX IF EXISTS idx_users_email;
DROP INDEX IF EXISTS idx_users_username;
DROP INDEX IF EXISTS idx_users_id;

DROP TABLE IF EXISTS users;
