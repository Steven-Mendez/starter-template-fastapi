"""Pure-application facts about the email feature's job contract.

Cross-feature consumers — producers that need to enqueue a ``send_email``
side effect — import the job name from here, not from
``features.email.composition.jobs`` (which would force their application
layer to depend on another feature's composition layer).

Composition layers ship factories and registry hooks; application layers
ship the names of things callers need at use-case construction time. The
job name is the latter.
"""

from __future__ import annotations

SEND_EMAIL_JOB = "send_email"
