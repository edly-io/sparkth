-- This file should undo anything in `up.sql`
DROP INDEX idx_plugin_settings_plugin_id;
DROP INDEX idx_plugin_settings_id;
DROP INDEX idx_plugin_id;

DROP TABLE plugin_settings;
DROP TABLE plugins;