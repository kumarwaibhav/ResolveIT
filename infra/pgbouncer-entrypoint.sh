#!/bin/sh
set -eu
case "${RESOLVEIT_APP_PASSWORD:-}" in
  ''|*[!a-zA-Z0-9_-]*) echo 'Generated app password required' >&2; exit 1 ;;
esac
umask 077
printf '"resolveit_app" "%s"\n' "$RESOLVEIT_APP_PASSWORD" > /tmp/resolveit-userlist.txt
exec pgbouncer /etc/resolveit/pgbouncer.ini
