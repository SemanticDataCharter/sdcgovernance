"""
Django middleware for automatic governance enforcement.

Intercepts save/update operations on workflow-governed entities.
Calls the core workflow, attestation, and provenance modules.
Configurable per model via Django settings.
"""

# TODO: Phase 2 implementation
# - Intercept model save/update via Django middleware
# - Read governance configuration from Django settings
# - Call workflow.enforce() for governed models
# - Call attestation.verify() for attested actions
# - Call provenance.record() for every state change
# - Generate receipt via receipts.issue()
