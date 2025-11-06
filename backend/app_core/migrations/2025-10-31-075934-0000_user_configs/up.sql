-- Your SQL goes here
CREATE TYPE config_type_enum AS ENUM (
    'string',
    'number',
    'boolean',
    'json',
    'url',
    'email',
    'password'
);

CREATE TABLE IF NOT EXISTS plugin_config_schema (
    "id" SERIAL PRIMARY KEY,
    "plugin_id" INTEGER NOT NULL REFERENCES plugins(id) ON DELETE CASCADE,
    "config_key" VARCHAR(255) NOT NULL,
    "config_type" config_type_enum NOT NULL, 
    "description" TEXT,
    "is_required" BOOLEAN NOT NULL DEFAULT false,
    "is_secret" BOOLEAN NOT NULL DEFAULT false,
    "default_value" TEXT,
    "created_at" TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(plugin_id, config_key)
);

CREATE TABLE IF NOT EXISTS user_plugins (
    "id" SERIAL PRIMARY KEY,
    "user_id" INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    "plugin_id" INTEGER NOT NULL REFERENCES plugins(id) ON DELETE CASCADE,
    "enabled" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMP NOT NULL DEFAULT NOW(),
    "updated_at" TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, plugin_id)
);

CREATE TRIGGER update_user_plugins_updated_at BEFORE UPDATE
    ON user_plugins FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


CREATE TABLE IF NOT EXISTS user_plugin_configs (
    "id" SERIAL PRIMARY KEY,
    "user_plugin_id" INTEGER NOT NULL REFERENCES user_plugins(id) ON DELETE CASCADE,
    "config_key" VARCHAR(255) NOT NULL,
    "config_value" TEXT,
    "created_at" TIMESTAMP NOT NULL DEFAULT NOW(),
    "updated_at" TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(user_plugin_id, config_key)
);

CREATE TRIGGER update_user_plugin_configs_updated_at BEFORE UPDATE
    ON user_plugin_configs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


CREATE INDEX idx_user_plugins_user_id ON user_plugins(user_id);
CREATE INDEX idx_user_plugins_plugin_id ON user_plugins(plugin_id);
CREATE INDEX idx_user_plugin_configs_user_plugin ON user_plugin_configs(user_plugin_id);
CREATE INDEX idx_plugin_config_schema_plugin ON plugin_config_schema(plugin_id);
