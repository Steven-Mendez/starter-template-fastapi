"""File-storage feature.

Provides :class:`FileStoragePort` and pluggable adapters (``local``
for filesystem-backed dev/test, ``s3`` as a stub for production
integration). No other feature consumes it yet; it ships as
scaffolding ready to be wired in.
"""
