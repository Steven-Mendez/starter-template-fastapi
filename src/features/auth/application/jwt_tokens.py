"""JWT access-token issuance and validation.

Wraps PyJWT so the rest of the application never touches raw JWT primitives.
The encoded payload deliberately includes ``authz_version`` so the server
can invalidate tokens on permission changes without keeping a blacklist.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import jwt

from src.features.auth.application.errors import ConfigurationError, InvalidTokenError
from src.features.auth.application.types import AccessTokenPayload
from src.platform.config.settings import AppSettings


class AccessTokenService:
    """Issues and validates JWT access tokens for authenticated principals.

    Encodes roles and the authorization version into the token payload so
    the application can detect stale tokens without a database lookup.
    """

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def _secret(self) -> str:
        """Return the configured JWT signing secret.

        Raises:
            ConfigurationError: If ``AUTH_JWT_SECRET_KEY`` is not set.
        """
        secret = self._settings.auth_jwt_secret_key
        if not secret:
            # Fail loudly at token issuance rather than silently producing
            # tokens that no deployment can verify.
            raise ConfigurationError("AUTH_JWT_SECRET_KEY is required")
        return secret

    def issue(
        self, *, subject: UUID, roles: set[str], authz_version: int
    ) -> tuple[str, int]:
        """Issue a signed JWT access token for the given principal.

        Args:
            subject: The user's UUID, stored in the ``sub`` claim.
            roles: Set of role names to embed in the token payload.
            authz_version: The user's current authorization version; used to
                detect stale tokens after permission changes.

        Returns:
            A tuple of ``(encoded_token, expires_in_seconds)``.

        Raises:
            ConfigurationError: If ``AUTH_JWT_SECRET_KEY`` is not configured.
        """
        now = datetime.now(timezone.utc)
        expires_delta = timedelta(
            minutes=self._settings.auth_access_token_expire_minutes
        )
        expires_at = now + expires_delta
        token_id = str(uuid4())
        payload: dict[str, Any] = {
            "sub": str(subject),
            "exp": expires_at,
            "iat": now,
            # nbf prevents a token from being accepted before issuance,
            # guarding against clock-skew replay on multi-node deployments.
            "nbf": now,
            # jti makes each token unique, enabling future token-level
            # revocation without a full token blacklist.
            "jti": token_id,
            # Sorting roles makes the token deterministic for the same
            # principal so caching or signature comparison is predictable.
            "roles": sorted(roles),
            "authz_version": authz_version,
        }
        if self._settings.auth_jwt_issuer:
            payload["iss"] = self._settings.auth_jwt_issuer
        if self._settings.auth_jwt_audience:
            payload["aud"] = self._settings.auth_jwt_audience
        token = jwt.encode(
            payload,
            self._secret(),
            algorithm=self._settings.auth_jwt_algorithm,
        )
        return token, int(expires_delta.total_seconds())

    def decode(self, token: str) -> AccessTokenPayload:
        """Validate and decode a JWT access token.

        Args:
            token: The encoded JWT string received from the client.

        Returns:
            An ``AccessTokenPayload`` with the verified claims.

        Raises:
            InvalidTokenError: If the token is malformed, expired, has an
                invalid signature, or fails issuer/audience validation.
        """
        options = {"require": ["sub", "exp", "iat", "nbf", "jti", "authz_version"]}
        kwargs: dict[str, Any] = {"options": options}
        if self._settings.auth_jwt_issuer:
            kwargs["issuer"] = self._settings.auth_jwt_issuer
        if self._settings.auth_jwt_audience:
            kwargs["audience"] = self._settings.auth_jwt_audience
        else:
            # When no audience is configured the library still validates the
            # aud claim if it is present, which breaks tokens that omit it.
            # Explicitly disabling audience verification keeps single-service
            # deployments working without requiring an artificial audience string.
            kwargs["options"] = {**options, "verify_aud": False}
        try:
            payload = jwt.decode(
                token,
                self._secret(),
                algorithms=[self._settings.auth_jwt_algorithm],
                **kwargs,
            )
            subject = UUID(str(payload["sub"]))
            roles_raw = payload.get("roles", [])
            if not isinstance(roles_raw, list):
                raise InvalidTokenError("Invalid roles claim")
            exp = datetime.fromtimestamp(float(payload["exp"]), tz=timezone.utc)
            return AccessTokenPayload(
                subject=subject,
                authz_version=int(payload["authz_version"]),
                roles=tuple(str(role) for role in roles_raw),
                expires_at=exp,
                token_id=str(payload["jti"]),
            )
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
            raise InvalidTokenError("Could not validate credentials") from exc
