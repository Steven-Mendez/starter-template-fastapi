"""Bind the AuthorizationPort contract to the in-memory fake.

The same scenarios that exercise :class:`SQLModelAuthorizationAdapter` in
``test_authorization_contract_sqlmodel`` run here against
:class:`FakeAuthorizationAdapter`. Any divergence between the fake and
the real adapter — the bug class that motivated
``strengthen-test-contracts`` — surfaces as a contract-test failure in a
single file rather than as drift between the unit suite and the real
adapter.
"""

from __future__ import annotations

import pytest

from features.authorization.tests.contracts.authorization_contract import (
    AuthorizationContract,
)
from features.authorization.tests.contracts.fake_user_authz_version import (
    FakeUserAuthzVersionPort,
)
from features.authorization.tests.contracts.registry_helper import (
    make_test_registry,
)
from features.authorization.tests.fakes.fake_authorization_adapter import (
    FakeAuthorizationAdapter,
)

pytestmark = pytest.mark.unit


class TestInMemoryAuthorizationContract(AuthorizationContract):
    def _make_adapter(self) -> FakeAuthorizationAdapter:
        return FakeAuthorizationAdapter(
            registry=make_test_registry(),
            user_authz_version=FakeUserAuthzVersionPort(),
        )
