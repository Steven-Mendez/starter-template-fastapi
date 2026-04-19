from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeVar

from src.domain.kanban.specifications.base.specification import Specification

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class PredicateSpecification(Specification[T]):
    predicate: Callable[[T], bool]

    def is_satisfied_by(self, candidate: T) -> bool:
        return self.predicate(candidate)
