#!/bin/sh
# entrypoint.sh — run DB migrations then start the Litestar server.
# Used by the container image so a fresh Postgres doesn't crash with
# "relation does not exist" on first boot (the README docker-compose
# quickstart relies on this).
set -e

echo "[entrypoint] running Piccolo migrations…"
uv run piccolo migrations forwards db || {
  echo "[entrypoint] WARNING: db migrations failed — the app may crash if tables are missing." >&2
}

exec "$@"