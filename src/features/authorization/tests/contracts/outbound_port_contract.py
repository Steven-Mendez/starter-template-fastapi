"""Behavioural contract for the three outbound ports auth implements.

Run by subclassing and overriding the ``_make_*`` factories. The fake
implementations and the real auth-side adapters MUST agree on this
contract — divergence shows up as a single test failure here rather
than as drift between unit and integration suites.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4


class UserAuthzVersionPortContract:
    """Subclass and override ``_make_port`` (and ``_seed_user`` when the
    implementation requires an existing user row before ``bump`` is
    observable via ``read_version``).
    """

    def _make_port(self) -> Any:
        raise NotImplementedError

    def _seed_user(self, port: Any) -> Any:
        """Return a ``user_id`` whose ``bump`` calls are observable.

        The default implementation issues a fresh ``UUID`` — sufficient
        for the in-memory fake whose ``read_version`` returns ``0`` for
        unknown users and increments unconditionally. SQLModel-backed
        implementors override this to insert a real ``users`` row first
        so the row-update bump and the row-read probe target the same
        primary key.
        """
        del port
        return uuid4()

    def test_bump_does_not_raise_for_unknown_user(self) -> None:
        # The contract allows a no-op when the user does not exist.
        self._make_port().bump(uuid4())

    def test_bump_accepts_multiple_distinct_users(self) -> None:
        port = self._make_port()
        port.bump(uuid4())
        port.bump(uuid4())

    def test_bump_in_session_method_exists(self) -> None:
        """Every implementor SHALL expose ``bump_in_session``.

        The session-aware bump is the seam authorization uses to
        commit the relationship write and the version bump atomically.
        The signature is checked here; the SQLModel-backed integration
        suite covers the transactional semantics with a real session.
        """
        port = self._make_port()
        assert callable(getattr(port, "bump_in_session", None))

    def test_read_version_is_zero_for_unknown_user(self) -> None:
        """Unknown users must surface as ``0`` rather than raising.

        Mirrors the no-op semantics of :meth:`bump`: callers (the
        principal-cache staleness check, the contract suite, ad-hoc
        admin probes) should be able to read a version without
        pre-checking existence.
        """
        port = self._make_port()
        assert port.read_version(uuid4()) == 0

    def test_bump_increments_read_version(self) -> None:
        """``bump`` MUST be observable: ``read_version`` returns a strictly
        larger value after the call. This is the probe the
        ``strengthen-test-contracts`` change adds — a silent ``pass`` in
        ``bump`` would previously satisfy the contract, masking a
        regression in the cache-invalidation path.
        """
        port = self._make_port()
        user_id = self._seed_user(port)
        before = port.read_version(user_id)
        port.bump(user_id)
        after = port.read_version(user_id)
        assert after > before, (
            f"bump did not increment read_version: before={before} after={after}"
        )

    def test_bump_repeated_increments_monotonically(self) -> None:
        """Two ``bump`` calls produce two strictly increasing reads."""
        port = self._make_port()
        user_id = self._seed_user(port)
        v0 = port.read_version(user_id)
        port.bump(user_id)
        v1 = port.read_version(user_id)
        port.bump(user_id)
        v2 = port.read_version(user_id)
        assert v0 < v1 < v2


class AuditPortContract:
    """Subclass and override ``_make_port`` and ``_read_events``.

    ``_read_events(port)`` returns the list of event-type strings
    persisted by the port so the contract can assert observability from
    a separate query path — not from the port's own write API. This is
    the gap the ``strengthen-test-contracts`` change closes: previously
    the contract only verified ``record`` "does not raise", which is
    satisfied by a no-op implementation.
    """

    def _make_port(self) -> Any:
        raise NotImplementedError

    def _read_events(self, port: Any) -> list[str]:
        raise NotImplementedError

    def test_record_accepts_a_minimal_event(self) -> None:
        self._make_port().record("authz.test_event")

    def test_record_accepts_user_id_and_metadata(self) -> None:
        self._make_port().record(
            "authz.test_event", user_id=uuid4(), metadata={"reason": "test"}
        )

    def test_recorded_event_is_observable(self) -> None:
        """A recorded event MUST be readable from a separate query.

        Asserting only "record does not raise" lets a silent-drop
        implementation slip through. Reading back the persisted event
        type proves the record actually landed.
        """
        port = self._make_port()
        port.record("authz.observable_event")
        events = self._read_events(port)
        assert "authz.observable_event" in events

    def test_multiple_records_are_all_observable(self) -> None:
        port = self._make_port()
        port.record("authz.event_one")
        port.record("authz.event_two", user_id=uuid4())
        port.record("authz.event_three", metadata={"k": "v"})
        events = self._read_events(port)
        assert {"authz.event_one", "authz.event_two", "authz.event_three"} <= set(
            events
        )
