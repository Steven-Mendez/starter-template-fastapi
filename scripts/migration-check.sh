#!/usr/bin/env bash
set -euo pipefail

if ! docker info >/dev/null 2>&1; then
  echo "Docker is required for migration-check but is not available."
  exit 1
fi

image="${MIGRATION_CHECK_POSTGRES_IMAGE:-postgres:16}"
container="starter-template-migration-check-$$"
database="kanban_ci"
username="postgres"
password="postgres"

cleanup() {
  docker stop "$container" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

docker run --rm -d \
  --name "$container" \
  -e POSTGRES_USER="$username" \
  -e POSTGRES_PASSWORD="$password" \
  -e POSTGRES_DB="$database" \
  -p "127.0.0.1::5432" \
  "$image" >/dev/null

for _ in {1..30}; do
  if docker exec "$container" pg_isready -U "$username" -d "$database" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! docker exec "$container" pg_isready -U "$username" -d "$database" >/dev/null 2>&1; then
  echo "PostgreSQL did not become ready in time."
  docker logs "$container" || true
  exit 1
fi

port="$(docker port "$container" 5432/tcp)"
port="${port##*:}"
dsn="postgresql+psycopg://${username}:${password}@127.0.0.1:${port}/${database}"

APP_POSTGRESQL_DSN="$dsn" uv run alembic upgrade head
APP_POSTGRESQL_DSN="$dsn" uv run alembic check

# Per the one-way migration policy (docs/operations.md#migration-policy),
# destructive migrations raise NotImplementedError in downgrade(). A full
# unwind to ``base`` would hit them, so we round-trip only the reversible
# tail — every migration newer than the most recent NotImplementedError
# downgrade — then re-upgrade to head.
floor_rev="$(
  uv run python <<'PY'
import re
from pathlib import Path

versions = Path("alembic/versions")
files = sorted(versions.glob("*.py"))
one_way: list[str] = []
for path in files:
    text = path.read_text()
    # Naive but sufficient: the downgrade body contains NotImplementedError.
    if re.search(r"def downgrade\(\)[^\n]*:\s*\n(?:[^\n]*\n){0,10}\s*raise NotImplementedError", text):
        m = re.search(r"^revision\s*[:=].*?['\"]([^'\"]+)['\"]", text, re.M)
        if m:
            one_way.append(m.group(1))
# Filenames are timestamp-ordered, so the last entry is the most recent.
print(one_way[-1] if one_way else "base")
PY
)"

if [ "$floor_rev" = "base" ]; then
  APP_POSTGRESQL_DSN="$dsn" uv run alembic downgrade base
else
  echo "Round-tripping reversible migrations newer than ${floor_rev} (one-way floor)."
  APP_POSTGRESQL_DSN="$dsn" uv run alembic downgrade "$floor_rev"
fi
APP_POSTGRESQL_DSN="$dsn" uv run alembic upgrade head
