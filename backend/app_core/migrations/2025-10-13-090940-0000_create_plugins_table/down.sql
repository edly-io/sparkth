-- This file should undo anything in `up.sql`
DROP INDEX IF EXISTS idx_plugin_id;

DROP TABLE IF EXISTS plugins;
DROP TYPE IF EXISTS plugin_type_enum;