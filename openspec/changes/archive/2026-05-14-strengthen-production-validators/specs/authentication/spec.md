## ADDED Requirements

### Requirement: Production validator refuses unsafe configuration

`AppSettings.validate_production()` SHALL refuse to start the application (raise from `__init__` or the equivalent boot path) when `APP_ENVIRONMENT=production` and any of the listed conditions hold. The validator MUST NOT have a warn-only mode; every offence MUST be a hard failure. The returned error list MUST name the offending env var so operators can fix the issue without reading source.

The previously documented refusals (`APP_AUTH_JWT_SECRET_KEY` unset, wildcard CORS, console email backend, in-process job backend, `APP_AUTH_RETURN_INTERNAL_TOKENS=true`, etc.) are unchanged. The list is extended with:

- `auth_jwt_algorithm` starts with `HS` AND `len(auth_jwt_secret_key) < 32`.
- `trusted_hosts` contains `"*"` or any wildcard pattern.
- `app_public_url` is unset, OR not HTTPS, OR has an empty host, OR its host does not appear in `cors_origins` (after scheme/port normalization).

#### Scenario: Short HS secret refused in production

- **GIVEN** `APP_ENVIRONMENT=production`, `APP_AUTH_JWT_ALGORITHM=HS256`, `APP_AUTH_JWT_SECRET_KEY=hunter2hunter2`
- **WHEN** `AppSettings.validate_production()` runs
- **THEN** the error list contains a message naming `APP_AUTH_JWT_SECRET_KEY`
- **AND** the message recommends `openssl rand -hex 32`
- **AND** boot fails (the validator raises)

#### Scenario: Wildcard trusted hosts refused in production

- **GIVEN** `APP_ENVIRONMENT=production`, `APP_TRUSTED_HOSTS=*`
- **WHEN** the validator runs
- **THEN** the error list names `APP_TRUSTED_HOSTS`
- **AND** boot fails

#### Scenario: Non-HTTPS public URL refused in production

- **GIVEN** `APP_ENVIRONMENT=production`, `APP_PUBLIC_URL=http://app.example.com`
- **WHEN** the validator runs
- **THEN** the error list names `APP_PUBLIC_URL`
- **AND** boot fails

#### Scenario: Public-URL host outside CORS origins refused

- **GIVEN** `APP_ENVIRONMENT=production`, `APP_PUBLIC_URL=https://malicious.example`, `APP_CORS_ORIGINS=https://app.example.com`
- **WHEN** the validator runs
- **THEN** the error list names both `APP_PUBLIC_URL` and `APP_CORS_ORIGINS`
- **AND** boot fails

## ADDED Requirements

### Requirement: Argon2 parameters are pinned in source

The `PasswordHasher` used by `authentication` SHALL be constructed with explicit parameters that meet OWASP 2024 recommendations: `time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16`. The parameters MUST NOT be sourced from environment variables; rotation is an explicit code change accompanied by a code review.

#### Scenario: Constructed hasher exposes pinned parameters

- **WHEN** a unit test imports the configured `PasswordHasher` from `src/features/authentication/application/crypto.py`
- **THEN** `hasher.time_cost == 3`
- **AND** `hasher.memory_cost == 65536`
- **AND** `hasher.parallelism == 4`
- **AND** `hasher.hash_len == 32`
- **AND** `hasher.salt_len == 16`

### Requirement: Every documented production refusal has a unit test

The test suite SHALL contain a unit test for every entry in the production validator (the existing entries listed in `CLAUDE.md` and the new entries added by this proposal). Each test MUST assert that the relevant unsafe configuration produces an error mentioning the corresponding env var AND that the validator raises (boot fails).

#### Scenario: Existing refusals covered

- **GIVEN** `src/app_platform/tests/test_settings.py`
- **WHEN** the file is loaded
- **THEN** it contains tests covering, at minimum: `APP_AUTH_RBAC_ENABLED=false`, `APP_STORAGE_BACKEND=local` with `APP_STORAGE_ENABLED=true`, and `APP_AUTH_REQUIRE_DISTRIBUTED_RATE_LIMIT=true` without `APP_AUTH_REDIS_URL`
- **AND** each test asserts the validator raises rather than warning

#### Scenario: New refusals covered

- **GIVEN** `src/app_platform/tests/test_settings.py`
- **WHEN** the file is loaded
- **THEN** it contains tests for: short HS JWT secret, wildcard `trusted_hosts`, unset/non-HTTPS `app_public_url`, and `app_public_url` host outside `cors_origins`
