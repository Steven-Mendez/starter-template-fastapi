## MODIFIED Requirements

### Requirement: Every documented production refusal has a unit test

The test suite SHALL contain a unit test for every entry in the production validator (the existing entries listed in `CLAUDE.md` and the new entries added by this proposal). Each test MUST assert that the relevant unsafe configuration produces an error mentioning the corresponding env var AND that the validator raises (boot fails). The settings surface SHALL NOT carry configuration fields for unimplemented features: every `APP_AUTH_*` field on `AppSettings` and every field on the `AuthenticationSettings` projection MUST correspond to behavior the running system actually consumes. A field whose only runtime effect is a startup log line announcing that it does nothing is dead configuration and MUST NOT exist. The email-backend production refusal SHALL be expressed as "production refuses `console` and no other email backend is accepted" (there is no production email transport until AWS SES is added at a later roadmap step); the settings surface SHALL define no `email_resend_api_key` or `email_resend_base_url` field, and the test suite SHALL NOT assert that any email backend is accepted in production. The jobs-backend production refusal SHALL be expressed as "production refuses `in_process` and no other job backend is accepted" (there is no production job runtime until the AWS SQS adapter and a Lambda worker are added at a later roadmap step); the settings surface SHALL define no `jobs_redis_url`, `jobs_queue_name`, `jobs_keep_result_seconds_default`, `jobs_max_jobs`, or `jobs_job_timeout_seconds` field, and the test suite SHALL NOT assert that any job backend is accepted in production. The `APP_OUTBOX_ENABLED=true` production refusal is unchanged and SHALL retain its unit test.

#### Scenario: Existing refusals covered

- **GIVEN** `src/app_platform/tests/test_settings.py`
- **WHEN** the file is loaded
- **THEN** it contains tests covering, at minimum: `APP_AUTH_RBAC_ENABLED=false`, `APP_STORAGE_BACKEND=local` with `APP_STORAGE_ENABLED=true`, `APP_AUTH_REQUIRE_DISTRIBUTED_RATE_LIMIT=true` without `APP_AUTH_REDIS_URL`, and `APP_OUTBOX_ENABLED=false`
- **AND** each test asserts the validator raises rather than warning

#### Scenario: New refusals covered

- **GIVEN** `src/app_platform/tests/test_settings.py`
- **WHEN** the file is loaded
- **THEN** it contains tests for: short HS JWT secret, wildcard `trusted_hosts`, unset/non-HTTPS `app_public_url`, and `app_public_url` host outside `cors_origins`

#### Scenario: Email-backend refusal covered without an accept-path

- **GIVEN** `src/app_platform/tests/test_settings.py`
- **WHEN** the file is loaded
- **THEN** it contains a test asserting `APP_ENVIRONMENT=production` with `APP_EMAIL_BACKEND=console` raises a `ValidationError` whose message reports the email-backend problem
- **AND** that message does NOT instruct the operator to configure `resend` or `smtp`
- **AND** the file contains no `test_resend_backend_requires_api_key`, `test_resend_backend_requires_from`, or `test_production_accepts_resend_backend`
- **AND** no test asserts that any email backend is accepted in production

#### Scenario: Jobs-backend refusal covered without an accept-path

- **GIVEN** `src/app_platform/tests/test_settings.py`
- **WHEN** the file is loaded
- **THEN** it contains a test asserting `APP_ENVIRONMENT=production` with `APP_JOBS_BACKEND=in_process` (the only accepted value) raises a `ValidationError` whose message reports the jobs-backend problem
- **AND** that message does NOT instruct the operator to configure `arq` or set `APP_JOBS_REDIS_URL`
- **AND** the file contains no `test_arq_backend_requires_redis_url`
- **AND** no test asserts that any job backend is accepted in production
- **AND** `_VALID_PROD_ENV` declares no `APP_JOBS_BACKEND` or `APP_JOBS_REDIS_URL` entry, and every other production-refusal test that loads `_VALID_PROD_ENV` isolates the now-always-present jobs-backend error so it still asserts its own target refusal

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
