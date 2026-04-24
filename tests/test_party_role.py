"""
Tests for party/role validation - Phase 3.

Tests extraction and validation of DM.subject, DM.provider[],
and DM.Participation[] (with function/role constraints).
"""

import pytest
from pathlib import Path
from sdcgovernance.party_role import (
    PartyInfo,
    ParticipationInfo,
    PartyRoleData,
    PartyRoleRequirements,
    extract_party_role,
    validate_party_role,
    check_actor_role,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestExtractPartyRole:
    """Extract party/role content from XML instances."""

    def test_subject_extracted(self):
        data = extract_party_role(str(FIXTURES / "instance-party-role.xml"))
        assert data.has_subject is True
        assert data.subject.name == "John Doe"
        assert "john-doe" in data.subject.ref_link

    def test_providers_extracted(self):
        data = extract_party_role(str(FIXTURES / "instance-party-role.xml"))
        assert data.has_providers is True
        assert len(data.providers) == 2
        assert data.providers[0].name == "Dr. Smith"
        assert data.providers[1].name == "Lab System A"

    def test_participations_extracted(self):
        data = extract_party_role(str(FIXTURES / "instance-party-role.xml"))
        assert data.has_participations is True
        assert len(data.participations) == 2

    def test_participation_function(self):
        data = extract_party_role(str(FIXTURES / "instance-party-role.xml"))
        approvers = data.participations_with_function("approver")
        assert len(approvers) == 1
        assert approvers[0].performer.name == "Dr. Jones"

    def test_participation_viewer(self):
        data = extract_party_role(str(FIXTURES / "instance-party-role.xml"))
        viewers = data.participations_with_function("viewer")
        assert len(viewers) == 1
        assert viewers[0].performer.name == "Nurse Williams"

    def test_participation_mode(self):
        data = extract_party_role(str(FIXTURES / "instance-party-role.xml"))
        approvers = data.participations_with_function("approver")
        assert approvers[0].mode == "present"

    def test_participation_temporal(self):
        data = extract_party_role(str(FIXTURES / "instance-party-role.xml"))
        approvers = data.participations_with_function("approver")
        assert "2026-04-24T09:00:00Z" in approvers[0].start
        assert "2026-04-24T09:30:00Z" in approvers[0].end

    def test_provider_ref_link(self):
        data = extract_party_role(str(FIXTURES / "instance-party-role.xml"))
        assert "dr-smith" in data.providers[0].ref_link

    def test_no_party_data(self):
        data = extract_party_role(str(FIXTURES / "instance-no-attestation.xml"))
        assert data.has_subject is False
        assert data.has_providers is False
        assert data.has_participations is False


class TestValidatePartyRole:
    """Validate party/role against requirements."""

    def test_no_requirements_permits(self):
        data = extract_party_role(str(FIXTURES / "instance-party-role.xml"))
        result = validate_party_role(data)
        assert result.valid is True

    def test_require_subject_passes(self):
        data = extract_party_role(str(FIXTURES / "instance-party-role.xml"))
        reqs = PartyRoleRequirements(require_subject=True)
        result = validate_party_role(data, reqs)
        assert result.valid is True

    def test_require_subject_fails(self):
        data = extract_party_role(str(FIXTURES / "instance-no-attestation.xml"))
        reqs = PartyRoleRequirements(require_subject=True)
        result = validate_party_role(data, reqs)
        assert result.valid is False
        assert any("subject" in e.lower() for e in result.errors)

    def test_require_provider_passes(self):
        data = extract_party_role(str(FIXTURES / "instance-party-role.xml"))
        reqs = PartyRoleRequirements(require_provider=True)
        result = validate_party_role(data, reqs)
        assert result.valid is True

    def test_require_provider_fails(self):
        data = extract_party_role(str(FIXTURES / "instance-no-attestation.xml"))
        reqs = PartyRoleRequirements(require_provider=True)
        result = validate_party_role(data, reqs)
        assert result.valid is False

    def test_require_function_approver_passes(self):
        data = extract_party_role(str(FIXTURES / "instance-party-role.xml"))
        reqs = PartyRoleRequirements(required_functions=["approver"])
        result = validate_party_role(data, reqs)
        assert result.valid is True

    def test_require_function_admin_fails(self):
        data = extract_party_role(str(FIXTURES / "instance-party-role.xml"))
        reqs = PartyRoleRequirements(required_functions=["admin"])
        result = validate_party_role(data, reqs)
        assert result.valid is False
        assert any("admin" in e for e in result.errors)

    def test_require_multiple_functions(self):
        data = extract_party_role(str(FIXTURES / "instance-party-role.xml"))
        reqs = PartyRoleRequirements(required_functions=["approver", "viewer"])
        result = validate_party_role(data, reqs)
        assert result.valid is True

    def test_require_function_not_present(self):
        data = extract_party_role(str(FIXTURES / "instance-party-role.xml"))
        reqs = PartyRoleRequirements(required_functions=["approver", "supervisor"])
        result = validate_party_role(data, reqs)
        assert result.valid is False
        assert any("supervisor" in e for e in result.errors)

    def test_error_lists_available_functions(self):
        data = extract_party_role(str(FIXTURES / "instance-party-role.xml"))
        reqs = PartyRoleRequirements(required_functions=["admin"])
        result = validate_party_role(data, reqs)
        assert any("approver" in e for e in result.errors)
        assert any("viewer" in e for e in result.errors)


class TestCheckActorRole:
    """Check specific actor has a specific role."""

    def test_actor_has_role(self):
        data = extract_party_role(str(FIXTURES / "instance-party-role.xml"))
        result = check_actor_role(data, actor="Dr. Jones", required_function="approver")
        assert result.valid is True

    def test_actor_wrong_role(self):
        data = extract_party_role(str(FIXTURES / "instance-party-role.xml"))
        result = check_actor_role(data, actor="Nurse Williams", required_function="approver")
        assert result.valid is False
        assert any("viewer" in e for e in result.errors)

    def test_actor_not_found(self):
        data = extract_party_role(str(FIXTURES / "instance-party-role.xml"))
        result = check_actor_role(data, actor="Unknown Person", required_function="approver")
        assert result.valid is False
        assert any("not found" in e.lower() for e in result.errors)

    def test_actor_by_ref_link(self):
        data = extract_party_role(str(FIXTURES / "instance-party-role.xml"))
        result = check_actor_role(
            data,
            actor="https://identity.example.com/providers/dr-jones",
            required_function="approver",
        )
        assert result.valid is True

    def test_actor_by_ref_link_wrong_role(self):
        data = extract_party_role(str(FIXTURES / "instance-party-role.xml"))
        result = check_actor_role(
            data,
            actor="https://identity.example.com/providers/dr-jones",
            required_function="viewer",
        )
        assert result.valid is False
