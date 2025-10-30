-- Your SQL goes here
CREATE TABLE IF NOT EXISTS users (
    "id" SERIAL PRIMARY KEY,
    "username" VARCHAR(255) NOT NULL UNIQUE,
    "email" VARCHAR(255) NOT NULL UNIQUE,
    "password_hash" VARCHAR(255) NOT NULL,
    "first_name" VARCHAR(255),
    "last_name" VARCHAR(255),
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "is_admin" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMP NOT NULL DEFAULT NOW(),
    "updated_at" TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_id ON users(id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TRIGGER update_users_updated_at BEFORE UPDATE
    ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();