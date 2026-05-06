"""Specification combinator that negates a predicate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from src.features.kanban.domain.specifications.base.specification import Specification

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class NotSpecification(Specification[T]):
    """Composite that inverts the result of the wrapped specification."""

    inner: Specification[T]

    def is_satisfied_by(self, candidate: T) -> bool:
        return not self.inner.is_satisfied_by(candidate)
