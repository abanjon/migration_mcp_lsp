-- Valid SQL fixture for testing LSP diagnostics (should produce zero errors)
SELECT
    id,
    name,
    created_at
FROM users
WHERE active = true
ORDER BY created_at DESC
LIMIT 10;
