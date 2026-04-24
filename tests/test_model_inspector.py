"""
Tests for model_inspector - Phase 1.

Tests that the model inspector correctly identifies governance dimensions
by reading known DMType root slots in SDC data model XSD files.
"""

import pytest
from sdcgovernance.model_inspector import inspect_model, GovernanceModel


class TestNoGovernance:
    """Model with no governance slots populated."""

    def test_has_governance_is_false(self, model_no_governance):
        result = inspect_model(model_no_governance)
        assert result.has_governance is False

    def test_all_dimensions_inactive(self, model_no_governance):
        result = inspect_model(model_no_governance)
        assert result.workflow.present is False
        assert result.audit.present is False
        assert result.attestation.present is False
        assert result.party_role.subject_defined is False
        assert result.party_role.provider_defined is False
        assert result.party_role.participation_defined is False

    def test_model_id_extracted(self, model_no_governance):
        result = inspect_model(model_no_governance)
        assert "dm-test-no-governance" in result.model_id

    def test_model_label_extracted(self, model_no_governance):
        result = inspect_model(model_no_governance)
        assert result.model_label == "Test No Governance"

    def test_instance_id_required(self, model_no_governance):
        result = inspect_model(model_no_governance)
        assert result.instance_id_required is True


class TestAllGovernance:
    """Model with all governance slots populated."""

    def test_has_governance_is_true(self, model_all_governance):
        result = inspect_model(model_all_governance)
        assert result.has_governance is True

    def test_workflow_present(self, model_all_governance):
        result = inspect_model(model_all_governance)
        assert result.workflow.present is True
        assert result.workflow.current_state_defined is True

    def test_audit_present(self, model_all_governance):
        result = inspect_model(model_all_governance)
        assert result.audit.present is True
        assert result.audit.max_occurs == "unbounded"

    def test_attestation_present(self, model_all_governance):
        result = inspect_model(model_all_governance)
        assert result.attestation.present is True

    def test_party_role_all_present(self, model_all_governance):
        result = inspect_model(model_all_governance)
        assert result.party_role.subject_defined is True
        assert result.party_role.provider_defined is True
        assert result.party_role.participation_defined is True

    def test_protocol_defined(self, model_all_governance):
        result = inspect_model(model_all_governance)
        assert result.protocol_defined is True

    def test_acs_defined(self, model_all_governance):
        result = inspect_model(model_all_governance)
        assert result.acs_defined is True

    def test_xdlink_defined(self, model_all_governance):
        result = inspect_model(model_all_governance)
        assert result.xdlink_defined is True

    def test_active_dimensions(self, model_all_governance):
        result = inspect_model(model_all_governance)
        dims = result.active_dimensions
        assert dims["workflow"] is True
        assert dims["audit"] is True
        assert dims["attestation"] is True
        assert dims["party_role"] is True
        assert dims["protocol"] is True
        assert dims["acs"] is True
        assert dims["xdlink"] is True

    def test_model_label(self, model_all_governance):
        result = inspect_model(model_all_governance)
        assert result.model_label == "Test All Governance"


class TestWorkflowOnly:
    """Model with only workflow governance."""

    def test_has_governance_is_true(self, model_workflow_only):
        result = inspect_model(model_workflow_only)
        assert result.has_governance is True

    def test_workflow_present(self, model_workflow_only):
        result = inspect_model(model_workflow_only)
        assert result.workflow.present is True
        assert result.workflow.current_state_defined is True

    def test_other_dimensions_inactive(self, model_workflow_only):
        result = inspect_model(model_workflow_only)
        assert result.audit.present is False
        assert result.attestation.present is False
        assert result.party_role.subject_defined is False
        assert result.party_role.provider_defined is False
        assert result.party_role.participation_defined is False


class TestAuditOnly:
    """Model with only audit/provenance governance."""

    def test_has_governance_is_true(self, model_audit_only):
        result = inspect_model(model_audit_only)
        assert result.has_governance is True

    def test_audit_present(self, model_audit_only):
        result = inspect_model(model_audit_only)
        assert result.audit.present is True

    def test_workflow_not_present(self, model_audit_only):
        result = inspect_model(model_audit_only)
        assert result.workflow.present is False


class TestAttestationOnly:
    """Model with only attestation governance."""

    def test_has_governance_is_true(self, model_attestation_only):
        result = inspect_model(model_attestation_only)
        assert result.has_governance is True

    def test_attestation_present(self, model_attestation_only):
        result = inspect_model(model_attestation_only)
        assert result.attestation.present is True

    def test_workflow_not_present(self, model_attestation_only):
        result = inspect_model(model_attestation_only)
        assert result.workflow.present is False

    def test_audit_not_present(self, model_attestation_only):
        result = inspect_model(model_attestation_only)
        assert result.audit.present is False


class TestRealModel:
    """Test against a real CordovaOS model."""

    @pytest.fixture
    def healthcare_model(self, fixtures_dir):
        return fixtures_dir / "dm-ftluo2nybgxmn7mawttoos20.xsd"

    def test_real_model_inspects(self, healthcare_model):
        result = inspect_model(healthcare_model)
        assert isinstance(result, GovernanceModel)
        assert result.model_label == "Healthcare Record"
        assert result.workflow.present is True
        assert result.audit.present is True
        assert result.attestation.present is True
        assert result.party_role.subject_defined is True
        assert result.party_role.provider_defined is True
        assert result.instance_id_required is True
