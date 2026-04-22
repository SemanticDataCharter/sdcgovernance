"""
Shared test fixtures for sdc-governance tests.
"""

import pytest


@pytest.fixture
def sample_entity():
    """A minimal entity dict for testing provenance and workflow."""
    return {
        "id": "cuid2_test_entity_001",
        "type": "PatientEncounter",
        "status": "draft",
        "data": {"bp_systolic": 120, "bp_unit": "mmHg"},
    }


@pytest.fixture
def sample_workflow():
    """A minimal workflow definition for testing state machine enforcement."""
    return {
        "name": "encounter_workflow",
        "states": ["draft", "reviewed", "finalized", "amended"],
        "transitions": [
            {"from": "draft", "to": "reviewed", "requires_attestation": "reviewer"},
            {"from": "reviewed", "to": "finalized", "requires_attestation": "approver"},
            {"from": "finalized", "to": "amended", "requires_attestation": "approver"},
            {"from": "amended", "to": "reviewed", "requires_attestation": "reviewer"},
        ],
    }


@pytest.fixture
def sample_attestation():
    """A minimal attestation for testing authority verification."""
    return {
        "issuer": "cuid2_user_dr_smith",
        "role": "reviewer",
        "timestamp": "2026-04-22T10:00:00Z",
        "claim": "reviewed_and_approved",
    }
