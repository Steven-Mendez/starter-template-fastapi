"""Pin the redacted field set between ``UserPublic`` and ``UserPublicSelf``.

The architectural contract from the ``hide-internal-fields-from-self-views``
proposal is that the only field redacted on self-views is the internal
cache-invalidation counter ``authz_version``. Encoding the symmetric
difference of the two schemas' field sets as an exact match means any
future addition or removal on either schema forces a deliberate decision
(and a test update), rather than silently re-leaking — or accidentally
hiding — a field on one side of the split.
"""

from __future__ import annotations

import pytest

from features.users.adapters.inbound.http.schemas import (
    UserPublic,
    UserPublicSelf,
)

pytestmark = pytest.mark.unit


def test_user_public_and_user_public_self_differ_only_by_authz_version() -> None:
    """Self-view drops exactly ``{"authz_version"}`` versus the admin view.

    Asserted as a symmetric difference so this also catches the
    reverse failure mode — a field that exists on ``UserPublicSelf``
    but not on ``UserPublic``. The self projection must be a strict
    subset of the admin projection minus the redacted set.
    """
    diff = set(UserPublic.model_fields.keys()).symmetric_difference(
        set(UserPublicSelf.model_fields.keys())
    )
    assert diff == {"authz_version"}
