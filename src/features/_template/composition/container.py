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
    """Per-feature container placeholder with one factory per use case."""

    repository: ExampleRepositoryPort

    def get_example_use_case(self) -> GetExampleUseCasePort:
        return GetExampleUseCase(repository=self.repository)
