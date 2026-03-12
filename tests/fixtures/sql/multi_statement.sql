-- Multi-statement SQL fixture for testing document-level diagnostics
BEGIN;

CREATE TABLE test_orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    total NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO test_orders (user_id, total, status)
SELECT id, 99.99, 'complete'
FROM users
WHERE active = true;

COMMIT;
