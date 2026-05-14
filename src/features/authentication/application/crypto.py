"""Password hashing and opaque-token primitives used across the auth feature.

Argon2id is preferred over bcrypt/scrypt because it resists both GPU-based
brute-force and side-channel attacks while staying tunable for future
hardware improvements without changing the stored hash format.

Argon2id parameters are pinned in source rather than env-tunable so that
two production deploys with different ``argon2-cffi`` library versions
rehash at the same cost. The chosen values follow the OWASP Password
Storage Cheat Sheet recommendations (`m=64 MiB, t=3, p=4`, dated 2024-09)
and target ~150 ms per hash on a modern CPU:

* ``time_cost=3`` — number of Argon2 iterations.
* ``memory_cost=65536`` — KiB of memory used per hash (64 MiB).
* ``parallelism=4`` — number of parallel lanes.
* ``hash_len=32`` — 256-bit derived key length.
* ``salt_len=16`` — 128-bit salt length.

Rotating these parameters is a deliberate, reviewable change: bump them
here, deploy, and rely on ``PasswordService.needs_rehash`` to upgrade
each user's hash on their next successful login.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Final

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

# OWASP 2024-09 Argon2id recommendations — see module docstring.
_ARGON2_TIME_COST: Final[int] = 3
_ARGON2_MEMORY_COST_KIB: Final[int] = 65536
_ARGON2_PARALLELISM: Final[int] = 4
_ARGON2_HASH_LEN: Final[int] = 32
_ARGON2_SALT_LEN: Final[int] = 16

# Module-level fixed-cost Argon2id hash used on miss branches across the
# authentication feature so the dominant wall-clock cost (~150 ms Argon2
# verify) matches the hit branch. ``verify_password`` against any
# candidate plaintext will return ``False`` while paying the full Argon2
# cost — closing the timing channel that would otherwise let an attacker
# enumerate registered emails. Generated with the default ``argon2-cffi``
# parameters (m=65536, t=3, p=4).
FIXED_DUMMY_ARGON2_HASH: Final[str] = (
    "$argon2id$v=19$m=65536,t=3,p=4$"
    "7+JuBWe0Hx8Q5eFgxf9fVQ$"
    "ZCoHJmWona5G0bfuPaZxJ/q2Jht4yAxCSvoP0IDkQ4U"
)


class PasswordService:
    """Handles password hashing and verification using Argon2id.

    Wraps ``argon2-cffi`` so the rest of the application never touches
    raw hashing primitives directly.
    """

    def __init__(self) -> None:
        # Parameters pinned in source — see module docstring for the
        # OWASP-derived rationale.
        self._hasher = PasswordHasher(
            time_cost=_ARGON2_TIME_COST,
            memory_cost=_ARGON2_MEMORY_COST_KIB,
            parallelism=_ARGON2_PARALLELISM,
            hash_len=_ARGON2_HASH_LEN,
            salt_len=_ARGON2_SALT_LEN,
        )

    def hash_password(self, password: str) -> str:
        """Hash a plaintext password with Argon2id.

        Args:
            password: The plaintext password to hash.

        Returns:
            An Argon2id hash string suitable for storage.
        """
        return self._hasher.hash(password)

    def verify_password(self, password_hash: str, password: str) -> bool:
        """Check whether a plaintext password matches a stored Argon2id hash.

        Args:
            password_hash: The stored Argon2id hash.
            password: The plaintext password to verify.

        Returns:
            ``True`` if the password matches the hash, ``False`` otherwise.
        """
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError):
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        """Return whether the hash was produced with outdated Argon2 parameters.

        Args:
            password_hash: The stored Argon2id hash to inspect.

        Returns:
            ``True`` if the hash should be replaced on next successful login.
        """
        # Allows silent in-place upgrades when Argon2 parameters are tightened
        # without forcing a global password reset.
        return self._hasher.check_needs_rehash(password_hash)


def generate_opaque_token() -> str:
    """Generate a cryptographically secure random opaque token.

    Returns:
        A URL-safe base64 string with 384 bits of entropy.
    """
    # 48 bytes gives 384 bits of entropy, well beyond the 128-bit minimum
    # needed to make brute-forcing refresh tokens computationally infeasible.
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of an opaque token.

    Used to derive a storable fingerprint without persisting the token itself.

    Args:
        token: The raw opaque token string (e.g. from ``generate_opaque_token``).

    Returns:
        A 64-character lowercase hex string representing the SHA-256 digest.
    """
    # Only the SHA-256 digest is persisted so a full DB dump never exposes
    # bearer tokens. SHA-256 is sufficient because the token itself already
    # carries enough entropy to prevent preimage attacks.
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
