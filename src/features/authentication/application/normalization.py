"""Canonical forms and validators for emails, role names, and permission names.

Centralising case and whitespace normalisation here prevents duplicate
accounts caused by inputs like ``"User@Example.com"`` vs ``"user@example.com"``,
and ensures role and permission names are stored in a consistent format
across seeds and runtime mutations.
"""

from __future__ import annotations

import re

# Permissions follow a "resource:action" convention so names are
# self-documenting and we avoid ambiguous flat strings like "read_users".
ROLE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
PERMISSION_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*:[a-z][a-z0-9_:]*$")


def normalize_email(email: str) -> str:
    """Strip whitespace and lowercase an email address.

    Args:
        email: Raw email string as received from the client.

    Returns:
        The canonical lowercase email string.
    """
    return email.strip().lower()


def normalize_role_name(name: str) -> str:
    """Strip whitespace, lowercase, and replace hyphens with underscores in a role name.

    Args:
        name: Raw role name as received from the client or seed data.

    Returns:
        The canonical role name string (e.g. ``"super_admin"``).
    """
    return name.strip().lower().replace("-", "_")


def normalize_permission_name(name: str) -> str:
    """Strip whitespace and lowercase a permission name.

    Args:
        name: Raw permission name (e.g. ``"roles:read"``).

    Returns:
        The canonical lowercase permission name string.
    """
    return name.strip().lower()


def is_role_name(value: str) -> bool:
    """Return whether a string is a valid normalised role name.

    Valid names start with a lowercase letter and contain only lowercase
    letters, digits, and underscores.

    Args:
        value: The string to validate (should already be normalised).

    Returns:
        ``True`` if the value matches the role name pattern, ``False`` otherwise.
    """
    return bool(ROLE_NAME_PATTERN.fullmatch(value))


def is_permission_name(value: str) -> bool:
    """Return whether a string is a valid normalised permission name.

    Valid names follow the ``resource:action`` format, e.g. ``"roles:read"``.

    Args:
        value: The string to validate (should already be normalised).

    Returns:
        ``True`` if the value matches the permission name pattern, ``False`` otherwise.
    """
    return bool(PERMISSION_NAME_PATTERN.fullmatch(value))
