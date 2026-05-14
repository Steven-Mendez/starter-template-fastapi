"""Cursor codec + ``list_audit_events`` keyset behavior."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from features.authentication.adapters.inbound.http.cursor import (
    InvalidCursorError,
    decode_cursor,
    encode_cursor,
)
from features.authentication.application.use_cases.admin.list_audit_events import (
    ListAuditEvents,
)
from features.authentication.domain.models import AuditEvent
from features.authentication.tests.fakes.fake_auth_repository import (
    FakeAuthRepository,
)

pytestmark = pytest.mark.unit


def test_cursor_round_trip_preserves_values() -> None:
    created = datetime(2026, 5, 1, 12, 34, 56, tzinfo=UTC)
    event_id = uuid4()
    token = encode_cursor(created, event_id)
    decoded_created, decoded_id = decode_cursor(token)
    assert decoded_created == created
    assert decoded_id == event_id


def test_decode_cursor_rejects_invalid_input() -> None:
    with pytest.raises(InvalidCursorError):
        decode_cursor("not-base64!!!")
    with pytest.raises(InvalidCursorError):
        decode_cursor("")


def _seed(repo: FakeAuthRepository, n: int) -> list[UUID]:
    """Insert n events with deterministic created_at; return ids newest-first."""
    base = datetime(2026, 1, 1, tzinfo=UTC)
    ids: list[UUID] = []
    for i in range(n):
        event = AuditEvent(
            id=uuid4(),
            user_id=None,
            event_type="auth.test",
            metadata={"i": i},
            created_at=base + timedelta(seconds=i),
            ip_address=None,
            user_agent=None,
        )
        repo._s.audit_events.append(event)
        ids.append(event.id)
    # Newest-first ordering.
    return list(reversed(ids))


def test_forward_pagination_walks_full_history_without_gaps_or_dupes() -> None:
    repo = FakeAuthRepository()
    expected_newest_first = _seed(repo, 25)
    use_case = ListAuditEvents(_repository=repo)

    seen: list[UUID] = []
    before: tuple[datetime, UUID] | None = None
    while True:
        page = use_case.execute(before=before, limit=10).value  # type: ignore[union-attr]
        if not page:
            break
        seen.extend(event.id for event in page)
        if len(page) < 10:
            break
        tail = page[-1]
        before = (tail.created_at, tail.id)

    assert seen == expected_newest_first
    assert len(set(seen)) == len(seen)
