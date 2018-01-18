#!/bin/bash -eux

# Dév fixture initializing a cluster with a «previous state», needing a lot of
# synchronization. See openldap-data.ldif for details.

roles=($(psql -tc "SELECT rolname FROM pg_roles WHERE rolname NOT LIKE 'pg_%' AND rolname != 'postgres'"))
# This is tricky: https://stackoverflow.com/questions/7577052/bash-empty-array-expansion-with-set-u
roles=$(IFS=', ' ; echo ${roles[*]+"${roles[*]}"})

for d in template1 postgres ; do
    psql -v ON_ERROR_STOP=1 $d <<EOSQL
UPDATE pg_namespace SET nspacl = NULL WHERE nspname NOT LIKE 'pg_%';
GRANT USAGE ON SCHEMA information_schema TO PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO PUBLIC;
DO \$\$BEGIN
  IF '${roles}' <> '' THEN
    DROP OWNED BY ${roles:-pouet};
  END IF;
END\$\$;
DELETE FROM pg_default_acl;
EOSQL
done

psql -v ON_ERROR_STOP=1 <<EOSQL
-- Purge everything.
DROP DATABASE IF EXISTS olddb;
DROP DATABASE IF EXISTS appdb;
DO \$\$BEGIN
  IF '${roles}' <> '' THEN
    DROP ROLE ${roles:-pouet};
  END IF;
END\$\$;
UPDATE pg_database SET datacl = NULL WHERE datallowconn IS TRUE;
EOSQL

psql -v ON_ERROR_STOP=1 <<'EOSQL'
-- Create role as it should be. for NOOP
CREATE ROLE app WITH NOLOGIN;
CREATE ROLE daniel WITH LOGIN;
CREATE ROLE david WITH LOGIN;
CREATE ROLE denis WITH LOGIN;
CREATE ROLE alan WITH SUPERUSER LOGIN;
-- Create alice superuser without login, for ALTER.
CREATE ROLE alice WITH SUPERUSER NOLOGIN IN ROLE app;

-- Create spurious roles, for DROP.
CREATE ROLE old WITH LOGIN;
CREATE ROLE omar;
CREATE ROLE olivier;
CREATE ROLE oscar WITH LOGIN IN ROLE app, old;
CREATE ROLE œdipe;

-- Create databases
CREATE DATABASE olddb;
CREATE DATABASE appdb WITH OWNER app;

-- Revoke connect on group app so that revoke connect from public wont grant it
-- back.
REVOKE CONNECT ON DATABASE "appdb" FROM "app" ;

EOSQL

# Create a legacy table owned by a legacy user. For reassign before drop
# cascade.
PGDATABASE=olddb psql <<EOSQL
CREATE TABLE keepme (id serial PRIMARY KEY);
ALTER TABLE keepme OWNER TO oscar;
EOSQL

# grant some privileges to daniel, to be revoked.
PGDATABASE=olddb psql <<EOSQL
CREATE SCHEMA oldns;
CREATE TABLE oldns.table1 (id SERIAL);
GRANT SELECT ON ALL TABLES IN SCHEMA oldns TO daniel;

-- For REVOKE
GRANT USAGE ON SCHEMA oldns TO daniel;
ALTER DEFAULT PRIVILEGES IN SCHEMA oldns GRANT SELECT ON TABLES TO daniel;
EOSQL

# Ensure daniel has no privileges on appdb, for grant.
PGDATABASE=appdb psql <<'EOSQL'
CREATE TABLE public.table1 (id SERIAL);
CREATE VIEW public.view1 AS SELECT 'row0';

CREATE SCHEMA appns;
CREATE TABLE appns.table1 (id SERIAL);
CREATE TABLE appns.table2 (id SERIAL);

CREATE FUNCTION appns.func1() RETURNS text AS $$ SELECT 'Coucou!'; $$ LANGUAGE SQL;
CREATE FUNCTION appns.func2() RETURNS text AS $$ SELECT 'Coucou!'; $$ LANGUAGE SQL;

CREATE SCHEMA empty;

-- No grant to olivier.
-- Partial grant for revoke
GRANT SELECT ON TABLE appns.table1 TO omar;
-- full grant for revoke
GRANT SELECT ON ALL TABLES IN SCHEMA appns TO oscar;

-- No grant to denis, for first grant.
-- Partial grant for regrant
GRANT SELECT ON TABLE appns.table1 TO daniel;
-- Full grant for noop
GRANT SELECT ON ALL TABLES IN SCHEMA appns TO david;
EOSQL