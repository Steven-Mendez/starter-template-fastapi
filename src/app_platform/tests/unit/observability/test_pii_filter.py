"""Unit coverage for the PII / token redaction filter and processor.

Covers tasks 6.2, 6.3, 6.4, and 6.5 from
``openspec/changes/redact-pii-and-tokens-in-logs/tasks.md``:

* 6.2 — ``extra={"email": "foo@bar.com"}`` renders as ``email=f***@bar.com``.
* 6.3 — ``extra={"password": "hunter2"}`` renders as ``password=***REDACTED***``.
* 6.4 — ``extra={"headers": {"Authorization": "Bearer abc"}}`` redacts the
  header value (case-insensitive match).
* 6.5 — parametrized: every key in :data:`REDACT_STRICT_KEYS` and
  :data:`REDACT_EMAIL_KEYS` is exercised once via both the structlog
  processor seam AND the stdlib :class:`PiiLogFilter` seam.

The tests deliberately exercise both seams so a regression in either
side is caught (the processor runs inside the structlog chain; the
filter is the safety net for uvicorn / third-party stdlib log calls
that never reach the structlog chain).
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from app_platform.observability.pii_filter import (
    PiiLogFilter,
    PiiRedactionProcessor,
)
from app_platform.observability.redaction import (
    REDACT_EMAIL_KEYS,
    REDACT_HEADER_NAMES,
    REDACT_STRICT_KEYS,
    REDACTED_PLACEHOLDER,
    redact_email,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(**extra: Any) -> logging.LogRecord:
    """Build a stdlib ``LogRecord`` with ``extra`` promoted as attributes.

    Mirrors what :meth:`logging.Logger.makeRecord` does for ``extra=``
    kwargs: every key becomes an attribute on the record. Standard
    record attributes are populated with safe defaults so the filter
    sees the same shape it does at runtime.
    """
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="message",
        args=None,
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def _apply_filter(**extra: Any) -> logging.LogRecord:
    """Run :class:`PiiLogFilter` over a record built from ``extra``."""
    record = _make_record(**extra)
    PiiLogFilter().filter(record)
    return record


def _apply_processor(event_dict: dict[str, Any]) -> dict[str, Any]:
    """Run :class:`PiiRedactionProcessor` over a copy of ``event_dict``."""
    return PiiRedactionProcessor()(None, "info", dict(event_dict))


# ---------------------------------------------------------------------------
# redact_email helper (sanity — the processor delegates to it for email keys)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("alice@example.com", "a***@example.com"),
        ("foo@bar.com", "f***@bar.com"),
        ("x@y.z", "x***@y.z"),
    ],
)
def test_redact_email_masks_local_part_and_keeps_domain(
    raw: str, expected: str
) -> None:
    assert redact_email(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "no-at-sign", "@nodomain", "nolocal@", 42, None],
)
def test_redact_email_falls_back_when_input_is_unusable(raw: Any) -> None:
    """Inputs without a usable local + domain collapse to ``***@***``."""
    assert redact_email(raw) == "***@***"


# ---------------------------------------------------------------------------
# 6.2 — email key is masked
# ---------------------------------------------------------------------------


def test_filter_masks_email_extra_key() -> None:
    """Task 6.2: ``extra={"email": "foo@bar.com"}`` becomes ``f***@bar.com``."""
    record = _apply_filter(email="foo@bar.com")
    assert record.email == "f***@bar.com"  # type: ignore[attr-defined]


def test_processor_masks_email_event_key() -> None:
    """Same contract, expressed against the structlog processor seam."""
    out = _apply_processor({"event": "user.signed_in", "email": "foo@bar.com"})
    assert out["email"] == "f***@bar.com"
    # Untouched keys round-trip verbatim.
    assert out["event"] == "user.signed_in"


# ---------------------------------------------------------------------------
# 6.3 — password key is replaced wholesale
# ---------------------------------------------------------------------------


def test_filter_replaces_password_with_placeholder() -> None:
    """Task 6.3: ``extra={"password": "hunter2"}`` → ``***REDACTED***``."""
    record = _apply_filter(password="hunter2")
    assert record.password == REDACTED_PLACEHOLDER  # type: ignore[attr-defined]
    assert "hunter2" not in str(record.password)  # type: ignore[attr-defined]


def test_processor_replaces_password_with_placeholder() -> None:
    out = _apply_processor({"password": "hunter2"})
    assert out["password"] == REDACTED_PLACEHOLDER


def test_strict_key_matches_case_insensitively() -> None:
    """``PASSWORD`` / ``Password`` are redacted just like ``password``."""
    record = _apply_filter(Password="hunter2")
    assert record.Password == REDACTED_PLACEHOLDER  # type: ignore[attr-defined]
    out = _apply_processor({"PASSWORD": "hunter2"})
    assert out["PASSWORD"] == REDACTED_PLACEHOLDER


# ---------------------------------------------------------------------------
# 6.4 — header values are redacted case-insensitively
# ---------------------------------------------------------------------------


def test_filter_redacts_authorization_header_in_extra() -> None:
    """Task 6.4: ``headers={"Authorization": ...}`` → ``***REDACTED***``."""
    record = _apply_filter(headers={"Authorization": "Bearer abc"})
    assert record.headers == {"Authorization": REDACTED_PLACEHOLDER}  # type: ignore[attr-defined]


def test_processor_redacts_authorization_header() -> None:
    out = _apply_processor({"headers": {"Authorization": "Bearer abc"}})
    assert out["headers"] == {"Authorization": REDACTED_PLACEHOLDER}


def test_processor_redacts_lowercase_authorization_header() -> None:
    """Header matching must be case-insensitive (the leak vector uses
    ``authorization`` with HTTP-style lowercasing)."""
    out = _apply_processor({"headers": {"authorization": "Bearer abc"}})
    assert out["headers"] == {"authorization": REDACTED_PLACEHOLDER}


def test_processor_redacts_nested_request_headers_path() -> None:
    """``request.headers`` is treated the same as a top-level ``headers``."""
    out = _apply_processor(
        {"request.headers": {"Cookie": "session=abc", "Accept": "json"}}
    )
    redacted = out["request.headers"]
    assert redacted["Cookie"] == REDACTED_PLACEHOLDER
    # Non-sensitive headers are left untouched.
    assert redacted["Accept"] == "json"


def test_processor_redacts_response_headers_set_cookie() -> None:
    """``response.headers``: ``Set-Cookie`` is on the header deny-list."""
    out = _apply_processor(
        {"response.headers": {"Set-Cookie": "refresh_token=xyz; HttpOnly"}}
    )
    assert out["response.headers"]["Set-Cookie"] == REDACTED_PLACEHOLDER


def test_filter_leaves_non_sensitive_headers_alone() -> None:
    """Headers outside the deny-list (and outside strict/email rules) pass through."""
    record = _apply_filter(
        headers={"Authorization": "Bearer abc", "Content-Type": "application/json"}
    )
    assert record.headers == {  # type: ignore[attr-defined]
        "Authorization": REDACTED_PLACEHOLDER,
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# 6.5 — exhaustively cover every key in the configured sets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("strict_key", sorted(REDACT_STRICT_KEYS))
def test_processor_redacts_every_strict_key(strict_key: str) -> None:
    """6.5: every entry in ``REDACT_STRICT_KEYS`` collapses to the placeholder."""
    out = _apply_processor({strict_key: "sensitive-value-do-not-log"})
    assert out[strict_key] == REDACTED_PLACEHOLDER
    assert "sensitive-value-do-not-log" not in str(out[strict_key])


@pytest.mark.parametrize("strict_key", sorted(REDACT_STRICT_KEYS))
def test_filter_redacts_every_strict_key(strict_key: str) -> None:
    """6.5: same coverage against the stdlib :class:`PiiLogFilter` seam.

    The filter is the safety net for log calls that bypass structlog.
    A drift between processor and filter coverage is a real leak: the
    spec requires both seams to apply the same policy.
    """
    record = _apply_filter(**{strict_key: "sensitive-value-do-not-log"})
    assert getattr(record, strict_key) == REDACTED_PLACEHOLDER


@pytest.mark.parametrize("email_key", sorted(REDACT_EMAIL_KEYS))
def test_processor_masks_every_email_key(email_key: str) -> None:
    """6.5: every entry in ``REDACT_EMAIL_KEYS`` passes through ``redact_email``."""
    out = _apply_processor({email_key: "carol@example.org"})
    assert out[email_key] == "c***@example.org"
    assert "carol@example.org" not in str(out[email_key])


@pytest.mark.parametrize("email_key", sorted(REDACT_EMAIL_KEYS))
def test_filter_masks_every_email_key(email_key: str) -> None:
    """6.5: stdlib-filter coverage for the email-key set."""
    record = _apply_filter(**{email_key: "carol@example.org"})
    assert getattr(record, email_key) == "c***@example.org"


def _title_case_header(name: str) -> str:
    """Return the canonical HTTP title-case form of a header name.

    ``"set-cookie"`` → ``"Set-Cookie"``. Mirrors the case real servers
    (Starlette, requests, etc.) emit on the wire — the form most
    likely to appear in a captured ``headers`` mapping at runtime.
    """
    return "-".join(part.capitalize() for part in name.split("-"))


@pytest.mark.parametrize("header_name", sorted(REDACT_HEADER_NAMES))
def test_processor_redacts_every_known_header_name(header_name: str) -> None:
    """Header deny-list: every entry is redacted regardless of case.

    Exercises the lowercase form (canonical in :data:`REDACT_HEADER_NAMES`),
    the upper-case form, and the canonical HTTP title-case form
    (``Authorization``, ``Set-Cookie``, ``X-Auth-Token``) — title-case is
    what Starlette and most HTTP clients emit on the wire, so it is the
    form the processor will see most often in production.
    """
    title_case = _title_case_header(header_name)
    out = _apply_processor(
        {
            "headers": {
                header_name: "sensitive-lower",
                header_name.upper(): "sensitive-upper",
                title_case: "sensitive-title",
            }
        }
    )
    assert out["headers"][header_name] == REDACTED_PLACEHOLDER
    assert out["headers"][header_name.upper()] == REDACTED_PLACEHOLDER
    assert out["headers"][title_case] == REDACTED_PLACEHOLDER


# ---------------------------------------------------------------------------
# Negative paths — defence in depth
# ---------------------------------------------------------------------------


def test_filter_leaves_stdlib_record_attrs_untouched() -> None:
    """The filter must NOT clobber standard ``LogRecord`` attributes.

    Reason: ``msg``/``args``/etc. drive formatting. A stray rewrite
    here would corrupt every log line.
    """
    record = _make_record()
    original_msg = record.msg
    original_levelname = record.levelname
    PiiLogFilter().filter(record)
    assert record.msg == original_msg
    assert record.levelname == original_levelname


def test_filter_returns_true_so_records_are_never_dropped() -> None:
    """``PiiLogFilter`` is a sanitiser, not a gate."""
    assert PiiLogFilter().filter(_make_record(password="x")) is True


def test_filter_does_not_scan_plain_string_args() -> None:
    """Value scanning is explicitly out of scope.

    Plain-string positional args that happen to look like an email
    pass through unchanged — call-site redaction is the intended
    approach for string-shaped log calls (see ``design.md``).
    """
    record = _make_record()
    record.args = ("alice@example.com",)
    PiiLogFilter().filter(record)
    assert record.args == ("alice@example.com",)


def test_filter_redacts_mapping_args() -> None:
    """``%(name)s``-style formatting with a dict args: the dict is sanitised."""
    record = _make_record()
    record.args = {"email": "bob@example.com", "password": "hunter2"}
    PiiLogFilter().filter(record)
    assert isinstance(record.args, dict)
    assert record.args["email"] == "b***@example.com"
    assert record.args["password"] == REDACTED_PLACEHOLDER


def test_processor_leaves_non_email_values_for_email_keys_untouched() -> None:
    """Email-key policy only fires on string values.

    A caller passing a non-string under an email key is unusual but
    not a leak; the processor passes it through rather than guessing.
    """
    out = _apply_processor({"email": None, "to": 42})
    assert out["email"] is None
    assert out["to"] == 42
