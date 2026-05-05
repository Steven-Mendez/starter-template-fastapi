from __future__ import annotations

from fastapi import FastAPI

from src.features._template.composition.container import TemplateContainer

# TODO(template):
# 1. Build a router in adapters/inbound/http/router.py
# 2. Implement an outbound adapter (e.g. SQLModel) under adapters/outbound/persistence/
# 3. Build a real `TemplateContainer` from settings/engine in this module
# 4. Add `register_<feature>(app, platform)` and call it from `src/main.py`
#
# This stub is intentionally inert: it is NOT registered in src/main.py.


def register_template(app: FastAPI, container: TemplateContainer) -> None:
    """TODO(template): mount routes and bind container, mirroring kanban.

    See ``src/features/kanban/composition/wiring.py`` for the canonical pattern.
    """
    raise NotImplementedError(
        "TODO(template): replace with real wiring before registering this feature"
    )
