-- Your SQL goes here
CREATE TABLE IF NOT EXISTS plugins (
    "id" SERIAL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "version" VARCHAR(50) NOT NULL,
    "description" TEXT,
    "enabled" BOOLEAN NOT NULL DEFAULT false,
    "plugin_type" VARCHAR(50) NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT NOW(),
    "updated_at" TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_plugin_enabled ON plugins(enabled);
CREATE INDEX IF NOT EXISTS idx_plugin_id on plugins(id);

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_plugins_updated_at BEFORE UPDATE
    ON plugins FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
