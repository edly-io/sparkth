-- Your SQL goes here

CREATE TYPE plugin_type_enum AS ENUM (
    'lms'
);

CREATE TABLE IF NOT EXISTS plugins (
    "id" SERIAL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "version" VARCHAR(50) NOT NULL,
    "description" TEXT,
    "plugin_type" plugin_type_enum NOT NULL,
    "is_builtin" BOOLEAN NOT NULL DEFAULT false,
    "created_by_user_id" INTEGER REFERENCES users(id) ON DELETE SET NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT NOW(),
    "updated_at" TIMESTAMP NOT NULL DEFAULT NOW()
);

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
