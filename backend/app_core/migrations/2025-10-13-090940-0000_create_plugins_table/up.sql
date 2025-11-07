-- Your SQL goes here
CREATE TYPE plugin_type_enum AS ENUM (
    'lms'
);

CREATE TABLE IF NOT EXISTS plugins (
    "id" SERIAL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "version" VARCHAR(50) NOT NULL,
    "description" TEXT,
    "enabled" BOOLEAN NOT NULL DEFAULT false,
    "plugin_type" plugin_type_enum NOT NULL,
    "is_builtin" BOOLEAN NOT NULL DEFAULT false,
    "created_by_user_id" INTEGER REFERENCES users(id) ON DELETE SET NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT NOW(),
    "updated_at" TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_plugin_id on plugins(id);
