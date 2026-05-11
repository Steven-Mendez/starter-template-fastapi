"""Outbound adapters that implement ``AuthorizationPort``.

Two adapters ship with the template:

* ``sqlmodel.SQLModelAuthorizationAdapter`` — default in-repo engine
  backed by the ``relationships`` table. Resolves the relation hierarchy
  and cross-resource inheritance at check time.
* ``spicedb.SpiceDBAuthorizationAdapter`` — non-functional stub that
  documents how a real SpiceDB integration would map onto the same port.
"""
