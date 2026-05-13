## Context

Local dev is the contributor's first impression. Email is the most common surface that breaks differently in dev vs prod (the console backend "just works", the SMTP backend has timing/auth/TLS subtleties). Mailpit closes that gap with one extra container.

## Decisions

- **Mailpit over Mailhog**: Mailhog is unmaintained; Mailpit is actively developed and ships a nicer UI.
- **No required swap**: console backend stays the default so contributors who don't care can ignore Mailpit.
- **Healthcheck targets `/health/live` today**: the route exists. Once `add-readiness-probe` lands, the compose healthcheck SHOULD migrate to `/health/ready` so contributors see a red service while the lifespan is still sealing — but that swap is a follow-up of this change, not a precondition.

## Non-goals

- Not a full devcontainer / Codespaces definition — `docker-compose.yml` remains a runtime stack, not an editor environment.
- Not a production compose file — the Mailpit service and the loose port bindings are dev-only.
- Not a swap of the platform default email backend — `APP_EMAIL_BACKEND=console` stays the default; Mailpit is opt-in.
- Not a replacement for Resend / SMTP integration tests — Mailpit catches what would be sent; it is not a substitute for the existing SMTP contract tests.

## Risks / Trade-offs

- **Risk**: contributors leave Mailpit running and forget the UI is publicly bound on 8025. Mitigation: documented; localhost-only by default.

## Depends on

- None. The healthcheck targets the already-existing `/health/live` route.

## Conflicts with

- `docker-compose.yml` (note: the file in this repo is `compose.yml` / `docker-compose.yml` — the audit lists `docker-compose.yml`) is currently only touched by this change.
- `.env.example` is shared with `fix-bootstrap-admin-escalation`, `harden-rate-limiting`, `strengthen-production-validators`, `redact-pii-and-tokens-in-logs`. This change only adds commented lines; no logical overlap.
- Follow-up: once `add-readiness-probe` ships, change the compose healthcheck `test` to hit `/health/ready` so the dev experience matches the K8s probe.

## Migration

Single PR. Additive only.
