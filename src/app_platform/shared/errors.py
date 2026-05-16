"""Shared application-error root.

CLAUDE.md describes ``Result[T, ApplicationError]`` as the universal use-case
return shape. Every feature's base error inherits (directly or transitively)
from :class:`ApplicationError`, giving the codebase one type to reason about
at the application/adapter boundary.

Concrete subclasses MUST be picklable so they round-trip across a serializing
job-runtime boundary (the future AWS SQS + Lambda worker; the ``arq`` runtime
was removed in ROADMAP ETAPA I step 5); if a subclass needs non-positional
constructor arguments, it MUST implement ``__reduce__`` to satisfy
``Exception.__reduce__``'s positional-only default.
"""

from __future__ import annotations


class ApplicationError(Exception):
    """Root of the application error hierarchy."""
