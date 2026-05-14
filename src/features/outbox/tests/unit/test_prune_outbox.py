"""Unit tests for :class:`PruneOutbox`.

The use case loops three repository calls until each returns 0, then
returns a :class:`PruneSummary` of per-table counts. We drive it with
a tiny fake repository that records its calls and returns scripted
row counts.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass, field
from datetime import datetime
from uuid import UUID

import pytest

from app_platform.shared.result import Ok
from features.outbox.application.use_cases.maintenance.prune_outbox import (
    PruneOutbox,
    PruneSummary,
)
from features.outbox.domain.message import OutboxMessage

pytestmark = pytest.mark.unit


@dataclass(slots=True)
class _FakeRepo:
    """Records each delete call's args and returns scripted row counts.

    The scripts are consumed in FIFO order; the loop in
    :class:`PruneOutbox` ends as soon as the script returns ``0``.
    """

    delivered_returns: list[int] = field(default_factory=list)
    failed_returns: list[int] = field(default_factory=list)
    processed_returns: list[int] = field(default_factory=list)
    delivered_calls: list[tuple[datetime, int]] = field(default_factory=list)
    failed_calls: list[tuple[datetime, int]] = field(default_factory=list)
    processed_calls: list[tuple[datetime, int]] = field(default_factory=list)

    # The repo port also declares the relay methods; the unit test
    # never calls them but the Protocol-style port requires them to
    # exist for structural typing.
    def claim_batch(self, **_: object) -> list[OutboxMessage]:  # pragma: no cover
        return []

    def mark_delivered(self, *_: object, **__: object) -> None:  # pragma: no cover
        pass

    def mark_retry(self, *_: object, **__: object) -> None:  # pragma: no cover
        pass

    def mark_failed(self, *_: object, **__: object) -> None:  # pragma: no cover
        pass

    def delete_delivered_before(self, *, cutoff: datetime, limit: int) -> int:
        self.delivered_calls.append((cutoff, limit))
        return self.delivered_returns.pop(0) if self.delivered_returns else 0

    def delete_failed_before(self, *, cutoff: datetime, limit: int) -> int:
        self.failed_calls.append((cutoff, limit))
        return self.failed_returns.pop(0) if self.failed_returns else 0

    def delete_processed_marks_before(self, *, cutoff: datetime, limit: int) -> int:
        self.processed_calls.append((cutoff, limit))
        return self.processed_returns.pop(0) if self.processed_returns else 0


def test_summary_reports_totals_across_internal_iterations() -> None:
    """Counts accumulate across the per-table drain loop."""
    repo = _FakeRepo(
        delivered_returns=[100, 100, 50, 0],
        failed_returns=[20, 0],
        processed_returns=[200, 200, 0],
    )
    use_case = PruneOutbox(_repository=repo)
    result = use_case.execute(
        retention_delivered_days=7,
        retention_failed_days=30,
        dedup_retention_seconds=1800.0,
        batch_size=100,
    )
    assert isinstance(result, Ok)
    assert result.value == PruneSummary(
        delivered_deleted=250,
        failed_deleted=20,
        processed_marks_deleted=400,
    )


def test_loop_stops_when_repository_returns_zero() -> None:
    """A zero-return on the first call short-circuits cleanly."""
    repo = _FakeRepo()  # all scripts empty -> first call returns 0
    use_case = PruneOutbox(_repository=repo)
    result = use_case.execute(
        retention_delivered_days=7,
        retention_failed_days=30,
        dedup_retention_seconds=1800.0,
        batch_size=100,
    )
    assert isinstance(result, Ok)
    assert result.value == PruneSummary(0, 0, 0)
    # Exactly one call per table — the loop stops after the first 0.
    assert len(repo.delivered_calls) == 1
    assert len(repo.failed_calls) == 1
    assert len(repo.processed_calls) == 1


def test_batch_size_is_passed_to_each_repo_call() -> None:
    repo = _FakeRepo(
        delivered_returns=[5, 0],
        failed_returns=[3, 0],
        processed_returns=[7, 0],
    )
    use_case = PruneOutbox(_repository=repo)
    use_case.execute(
        retention_delivered_days=7,
        retention_failed_days=30,
        dedup_retention_seconds=1800.0,
        batch_size=250,
    )
    assert all(limit == 250 for _, limit in repo.delivered_calls)
    assert all(limit == 250 for _, limit in repo.failed_calls)
    assert all(limit == 250 for _, limit in repo.processed_calls)


def test_cutoffs_are_distinct_per_table() -> None:
    """Each table uses a different cutoff derived from its retention."""
    repo = _FakeRepo(
        delivered_returns=[0],
        failed_returns=[0],
        processed_returns=[0],
    )
    use_case = PruneOutbox(_repository=repo)
    use_case.execute(
        retention_delivered_days=7,
        retention_failed_days=30,
        dedup_retention_seconds=1800.0,
        batch_size=10,
    )
    delivered_cutoff, _ = repo.delivered_calls[0]
    failed_cutoff, _ = repo.failed_calls[0]
    processed_cutoff, _ = repo.processed_calls[0]
    # Delivered cutoff is 7d back; failed cutoff is 30d back; processed
    # cutoff is 30 minutes back. The relative ordering must be
    # processed > delivered > failed (most recent → oldest).
    assert processed_cutoff > delivered_cutoff > failed_cutoff


def test_prune_summary_is_frozen_dataclass() -> None:
    """PruneSummary is immutable so caller code cannot mutate counts."""
    summary = PruneSummary(1, 2, 3)
    with pytest.raises(FrozenInstanceError):
        summary.delivered_deleted = 99  # type: ignore[misc]


def _noop_uuid() -> UUID:  # pragma: no cover - kept to satisfy static analyzers
    """Placeholder kept for import symmetry with the integration tests."""
    return UUID("00000000-0000-0000-0000-000000000000")
