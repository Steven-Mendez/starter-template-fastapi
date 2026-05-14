"""Cursor codec + ``list_paginated`` keyset behavior."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from features.users.adapters.inbound.http.cursor import (
    InvalidCursorError,
    decode_cursor,
    encode_cursor,
)
from features.users.application.use_cases.list_users import ListUsers
from features.users.tests.fakes.fake_user_port import FakeUserPort

pytestmark = pytest.mark.unit


def test_cursor_round_trip_preserves_values() -> None:
    created = datetime(2026, 5, 1, 12, 34, 56, tzinfo=UTC)
    user_id = uuid4()
    token = encode_cursor(created, user_id)
    decoded_created, decoded_id = decode_cursor(token)
    assert decoded_created == created
    assert decoded_id == user_id


@pytest.mark.parametrize(
    "bad",
    [
        "not-valid-base64!!!",
        # Valid base64 but not JSON.
        "Zm9v",  # "foo"
        # Valid base64 JSON but missing fields.
        "eyJhIjogMX0=",  # {"a": 1}
        # Valid shape but bad datetime.
        "eyJjcmVhdGVkX2F0IjogIm5vdC1hLWRhdGUiLCAiaWQiOiAibm90LWEtdXVpZCJ9",
        "",
    ],
)
def test_decode_cursor_rejects_invalid_input(bad: str) -> None:
    with pytest.raises(InvalidCursorError):
        decode_cursor(bad)


def _seed(port: FakeUserPort, n: int) -> list[UUID]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    ids: list[UUID] = []
    # FakeUserPort.create stamps created_at internally; advance by replacing
    # the row each insert so timestamps are deterministic and ordered.
    for i in range(n):
        result = port.create(email=f"u{i}@example.com")
        user = result.value  # type: ignore[union-attr]
        # Replace with a deterministic created_at so ordering is stable.
        from dataclasses import replace

        port._s.users[user.id] = replace(user, created_at=base + timedelta(seconds=i))
        ids.append(user.id)
    return ids


def test_keyset_pagination_walks_every_row_exactly_once() -> None:
    port = FakeUserPort()
    seeded = _seed(port, 25)
    use_case = ListUsers(_users=port)

    seen: list[UUID] = []
    cursor: tuple[datetime, UUID] | None = None
    while True:
        page = use_case.execute(cursor=cursor, limit=10).value  # type: ignore[union-attr]
        if not page:
            break
        seen.extend(u.id for u in page)
        if len(page) < 10:
            break
        last = page[-1]
        cursor = (last.created_at, last.id)

    assert seen == seeded
    # No duplicates.
    assert len(set(seen)) == len(seen)


def test_keyset_pagination_under_concurrent_insert_visits_every_original_row() -> None:
    port = FakeUserPort()
    seeded = _seed(port, 20)
    use_case = ListUsers(_users=port)

    first = use_case.execute(cursor=None, limit=10).value  # type: ignore[union-attr]
    assert len(first) == 10

    # Insert a new user "after" the first page but before fetching the second.
    # The cursor must still terminate and visit each original row once.
    port.create(email="concurrent@example.com")

    cursor = (first[-1].created_at, first[-1].id)
    rest_seen: list[UUID] = []
    while True:
        page = use_case.execute(cursor=cursor, limit=10).value  # type: ignore[union-attr]
        if not page:
            break
        rest_seen.extend(u.id for u in page)
        if len(page) < 10:
            break
        last = page[-1]
        cursor = (last.created_at, last.id)

    all_seen = [u.id for u in first] + rest_seen
    # Every original seeded user appears once.
    for sid in seeded:
        assert all_seen.count(sid) == 1
