-- Your SQL goes here

CREATE TABLE plugin_configs (
    id SERIAL PRIMARY KEY,
    plugin_id INTEGER NOT NULL REFERENCES plugins(id) ON DELETE CASCADE,
    config_key VARCHAR(255) NOT NULL,
    config_value TEXT,
    is_secret BOOLEAN NOT NULL DEFAULT FALSE, -- Mark sensitive values
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(plugin_id, config_key)
);

CREATE INDEX idx_plugin_configs_plugin_id ON plugin_configs(plugin_id);

CREATE TRIGGER update_plugin_configs_updated_at BEFORE UPDATE
    ON plugin_configs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
