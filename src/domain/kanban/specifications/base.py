from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class Specification(Generic[T]):
    def is_satisfied_by(self, candidate: T) -> bool:
        raise NotImplementedError

    def and_spec(self, other: Specification[T]) -> Specification[T]:
        return AndSpecification(left=self, right=other)

    def or_spec(self, other: Specification[T]) -> Specification[T]:
        return OrSpecification(left=self, right=other)

    def not_spec(self) -> Specification[T]:
        return NotSpecification(inner=self)


@dataclass(frozen=True, slots=True)
class PredicateSpecification(Specification[T]):
    predicate: Callable[[T], bool]

    def is_satisfied_by(self, candidate: T) -> bool:
        return self.predicate(candidate)


@dataclass(frozen=True, slots=True)
class AndSpecification(Specification[T]):
    left: Specification[T]
    right: Specification[T]

    def is_satisfied_by(self, candidate: T) -> bool:
        return self.left.is_satisfied_by(candidate) and self.right.is_satisfied_by(
            candidate
        )


@dataclass(frozen=True, slots=True)
class OrSpecification(Specification[T]):
    left: Specification[T]
    right: Specification[T]

    def is_satisfied_by(self, candidate: T) -> bool:
        return self.left.is_satisfied_by(candidate) or self.right.is_satisfied_by(
            candidate
        )


@dataclass(frozen=True, slots=True)
class NotSpecification(Specification[T]):
    inner: Specification[T]

    def is_satisfied_by(self, candidate: T) -> bool:
        return not self.inner.is_satisfied_by(candidate)
