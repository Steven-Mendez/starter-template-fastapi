## 1. Mailpit

- [x] 1.1 Add to `docker-compose.yml`:
  ```yaml
  mailpit:
    image: axllent/mailpit:latest
    ports: ["1025:1025", "8025:8025"]
    restart: unless-stopped
  ```
- [x] 1.2 Add commented env vars in `.env.example` showing how to point the SMTP backend at it.

## 2. App service hardening

- [x] 2.1 Add `restart: unless-stopped` to the `app` service.
- [x] 2.2 Add `healthcheck: { test: ["CMD-SHELL", "python -c \"import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health/live', timeout=2).status==200 else 1)\""], interval: 10s, timeout: 3s, retries: 3, start_period: 15s }`. Use python (always present in the base image) rather than `curl`, which is not on `python:3.12-slim`. `start_period` gives the lifespan time to seal registries before health checks start.

## 3. Docs

- [x] 3.1 Update `docs/development.md` (or `CLAUDE.md`) with the Mailpit UI URL and the swap procedure.
- [x] 3.2 `make ci` green.
