-- This file should undo anything in `up.sql`
DROP TRIGGER IF EXISTS update_plugin_configs_updated_at ON plugin_configs;

DROP INDEX IF EXISTS idx_plugin_configs_plugin_id;
DROP TABLE IF EXISTS plugin_configs;