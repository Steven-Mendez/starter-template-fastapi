"""Specification combinator that accepts either predicate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from src.features.kanban.domain.specifications.base.specification import Specification

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class OrSpecification(Specification[T]):
    """Composite that holds when either wrapped specification is satisfied."""

    left: Specification[T]
    right: Specification[T]

    def is_satisfied_by(self, candidate: T) -> bool:
        return self.left.is_satisfied_by(candidate) or self.right.is_satisfied_by(
            candidate
        )
