from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ExampleAggregate:
    """Placeholder aggregate root for a copied feature.

    Domain rules and invariants live here. Methods return new instances or
    a ``Result[T, E]`` from ``src.platform.shared.result`` for failure paths.
    """

    id: str
    name: str
