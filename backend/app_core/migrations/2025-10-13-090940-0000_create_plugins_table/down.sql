-- This file should undo anything in `up.sql`
DROP TRIGGER IF EXISTS update_plugins_updated_at ON plugins;

DROP INDEX IF EXISTS idx_plugin_id;
DROP TABLE IF EXISTS plugins;