## ADDED Requirements

### Requirement: Principal cache TTL default is lowered from 30 to 5 seconds
The system ALREADY exposes `APP_AUTH_PRINCIPAL_CACHE_TTL_SECONDS` (`AppSettings.auth_principal_cache_ttl_seconds`, default `30`). This change SHALL lower the default value to `5` seconds. The setting itself, the env var name, the wiring in `auth/composition/container.py:116/121`, and the consumers in `cache.py` SHALL remain unchanged.

The hard-coded fallback `ttl: int = 30` in `InProcessPrincipalCache.create(...)` (`src/features/auth/application/cache.py:49`) SHALL be updated to default to `5` so the in-process default matches the settings default.

#### Scenario: Default TTL is 5 seconds
- **WHEN** `AppSettings()` is constructed with no `APP_AUTH_PRINCIPAL_CACHE_TTL_SECONDS` value set
- **THEN** `settings.auth_principal_cache_ttl_seconds == 5`

#### Scenario: TTL remains configurable via environment
- **WHEN** `APP_AUTH_PRINCIPAL_CACHE_TTL_SECONDS=60` is set in the environment
- **THEN** `settings.auth_principal_cache_ttl_seconds == 60` and both `InProcessPrincipalCache` and `RedisPrincipalCache` use this value

#### Scenario: Permission change propagates within TTL window
- **WHEN** a permission is revoked from a user and `APP_AUTH_PRINCIPAL_CACHE_TTL_SECONDS=5`
- **THEN** within 5 seconds (worst case) the next request reflects the revocation in the resolved `Principal`

#### Scenario: Existing settings test cases are updated
- **WHEN** the existing settings tests run after the default change
- **THEN** any test that asserted the default of `30` is updated to assert `5`; no new test failures are introduced
