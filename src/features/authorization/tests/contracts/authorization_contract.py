"""Behavioural contract for any ``AuthorizationPort`` implementation.

The same scenarios run against the in-memory fake (in
``test_authorization_contract_in_memory``) and the SQLite-backed real
adapter (in ``test_authorization_contract_sqlmodel``) so a divergence
between the two surfaces in a single test failure rather than a fleet
of disagreeing tests.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from features.authorization.application.ports.authorization_port import (
    AuthorizationPort,
)
from features.authorization.application.types import Relationship


def _tuple(*, board_id: str, relation: str, user_id: UUID) -> Relationship:
    return Relationship(
        resource_type="thing",
        resource_id=board_id,
        relation=relation,
        subject_type="user",
        subject_id=str(user_id),
    )


class AuthorizationContract:
    """Subclass and override ``_make_adapter`` to bind the contract.

    Pytest collects the public ``test_*`` methods on the subclass.
    """

    def _make_adapter(self) -> AuthorizationPort:
        raise NotImplementedError

    # ── Hierarchy ─────────────────────────────────────────────────────────────

    def test_owner_satisfies_every_action(self) -> None:
        adapter = self._make_adapter()
        user_id, board_id = uuid4(), str(uuid4())
        adapter.write_relationships(
            [_tuple(board_id=board_id, relation="owner", user_id=user_id)]
        )
        for action in ("read", "update", "delete"):
            assert adapter.check(
                user_id=user_id,
                action=action,
                resource_type="thing",
                resource_id=board_id,
            ), action

    def test_writer_can_update_but_not_delete(self) -> None:
        adapter = self._make_adapter()
        user_id, board_id = uuid4(), str(uuid4())
        adapter.write_relationships(
            [_tuple(board_id=board_id, relation="writer", user_id=user_id)]
        )
        assert adapter.check(
            user_id=user_id,
            action="update",
            resource_type="thing",
            resource_id=board_id,
        )
        assert not adapter.check(
            user_id=user_id,
            action="delete",
            resource_type="thing",
            resource_id=board_id,
        )

    def test_reader_cannot_update(self) -> None:
        adapter = self._make_adapter()
        user_id, board_id = uuid4(), str(uuid4())
        adapter.write_relationships(
            [_tuple(board_id=board_id, relation="reader", user_id=user_id)]
        )
        assert not adapter.check(
            user_id=user_id,
            action="update",
            resource_type="thing",
            resource_id=board_id,
        )

    def test_no_grant_denies_every_action(self) -> None:
        adapter = self._make_adapter()
        for action in ("read", "update", "delete"):
            assert not adapter.check(
                user_id=uuid4(),
                action=action,
                resource_type="thing",
                resource_id=str(uuid4()),
            )

    # ── Lookup ────────────────────────────────────────────────────────────────

    def test_lookup_resources_returns_authorized_ids(self) -> None:
        adapter = self._make_adapter()
        user_id = uuid4()
        owned, written, read = (str(uuid4()) for _ in range(3))
        adapter.write_relationships(
            [
                _tuple(board_id=owned, relation="owner", user_id=user_id),
                _tuple(board_id=written, relation="writer", user_id=user_id),
                _tuple(board_id=read, relation="reader", user_id=user_id),
            ]
        )
        result = set(
            adapter.lookup_resources(
                user_id=user_id, action="read", resource_type="thing"
            )
        )
        assert result == {owned, written, read}

    def test_lookup_subjects_includes_higher_relations(self) -> None:
        adapter = self._make_adapter()
        board_id = str(uuid4())
        owner, writer = uuid4(), uuid4()
        adapter.write_relationships(
            [
                _tuple(board_id=board_id, relation="owner", user_id=owner),
                _tuple(board_id=board_id, relation="writer", user_id=writer),
            ]
        )
        readers = set(
            adapter.lookup_subjects(
                resource_type="thing", resource_id=board_id, relation="reader"
            )
        )
        assert readers == {owner, writer}

    # ── Idempotency ───────────────────────────────────────────────────────────

    def test_duplicate_writes_are_idempotent(self) -> None:
        adapter = self._make_adapter()
        user_id, board_id = uuid4(), str(uuid4())
        tup = _tuple(board_id=board_id, relation="owner", user_id=user_id)
        adapter.write_relationships([tup, tup])
        adapter.write_relationships([tup])
        assert adapter.check(
            user_id=user_id,
            action="read",
            resource_type="thing",
            resource_id=board_id,
        )

    def test_delete_of_unknown_tuple_is_a_noop(self) -> None:
        adapter = self._make_adapter()
        # Should not raise and should leave any unrelated state alone.
        adapter.delete_relationships(
            [_tuple(board_id=str(uuid4()), relation="reader", user_id=uuid4())]
        )
