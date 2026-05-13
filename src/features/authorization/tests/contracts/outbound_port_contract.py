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
    """Subclass and override ``_make_port``."""

    def _make_port(self) -> Any:
        raise NotImplementedError

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


class AuditPortContract:
    """Subclass and override ``_make_port``."""

    def _make_port(self) -> Any:
        raise NotImplementedError

    def test_record_accepts_a_minimal_event(self) -> None:
        self._make_port().record("authz.test_event")

    def test_record_accepts_user_id_and_metadata(self) -> None:
        self._make_port().record(
            "authz.test_event", user_id=uuid4(), metadata={"reason": "test"}
        )
