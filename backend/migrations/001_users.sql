-- Users table for auth (restaurant staff accounts)
CREATE TABLE IF NOT EXISTS users (
    user_id         SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    email           VARCHAR(150) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    restaurant_id   INT REFERENCES restaurants(restaurant_id),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
