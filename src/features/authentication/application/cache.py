"""Principal cache implementations.

Two implementations share a common ``PrincipalCachePort`` Protocol:

* ``InProcessPrincipalCache`` — TTLCache backed, single-replica only.
* ``RedisPrincipalCache`` — Redis backed, safe for multi-replica deployments.

Both maintain a secondary user→token index so that invalidating a user evicts
all of that user's cached entries at once without scanning the whole cache.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cachetools import TTLCache

from app_platform.shared.principal import Principal


class PrincipalCachePort(Protocol):
    """Read-through cache for resolved JWT principals."""

    def get(self, token_id: str) -> Principal | None: ...
    def set(self, token_id: str, principal: Principal) -> None: ...
    def pop(self, token_id: str) -> None: ...
    def invalidate_user(self, user_id: UUID) -> None: ...
    def close(self) -> None: ...


@dataclass(slots=True)
class InProcessPrincipalCache:
    """TTLCache-backed cache — single replica only.

    The user index maps ``str(user_id)`` to a set of token IDs so that
    ``invalidate_user`` can evict all sessions without scanning the whole
    cache. The lock serialises every operation to keep TTLCache thread-safe.
    """

    _cache: TTLCache  # type: ignore[type-arg]
    _lock: threading.Lock
    _user_index: dict[str, set[str]]

    @classmethod
    def create(cls, maxsize: int = 1000, ttl: int = 5) -> InProcessPrincipalCache:
        return cls(
            _cache=TTLCache(maxsize=maxsize, ttl=ttl),
            _lock=threading.Lock(),
            _user_index={},
        )

    def get(self, token_id: str) -> Principal | None:
        with self._lock:
            return self._cache.get(token_id)

    def set(self, token_id: str, principal: Principal) -> None:
        uid = str(principal.user_id)
        with self._lock:
            self._cache[token_id] = principal
            self._user_index.setdefault(uid, set()).add(token_id)

    def pop(self, token_id: str) -> None:
        with self._lock:
            self._cache.pop(token_id, None)

    def invalidate_user(self, user_id: UUID) -> None:
        uid = str(user_id)
        with self._lock:
            token_ids = self._user_index.pop(uid, set())
            for tid in token_ids:
                self._cache.pop(tid, None)

    def close(self) -> None:
        pass


@dataclass(slots=True)
class RedisPrincipalCache:
    """Redis-backed cache — safe for multi-replica deployments.

    Key layout::

        auth:principal:{token_id}       SETEX {ttl}  — JSON-encoded Principal
        auth:user_tokens:{user_id}      SET of token_ids (secondary index)

    ``invalidate_user`` reads the user's token set, deletes every principal
    key, then deletes the set itself — all in one pipeline call.
    """

    # redis.Redis kept as `object` to avoid a hard import at type-check time.
    _redis: object
    _ttl: int

    def _key(self, token_id: str) -> str:
        return f"auth:principal:{token_id}"

    def _user_key(self, user_id: str) -> str:
        return f"auth:user_tokens:{user_id}"

    def _encode(self, principal: Principal) -> str:
        return json.dumps(
            {
                "user_id": str(principal.user_id),
                "email": principal.email,
                "is_active": principal.is_active,
                "is_verified": principal.is_verified,
                "authz_version": principal.authz_version,
            }
        )

    def _decode(self, raw: bytes | str) -> Principal:
        data = json.loads(raw)
        return Principal(
            user_id=UUID(data["user_id"]),
            email=data["email"],
            is_active=data["is_active"],
            is_verified=data["is_verified"],
            authz_version=data["authz_version"],
        )

    def get(self, token_id: str) -> Principal | None:
        raw = self._redis.get(self._key(token_id))  # type: ignore[attr-defined]
        if raw is None:
            return None
        return self._decode(raw)

    def set(self, token_id: str, principal: Principal) -> None:
        uid = str(principal.user_id)
        pipe = self._redis.pipeline()  # type: ignore[attr-defined]
        pipe.setex(self._key(token_id), self._ttl, self._encode(principal))
        pipe.sadd(self._user_key(uid), token_id)
        pipe.expire(self._user_key(uid), self._ttl)
        pipe.execute()

    def pop(self, token_id: str) -> None:
        self._redis.delete(self._key(token_id))  # type: ignore[attr-defined]

    def invalidate_user(self, user_id: UUID) -> None:
        uid = str(user_id)
        user_key = self._user_key(uid)
        pipe = self._redis.pipeline()  # type: ignore[attr-defined]
        pipe.smembers(user_key)
        pipe.delete(user_key)
        results = pipe.execute()
        token_ids: set[bytes] = results[0]
        if token_ids:
            self._redis.delete(  # type: ignore[attr-defined]
                *(self._key(tid.decode()) for tid in token_ids)
            )

    def close(self) -> None:
        self._redis.close()  # type: ignore[attr-defined]

    @classmethod
    def from_url(cls, url: str, ttl: int) -> RedisPrincipalCache:
        """Connect to Redis and return a ready-to-use cache.

        Raises:
            redis.exceptions.ConnectionError: If the server is unreachable.
        """
        import redis as redis_lib

        client = redis_lib.Redis.from_url(url, decode_responses=False)
        client.ping()
        return cls(_redis=client, _ttl=ttl)
