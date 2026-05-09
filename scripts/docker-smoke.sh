#!/usr/bin/env bash
set -euo pipefail

if ! docker info >/dev/null 2>&1; then
  echo "Docker is required for docker-smoke but is not available."
  exit 1
fi

image="${DOCKER_SMOKE_IMAGE:-starter-template-fastapi:ci-local}"
container="starter-template-docker-smoke-$$"

cleanup() {
  docker stop "$container" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

docker build --target runtime -t "$image" .

docker run --rm -d \
  --name "$container" \
  -e APP_AUTH_JWT_SECRET_KEY=ci-test-secret-key-min-32-chars \
  -e APP_ENVIRONMENT=development \
  -p "127.0.0.1::8000" \
  "$image" >/dev/null

port="$(docker port "$container" 8000/tcp)"
port="${port##*:}"
url="http://127.0.0.1:${port}/health/live"

for _ in {1..15}; do
  if curl -fsS "$url" >/dev/null; then
    echo "Docker smoke liveness probe passed."
    exit 0
  fi
  sleep 2
done

docker logs "$container" || true
curl -fsS "$url"
