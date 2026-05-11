"""SpiceDB authorization adapter (stub).

This package ships a non-functional placeholder so a reader can see at
a glance that swapping the in-repo engine for SpiceDB is a one-adapter
change. See ``README.md`` for the API mapping and ``.zed`` schema.
"""

from src.features.authorization.adapters.outbound.spicedb.adapter import (
    SpiceDBAuthorizationAdapter,
)

__all__ = ["SpiceDBAuthorizationAdapter"]
