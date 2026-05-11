"""Bind the AuthorizationPort contract to the in-memory fake.

Confirms the kanban e2e fixture's ``FakeAuthorization`` honours the same
behavioural contract as the real adapter, so divergence between them
shows up immediately rather than as inconsistent test results.
"""

from __future__ import annotations

import pytest

from src.features.authorization.tests.contracts.authorization_contract import (
    AuthorizationContract,
)
from src.features.authorization.tests.contracts.registry_helper import (
    make_test_registry,
)
from src.features.kanban.tests.e2e.conftest import FakeAuthorization

pytestmark = pytest.mark.unit


class TestInMemoryAuthorizationContract(AuthorizationContract):
    def _make_adapter(self) -> FakeAuthorization:
        return FakeAuthorization(registry=make_test_registry())
