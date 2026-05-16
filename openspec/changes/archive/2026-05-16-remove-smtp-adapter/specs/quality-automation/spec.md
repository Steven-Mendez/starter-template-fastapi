## MODIFIED Requirements

### Requirement: docker-compose provides an SMTP catcher for dev

`docker-compose.yml` SHALL NOT ship a `mailpit` (or any other SMTP-catcher) service: the SMTP email backend no longer exists, so a local SMTP sink would catch traffic the default `console` backend never sends. `.env.example` SHALL NOT include `APP_EMAIL_SMTP_*` keys or a mailpit how-to comment block.

The `app` service SHALL declare `restart: unless-stopped` and a `healthcheck` hitting `/health/live`.

#### Scenario: No SMTP-catcher service is defined

- **GIVEN** the repository's `docker-compose.yml`
- **WHEN** `docker compose config --services` is listed
- **THEN** no `mailpit` service is present
- **AND** no remaining service declares a `depends_on` referencing `mailpit`

#### Scenario: App service marked unhealthy when /health/live fails

- **GIVEN** the `app` service is up but its `/health/live` endpoint returns a non-200 response (e.g. lifespan startup raised)
- **WHEN** the compose healthcheck retries past the configured `retries` budget
- **THEN** `docker compose ps` reports the `app` service as `unhealthy`
- **AND** the `restart: unless-stopped` policy attempts to restart it

#### Scenario: Default backend is unchanged

- **GIVEN** a developer runs `docker compose up` without overriding `APP_EMAIL_BACKEND`
- **WHEN** the API sends an email
- **THEN** the email is routed via the console backend (printed to stdout)
- **AND** no outbound SMTP connection is attempted by any code path
