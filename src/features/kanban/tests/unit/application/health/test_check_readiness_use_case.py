from __future__ import annotations

import pytest

from src.features.kanban.application.queries import HealthCheckQuery
from src.features.kanban.application.use_cases.health.check_readiness import (
    CheckReadinessUseCase,
)
from src.features.kanban.tests.fakes import InMemoryKanbanRepository

pytestmark = pytest.mark.unit


def test_check_readiness_returns_true_when_ready() -> None:
    repo = InMemoryKanbanRepository()
    repo.set_ready(True)
    assert CheckReadinessUseCase(readiness=repo).execute(HealthCheckQuery()) is True


def test_check_readiness_returns_false_when_unhealthy() -> None:
    repo = InMemoryKanbanRepository()
    repo.set_ready(False)
    assert CheckReadinessUseCase(readiness=repo).execute(HealthCheckQuery()) is False
