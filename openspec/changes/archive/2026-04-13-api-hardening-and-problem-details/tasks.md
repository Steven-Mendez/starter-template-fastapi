## 1. TDD for API Hardening Contracts

- [x] 1.1 Add failing integration tests for docs enabled/disabled behavior by environment settings.
- [x] 1.2 Add failing integration tests for CORS allowlist and trusted-host rejection behavior.
- [x] 1.3 Add failing tests for request ID propagation in success and error responses.

## 2. Implement Middleware and Settings

- [x] 2.1 Introduce settings for environment, docs visibility, CORS origins, and trusted hosts.
- [x] 2.2 Register CORS and TrustedHost middleware with safe development defaults and strict non-dev behavior.
- [x] 2.3 Implement request ID middleware and response header propagation to satisfy tests.

## 3. Refine Problem Details and Domain Error Mapping

- [x] 3.1 Add failing tests for domain error HTTP mapping (invalid card move vs not found).
- [x] 3.2 Update router/domain exception mapping to return semantically correct status codes.
- [x] 3.3 Extend Problem Details handlers for unexpected exceptions while preserving RFC 9457 structure.
- [x] 3.4 Make all API-hardening tests pass and run full non-e2e suite.
