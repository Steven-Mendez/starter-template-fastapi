from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")


class Specification(Generic[T]):
    def is_satisfied_by(self, candidate: T) -> bool:
        raise NotImplementedError

    def and_spec(self, other: Specification[T]) -> Specification[T]:
        from src.domain.kanban.specifications.base.and_specification import (
            AndSpecification,
        )

        return AndSpecification(left=self, right=other)

    def or_spec(self, other: Specification[T]) -> Specification[T]:
        from src.domain.kanban.specifications.base.or_specification import (
            OrSpecification,
        )

        return OrSpecification(left=self, right=other)

    def not_spec(self) -> Specification[T]:
        from src.domain.kanban.specifications.base.not_specification import (
            NotSpecification,
        )

        return NotSpecification(inner=self)
