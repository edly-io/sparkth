-- This file should undo anything in `up.sql`
DROP INDEX IF EXISTS idx_user_plugin_configs_plugin_id;
DROP INDEX IF EXISTS idx_user_plugin_configs_user_id;
DROP INDEX IF EXISTS idx_plugin_config_schema_plugin;

DROP TRIGGER IF EXISTS update_user_plugin_configs_updated_at ON user_plugin_configs;

DROP TABLE IF EXISTS user_plugin_configs;
DROP TABLE IF EXISTS plugin_config_schema;

DROP TYPE IF EXISTS config_type_enum;