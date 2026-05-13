## ADDED Requirements

### Requirement: docker-compose provides an SMTP catcher for dev

`docker-compose.yml` SHALL include a `mailpit` service exposing SMTP on `1025` and the UI on `8025`. `.env.example` SHALL include commented env-var examples wiring the SMTP backend to the catcher.

The `app` service SHALL declare `restart: unless-stopped` and a `healthcheck` hitting `/health/live`.

#### Scenario: Mailpit catches a password-reset email

- **GIVEN** a developer runs `docker compose up` and switches `APP_EMAIL_BACKEND=smtp` + `APP_EMAIL_SMTP_HOST=mailpit`
- **WHEN** the developer triggers a password reset
- **THEN** the email appears in the Mailpit UI at `http://localhost:8025`

#### Scenario: App service marked unhealthy when /health/live fails

- **GIVEN** the `app` service is up but its `/health/live` endpoint returns a non-200 response (e.g. lifespan startup raised)
- **WHEN** the compose healthcheck retries past the configured `retries` budget
- **THEN** `docker compose ps` reports the `app` service as `unhealthy`
- **AND** the `restart: unless-stopped` policy attempts to restart it

#### Scenario: Default backend is unchanged

- **GIVEN** a developer runs `docker compose up` without overriding `APP_EMAIL_BACKEND`
- **WHEN** the API sends an email
- **THEN** the email is routed via the console backend (printed to stdout)
- **AND** no SMTP connection to the `mailpit` service is opened
