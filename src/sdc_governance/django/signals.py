"""
Django model signals for governance enforcement.

Alternative to middleware for finer-grained control. Uses Django's
pre_save and post_save signals to intercept state changes on
governed entities.
"""

# TODO: Phase 2 implementation
# - pre_save signal: workflow enforcement check before commit
# - post_save signal: provenance record after successful commit
# - Signal-based attestation verification
# - Configurable per model via Django settings
