"""Runtime registry of resource types, actions, hierarchies, and parent walks.

The registry is the single seam between the authorization engine and the
rest of the system. A feature contributes resource types to the engine by
calling ``register_resource_type`` (for "leaf" types that own stored
relationship tuples) or ``register_parent`` (for "inherited" types that
delegate to a parent via a feature-supplied callable).

The composition root calls ``seal()`` after every feature has registered
its types; subsequent registration attempts raise. Read methods stay
callable for the lifetime of the registry.

Zanzibar parallel
=================
``register_resource_type`` is the rough equivalent of a ``definition`` in
a Zanzibar-style schema: a resource type with its actions (permissions)
and the relation hierarchy that satisfies them. ``register_parent``
expresses computed userset rewrites — an inherited resource type
borrows its permissions from a parent type and exposes a callable that
maps a child id to the parent. The engine walks the chain at check
time; a real ReBAC backend would materialize the implied tuples instead.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from features.authorization.application.errors import UnknownActionError

ParentLookup = Callable[[str], tuple[str, str] | None]


@dataclass(slots=True)
class _LeafEntry:
    actions: dict[str, frozenset[str]]
    hierarchy: dict[str, frozenset[str]]


@dataclass(slots=True)
class _ParentEntry:
    parent_of: ParentLookup
    inherits_from: str


@dataclass(slots=True)
class AuthorizationRegistry:
    """Mutable registry that the engine reads on every check.

    Two roles are explicit at the registration boundary:

    * ``register_resource_type`` declares a *leaf* type — one whose
      relationship tuples are persisted in the storage backend. The
      caller supplies the action map and the relation hierarchy.
    * ``register_parent`` declares an *inherited* type — one whose
      checks resolve by walking to a parent via the supplied callable
      and evaluating the parent's permissions. The inherited type reuses
      its ``inherits_from`` ancestor's actions and hierarchy.

    Multi-level walks (e.g., ``card → column → board``) compose
    naturally: the engine iterates ``parent_of`` until it lands on a
    leaf type. There is no special-case logic for any particular feature.
    """

    _leaves: dict[str, _LeafEntry] = field(default_factory=dict)
    _parents: dict[str, _ParentEntry] = field(default_factory=dict)
    _sealed: bool = False

    # ── Registration API ────────────────────────────────────────────────────

    def register_resource_type(
        self,
        resource_type: str,
        *,
        actions: dict[str, frozenset[str]],
        hierarchy: dict[str, frozenset[str]],
    ) -> None:
        """Declare a leaf resource type with its action map and hierarchy.

        Raises:
            RuntimeError: If the registry has been ``seal()``-ed.
            ValueError: If ``resource_type`` was already registered (with
                either ``register_resource_type`` or ``register_parent``).
        """
        self._guard_unsealed()
        self._guard_unique(resource_type)
        self._leaves[resource_type] = _LeafEntry(actions=actions, hierarchy=hierarchy)

    def register_parent(
        self,
        resource_type: str,
        *,
        parent_of: ParentLookup,
        inherits_from: str,
    ) -> None:
        """Declare an inherited resource type that walks to ``inherits_from``.

        ``parent_of`` returns ``(parent_type, parent_id)`` for a child id,
        or ``None`` if the child does not exist; the engine treats ``None``
        as a denied check. ``inherits_from`` names the resource type
        ``resource_type`` borrows its actions and hierarchy from. It does
        not have to be a leaf — multi-level chains are resolved at lookup
        time by following ``inherits_from`` recursively.

        Raises:
            RuntimeError: If the registry has been ``seal()``-ed.
            ValueError: If ``resource_type`` was already registered.
        """
        self._guard_unsealed()
        self._guard_unique(resource_type)
        self._parents[resource_type] = _ParentEntry(
            parent_of=parent_of, inherits_from=inherits_from
        )

    def seal(self) -> None:
        """Freeze the registry; further register calls raise ``RuntimeError``."""
        self._sealed = True

    # ── Read API used by the engine ─────────────────────────────────────────

    def relations_for(self, resource_type: str, action: str) -> frozenset[str]:
        """Return the relation set that satisfies ``action`` on ``resource_type``.

        Inherited types delegate up the ``inherits_from`` chain until a
        leaf is found. Unknown types or actions raise ``UnknownActionError``
        — the HTTP layer maps that to 500 so the bug surfaces in
        integration testing instead of as a silent 403.
        """
        leaf = self._resolve_leaf(resource_type)
        relations = leaf.actions.get(action)
        if relations is None:
            raise UnknownActionError(
                f"Unknown action {action!r} for resource_type {resource_type!r}"
            )
        return relations

    def expand_relations(
        self, resource_type: str, relations: frozenset[str]
    ) -> frozenset[str]:
        """Return every relation that, if held, satisfies any input relation.

        For a resource type registered with the ``owner ⊇ writer ⊇ reader``
        hierarchy, expanding ``{"reader"}`` returns ``{reader, writer, owner}``.
        """
        leaf = self._resolve_leaf(resource_type)
        expanded: set[str] = set()
        for relation in relations:
            members = leaf.hierarchy.get(relation)
            if members is None:
                raise UnknownActionError(
                    f"Unknown relation {relation!r} for resource_type {resource_type!r}"
                )
            expanded.update(members)
        return frozenset(expanded)

    def parent_of(self, resource_type: str, resource_id: str) -> tuple[str, str] | None:
        """Return ``(parent_type, parent_id)`` for an inherited child, or ``None``.

        Returns ``None`` for leaf types and for inherited children whose
        registered lookup callable returns ``None`` (e.g., a soft-deleted
        card).
        """
        entry = self._parents.get(resource_type)
        if entry is None:
            return None
        return entry.parent_of(resource_id)

    def has_stored_relations(self, resource_type: str) -> bool:
        """Return whether the engine should query storage for this type directly."""
        return resource_type in self._leaves

    def nearest_leaf_type(self, resource_type: str) -> str:
        """Return the leaf resource type ``resource_type`` resolves to.

        Identity for leaf types; follows ``inherits_from`` declarations
        for inherited types. Raises ``UnknownActionError`` if the chain
        cannot be resolved (same semantics as ``relations_for``).
        """
        seen: set[str] = set()
        current = resource_type
        while current not in self._leaves:
            if current in seen:
                raise UnknownActionError(
                    f"Cycle detected resolving parents for {resource_type!r}"
                )
            seen.add(current)
            parent = self._parents.get(current)
            if parent is None:
                raise UnknownActionError(
                    f"Unknown resource_type for authorization: {resource_type!r}"
                )
            current = parent.inherits_from
        return current

    def registered_resource_types(self) -> set[str]:
        """Return every resource type known to the registry (leaf + inherited)."""
        return set(self._leaves) | set(self._parents)

    # ── Internals ───────────────────────────────────────────────────────────

    def _guard_unsealed(self) -> None:
        if self._sealed:
            raise RuntimeError(
                "AuthorizationRegistry is sealed; register all resource types "
                "before composition completes"
            )

    def _guard_unique(self, resource_type: str) -> None:
        if resource_type in self._leaves or resource_type in self._parents:
            raise ValueError(f"Resource type {resource_type!r} is already registered")

    def _resolve_leaf(self, resource_type: str) -> _LeafEntry:
        return self._leaves[self.nearest_leaf_type(resource_type)]
