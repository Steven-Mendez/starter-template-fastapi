"""Default permissions, roles, and role-permission mappings seeded at startup.

The dictionaries in this module are the single source of truth for the
seeded RBAC hierarchy. Editing them and re-running the seed command is the
intended way to evolve the default permission model.
"""

from __future__ import annotations

ALL_PERMISSIONS: dict[str, str] = {
    "users:read": "Read user records",
    "users:create": "Create user records",
    "users:update": "Update user records",
    "users:delete": "Delete user records",
    "users:roles:manage": "Assign and remove user roles",
    "roles:read": "Read roles",
    "roles:manage": "Manage roles",
    "permissions:read": "Read permissions",
    "permissions:manage": "Manage permissions and role grants",
    "auth:sessions:revoke": "Revoke user sessions",
    "audit:read": "Read auth and RBAC audit events",
    "admin:access": "Access administrative API surface",
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    # super_admin receives all seeded permissions automatically so that
    # adding a new permission to ALL_PERMISSIONS also extends this role.
    "super_admin": set(ALL_PERMISSIONS),
    "admin": {
        "users:read",
        "users:create",
        "users:update",
        "users:roles:manage",
        "roles:read",
        "roles:manage",
        "permissions:read",
        "permissions:manage",
        "auth:sessions:revoke",
        "admin:access",
    },
    "manager": {"users:read", "roles:read", "permissions:read"},
    # The default user role intentionally starts with no permissions so that
    # access is explicitly granted rather than accidentally inherited.
    "user": set(),
}

ROLE_DESCRIPTIONS: dict[str, str] = {
    "super_admin": "Full access to all seeded permissions",
    "admin": "Operational administration without global-only shortcuts",
    "manager": "Read and limited operational access",
    "user": "Default non-administrative user",
}
