"""Specification combinator that requires both predicates to pass."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from src.features.kanban.domain.specifications.base.specification import Specification

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class AndSpecification(Specification[T]):
    left: Specification[T]
    right: Specification[T]

    def is_satisfied_by(self, candidate: T) -> bool:
        return self.left.is_satisfied_by(candidate) and self.right.is_satisfied_by(
            candidate
        )
