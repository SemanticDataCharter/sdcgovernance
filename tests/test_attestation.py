"""
Tests for attestation validation - Phase 3.

Tests AttestationType content extraction and validation against
requirements (pending flag, committer, proof, committed timestamp, reason).
"""

import pytest
from pathlib import Path
from sdcgovernance.attestation import (
    AttestationData,
    AttestationRequirements,
    AttestationResult,
    extract_attestation,
    validate_attestation,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestExtractAttestation:
    """Extract attestation content from XML instances."""

    def test_complete_attestation(self):
        data = extract_attestation(str(FIXTURES / "instance-attestation-complete.xml"))
        assert data.present is True
        assert data.pending is False
        assert data.has_committer is True
        assert data.committer_name == "Dr. Smith"
        assert "dr-smith" in data.committer_ref
        assert data.has_proof is True
        assert data.has_reason is True
        assert data.reason_value == "reviewed_and_approved"
        assert data.has_committed is True
        assert "2026-04-24" in data.committed_timestamp

    def test_pending_attestation(self):
        data = extract_attestation(str(FIXTURES / "instance-attestation-pending.xml"))
        assert data.present is True
        assert data.pending is True
        assert data.has_committer is False
        assert data.has_proof is False

    def test_no_committer_attestation(self):
        data = extract_attestation(str(FIXTURES / "instance-attestation-no-committer.xml"))
        assert data.present is True
        assert data.pending is False
        assert data.has_committer is False
        assert data.has_reason is True
        assert data.has_committed is True

    def test_no_attestation(self):
        data = extract_attestation(str(FIXTURES / "instance-no-attestation.xml"))
        assert data.present is False
        assert data.pending is None


class TestValidateAttestation:
    """Validate attestation against requirements."""

    def test_complete_passes_defaults(self):
        data = extract_attestation(str(FIXTURES / "instance-attestation-complete.xml"))
        result = validate_attestation(data)
        assert result.valid is True
        assert result.errors == []

    def test_pending_fails_require_completed(self):
        data = extract_attestation(str(FIXTURES / "instance-attestation-pending.xml"))
        result = validate_attestation(data, AttestationRequirements(require_completed=True))
        assert result.valid is False
        assert any("pending" in e.lower() for e in result.errors)

    def test_no_committer_fails_require_committer(self):
        data = extract_attestation(str(FIXTURES / "instance-attestation-no-committer.xml"))
        result = validate_attestation(data, AttestationRequirements(require_committer=True))
        assert result.valid is False
        assert any("committer" in e.lower() for e in result.errors)

    def test_no_proof_fails_require_proof(self):
        data = extract_attestation(str(FIXTURES / "instance-attestation-no-committer.xml"))
        result = validate_attestation(data, AttestationRequirements(require_proof=True))
        assert result.valid is False
        assert any("proof" in e.lower() for e in result.errors)

    def test_complete_passes_all_requirements(self):
        data = extract_attestation(str(FIXTURES / "instance-attestation-complete.xml"))
        reqs = AttestationRequirements(
            require_completed=True,
            require_committer=True,
            require_proof=True,
            require_committed=True,
            require_reason=True,
        )
        result = validate_attestation(data, reqs)
        assert result.valid is True

    def test_missing_attestation_fails(self):
        data = extract_attestation(str(FIXTURES / "instance-no-attestation.xml"))
        result = validate_attestation(data)
        assert result.valid is False
        assert any("missing" in e.lower() for e in result.errors)

    def test_no_requirements_permits(self):
        """No requirements means anything passes (even pending)."""
        data = extract_attestation(str(FIXTURES / "instance-attestation-pending.xml"))
        reqs = AttestationRequirements()  # all False
        result = validate_attestation(data, reqs)
        assert result.valid is True

    def test_multiple_failures_reported(self):
        data = extract_attestation(str(FIXTURES / "instance-attestation-pending.xml"))
        reqs = AttestationRequirements(
            require_completed=True,
            require_committer=True,
            require_proof=True,
            require_committed=True,
        )
        result = validate_attestation(data, reqs)
        assert result.valid is False
        assert len(result.errors) >= 3  # pending, committer, proof, committed


class TestAttestationIndependence:
    """Attestation is independent from workflow."""

    def test_attestation_without_workflow(self):
        """Attestation works when no workflow is present."""
        data = extract_attestation(str(FIXTURES / "instance-attestation-complete.xml"))
        result = validate_attestation(data)
        assert result.valid is True
