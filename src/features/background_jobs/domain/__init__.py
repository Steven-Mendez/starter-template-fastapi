"""Background-jobs has no domain layer.

The feature is pure infrastructure (port + adapters + registry); there
is no business-rule surface to model. The empty package exists so
Import Linter contracts referencing ``background_jobs.domain`` resolve.
"""
