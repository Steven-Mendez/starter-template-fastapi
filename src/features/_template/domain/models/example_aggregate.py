from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ExampleAggregate:
    """TODO(template): replace with your real aggregate root.

    Domain rules and invariants live here. Methods return new instances or
    a ``Result[T, E]`` from ``src.platform.shared.result`` for failure paths.
    """

    id: str
    name: str
