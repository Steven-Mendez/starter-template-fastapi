## Depends on

(none) — this change is independent and can land at any time.

## Conflicts with

- `add-error-reporting-seam` — both bind to `APP_OTEL_TRACES_SAMPLER_RATIO`. The Sentry adapter reads the same ratio; if both land together, share the value and document the coupling. No hard ordering.
- `propagate-trace-context-through-jobs` — the outbox relay span shape (per-row child spans) defined here is the same shape that change consumes via the `__trace` payload key. Land this first or coordinate the span name (`outbox.dispatch_row`).
- `expose-domain-metrics` — both edit `src/app_platform/observability/__init__.py` / `metrics.py`. No hard ordering; flag merge friction.
- `harden-auth-defense-in-depth` — also edits `login_user.py` (timing-equalization refactor). Merge-friction only.
- `redact-pii-and-tokens-in-logs` — both touch `dispatch_pending.py` (per-row span vs. payload-log redaction). Apply redaction inside the spanned scope so attributes inherit the same hygiene; no hard ordering.

## Context

OTel auto-instrumentation is generous; production traces are noisy unless sampled. Use-case spans are the missing complement: HTTP and SQL spans tell you where time went *in the request*, but only application spans tell you which *use case* was running. Pairing them is what makes "slow login" debuggable.

## Decisions

- **Default sampler ratio 1.0 in dev, 0.1 in production**: dev wants every trace; production wants enough signal to detect issues without flooding the collector. Ratio is a single env var; operators tune as they observe.
- **`@traced` decorator on application-layer functions**: keeps the instrumentation declarative. Span name is hand-picked (`auth.login_user`), not derived from function path (which changes on refactor).
- **No PII in attributes**: `user.email_hash` (a deterministic short hash), never `user.email`. Same rule applies to all attributes.

## Risks / Trade-offs

- **Risk**: a decorator with `record_exception=True` swallows the original exception's traceback in some configs. Mitigation: we don't catch; the decorator only records and re-raises.
- **Trade-off**: decorator adds a span-start round trip per call (~1 µs). Trivial.

## Non-goals

- Tail-based sampling. The decision is per-trace at root span start (head-based); promoting interesting traces by latency/error tag is a collector-side feature, not a producer-side one.
- A full APM replacement. Decorators cover hot-path use cases; comprehensive coverage (every adapter, every infra call) is intentionally out of scope.
- Log-trace correlation injection. Trace IDs on log records belong to a separate change; this one only emits spans.
- New domain metrics. Instruments are a meter concern (`expose-domain-metrics`); this change is spans + attributes only.
- OTLP-over-gRPC. The HTTP exporter wired today stays; gRPC is not introduced.

## Migration

Single PR. Rollback: revert. No persistence.
