"""Specification pattern — base classes and combinators."""

from src.domain.kanban.specifications.base.and_specification import AndSpecification
from src.domain.kanban.specifications.base.not_specification import NotSpecification
from src.domain.kanban.specifications.base.or_specification import OrSpecification
from src.domain.kanban.specifications.base.predicate import PredicateSpecification
from src.domain.kanban.specifications.base.specification import Specification

__all__ = [
    "AndSpecification",
    "NotSpecification",
    "OrSpecification",
    "PredicateSpecification",
    "Specification",
]
