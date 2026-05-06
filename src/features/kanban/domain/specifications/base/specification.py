"""Base specification contract for composable domain predicates."""

from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")


class Specification(Generic[T]):
    """Base class for the Specification design pattern.

    Subclasses encode a single business rule by overriding
    :meth:`is_satisfied_by`. Combinator helpers (``and_spec``,
    ``or_spec``, ``not_spec``) return composite specifications, allowing
    rules to be assembled like algebraic expressions instead of nested
    ``if`` statements.
    """

    def is_satisfied_by(self, candidate: T) -> bool:
        """Return ``True`` if ``candidate`` matches this specification."""
        raise NotImplementedError

    def and_spec(self, other: Specification[T]) -> Specification[T]:
        """Composite spec satisfied when both ``self`` and ``other`` hold."""
        from src.features.kanban.domain.specifications.base.and_specification import (
            AndSpecification,
        )

        return AndSpecification(left=self, right=other)

    def or_spec(self, other: Specification[T]) -> Specification[T]:
        """Composite spec satisfied when ``self`` or ``other`` holds."""
        from src.features.kanban.domain.specifications.base.or_specification import (
            OrSpecification,
        )

        return OrSpecification(left=self, right=other)

    def not_spec(self) -> Specification[T]:
        """Return the negation of this specification."""
        from src.features.kanban.domain.specifications.base.not_specification import (
            NotSpecification,
        )

        return NotSpecification(inner=self)
