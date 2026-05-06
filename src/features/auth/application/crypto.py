"""Password hashing and opaque-token primitives used across the auth feature.

Argon2id is preferred over bcrypt/scrypt because it resists both GPU-based
brute-force and side-channel attacks while staying tunable for future
hardware improvements without changing the stored hash format.
"""

from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError


class PasswordService:
    """Handles password hashing and verification using Argon2id.

    Wraps ``argon2-cffi`` so the rest of the application never touches
    raw hashing primitives directly.
    """

    def __init__(self) -> None:
        self._hasher = PasswordHasher()

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
        except VerifyMismatchError, VerificationError:
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
