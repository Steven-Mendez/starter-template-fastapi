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
APP_POSTGRESQL_DSN="$dsn" uv run alembic downgrade base
APP_POSTGRESQL_DSN="$dsn" uv run alembic upgrade head
