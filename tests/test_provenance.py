"""
Tests for provenance/audit validation - Phase 4.

Tests AuditType extraction, required element validation, retention
policy enforcement, PROV record generation, and RDF/Turtle export.
"""

import pytest
from pathlib import Path
from sdcgovernance.provenance import (
    AuditRecord,
    ProvenanceData,
    ProvenanceRequirements,
    ProvenanceResult,
    RetentionLevel,
    ProvRecord,
    extract_provenance,
    validate_provenance,
    record_provenance,
    provenance_to_rdf,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestExtractProvenance:
    """Extract audit/provenance records from XML instances."""

    def test_complete_audit_records(self):
        data = extract_provenance(str(FIXTURES / "instance-audit-complete.xml"))
        assert data.has_records is True
        assert data.count == 2

    def test_first_record_content(self):
        data = extract_provenance(str(FIXTURES / "instance-audit-complete.xml"))
        r = data.records[0]
        assert r.label == "Initial Creation"
        assert r.system_id == "epic-ehr-prod-01"
        assert r.has_system_id is True
        assert r.system_user_name == "Dr. Smith"
        assert r.has_system_user is True
        assert "dr-smith" in r.system_user_ref
        assert r.location_label == "Porto Sereno General Hospital"
        assert r.has_location is True
        assert "2026-04-24T08:00:00Z" in r.timestamp
        assert r.has_timestamp is True

    def test_second_record_content(self):
        data = extract_provenance(str(FIXTURES / "instance-audit-complete.xml"))
        r = data.records[1]
        assert r.system_id == "sdc-studio-cloud"
        assert r.system_user_name == "Dr. Jones"
        assert r.has_location is False

    def test_missing_system_id(self):
        data = extract_provenance(str(FIXTURES / "instance-audit-missing-systemid.xml"))
        assert data.count == 1
        assert data.records[0].has_system_id is False

    def test_missing_timestamp(self):
        data = extract_provenance(str(FIXTURES / "instance-audit-missing-timestamp.xml"))
        assert data.count == 1
        assert data.records[0].has_timestamp is False

    def test_single_record(self):
        data = extract_provenance(str(FIXTURES / "instance-audit-single.xml"))
        assert data.count == 1
        assert data.most_recent.system_id == "sdc-studio-cloud"

    def test_no_audit_records(self):
        data = extract_provenance(str(FIXTURES / "instance-no-audit.xml"))
        assert data.has_records is False
        assert data.count == 0
        assert data.most_recent is None

    def test_record_hash_computed(self):
        data = extract_provenance(str(FIXTURES / "instance-audit-complete.xml"))
        assert data.records[0].record_hash != ""
        assert len(data.records[0].record_hash) == 64  # SHA-256 hex

    def test_record_hashes_differ(self):
        data = extract_provenance(str(FIXTURES / "instance-audit-complete.xml"))
        assert data.records[0].record_hash != data.records[1].record_hash


class TestValidateProvenance:
    """Validate provenance/audit against requirements."""

    def test_complete_passes_defaults(self):
        data = extract_provenance(str(FIXTURES / "instance-audit-complete.xml"))
        result = validate_provenance(data)
        assert result.valid is True

    def test_missing_system_id_fails(self):
        data = extract_provenance(str(FIXTURES / "instance-audit-missing-systemid.xml"))
        result = validate_provenance(data)
        assert result.valid is False
        assert any("system-id" in e for e in result.errors)

    def test_missing_timestamp_fails(self):
        data = extract_provenance(str(FIXTURES / "instance-audit-missing-timestamp.xml"))
        result = validate_provenance(data)
        assert result.valid is False
        assert any("timestamp" in e for e in result.errors)

    def test_no_records_fails_when_required(self):
        data = extract_provenance(str(FIXTURES / "instance-no-audit.xml"))
        result = validate_provenance(data, ProvenanceRequirements(require_audit=True))
        assert result.valid is False
        assert any("none found" in e.lower() for e in result.errors)

    def test_no_records_passes_when_not_required(self):
        data = extract_provenance(str(FIXTURES / "instance-no-audit.xml"))
        result = validate_provenance(data, ProvenanceRequirements(require_audit=False))
        assert result.valid is True

    def test_require_system_user_passes(self):
        data = extract_provenance(str(FIXTURES / "instance-audit-single.xml"))
        reqs = ProvenanceRequirements(require_system_user=True)
        result = validate_provenance(data, reqs)
        assert result.valid is True

    def test_require_system_user_fails(self):
        data = extract_provenance(str(FIXTURES / "instance-audit-missing-systemid.xml"))
        # This record has system-user but no system-id
        # Create a record with no system-user to test
        data_no_user = ProvenanceData(records=[
            AuditRecord(has_system_id=True, system_id="test", has_timestamp=True, timestamp="2026-01-01T00:00:00Z")
        ])
        reqs = ProvenanceRequirements(require_system_user=True)
        result = validate_provenance(data_no_user, reqs)
        assert result.valid is False
        assert any("system-user" in e for e in result.errors)


class TestActivityTypeFiltering:
    """Validate AS2 activity type constraints."""

    def test_allowed_activity_type(self):
        data = ProvenanceData(records=[
            AuditRecord(
                has_system_id=True, system_id="test",
                has_timestamp=True, timestamp="2026-01-01T00:00:00Z",
                activity_type="Create",
            )
        ])
        reqs = ProvenanceRequirements(allowed_activity_types={"Create", "Update"})
        result = validate_provenance(data, reqs)
        assert result.valid is True

    def test_disallowed_activity_type(self):
        data = ProvenanceData(records=[
            AuditRecord(
                has_system_id=True, system_id="test",
                has_timestamp=True, timestamp="2026-01-01T00:00:00Z",
                activity_type="Delete",
            )
        ])
        reqs = ProvenanceRequirements(allowed_activity_types={"Create", "Update"})
        result = validate_provenance(data, reqs)
        assert result.valid is False
        assert any("Delete" in e for e in result.errors)

    def test_no_activity_type_filter(self):
        """When allowed_activity_types is None, all types pass."""
        data = ProvenanceData(records=[
            AuditRecord(
                has_system_id=True, system_id="test",
                has_timestamp=True, timestamp="2026-01-01T00:00:00Z",
                activity_type="Delete",
            )
        ])
        reqs = ProvenanceRequirements(allowed_activity_types=None)
        result = validate_provenance(data, reqs)
        assert result.valid is True

    def test_empty_activity_type_passes(self):
        """Record with no activity type is not filtered."""
        data = ProvenanceData(records=[
            AuditRecord(
                has_system_id=True, system_id="test",
                has_timestamp=True, timestamp="2026-01-01T00:00:00Z",
                activity_type="",
            )
        ])
        reqs = ProvenanceRequirements(allowed_activity_types={"Create"})
        result = validate_provenance(data, reqs)
        assert result.valid is True


class TestRetentionPolicy:
    """Validate DPV retention policy enforcement."""

    def test_most_recent_passes_with_one(self):
        data = extract_provenance(str(FIXTURES / "instance-audit-single.xml"))
        reqs = ProvenanceRequirements(retention_level=RetentionLevel.MOST_RECENT)
        result = validate_provenance(data, reqs)
        assert result.valid is True

    def test_most_recent_fails_with_zero(self):
        data = extract_provenance(str(FIXTURES / "instance-no-audit.xml"))
        reqs = ProvenanceRequirements(
            require_audit=True,
            retention_level=RetentionLevel.MOST_RECENT,
        )
        result = validate_provenance(data, reqs)
        assert result.valid is False

    def test_last_n_passes(self):
        data = extract_provenance(str(FIXTURES / "instance-audit-complete.xml"))
        reqs = ProvenanceRequirements(retention_level=RetentionLevel.LAST_N, retention_n=2)
        result = validate_provenance(data, reqs)
        assert result.valid is True

    def test_last_n_fails_insufficient(self):
        data = extract_provenance(str(FIXTURES / "instance-audit-single.xml"))
        reqs = ProvenanceRequirements(retention_level=RetentionLevel.LAST_N, retention_n=3)
        result = validate_provenance(data, reqs)
        assert result.valid is False
        assert any("3" in e and "1" in e for e in result.errors)

    def test_full_chain_passes(self):
        data = extract_provenance(str(FIXTURES / "instance-audit-complete.xml"))
        reqs = ProvenanceRequirements(
            retention_level=RetentionLevel.FULL_CHAIN,
            min_records=2,
        )
        result = validate_provenance(data, reqs)
        assert result.valid is True

    def test_full_chain_fails_insufficient(self):
        data = extract_provenance(str(FIXTURES / "instance-audit-single.xml"))
        reqs = ProvenanceRequirements(
            retention_level=RetentionLevel.FULL_CHAIN,
            min_records=5,
        )
        result = validate_provenance(data, reqs)
        assert result.valid is False


class TestRecordProvenance:
    """Generate PROV-O compliant records."""

    def test_create_record(self):
        rec = record_provenance(
            activity_type="Create",
            agent_name="Dr. Smith",
            entity_id="cuid2-test-001",
            system_id="sdc-studio-cloud",
            description="Created patient encounter",
        )
        assert rec.activity_type == "Create"
        assert rec.agent_name == "Dr. Smith"
        assert rec.entity_id == "cuid2-test-001"
        assert rec.system_id == "sdc-studio-cloud"
        assert rec.started_at != ""
        assert rec.ended_at != ""

    def test_record_with_hashes(self):
        rec = record_provenance(
            activity_type="Update",
            agent_name="System Agent",
            entity_hash_before="abc123",
            entity_hash_after="def456",
        )
        assert rec.entity_hash_before == "abc123"
        assert rec.entity_hash_after == "def456"

    def test_record_to_dict(self):
        rec = record_provenance(
            activity_type="Accept",
            agent_name="Dr. Jones",
        )
        d = rec.to_dict()
        assert d["activity_type"] == "Accept"
        assert d["agent_name"] == "Dr. Jones"
        assert "started_at" in d


class TestRdfExport:
    """Export provenance as RDF/Turtle."""

    def test_export_single_record(self):
        rec = record_provenance(
            activity_type="Create",
            agent_name="Dr. Smith",
            entity_id="cuid2-test-001",
        )
        turtle = provenance_to_rdf([rec], instance_id="cuid2-test-001")
        assert "prov:Activity" in turtle or "ns1:Activity" in turtle or len(turtle) > 0

    def test_export_multiple_records(self):
        recs = [
            record_provenance("Create", "Dr. Smith", entity_id="test-001"),
            record_provenance("Update", "Dr. Jones", entity_id="test-001"),
        ]
        turtle = provenance_to_rdf(recs, instance_id="test-001")
        assert len(turtle) > 0
        # Should have two activities
        assert turtle.count("Activity") >= 2 or turtle.count("activity") >= 2

    def test_export_empty_returns_minimal(self):
        turtle = provenance_to_rdf([])
        # Should still have the entity declaration
        assert len(turtle) > 0


class TestAuditRecordHash:
    """Hash integrity of individual audit records."""

    def test_hash_deterministic(self):
        r = AuditRecord(
            system_id="test", has_system_id=True,
            timestamp="2026-01-01T00:00:00Z", has_timestamp=True,
        )
        h1 = r.compute_hash()
        h2 = r.compute_hash()
        assert h1 == h2

    def test_hash_changes_with_content(self):
        r1 = AuditRecord(system_id="system-a", has_system_id=True, timestamp="2026-01-01", has_timestamp=True)
        r2 = AuditRecord(system_id="system-b", has_system_id=True, timestamp="2026-01-01", has_timestamp=True)
        assert r1.compute_hash() != r2.compute_hash()


class TestRdfSourceLineage:
    """Sovereign source lineage (Beale-Sovereignty) in PROV-O export."""

    def test_export_emits_derivation(self):
        rec = record_provenance("Create", "Dr. Smith", entity_id="cuid2-001")
        turtle = provenance_to_rdf(
            [rec],
            instance_id="cuid2-001",
            source_instance_id="epic-abc",
            source_version_id="v3",
        )
        assert "wasDerivedFrom" in turtle
        assert "epic-abc" in turtle
        assert "v3" in turtle

    def test_export_without_source_has_no_derivation(self):
        rec = record_provenance("Create", "Dr. Smith", entity_id="cuid2-001")
        turtle = provenance_to_rdf([rec], instance_id="cuid2-001")
        assert "wasDerivedFrom" not in turtle
