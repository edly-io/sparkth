-- This file should undo anything in `up.sql`
DROP INDEX IF EXISTS idx_user_plugins_user_id;
DROP INDEX IF EXISTS idx_user_plugins_plugin_id;
DROP INDEX IF EXISTS idx_user_plugin_configs_user_plugin;
DROP INDEX IF EXISTS idx_plugin_config_schema_plugin;

DROP TRIGGER IF EXISTS update_user_plugins_updated_at ON user_plugins;
DROP TRIGGER IF EXISTS update_user_plugin_configs_updated_at ON user_plugin_configs;

DROP TABLE IF EXISTS user_plugin_configs;
DROP TABLE IF EXISTS user_plugins;
DROP TABLE IF EXISTS plugin_config_schema;