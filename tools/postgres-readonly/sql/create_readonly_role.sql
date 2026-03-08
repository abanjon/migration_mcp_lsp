-- One-time setup script for local MCP read-only role.
-- Run this as an admin user and replace role/password/database placeholders.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'client_mcp_readonly') THEN
        CREATE ROLE client_mcp_readonly
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOINHERIT
            NOREPLICATION
            NOBYPASSRLS
            PASSWORD 'replace_me';
    END IF;
END
$$;

ALTER ROLE client_mcp_readonly SET default_transaction_read_only = on;
ALTER ROLE client_mcp_readonly SET statement_timeout = '30s';
ALTER ROLE client_mcp_readonly SET idle_in_transaction_session_timeout = '15s';

GRANT CONNECT ON DATABASE client_database TO client_mcp_readonly;
GRANT USAGE ON SCHEMA public TO client_mcp_readonly;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO client_mcp_readonly;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO client_mcp_readonly;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
GRANT SELECT ON TABLES TO client_mcp_readonly;
