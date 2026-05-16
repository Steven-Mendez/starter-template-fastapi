"""File-storage feature.

Provides :class:`FileStoragePort` and pluggable adapters (``local``
for filesystem-backed dev/test, ``s3`` a real ``boto3``-backed
adapter selected with ``APP_STORAGE_BACKEND=s3``, which requires
``boto3`` / the ``s3`` extra and bucket configuration). No other
feature consumes it yet; it ships as scaffolding ready to be wired
in.
"""
