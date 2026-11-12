#!/usr/bin/env bash
# Start a throwaway local Postgres 16 for tests. Usage: pg_local.sh start|stop
set -euo pipefail
PGBIN="${PGBIN:-/usr/lib/postgresql/16/bin}"
DATA="${PGDATA_DIR:-/tmp/resolveit-pg}"
PORT="${PGPORT:-54329}"
RUN=""; [ "$(id -u)" = "0" ] && RUN="runuser -u postgres --"
case "${1:-start}" in
  start)
    if [ ! -d "$DATA" ]; then
      mkdir -p "$DATA"; [ -n "$RUN" ] && chown postgres "$DATA"
      $RUN "$PGBIN/initdb" -D "$DATA" -A trust -U postgres >/dev/null
    fi
    "$PGBIN/pg_isready" -h 127.0.0.1 -p "$PORT" -q || $RUN "$PGBIN/pg_ctl" -D "$DATA" -o "-p $PORT -c listen_addresses=127.0.0.1 -k /tmp" -l "$DATA/log" -w start >/dev/null
    psql() { "$PGBIN/psql" -h 127.0.0.1 -p "$PORT" -U postgres -v ON_ERROR_STOP=1 -q "$@"; }
    if ! psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='resolveit_app'" | grep -q 1; then
      psql -v app_pw=app_dev_pw -v mig_pw=mig_dev_pw -f "$(dirname "$0")/bootstrap_roles.sql"
    fi
    echo "postgres up on 127.0.0.1:$PORT" ;;
  stop) $RUN "$PGBIN/pg_ctl" -D "$DATA" -m fast stop >/dev/null; echo stopped ;;
esac
