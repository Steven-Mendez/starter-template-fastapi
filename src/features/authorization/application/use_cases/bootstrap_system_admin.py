"""Bootstrap the first system administrator under the ReBAC model.

Composes five outbound ports: ``UserRegistrarPort`` to look up or
create the configured account, ``AuthorizationPort`` to read the
existing ``system:main#admin`` tuple and write a new one,
``CredentialVerifierPort`` to confirm the supplied password on the
opt-in promote-existing path, ``AuditPort`` to record the
``authz.system_admin_bootstrapped`` event, and
``PrincipalCacheInvalidatorPort`` to drop any cached principal
entries for the bootstrapped user so the new admin permission is
honoured on the very next request.

The relationships table's unique constraint keeps re-runs idempotent.

This use case lives in the authorization feature because it operates on
the authorization domain (the system-admin relationship). The fact that
it needs a user is incidental and is routed through ports so
authorization never imports from auth.

Decision tree (see ``fix-bootstrap-admin-escalation`` proposal):

* No user exists with ``email`` → create the user, grant admin, emit
  ``authz.system_admin_bootstrapped`` (``subevent="created"``).
* User exists AND already holds ``system:main#admin`` → idempotent
  no-op; return ``Ok(user_id)`` with no audit event and no write.
* User exists, not admin, ``promote_existing=False`` → return
  ``Err(BootstrapRefusedExistingUserError)``; write nothing; emit
  nothing.
* User exists, not admin, ``promote_existing=True`` → verify the
  supplied password against the stored credential. On match, grant
  admin and emit ``authz.system_admin_bootstrapped``
  (``subevent="promoted_existing"``). On mismatch, return
  ``Err(BootstrapPasswordMismatchError)``; write nothing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from app_platform.observability.tracing import traced
from app_platform.shared.result import Err, Ok, Result
from features.authorization.application.errors import (
    BootstrapPasswordMismatchError,
    BootstrapRefusedExistingUserError,
)
from features.authorization.application.ports.authorization_port import (
    AuthorizationPort,
)
from features.authorization.application.ports.outbound import (
    AuditPort,
    CredentialVerifierPort,
    PrincipalCacheInvalidatorPort,
    UserRegistrarPort,
)
from features.authorization.application.types import Relationship

_logger = logging.getLogger(__name__)

_EVENT_TYPE = "authz.system_admin_bootstrapped"
_SUBEVENT_CREATED = "created"
_SUBEVENT_PROMOTED_EXISTING = "promoted_existing"


@dataclass(slots=True)
class BootstrapSystemAdmin:
    """Ensure the configured account exists and holds ``system:main#admin``.

    The decision tree above is intentionally branched in the use case
    rather than at the caller so the audit and refusal contracts are
    enforced in one place regardless of who invokes bootstrap (web
    process lifespan, CLI, or future operator tooling).
    """

    _authorization: AuthorizationPort
    _user_registrar: UserRegistrarPort
    _credential_verifier: CredentialVerifierPort
    _audit: AuditPort
    _principal_cache_invalidator: PrincipalCacheInvalidatorPort
    _promote_existing: bool = False

    @traced("authz.bootstrap_system_admin")
    def execute(
        self, *, email: str, password: str
    ) -> Result[
        UUID,
        BootstrapRefusedExistingUserError | BootstrapPasswordMismatchError,
    ]:
        """Return the bootstrapped user's id wrapped in a ``Result``.

        After every successful relationship write, drops any cached
        principal entries for the bootstrapped user. Cache invalidation
        is best-effort — a transport failure (e.g., Redis blip) is
        logged at WARNING and swallowed so the durable success (the
        DB-side relationship + ``authz_version`` bump committed
        atomically) is not undone by an optimisation failure.
        """
        existing_id = self._user_registrar.lookup_by_email(email=email)
        if existing_id is None:
            user_id = self._user_registrar.register_or_lookup(
                email=email, password=password
            )
            self._grant_and_invalidate(user_id)
            self._audit.record(
                _EVENT_TYPE,
                user_id=user_id,
                metadata={
                    "actor": "system",
                    "reason": "bootstrap_on_startup",
                    "subevent": _SUBEVENT_CREATED,
                },
            )
            return Ok(user_id)

        if self._authorization.check(
            user_id=existing_id,
            action="manage_users",
            resource_type="system",
            resource_id="main",
        ):
            # Idempotent re-bootstrap: the user already holds the
            # admin relation, so there is nothing to write and no new
            # audit event to emit.
            return Ok(existing_id)

        if not self._promote_existing:
            _logger.error(
                "event=authz.bootstrap.refused_existing user_id=%s email=%s "
                "message=refusing to promote existing non-admin user; set "
                "APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING=true to opt in",
                existing_id,
                email,
            )
            return Err(BootstrapRefusedExistingUserError(existing_id, email))

        verification = self._credential_verifier.verify(existing_id, password)
        if isinstance(verification, Err):
            _logger.error(
                "event=authz.bootstrap.password_mismatch user_id=%s "
                "message=bootstrap password did not match existing "
                "user's credential — refusing to promote",
                existing_id,
            )
            return Err(BootstrapPasswordMismatchError(existing_id))

        self._grant_and_invalidate(existing_id)
        self._audit.record(
            _EVENT_TYPE,
            user_id=existing_id,
            metadata={
                "actor": "system",
                "reason": "bootstrap_on_startup",
                "subevent": _SUBEVENT_PROMOTED_EXISTING,
            },
        )
        return Ok(existing_id)

    def _grant_and_invalidate(self, user_id: UUID) -> None:
        """Write the admin tuple and drop cached principals for the user.

        The cache invalidation is best-effort: a transport failure
        (e.g., Redis blip) is logged at WARNING and swallowed so the
        durable success (the DB-side relationship + ``authz_version``
        bump committed atomically by ``write_relationships``) is not
        undone by an optimisation failure.
        """
        self._authorization.write_relationships(
            [
                Relationship(
                    resource_type="system",
                    resource_id="main",
                    relation="admin",
                    subject_type="user",
                    subject_id=str(user_id),
                )
            ]
        )
        try:
            self._principal_cache_invalidator.invalidate_user(user_id)
        except Exception as exc:
            _logger.warning(
                "event=authz.cache_invalidation.failed user_id=%s reason=%r",
                user_id,
                exc,
            )
