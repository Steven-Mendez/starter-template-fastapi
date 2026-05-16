"""Background-jobs feature.

Owns the :class:`JobQueuePort` contract, the in-process adapter (for
dev/test — the only shipped adapter; the production job runtime, AWS
SQS + a Lambda worker, arrives at a later roadmap step), and the
:class:`JobHandlerRegistry` features use to contribute their job
handlers at composition time.
"""
