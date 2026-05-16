# authentication Specification Delta — remove-oauth-dead-config

## MODIFIED Requirements

### Requirement: Every documented production refusal has a unit test

The test suite SHALL contain a unit test for every entry in the production validator (the existing entries listed in `CLAUDE.md` and the new entries added by this proposal). Each test MUST assert that the relevant unsafe configuration produces an error mentioning the corresponding env var AND that the validator raises (boot fails). The settings surface SHALL NOT carry configuration fields for unimplemented features: every `APP_AUTH_*` field on `AppSettings` and every field on the `AuthenticationSettings` projection MUST correspond to behavior the running system actually consumes. A field whose only runtime effect is a startup log line announcing that it does nothing is dead configuration and MUST NOT exist.

#### Scenario: Existing refusals covered

- **GIVEN** `src/app_platform/tests/test_settings.py`
- **WHEN** the file is loaded
- **THEN** it contains tests covering, at minimum: `APP_AUTH_RBAC_ENABLED=false`, `APP_STORAGE_BACKEND=local` with `APP_STORAGE_ENABLED=true`, and `APP_AUTH_REQUIRE_DISTRIBUTED_RATE_LIMIT=true` without `APP_AUTH_REDIS_URL`
- **AND** each test asserts the validator raises rather than warning

#### Scenario: New refusals covered

- **GIVEN** `src/app_platform/tests/test_settings.py`
- **WHEN** the file is loaded
- **THEN** it contains tests for: short HS JWT secret, wildcard `trusted_hosts`, unset/non-HTTPS `app_public_url`, and `app_public_url` host outside `cors_origins`

#### Scenario: No placeholder OAuth config exists in the settings surface

- **WHEN** the codebase is loaded
- **THEN** `src/app_platform/config/settings.py` defines no `auth_oauth_enabled`, `auth_oauth_google_client_id`, `auth_oauth_google_client_secret`, or `auth_oauth_google_redirect_uri` field
- **AND** `src/features/authentication/composition/settings.py` defines no `oauth_*` field on `AuthenticationSettings` and assigns no `oauth_*` value in `from_app_settings`
- **AND** `src/features/authentication/composition/container.py` defines no `_warn_unused_oauth_settings` function and calls no such function from `build_auth_container`
- **AND** no test asserts a startup warning for unimplemented OAuth settings

#### Scenario: No placeholder OAuth config is documented as an operator tunable

- **WHEN** `.env.example` and `docs/operations.md` are loaded
- **THEN** `.env.example` declares no `APP_AUTH_OAUTH_*` key
- **AND** `docs/operations.md` contains no `OAuth Preparation` section and no `APP_AUTH_OAUTH_*` row in its env-var reference table
