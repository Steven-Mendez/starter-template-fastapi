## Why

Two dev-experience gaps in `docker-compose.yml`:

1. **No Mailpit / Mailhog service.** `APP_EMAIL_BACKEND=console` is the dev default, but contributors can never realistically exercise the `smtp` backend locally before shipping. SMTP edge cases (auth, TLS, large bodies, retry) are only caught in staging.
2. **`app` service has no healthcheck and no `restart` policy.** A crashed `dev` container stays down silently; `docker compose up` doesn't surface the failure.

## What Changes

- Add a `mailpit` service (`axllent/mailpit`) exposing `1025` (SMTP) and `8025` (UI). Document `APP_EMAIL_BACKEND=smtp APP_EMAIL_SMTP_HOST=mailpit APP_EMAIL_SMTP_PORT=1025` for local dev.
- Add `restart: unless-stopped` to the `app` service.
- Add a compose-level `healthcheck` on `app` hitting `/health/live` (depends on `add-readiness-probe` for `/health/ready` separately).

**Capabilities — Modified**: `quality-automation`.

## Impact

- **Code**: `docker-compose.yml`, `.env.example` comments.
- **Onboarding**: contributors can `docker compose up`, hit `http://localhost:8025`, and see emails from password-reset/verify flows.
