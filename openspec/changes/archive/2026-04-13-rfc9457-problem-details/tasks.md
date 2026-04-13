## 1. Specification-driven artifacts

- [x] 1.1 Add OpenSpec change `rfc9457-problem-details` with proposal, design, capability spec, and tasks (this file).

## 2. Tests first (TDD)

- [x] 2.1 Add integration tests that assert `application/problem+json` and RFC 9457 core members for `404` (`HTTPException`) and `422` (validation and application-level unprocessable).

## 3. Implementation

- [x] 3.1 Implement Problem Details model and register FastAPI exception handlers; wire from `main.py`.
- [x] 3.2 Run the full test suite and fix any regressions.
