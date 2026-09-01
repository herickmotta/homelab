-- Managed by herickmotta.homelab.data_platform.
-- Idempotent login roles for PostgREST, GoTrue, and ops_ledger.
-- Invoked as: psql -v pgpass=... -v jwt_secret=...

\set ON_ERROR_STOP on

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon NOLOGIN NOINHERIT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN NOINHERIT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    CREATE ROLE service_role NOLOGIN NOINHERIT BYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticator') THEN
    CREATE ROLE authenticator LOGIN NOINHERIT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'supabase_auth_admin') THEN
    CREATE ROLE supabase_auth_admin LOGIN NOINHERIT CREATEROLE;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ops_ledger_owner') THEN
    CREATE ROLE ops_ledger_owner NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ops_ledger_migrator') THEN
    CREATE ROLE ops_ledger_migrator NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ops_ledger_hermes') THEN
    CREATE ROLE ops_ledger_hermes NOLOGIN NOINHERIT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ops_ledger_readonly') THEN
    CREATE ROLE ops_ledger_readonly NOLOGIN NOINHERIT;
  END IF;
END
$$;

ALTER ROLE authenticator WITH PASSWORD :'pgpass';
ALTER ROLE supabase_auth_admin WITH PASSWORD :'pgpass';

GRANT anon TO authenticator;
GRANT authenticated TO authenticator;
GRANT service_role TO authenticator;
GRANT ops_ledger_hermes TO authenticator;
GRANT ops_ledger_readonly TO authenticator;

GRANT ops_ledger_owner TO postgres;
GRANT ops_ledger_migrator TO postgres;

ALTER DATABASE postgres SET "app.settings.jwt_secret" TO :'jwt_secret';
ALTER DATABASE postgres SET "app.settings.jwt_exp" TO '3600';
