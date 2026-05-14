"""OpenAPI presence checks for Problem Details responses and operationIds.

Lives under the authentication e2e suite because it reuses the
``auth_context`` fixture (a fully wired app with every feature
mounted). The contracts under test are platform-level — see
``openspec/changes/declare-error-responses-in-openapi``.

The tests assert two SDK-facing contracts:

1. **Error branches are declared.** Every documented path declares the
   4xx responses listed in its feature's response subset and each
   declared error response references ``ProblemDetails``.
2. **OperationIds follow the convention.** Every ``operationId``
   matches ``^[a-z_]+_[a-z_]+$`` and no two operations share the same
   ``operationId``.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from features.authentication.tests.e2e.conftest import AuthTestContext

pytestmark = pytest.mark.e2e


# Minimum 4xx codes per path-prefix family, mirroring the per-feature
# ``*_RESPONSES`` constants in ``src/app_platform/api/responses.py``.
_AUTH_REQUIRED = {"401", "422", "429"}
_USERS_REQUIRED = {"401", "403", "422"}
_ADMIN_REQUIRED = {"401", "403", "422"}


def _required_codes_for_path(path: str) -> set[str]:
    """Return the minimum 4xx codes the OpenAPI doc must declare for ``path``."""
    if path.startswith("/admin"):
        return _ADMIN_REQUIRED
    if path.startswith("/auth"):
        return _AUTH_REQUIRED
    if path == "/" or path.startswith("/health"):
        # Root and health routes are unauthenticated, take no body, and
        # have no useful 4xx branches to declare.
        return set()
    return _USERS_REQUIRED


def _fetch_openapi(auth_context: AuthTestContext) -> dict[str, Any]:
    response = auth_context.client.get("/openapi.json")
    assert response.status_code == 200, response.text
    spec: dict[str, Any] = response.json()
    return spec


def test_problem_details_and_violation_schemas_are_present(
    auth_context: AuthTestContext,
) -> None:
    """``components.schemas`` carries both ProblemDetails and Violation."""
    spec = _fetch_openapi(auth_context)
    schemas = spec.get("components", {}).get("schemas", {})

    assert "ProblemDetails" in schemas, sorted(schemas)
    assert "Violation" in schemas, sorted(schemas)

    pd_props = schemas["ProblemDetails"].get("properties", {})
    for field in ("type", "title", "status", "detail", "instance", "violations"):
        assert field in pd_props, f"ProblemDetails missing field: {field}"

    v_props = schemas["Violation"].get("properties", {})
    for field in ("loc", "type", "msg", "input"):
        assert field in v_props, f"Violation missing field: {field}"


def test_every_route_declares_its_4xx_responses(
    auth_context: AuthTestContext,
) -> None:
    """Every documented route declares the 4xx responses its feature emits.

    Failures cite the offending ``METHOD path`` and the missing status
    codes so the message points at the route that forgot to spread
    ``responses=*_RESPONSES``.
    """
    spec = _fetch_openapi(auth_context)
    paths = spec["paths"]

    missing: list[str] = []
    for path, methods in paths.items():
        required = _required_codes_for_path(path)
        if not required:
            continue
        for method, operation in methods.items():
            if method.upper() not in {
                "GET",
                "POST",
                "PUT",
                "PATCH",
                "DELETE",
                "HEAD",
                "OPTIONS",
            }:
                continue
            declared = set(operation.get("responses", {}).keys())
            absent = required - declared
            if absent:
                missing.append(
                    f"{method.upper()} {path} is missing 4xx response codes: "
                    f"{sorted(absent)}"
                )

    assert not missing, "\n".join(missing)


def test_4xx_responses_reference_problem_details(
    auth_context: AuthTestContext,
) -> None:
    """Every declared 4xx response references the ProblemDetails schema."""
    spec = _fetch_openapi(auth_context)
    paths = spec["paths"]

    mismatches: list[str] = []
    for path, methods in paths.items():
        for method, operation in methods.items():
            responses = operation.get("responses", {})
            for code, payload in responses.items():
                if not code.startswith("4"):
                    continue
                content = payload.get("content", {})
                # Accept either media type (FastAPI may emit both); we
                # only require at least one to point at ProblemDetails.
                media = content.get("application/problem+json") or content.get(
                    "application/json"
                )
                if media is None:
                    mismatches.append(
                        f"{method.upper()} {path} response {code} declares no content"
                    )
                    continue
                schema = media.get("schema", {})
                ref = schema.get("$ref", "")
                if "ProblemDetails" not in ref:
                    mismatches.append(
                        f"{method.upper()} {path} response {code} does not "
                        f"reference ProblemDetails (got {schema!r})"
                    )

    assert not mismatches, "\n".join(mismatches)


def test_every_operation_id_follows_convention(
    auth_context: AuthTestContext,
) -> None:
    """Every ``operationId`` matches ``^[a-z_]+_[a-z_]+$``."""
    spec = _fetch_openapi(auth_context)
    pattern = re.compile(r"^[a-z_]+_[a-z_]+$")

    offenders: list[str] = []
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            op_id = operation.get("operationId")
            if op_id is None:
                offenders.append(f"{method.upper()} {path} has no operationId")
                continue
            if not pattern.match(op_id):
                offenders.append(
                    f"{method.upper()} {path} operationId {op_id!r} "
                    "does not match ^[a-z_]+_[a-z_]+$"
                )

    assert not offenders, "\n".join(offenders)


def test_operation_ids_are_unique(auth_context: AuthTestContext) -> None:
    """No two operations share the same ``operationId``."""
    spec = _fetch_openapi(auth_context)
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            op_id = operation.get("operationId")
            if op_id is None:
                continue
            location = f"{method.upper()} {path}"
            if op_id in seen:
                duplicates.append(
                    f"operationId {op_id!r} appears on both {seen[op_id]} "
                    f"and {location}"
                )
            else:
                seen[op_id] = location
    assert not duplicates, "\n".join(duplicates)


def test_canonical_operation_id_examples(auth_context: AuthTestContext) -> None:
    """Canonical examples produced by the convention.

    Locks down the convention with two explicit examples drawn from
    the spec: ``POST /auth/login`` → ``auth_login`` and
    ``PATCH /me`` → ``users_patch_me``.
    """
    spec = _fetch_openapi(auth_context)
    paths = spec["paths"]

    assert paths["/auth/login"]["post"]["operationId"] == "auth_login"
    assert paths["/me"]["patch"]["operationId"] == "users_patch_me"
