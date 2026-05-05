from __future__ import annotations

from dataclasses import dataclass

from src.features._template.application.ports.inbound.get_example import (
    GetExampleUseCasePort,
)
from src.features._template.application.ports.outbound.example_repository import (
    ExampleRepositoryPort,
)
from src.features._template.application.use_cases.get_example import GetExampleUseCase


@dataclass(slots=True)
class TemplateContainer:
    """TODO(template): per-feature container — factory methods per use case."""

    repository: ExampleRepositoryPort

    def get_example_use_case(self) -> GetExampleUseCasePort:
        return GetExampleUseCase(repository=self.repository)
