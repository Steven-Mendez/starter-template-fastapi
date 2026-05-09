"""Pydantic request/response schemas for the auth and admin HTTP endpoints.

Normalisation lives in field validators so that the service layer always
receives canonical values regardless of what the client sends, removing
any chance of duplicate accounts or roles from inconsistent casing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.features.auth.application.normalization import (
    normalize_email,
    normalize_permission_name,
    normalize_role_name,
)

# NIST SP 800-63B §5.1.1.2 finds long passphrases with low character-class
# diversity at least as strong as short complex ones, and cautions that
# forcing all four classes pushes users toward predictable transformations
# ("Password1!"). We accept either path: ≥ 3 of 4 classes, or length ≥ 20.
_MIN_PASSWORD_LENGTH_FOR_RELAXED_RULE = 20


def _validate_password_complexity(value: str) -> str:
    """Accept passwords with ≥ 3 of 4 character classes, or length ≥ 20."""
    if len(value) >= _MIN_PASSWORD_LENGTH_FOR_RELAXED_RULE:
        return value
    classes = (
        any(ch.isupper() for ch in value),
        any(ch.islower() for ch in value),
        any(ch.isdigit() for ch in value),
        any(not ch.isalnum() and not ch.isspace() for ch in value),
    )
    if sum(classes) < 3:
        raise ValueError(
            "Password must contain at least 3 of: uppercase, lowercase, "
            "digit, symbol — or be at least 20 characters long"
        )
    return value


class RegisterRequest(BaseModel):
    """Body of ``POST /auth/register``. Enforces a 12+ character password."""

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email_value(cls, value: str) -> str:
        normalized = normalize_email(value)
        # Reject bare strings without "@" early so the service layer never
        # has to consider obviously invalid emails.
        if "@" not in normalized:
            raise ValueError("Invalid email")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_password_complexity(value)


class LoginRequest(BaseModel):
    """Body of ``POST /auth/login``. Allows any non-empty password length."""

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email_value(cls, value: str) -> str:
        return normalize_email(value)


class UserPublic(BaseModel):
    """Public projection of a user row, used in registration responses."""

    id: UUID
    email: str
    is_active: bool
    is_verified: bool
    authz_version: int
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PrincipalPublic(BaseModel):
    """Identity payload returned alongside tokens and on ``GET /auth/me``."""

    id: UUID
    email: str
    is_active: bool
    is_verified: bool
    roles: list[str]
    permissions: list[str]


class TokenResponse(BaseModel):
    """Login/refresh response with access token and current identity."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: PrincipalPublic


class MessageResponse(BaseModel):
    """Generic acknowledgement payload used by mutation endpoints."""

    message: str


class InternalTokenResponse(BaseModel):
    """Response for password-reset / email-verification requests.

    ``dev_token`` is intentionally ``None`` in production. It is only
    populated when ``AUTH_RETURN_INTERNAL_TOKENS=true`` so local development
    and e2e tests can complete the flow without a real email delivery
    service.
    """

    message: str
    dev_token: str | None = None
    expires_at: datetime | None = None


class PasswordForgotRequest(BaseModel):
    """Body of ``POST /auth/password/forgot``."""

    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def normalize_email_value(cls, value: str) -> str:
        return normalize_email(value)


class PasswordResetRequest(BaseModel):
    """Body of ``POST /auth/password/reset``.

    Token length allows opaque reset tokens with margin.
    """

    token: str = Field(min_length=32, max_length=512)
    new_password: str = Field(min_length=12, max_length=256)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return _validate_password_complexity(value)


class EmailVerifyRequest(BaseModel):
    """Body of ``POST /auth/email/verify``."""

    token: str = Field(min_length=32, max_length=512)


class RoleCreate(BaseModel):
    """Body of ``POST /admin/roles``. Names are normalised before validation."""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return normalize_role_name(value)


class RoleUpdate(BaseModel):
    """Body of ``PATCH /admin/roles/{id}``.

    All fields are optional and patched independently.
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return normalize_role_name(value) if value is not None else None


class RoleRead(BaseModel):
    """Public projection of a role row."""

    id: UUID
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PermissionCreate(BaseModel):
    """Body of ``POST /admin/permissions``.

    Name must follow ``resource:action`` format.
    """

    name: str = Field(min_length=3, max_length=150)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return normalize_permission_name(value)


class PermissionRead(BaseModel):
    """Public projection of a permission row."""

    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PermissionAssignmentRequest(BaseModel):
    """Body for assigning a permission to a role."""

    permission_id: UUID


class UserRoleAssignmentRequest(BaseModel):
    """Body for assigning a role to a user."""

    role_id: UUID


class AuditEventRead(BaseModel):
    """Public projection of an audit-log row."""

    id: UUID
    user_id: UUID | None
    event_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogRead(BaseModel):
    """Paginated audit-log response."""

    items: list[AuditEventRead]
    count: int
    limit: int
