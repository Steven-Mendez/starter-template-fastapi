"""Background-jobs feature.

Owns the :class:`JobQueuePort` contract, the in-process adapter (for
dev/test), the arq adapter (for production), and the
:class:`JobHandlerRegistry` features use to contribute their job
handlers at composition time.
"""
