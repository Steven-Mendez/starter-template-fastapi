---
name: project-contract-test-pattern
description: how contract tests are structured in this repo — one base class subclassed per binding
metadata:
  type: project
---

Contract suites in this repo follow a Russian-doll pattern: one base class with the scenarios; concrete subclasses bind it to each implementation (fake + real adapter). Examples:

- `src/features/authorization/tests/contracts/authorization_contract.py` — base; subclassed by `test_authorization_contract_in_memory.py` (FakeAuthorizationAdapter) and `test_authorization_contract_sqlmodel.py` (SQLite-backed real adapter).
- `src/features/authentication/tests/contracts/rate_limiter_contract.py` — base; subclassed by `test_rate_limiter_contract.py` for `FixedWindowRateLimiter`, fakeredis-backed `RedisRateLimiter`, and real-Redis `RedisRateLimiter`.
- `src/features/authentication/tests/contracts/principal_cache_contract.py` — analogous shape for `InProcessPrincipalCache` / `RedisPrincipalCache`.

Two structural rules the `strengthen-test-contracts` change pinned:

1. **Parametrise, don't duplicate.** Separate `..._contract_fake.py` and `..._contract_real.py` files drift; one base class subclassed per binding does not.
2. **Fakes are strict by default.** `FakeEmailPort` takes the sealed `EmailTemplateRegistry`; `FakeJobQueue` defaults `known_jobs` to "raise on unknown". `permissive=True` is the explicit opt-out.

For real-adapter testcontainers parametrisations: skip cleanly when `KANBAN_SKIP_TESTCONTAINERS=1` or Docker is unavailable. The skip should surface at fixture resolution time, not inside the test body, so collection is fast either way.

**Why:** the "outbox contract claimed dual-binding but never ran against the real adapter" gap was the motivating bug. Single-class-per-binding makes drift impossible — adding a new binding is one subclass; adding a new scenario is one method on the base.

**How to apply:** when extending a port that has multiple production implementations, add the scenario to the base class once and let every existing subclass pick it up automatically. When adding a new adapter, subclass the base; do not copy-paste tests.
