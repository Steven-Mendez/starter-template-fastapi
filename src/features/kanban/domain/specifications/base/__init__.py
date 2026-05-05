"""Specification pattern — base classes and combinators."""

from src.features.kanban.domain.specifications.base.and_specification import (
    AndSpecification,
)
from src.features.kanban.domain.specifications.base.not_specification import (
    NotSpecification,
)
from src.features.kanban.domain.specifications.base.or_specification import (
    OrSpecification,
)
from src.features.kanban.domain.specifications.base.predicate import (
    PredicateSpecification,
)
from src.features.kanban.domain.specifications.base.specification import Specification

__all__ = [
    "AndSpecification",
    "NotSpecification",
    "OrSpecification",
    "PredicateSpecification",
    "Specification",
]
