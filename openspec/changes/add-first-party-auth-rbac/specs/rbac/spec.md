## ADDED Requirements

### Requirement: Persistent roles
The system MUST persist roles in PostgreSQL. Roles MUST have unique normalized names, optional descriptions, active status, and timestamps. Roles MUST be deactivatable without deleting history.

#### Scenario: Create role
- **WHEN** an authorized admin creates a role with a normalized unique name
- **THEN** the system MUST persist the role with active status and timestamps

#### Scenario: Duplicate role
- **WHEN** an authorized admin creates a role whose normalized name already exists
- **THEN** the system MUST reject the duplicate role

#### Scenario: Inactive role ignored
- **WHEN** a user has an inactive role assigned
- **THEN** the inactive role MUST NOT grant permissions

### Requirement: Persistent permissions
The system MUST persist permissions in PostgreSQL. Permissions MUST have unique normalized names in `resource:action` format, optional descriptions, and timestamps. Permissions MUST be assignable to multiple roles.

#### Scenario: Create permission
- **WHEN** an authorized admin creates a permission named in `resource:action` format
- **THEN** the system MUST persist the permission with a unique normalized name

#### Scenario: Duplicate permission
- **WHEN** an authorized admin creates a permission whose normalized name already exists
- **THEN** the system MUST reject the duplicate permission

### Requirement: User role assignment
A user MUST be assignable to zero or more roles. Role assignment and removal MUST only be available to users with administrative permission. Changing a user's roles MUST update the affected user's `authz_version` or equivalent.

#### Scenario: Assign role to user
- **WHEN** a user with `users:roles:manage` assigns a role to another user
- **THEN** the system MUST persist the assignment, update the target user's authorization version, and audit the change

#### Scenario: Remove role from user
- **WHEN** a user with `users:roles:manage` removes a role from another user
- **THEN** the system MUST remove the assignment, update the target user's authorization version, and audit the change

#### Scenario: Public user cannot assign role
- **WHEN** a user without administrative permission attempts to assign a role
- **THEN** the system MUST reject the request with `403`

### Requirement: Role permission assignment
A role MUST be assignable to zero or more permissions. Changing permissions on a role MUST invalidate or obsolete affected access tokens through `authz_version`, `permissions_version`, or an equivalent strategy.

#### Scenario: Add permission to role
- **WHEN** a user with `permissions:manage` assigns a permission to a role
- **THEN** the system MUST persist the assignment, update authorization versions for users with that role, and audit the change

#### Scenario: Remove permission from role
- **WHEN** a user with `permissions:manage` removes a permission from a role
- **THEN** the system MUST remove the assignment, update authorization versions for users with that role, and audit the change

### Requirement: Authorization dependencies
The system MUST provide authorization dependencies such as `require_permissions("users:read")`, `require_any_permission`, `require_all_permissions`, `require_roles`, `require_active_user`, `get_current_user`, and `get_current_principal`.

#### Scenario: Missing authentication
- **WHEN** a protected endpoint receives no bearer token or an invalid bearer token
- **THEN** the system MUST return `401`

#### Scenario: Insufficient permission
- **WHEN** a valid authenticated user lacks a required permission
- **THEN** the system MUST return `403`

#### Scenario: Sufficient permission
- **WHEN** a valid active user has the required permission through an active role
- **THEN** the system MUST allow the request

### Requirement: Admin RBAC endpoints
The system MUST expose protected admin RBAC endpoints for role, permission, role-permission, and user-role management.

#### Scenario: List roles
- **WHEN** an authenticated user with `roles:read` or `roles:manage` calls `GET /admin/roles`
- **THEN** the system MUST return roles without requiring broader administrative shortcuts

#### Scenario: Create role endpoint
- **WHEN** an authenticated user with `roles:manage` calls `POST /admin/roles`
- **THEN** the system MUST create the role and audit the change

#### Scenario: Patch role endpoint
- **WHEN** an authenticated user with `roles:manage` calls `PATCH /admin/roles/{role_id}`
- **THEN** the system MUST update mutable role fields and audit the change

#### Scenario: List permissions endpoint
- **WHEN** an authenticated user with `permissions:read` or `permissions:manage` calls `GET /admin/permissions`
- **THEN** the system MUST return permissions

#### Scenario: Create permission endpoint
- **WHEN** an authenticated user with `permissions:manage` calls `POST /admin/permissions`
- **THEN** the system MUST create the permission and audit the change

#### Scenario: Assign permission endpoint
- **WHEN** an authenticated user with `permissions:manage` calls `POST /admin/roles/{role_id}/permissions`
- **THEN** the system MUST assign the permission to the role and update affected authorization versions

#### Scenario: Remove permission endpoint
- **WHEN** an authenticated user with `permissions:manage` calls `DELETE /admin/roles/{role_id}/permissions/{permission_id}`
- **THEN** the system MUST remove the permission from the role and update affected authorization versions

#### Scenario: Assign user role endpoint
- **WHEN** an authenticated user with `users:roles:manage` calls `POST /admin/users/{user_id}/roles`
- **THEN** the system MUST assign the role to the user and update the target user's authorization version

#### Scenario: Remove user role endpoint
- **WHEN** an authenticated user with `users:roles:manage` calls `DELETE /admin/users/{user_id}/roles/{role_id}`
- **THEN** the system MUST remove the role from the user and update the target user's authorization version

### Requirement: Least privilege
The system MUST NOT grant administrative permissions to newly registered users by default. The first privileged admin MUST be created through a secure command, controlled migration, or explicit seed, never through public registration.

#### Scenario: New public user
- **WHEN** a public user registers successfully
- **THEN** the user MUST receive no administrative permissions

#### Scenario: First super admin creation
- **WHEN** an operator creates the first `super_admin`
- **THEN** the system MUST require a non-public command or seed path and MUST NOT expose this promotion through public registration

### Requirement: Audit RBAC changes
The system MUST create audit events for creating roles, creating permissions, changing role permissions, changing user roles, and changing role active status.

#### Scenario: Role permission change audited
- **WHEN** a role permission is added or removed
- **THEN** the system MUST persist an audit event with actor, target identifiers, event type, and safe metadata when available

#### Scenario: User role change audited
- **WHEN** a user role is added or removed
- **THEN** the system MUST persist an audit event with actor, target identifiers, event type, and safe metadata when available

### Requirement: RBAC tests
The system MUST include tests for role and permission persistence, inactive roles, required permissions, `401` vs `403`, assigning/removing roles, assigning/removing permissions to roles, least privilege registration, and RBAC audit events.

#### Scenario: RBAC test suite
- **WHEN** the relevant test suite runs
- **THEN** tests MUST verify RBAC success paths, failure paths, authorization invalidation, and audit behavior
