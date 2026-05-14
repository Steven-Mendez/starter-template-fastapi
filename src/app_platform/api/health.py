"""Readiness probe (``/health/ready``) and its dependency checks.

The probe sits next to :func:`app_platform.api.root.health_live` and is
mounted by :mod:`app_platform.api.root`. Liveness stays a process-only
check returning 200 unconditionally; readiness probes every configured
dependency in parallel and is what a Kubernetes load balancer should
gate traffic on.

The lifespan flag (``app.state.ready``) is set as the LAST step of
startup (after every registry is sealed and every container is built)
and cleared as the FIRST step of shutdown. While the flag is unset or
False the probe short-circuits with ``503 {"status":"starting"}`` and
does NOT touch any dependency — this is the contract paired with
``add-graceful-shutdown`` (the shutdown finalizer flips the same flag).

Each dependency probe is bounded by
``APP_HEALTH_READY_PROBE_TIMEOUT_SECONDS`` (default 1.0 s). Probes run
in parallel via :func:`asyncio.gather` so the worst-case probe latency
is the slowest single dependency, not the sum.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app_platform.api.operation_ids import feature_operation_id

__all__ = ["health_router"]

_logger = logging.getLogger(__name__)

# Bound the per-dependency ``reason`` string written to the JSON body so a
# verbose client exception can't bloat the payload that kubelet logs scrape.
_MAX_REASON_LEN = 200
# Upper bound on the configurable per-dependency probe timeout. Kubelet
# readiness probes run on a ~10 s cadence, so 30 s is already permissive.
_MAX_HEALTH_READY_TIMEOUT_SECONDS = 30.0

health_router = APIRouter(
    tags=["health"],
    generate_unique_id_function=feature_operation_id,
)


async def _probe_db(engine: Any) -> None:
    """Run ``SELECT 1`` against the SQLAlchemy engine in a worker thread.

    SQLAlchemy's sync engine API blocks; running it on the event loop
    would stall the probe (and every other coroutine) for the duration
    of the round-trip. Off-loading to the default thread pool keeps the
    event loop free.
    """
    import sqlalchemy as sa

    def _run() -> None:
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))

    await asyncio.to_thread(_run)


async def _probe_redis(redis_client: Any) -> None:
    """Run ``PING`` against the synchronous ``redis.Redis`` client.

    The shared ``app.state.redis_client`` is the sync client; off-load
    the call so the event loop stays responsive.
    """

    def _run() -> None:
        redis_client.ping()

    await asyncio.to_thread(_run)


async def _probe_s3(bucket: str, region: str) -> None:
    """Run ``head_bucket`` against the configured S3 bucket.

    Constructs a fresh ``boto3`` client per probe — readiness probes
    run at kubelet cadence (every 10 s by default), so the
    construction overhead is negligible and keeps the probe stateless.
    """
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - dev install has boto3
        raise RuntimeError(
            "boto3 is not installed; install with: uv sync --extra s3"
        ) from exc

    def _run() -> None:
        client = boto3.client("s3", region_name=region)
        client.head_bucket(Bucket=bucket)

    await asyncio.to_thread(_run)


def _short_reason(exc: BaseException) -> str:
    """Return a one-line description of ``exc`` for the JSON body.

    Keeps the wire payload bounded even if the dependency client
    surfaces a verbose multi-line exception.
    """
    if isinstance(exc, TimeoutError):
        return "timeout"
    stripped = str(exc).strip()
    cls_name = exc.__class__.__name__
    message = stripped.splitlines()[0] if stripped else cls_name
    if len(message) > _MAX_REASON_LEN:
        message = message[: _MAX_REASON_LEN - 3] + "..."
    if message == cls_name:
        return message
    return f"{cls_name}: {message}"


async def _run_probe(
    name: str,
    coro: Any,
    timeout: float,  # noqa: ASYNC109 - probe seam takes the bound as a value
) -> tuple[str, dict[str, str]]:
    """Run a probe with ``asyncio.wait_for`` and return its JSON shape.

    Always returns ``(name, status_dict)`` so the gather aggregator can
    treat every dependency uniformly regardless of outcome. WARN logs
    are emitted on failure so operators see the dependency name and
    exception class even when the body is consumed by a kubelet.
    """
    try:
        await asyncio.wait_for(coro, timeout=timeout)
    except TimeoutError as exc:
        _logger.warning(
            "event=health.ready.fail dependency=%s exception=%s",
            name,
            exc.__class__.__name__,
        )
        return name, {"status": "fail", "reason": "timeout"}
    except Exception as exc:
        _logger.warning(
            "event=health.ready.fail dependency=%s exception=%s",
            name,
            exc.__class__.__name__,
        )
        return name, {"status": "fail", "reason": _short_reason(exc)}
    return name, {"status": "ok"}


@health_router.get("/health/ready")
async def health_ready(request: Request) -> Response:
    """Readiness probe.

    Returns 200 when the lifespan has completed AND every configured
    dependency responds within its timeout. Returns 503 with
    ``{"status":"starting"}`` while startup is still in progress (no
    ``Retry-After`` header — kubelet's own backoff is sufficient).
    Returns 503 with a ``Retry-After: 1`` header and a named failing
    dependency when any probe times out or raises.
    """
    state = request.app.state
    if not getattr(state, "ready", False):
        return JSONResponse(status_code=503, content={"status": "starting"})

    container = getattr(state, "container", None)
    if container is None:  # pragma: no cover - lifespan invariant
        return JSONResponse(status_code=503, content={"status": "starting"})
    settings = container.settings

    timeout = settings.health_ready_probe_timeout_seconds
    engine = getattr(state, "health_db_engine", None)
    redis_client = getattr(state, "redis_client", None)

    tasks: list[Any] = []
    if engine is not None:
        tasks.append(_run_probe("db", _probe_db(engine), timeout))
    if redis_client is not None:
        tasks.append(_run_probe("redis", _probe_redis(redis_client), timeout))
    if (
        getattr(settings, "storage_enabled", False)
        and getattr(settings, "storage_backend", None) == "s3"
        and getattr(settings, "storage_s3_bucket", None)
    ):
        tasks.append(
            _run_probe(
                "s3",
                _probe_s3(settings.storage_s3_bucket, settings.storage_s3_region),
                timeout,
            )
        )

    results: dict[str, dict[str, str]] = {}
    if tasks:
        gathered = await asyncio.gather(*tasks)
        results = dict(gathered)

    has_failure = any(payload["status"] == "fail" for payload in results.values())
    deps_view: dict[str, Any] = {}
    for name, payload in results.items():
        if payload["status"] == "ok":
            deps_view[name] = "ok"
        else:
            deps_view[name] = {"status": "fail", "reason": payload["reason"]}

    if has_failure:
        return JSONResponse(
            status_code=503,
            content={"status": "fail", "deps": deps_view},
            headers={"Retry-After": "1"},
        )
    return JSONResponse(status_code=200, content={"status": "ok", "deps": deps_view})
