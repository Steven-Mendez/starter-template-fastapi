"""Unit tests for ``ListBoardsUseCase`` authorization-driven filtering.

Confirms the use case asks the authorization port for accessible board ids
rather than relying on ``query_repository.list_all`` and post-filtering.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.features.authorization.application.ports.authorization_port import (
    LOOKUP_DEFAULT_LIMIT,
)
from src.features.kanban.application.ports.outbound import KanbanQueryRepositoryPort
from src.features.kanban.application.queries import ListBoardsQuery
from src.features.kanban.application.use_cases.board import ListBoardsUseCase
from src.features.kanban.domain.errors import KanbanError
from src.features.kanban.domain.models import Board, BoardSummary, Card
from src.platform.shared.result import Err, Ok, Result

pytestmark = pytest.mark.unit


class _FixedBoardRepo(KanbanQueryRepositoryPort):
    """Query repo returning a fixed set of summaries indexed by id."""

    def __init__(self, summaries: list[BoardSummary]) -> None:
        self._by_id = {s.id: s for s in summaries}
        self.last_ids: list[str] | None = None

    def list_all(self) -> list[BoardSummary]:
        return list(self._by_id.values())

    def list_by_ids(self, board_ids: list[str]) -> list[BoardSummary]:
        self.last_ids = list(board_ids)
        return [self._by_id[bid] for bid in board_ids if bid in self._by_id]

    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]:
        raise NotImplementedError

    def find_card_by_id(self, card_id: str) -> Result[Card, KanbanError]:
        raise NotImplementedError


class _RecordingAuthorization:
    """Records ``lookup_resources`` calls and returns a configured id list."""

    def __init__(self, ids: list[str]) -> None:
        self._ids = ids
        self.calls: list[tuple[UUID, str, str, int]] = []

    def lookup_resources(
        self,
        *,
        user_id: UUID,
        action: str,
        resource_type: str,
        limit: int = LOOKUP_DEFAULT_LIMIT,
    ) -> list[str]:
        self.calls.append((user_id, action, resource_type, limit))
        return list(self._ids)

    # The other AuthorizationPort methods are unused by this use case but are
    # required for protocol compliance; default to no-ops.
    def check(self, **_: object) -> bool:  # pragma: no cover
        return True

    def lookup_subjects(self, **_: object) -> list[UUID]:  # pragma: no cover
        return []

    def write_relationships(self, *_: object) -> None:  # pragma: no cover
        return None

    def delete_relationships(self, *_: object) -> None:  # pragma: no cover
        return None


def _summary(board_id: str) -> BoardSummary:
    return BoardSummary(
        id=board_id, title=f"Board {board_id}", created_at=datetime.now(timezone.utc)
    )


def test_anonymous_query_returns_empty_without_touching_repo() -> None:
    repo = _FixedBoardRepo([_summary("a")])
    authz = _RecordingAuthorization(["a"])
    use_case = ListBoardsUseCase(query_repository=repo, authorization=authz)

    result = use_case.execute(ListBoardsQuery(actor_id=None))

    assert isinstance(result, Ok)
    assert result.value == []
    assert authz.calls == []  # never asks the engine for an anonymous user
    assert repo.last_ids is None


def test_full_access_returns_every_summary_authz_lists() -> None:
    repo = _FixedBoardRepo([_summary("a"), _summary("b"), _summary("c")])
    authz = _RecordingAuthorization(["a", "b", "c"])
    user = uuid4()
    use_case = ListBoardsUseCase(query_repository=repo, authorization=authz)

    result = use_case.execute(ListBoardsQuery(actor_id=user))

    assert isinstance(result, Ok)
    assert {s.id for s in result.value} == {"a", "b", "c"}
    assert authz.calls == [(user, "read", "kanban", 500)]
    assert repo.last_ids == ["a", "b", "c"]


def test_partial_access_filters_to_authorized_ids_only() -> None:
    repo = _FixedBoardRepo([_summary("a"), _summary("b"), _summary("c")])
    authz = _RecordingAuthorization(["b"])
    user = uuid4()
    use_case = ListBoardsUseCase(query_repository=repo, authorization=authz)

    result = use_case.execute(ListBoardsQuery(actor_id=user))

    assert isinstance(result, Ok)
    assert [s.id for s in result.value] == ["b"]


def test_no_access_skips_repo_call_entirely() -> None:
    repo = _FixedBoardRepo([_summary("a")])
    authz = _RecordingAuthorization([])
    user = uuid4()
    use_case = ListBoardsUseCase(query_repository=repo, authorization=authz)

    result = use_case.execute(ListBoardsQuery(actor_id=user))

    assert isinstance(result, Ok)
    assert result.value == []
    assert repo.last_ids is None  # the use case must short-circuit


def test_use_case_never_returns_an_err() -> None:
    """Listing is open-by-design: missing access is empty, not error."""
    repo = _FixedBoardRepo([])
    authz = _RecordingAuthorization([])
    use_case = ListBoardsUseCase(query_repository=repo, authorization=authz)
    result = use_case.execute(ListBoardsQuery(actor_id=uuid4()))
    assert not isinstance(result, Err)
