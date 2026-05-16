"""Outbound adapters that implement ``AuthorizationPort``.

One adapter ships with the template:

* ``sqlmodel.SQLModelAuthorizationAdapter`` — default in-repo engine
  backed by the ``relationships`` table. Resolves the relation hierarchy
  and cross-resource inheritance at check time.

The port stays the single swap boundary: a future ReBAC backend can be
introduced as one new adapter here without an application-layer change.
"""
