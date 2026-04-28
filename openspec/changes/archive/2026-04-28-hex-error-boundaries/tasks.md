## 1. Error taxonomy and boundary contract

- [x] 1.1 Define canonical application error categories and stable codes for business, conflict, availability, validation, and internal failures.
- [x] 1.2 Implement a boundary translation component that maps infrastructure exceptions to application errors.
- [x] 1.3 Remove direct infrastructure exception handling from inbound HTTP adapters.

## 2. HTTP mapping and payload standardization

- [x] 2.1 Create deterministic mapping table from application error category to HTTP status.
- [x] 2.2 Standardize error response schema fields and ensure consistent serialization across routers.
- [x] 2.3 Publish breaking-change migration notes for clients consuming legacy error semantics.

## 3. Verification and observability

- [x] 3.1 Add tests for infrastructure-to-application translation behavior.
- [x] 3.2 Add API contract tests for status and payload consistency per error category.
- [x] 3.3 Add structured logging assertions for translated technical failures.
