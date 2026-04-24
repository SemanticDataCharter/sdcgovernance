"""
Shared test fixtures for sdcgovernance tests.

Test models are minimal XSD files that restrict sdc4:DMType with
various governance slots populated or absent.
"""

import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    """Path to the test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def model_no_governance(fixtures_dir):
    """XSD model with no governance slots populated."""
    return fixtures_dir / "dm-no-governance.xsd"


@pytest.fixture
def model_all_governance(fixtures_dir):
    """XSD model with all governance slots populated."""
    return fixtures_dir / "dm-all-governance.xsd"


@pytest.fixture
def model_workflow_only(fixtures_dir):
    """XSD model with only workflow governance."""
    return fixtures_dir / "dm-workflow-only.xsd"


@pytest.fixture
def model_audit_only(fixtures_dir):
    """XSD model with only audit/provenance governance."""
    return fixtures_dir / "dm-audit-only.xsd"


@pytest.fixture
def model_attestation_only(fixtures_dir):
    """XSD model with only attestation governance."""
    return fixtures_dir / "dm-attestation-only.xsd"
