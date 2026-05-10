"""Cross-resource parent walk for computed inheritance.

Card and column resources do not store relationship tuples directly.
A ``check("read", "card", id)`` resolves by walking the parent chain
``card → column → board`` and evaluating the equivalent check on the
parent board. This avoids unbounded write amplification when a board
membership is granted (which would otherwise fan out to every card and
column on the board).

The ``ParentResolver`` Protocol is the only seam between auth's
authorization engine and kanban's persistence — auth never imports
kanban; the resolver instance is wired by the composition root.
"""

from __future__ import annotations

from typing import Protocol


class ParentResolver(Protocol):
    """Resolve the parent kanban resource for a given child resource id.

    The default in-process implementation is provided by the kanban
    feature's lookup repository at composition time; tests can substitute
    a fake.
    """

    def board_id_for_card(self, card_id: str) -> str | None:
        """Return the parent board id for ``card_id``, or ``None`` if absent.

        SHALL NOT raise: a missing card should produce a denied check, not
        an exception. Soft-deleted cards are treated as absent.
        """
        ...

    def board_id_for_column(self, column_id: str) -> str | None:
        """Return the parent board id for ``column_id``, or ``None`` if absent."""
        ...


def resolve_board_id(
    resolver: ParentResolver, resource_type: str, resource_id: str
) -> str | None:
    """Walk the resource chain to the owning board id.

    For ``kanban`` the input is already a board id. For ``column`` /
    ``card`` the resolver performs the parent walk. Returns ``None`` if
    the resource (or any parent) does not exist; callers should treat
    that as a denied check.
    """
    if resource_type == "kanban":
        return resource_id
    if resource_type == "column":
        return resolver.board_id_for_column(resource_id)
    if resource_type == "card":
        return resolver.board_id_for_card(resource_id)
    return None
