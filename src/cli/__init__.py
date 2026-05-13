"""Project-level composition roots for one-shot CLI tooling.

Modules in this package are peers of ``main.py`` and ``worker.py``:
they may import every feature's published ``composition/container.py``
API to assemble the same set of containers the live processes use.
Features themselves MUST NOT import from this package — see the
``Features do not import the CLI composition root`` contract in
``pyproject.toml``.
"""
