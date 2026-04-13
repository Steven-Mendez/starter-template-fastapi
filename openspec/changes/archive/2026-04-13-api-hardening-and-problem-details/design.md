## Context

FastAPI supports production middleware patterns such as CORS and trusted host protection, but the starter currently does not codify these defaults. Error handling already emits Problem Details for some errors, yet domain and unexpected failures need clearer, consistent treatment.

## Goals / Non-Goals

**Goals:**
- Introduce secure-by-default middleware configuration for host and origin controls.
- Improve traceability with request identifiers in logs and problem responses.
- Align domain error mapping and Problem Details responses with clearer client semantics.

**Non-Goals:**
- Implement authentication/authorization flows in this change.
- Add distributed tracing infrastructure (OTel exporters) yet.
- Re-architect all router modules.

## Decisions

- Create typed settings for environment, CORS allowlist, trusted hosts, and docs visibility.
- Register middleware in app initialization with environment-aware defaults (strict outside local development).
- Add a request ID middleware that injects `X-Request-ID` when missing and reuses inbound value when present.
- Update domain error mapping so invalid state transitions map to 400 or 409, while missing resources remain 404.
- Extend Problem Details handlers for unhandled exceptions to avoid non-uniform payloads.

## Risks / Trade-offs

- [Overly strict host/origin config can block valid traffic] -> Provide explicit settings and safe local defaults.
- [More middleware adds minor latency] -> Keep middleware lightweight and avoid heavy per-request I/O.
- [Changed status codes may impact existing clients] -> Update tests and changelog notes with migration expectations.
