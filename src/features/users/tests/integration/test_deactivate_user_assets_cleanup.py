"""End-to-end coverage for ``DeactivateUser`` → relay → cleanup handler.

Drives the full asset-cleanup pipeline against real adapters:

- ``LocalFileStorageAdapter`` for the per-user blob prefix.
- ``SQLModelOutboxRepository`` + ``DispatchPending`` for the relay tick.
- The in-process ``JobQueuePort`` adapter for the worker tick.
- ``FileStorageUserAssetsAdapter`` as the cleanup port implementation.

Asserts the scenario described in the change-delta spec:

- A ``delete_user_assets`` row is written in the deactivation transaction.
- One relay tick + one worker tick deletes every blob under
  ``users/{user_id}/`` and the outbox row reaches ``delivered``.
- A user with no blobs still transitions to ``delivered`` on the first
  tick (handler idempotency on the empty prefix).

The S3 (moto-backed) variant is parametrized so the same scenario
exercises both backends. ``moto`` ships in the dev-deps so this does
not require Docker beyond the testcontainer Postgres.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import timedelta
from pathlib import Path
from uuid import UUID

import boto3
import pytest
from moto import mock_aws
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app_platform.shared.result import Err, Ok
from features.background_jobs.adapters.outbound.in_process import (
    InProcessJobQueueAdapter,
)
from features.background_jobs.application.registry import JobHandlerRegistry
from features.file_storage.adapters.outbound.local import LocalFileStorageAdapter
from features.file_storage.adapters.outbound.s3 import S3FileStorageAdapter
from features.file_storage.application.ports.file_storage_port import FileStoragePort
from features.outbox.adapters.outbound.sqlmodel.models import OutboxMessageTable
from features.outbox.adapters.outbound.sqlmodel.repository import (
    SQLModelOutboxRepository,
)
from features.outbox.adapters.outbound.sqlmodel.unit_of_work import (
    SQLModelOutboxUnitOfWork,
)
from features.outbox.application.use_cases.dispatch_pending import DispatchPending
from features.users.adapters.outbound.file_storage_user_assets import (
    FileStorageUserAssetsAdapter,
    user_prefix,
)
from features.users.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelUserRepository,
)
from features.users.application.use_cases.deactivate_user import (
    DELETE_USER_ASSETS_JOB,
    DeactivateUser,
)
from features.users.composition.jobs import register_delete_user_assets_handler

pytestmark = pytest.mark.integration


# Storage factories: yield a (port, list_keys_callable) so the test
# can assert blob presence without depending on the concrete backend.
StorageFactory = Callable[[Path], tuple[FileStoragePort, Callable[[str], list[str]]]]


def _local_storage_factory(
    tmp_path: Path,
) -> tuple[FileStoragePort, Callable[[str], list[str]]]:
    adapter = LocalFileStorageAdapter(root=tmp_path / "storage")

    def list_keys(prefix: str) -> list[str]:
        result = adapter.list(prefix)
        assert isinstance(result, Ok)
        return sorted(result.value)

    return adapter, list_keys


_S3_BUCKET = "users-cleanup-test"
_S3_REGION = "us-east-1"


@pytest.fixture
def _aws_mock() -> Iterator[None]:
    with mock_aws():
        client = boto3.client("s3", region_name=_S3_REGION)
        client.create_bucket(Bucket=_S3_BUCKET)
        yield


def _s3_storage_factory(
    _tmp_path: Path,
) -> tuple[FileStoragePort, Callable[[str], list[str]]]:
    client = boto3.client("s3", region_name=_S3_REGION)
    adapter = S3FileStorageAdapter(bucket=_S3_BUCKET, region=_S3_REGION, client=client)

    def list_keys(prefix: str) -> list[str]:
        result = adapter.list(prefix)
        assert isinstance(result, Ok)
        return sorted(result.value)

    return adapter, list_keys


_STORAGE_BACKENDS = pytest.mark.parametrize(
    "storage_factory",
    [_local_storage_factory, _s3_storage_factory],
    ids=["local", "s3-moto"],
)


def _create_user(engine: Engine, *, email: str = "u@example.com") -> UUID:
    repo = SQLModelUserRepository(engine=engine)
    result = repo.create(email=email)
    assert isinstance(result, Ok)
    return result.value.id


def _build_relay(engine: Engine, queue: InProcessJobQueueAdapter) -> DispatchPending:
    return DispatchPending(
        _repository=SQLModelOutboxRepository(_engine=engine),
        _job_queue=queue,
        _batch_size=10,
        _max_attempts=5,
        _worker_id="users-integration-test",
        _retry_base=timedelta(seconds=30.0),
        _retry_max=timedelta(seconds=900.0),
    )


def _all_outbox_rows(engine: Engine) -> list[OutboxMessageTable]:
    with Session(engine, expire_on_commit=False) as session:
        return list(session.exec(select(OutboxMessageTable)).all())


def _build_deactivate_use_case(
    engine: Engine,
) -> tuple[DeactivateUser, SQLModelUserRepository]:
    repo = SQLModelUserRepository(engine=engine)
    outbox_uow = SQLModelOutboxUnitOfWork.from_engine(engine)
    use_case = DeactivateUser(_users=repo, _outbox_uow=outbox_uow)
    return use_case, repo


@pytest.mark.usefixtures("_aws_mock")
@_STORAGE_BACKENDS
def test_deactivate_user_cleans_up_blobs_after_relay_and_worker_tick(
    postgres_users_engine: Engine,
    tmp_path: Path,
    storage_factory: StorageFactory,
) -> None:
    storage, list_keys = storage_factory(tmp_path)
    user_id = _create_user(postgres_users_engine)

    # Upload 3 blobs under the per-user prefix and one decoy under a
    # different user's prefix; cleanup must touch only the target's.
    target_prefix = user_prefix(user_id)
    for name in ("avatar.png", "banner.png", "doc.txt"):
        put_result = storage.put(
            f"{target_prefix}{name}", b"x", "application/octet-stream"
        )
        assert isinstance(put_result, Ok)
    other_user = UUID("00000000-0000-0000-0000-000000000999")
    decoy_key = f"{user_prefix(other_user)}avatar.png"
    storage.put(decoy_key, b"y", "application/octet-stream")

    assert len(list_keys(target_prefix)) == 3

    # Wire the worker side: registry + in-process queue + handler with
    # a dedupe callable backed by ``processed_outbox_messages``.
    from features.outbox.composition.handler_dedupe import build_handler_dedupe

    registry = JobHandlerRegistry()
    register_delete_user_assets_handler(
        registry,
        FileStorageUserAssetsAdapter(_storage=storage),
        dedupe=build_handler_dedupe(postgres_users_engine),
    )
    registry.seal()
    queue = InProcessJobQueueAdapter(registry=registry)

    # Deactivate inside the outbox transaction. After this returns the
    # outbox row exists with ``status='pending'`` (no relay tick yet).
    use_case, _ = _build_deactivate_use_case(postgres_users_engine)
    deactivate_result = use_case.execute(user_id)
    assert isinstance(deactivate_result, Ok)

    rows = _all_outbox_rows(postgres_users_engine)
    assert len(rows) == 1
    assert rows[0].job_name == DELETE_USER_ASSETS_JOB
    assert rows[0].payload == {"user_id": str(user_id)}
    assert rows[0].status == "pending"

    # Run one relay tick — the in-process queue dispatches the handler
    # synchronously, so this single call covers both the "relay tick"
    # and the "worker tick" the spec mentions.
    relay = _build_relay(postgres_users_engine, queue)
    report = relay.execute()
    assert report.dispatched == 1
    assert report.retried == 0
    assert report.failed == 0

    # Target user's blobs are gone; the decoy is untouched.
    assert list_keys(target_prefix) == []
    decoy_listing = list_keys(user_prefix(other_user))
    assert decoy_listing == [decoy_key]

    # The outbox row reached ``delivered``.
    rows = _all_outbox_rows(postgres_users_engine)
    assert len(rows) == 1
    assert rows[0].status == "delivered"
    assert rows[0].delivered_at is not None


@pytest.mark.usefixtures("_aws_mock")
@_STORAGE_BACKENDS
def test_deactivate_user_with_no_blobs_still_reaches_delivered(
    postgres_users_engine: Engine,
    tmp_path: Path,
    storage_factory: StorageFactory,
) -> None:
    """Empty-prefix case: handler returns Ok immediately, row goes delivered."""
    storage, list_keys = storage_factory(tmp_path)
    user_id = _create_user(postgres_users_engine, email="empty@example.com")
    assert list_keys(user_prefix(user_id)) == []

    from features.outbox.composition.handler_dedupe import build_handler_dedupe

    registry = JobHandlerRegistry()
    register_delete_user_assets_handler(
        registry,
        FileStorageUserAssetsAdapter(_storage=storage),
        dedupe=build_handler_dedupe(postgres_users_engine),
    )
    registry.seal()
    queue = InProcessJobQueueAdapter(registry=registry)

    use_case, _ = _build_deactivate_use_case(postgres_users_engine)
    result = use_case.execute(user_id)
    assert isinstance(result, Ok)

    relay = _build_relay(postgres_users_engine, queue)
    report = relay.execute()
    assert report.dispatched == 1
    assert report.failed == 0

    rows = _all_outbox_rows(postgres_users_engine)
    assert len(rows) == 1
    assert rows[0].status == "delivered"


def test_cleanup_adapter_surfaces_backend_errors_as_err(
    postgres_users_engine: Engine,
) -> None:
    """A storage failure must surface as ``Err`` so the relay can retry."""

    class _BrokenStorage:
        def put(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
            raise NotImplementedError

        def get(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
            raise NotImplementedError

        def delete(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
            raise NotImplementedError

        def signed_url(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
            raise NotImplementedError

        def list(self, _prefix: str):  # type: ignore[no-untyped-def]
            from features.file_storage.application.errors import StorageBackendError

            return Err(StorageBackendError(reason="forced"))

    adapter = FileStorageUserAssetsAdapter(_storage=_BrokenStorage())
    result = adapter.delete_user_assets(UUID("11111111-1111-1111-1111-111111111111"))
    assert isinstance(result, Err)
