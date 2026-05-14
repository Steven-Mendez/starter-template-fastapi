"""Maintenance use cases for the outbox feature.

These run on an operational schedule (cron or one-shot CLI) rather
than on the request path. The first inhabitant is :mod:`prune_outbox`,
which trims terminal-state rows and dedup marks past their retention
window so the outbox-related tables stay bounded in size.
"""
