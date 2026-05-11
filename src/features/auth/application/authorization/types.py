"""Value objects shared across the authorization port and adapters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Relationship:
    """A Zanzibar-style relationship tuple.

    Reads as: ``{subject_type}:{subject_id}`` has relation ``{relation}``
    on ``{resource_type}:{resource_id}``. For example, a
    ``Relationship("system", "main", "admin", "user", str(user_id))``
    means the user holds the ``admin`` relation on the ``system:main``
    resource.

    All fields are strings so the same record can describe future subject
    types (e.g., service accounts, group sets) without a schema migration.
    """

    resource_type: str
    resource_id: str
    relation: str
    subject_type: str
    subject_id: str
