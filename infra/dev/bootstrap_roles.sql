-- Run once per cluster as a superuser. Passwords come from psql variables:
--   psql -v app_pw=... -v mig_pw=... -f bootstrap_roles.sql
CREATE ROLE resolveit_migrator LOGIN NOSUPERUSER NOBYPASSRLS CREATEROLE PASSWORD :'mig_pw';
CREATE ROLE resolveit_app      LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD :'app_pw';
CREATE ROLE resolveit_auth     NOLOGIN NOSUPERUSER BYPASSRLS;
GRANT resolveit_auth TO resolveit_migrator WITH ADMIN OPTION;
