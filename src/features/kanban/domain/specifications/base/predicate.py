"""Specification wrapper for callable predicates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeVar

from src.features.kanban.domain.specifications.base.specification import Specification

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class PredicateSpecification(Specification[T]):
    """Adapt a plain callable into a :class:`Specification` so it can be composed."""

    predicate: Callable[[T], bool]

    def is_satisfied_by(self, candidate: T) -> bool:
        return self.predicate(candidate)
