## Context

`/health/live` (registered in `src/app_platform/api/root.py:23`) answers "is the process alive?" — cheap, returns 200 always. There is no `/health/ready` route — the tracing/metrics URL exclusion lists already reference it, but the route is never registered. K8s rolling deploys will route traffic the moment the process accepts TCP — before DB warm-up or registry sealing — and after a Postgres restart the pod will never drop out of rotation.

## Decisions

- **Path is `/health/ready`** (matches the existing `/health/live` prefix). The probe sits next to the liveness route in `src/app_platform/api/health.py` (new) and is mounted by `src/app_platform/api/root.py`.
- **Liveness already exists**: no separate `/healthz/live` route is added.
- **Dependencies probed**: PostgreSQL (`SELECT 1` against the engine) AND Redis `PING` when `APP_AUTH_REDIS_URL` or `APP_JOBS_REDIS_URL` is configured. S3 (`head_bucket`) is probed only when `APP_STORAGE_ENABLED=true` and `APP_STORAGE_BACKEND=s3`. Each probe is run in parallel via `asyncio.gather` so the worst-case probe latency is bounded by the slowest single dependency, not their sum.
- **Per-dependency timeout 1.0 s**, overridable via `APP_HEALTH_READY_PROBE_TIMEOUT_SECONDS`. Kubelet probes typically run every 10 s; a dependency probe slower than 1 s is itself a problem we want to surface as "not ready" rather than letting it pile up.
- **Lifespan flag is in-memory, not Redis**: readiness is per-replica. Each replica decides its own state. The flag is set at the end of the FastAPI lifespan startup (after registries are sealed and containers are built) and cleared at the start of shutdown (so the probe goes red the instant SIGTERM lands).
- **Return 503 with named failing dependency**, not generic. Operators reading the kubelet event stream want to know "Redis is down on pod-3", not "ready returned false". The 503 response also carries `Retry-After: 1`.

## Risks / Trade-offs

- **Risk**: a flapping dependency makes pods bounce in/out of the load balancer. Mitigation: K8s readiness probe `failureThreshold: 3` is the operator-side control; we don't override it.
- **Trade-off**: each probe adds a connection round-trip every kubelet poll (default 10 s). Negligible.

## Depends on

- None hard. Pairs with `add-graceful-shutdown` (the shutdown finalizer clears the same readiness flag) and `improve-dev-compose-ux` (compose healthcheck currently targets `/health/live`; a future iteration can target `/health/ready`).

## Conflicts with

- `src/main.py` lifespan is also touched by `add-graceful-shutdown`, `clean-architecture-seams`, `fix-bootstrap-admin-escalation`, `make-auth-flows-transactional`. The readiness flag must be set as the last step of startup and (per `add-graceful-shutdown`) cleared as the first step of shutdown.
- `src/app_platform/api/root.py` adds the new route; no overlap, but the file is shared with `add-graceful-shutdown` only insofar as `root.py` may import from `health.py`.

## Non-goals

- Replacing kubelet liveness with a deep check. `/health/live` stays a process-only 200 — only `/health/ready` probes dependencies.
- Multi-replica coordination of readiness state. Each replica owns its own flag; we do not share readiness through Redis or any external store.
- Auto-tuning per-dependency timeouts. The single `APP_HEALTH_READY_PROBE_TIMEOUT_SECONDS` knob applies uniformly; operators tune per environment.
- Auth on `/health/ready`. The probe is unauthenticated; do not put it behind the API gateway's auth layer.

## Migration

Single PR. Rollback by reverting; no persistence.
