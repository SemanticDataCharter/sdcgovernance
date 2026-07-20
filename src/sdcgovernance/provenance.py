"""
Provenance/Audit validation and W3C PROV record generation for SDC governance.

Audit and Provenance are the same governance dimension in SDC. Both answer:
what happened, who did it, when, to what entity. This module handles both.

The SDC RM component is sdc4:AuditType, which provides who/where/when
tracking of instances as they move between systems:
- system-id (XdStringType, required) -> prov:Entity context
- system-user (PartyType, optional) -> prov:Agent
- location (ClusterType, optional) -> provenance metadata
- timestamp (xs:dateTime, required) -> prov:Activity temporal bounds

External docs use "Provenance" (W3C vocabulary). Implementation discovers
AuditType components by their PROV-O vocabulary bindings.

Retention policies (modeled via DPV, same vocabulary used for SDC access control):
- Most recent record + hash (long-lived records, e.g., patient records)
- Last N records (configurable per model)
- Full chain (short-lived records, e.g., financial transactions)

Industry-specific agents advise on retention policy during modeling.
sdcgovernance validates whatever the model defines.

Standards: W3C PROV-O (https://www.w3.org/TR/prov-o/)
           W3C PROV-DM (https://www.w3.org/TR/prov-dm/)
           W3C Activity Streams 2.0 (https://www.w3.org/TR/activitystreams-core/)
           W3C DPV (https://w3c.github.io/dpv/dpv/)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from lxml import etree

try:
    from rdflib import Graph, Namespace, Literal, URIRef, BNode
    from rdflib.namespace import RDF, RDFS, XSD as RDF_XSD
    HAS_RDFLIB = True
except ImportError:
    HAS_RDFLIB = False

SDC4_NS = "https://semanticdatacharter.com/ns/sdc4/"


class RetentionLevel(Enum):
    """DPV-aligned retention policy levels."""
    MOST_RECENT = "most_recent"  # 1 record + hash
    LAST_N = "last_n"           # N records + hash
    FULL_CHAIN = "full_chain"   # Complete history


# W3C Activity Streams 2.0 activity types commonly used in governance
VALID_AS2_ACTIVITY_TYPES = {
    "Create", "Update", "Delete", "Accept", "Reject",
    "Add", "Remove", "Move", "Read", "View",
    "Approve", "Block", "Flag", "Ignore",
}


@dataclass
class AuditRecord:
    """Extracted content from a single sdc4:Audit (AuditType) element."""
    label: str = ""
    system_id: str = ""
    system_user_name: str = ""
    system_user_ref: str = ""
    has_system_user: bool = False
    location_label: str = ""
    has_location: bool = False
    timestamp: str = ""
    has_timestamp: bool = False
    has_system_id: bool = False
    # Activity type (if annotated via AS2 vocabulary)
    activity_type: str = ""
    # Hash for chain integrity
    record_hash: str = ""

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of this audit record's content."""
        content = {
            "system_id": self.system_id,
            "system_user_name": self.system_user_name,
            "system_user_ref": self.system_user_ref,
            "location_label": self.location_label,
            "timestamp": self.timestamp,
            "activity_type": self.activity_type,
        }
        canonical = json.dumps(
            content,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class ProvenanceData:
    """Extracted provenance/audit content from an instance."""
    records: list[AuditRecord] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.records)

    @property
    def has_records(self) -> bool:
        return len(self.records) > 0

    @property
    def most_recent(self) -> AuditRecord | None:
        """Most recent record by timestamp (last in document order)."""
        if self.records:
            return self.records[-1]
        return None


@dataclass
class ProvenanceRequirements:
    """What the model requires for provenance validation."""
    require_audit: bool = True
    require_system_user: bool = False
    retention_level: RetentionLevel = RetentionLevel.MOST_RECENT
    retention_n: int = 1  # For LAST_N policy
    allowed_activity_types: set[str] | None = None  # None = all allowed
    min_records: int = 1


@dataclass
class ProvenanceResult:
    """Result of provenance/audit validation."""
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    data: ProvenanceData | None = None


@dataclass
class ProvRecord:
    """A generated W3C PROV-O compliant record."""
    activity_type: str  # AS2 activity type
    agent_name: str
    agent_ref: str = ""
    entity_id: str = ""
    entity_hash_before: str = ""
    entity_hash_after: str = ""
    started_at: str = ""
    ended_at: str = ""
    system_id: str = ""
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "activity_type": self.activity_type,
            "agent_name": self.agent_name,
            "agent_ref": self.agent_ref,
            "entity_id": self.entity_id,
            "entity_hash_before": self.entity_hash_before,
            "entity_hash_after": self.entity_hash_after,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "system_id": self.system_id,
            "description": self.description,
        }


def extract_provenance(instance_path: str) -> ProvenanceData:
    """
    Extract provenance/audit records from an XML instance.

    Reads all DM.Audit[] (AuditType) elements from the DM root.
    """
    tree = etree.parse(str(instance_path))
    root = tree.getroot()
    return extract_provenance_from_element(root)


def extract_provenance_from_element(root: etree._Element) -> ProvenanceData:
    """Extract provenance/audit from a parsed XML root element."""
    data = ProvenanceData()

    # Find all Audit elements (use ref-based elements: sdc4:Audit)
    for audit_elem in _find_all_elements(root, "Audit"):
        record = _parse_audit_record(audit_elem)
        record.record_hash = record.compute_hash()
        data.records.append(record)

    return data


def validate_provenance(
    data: ProvenanceData,
    requirements: ProvenanceRequirements | None = None,
) -> ProvenanceResult:
    """
    Validate provenance/audit content against requirements.

    Checks:
    - Required elements present in each record (system-id, timestamp)
    - system-user present when required
    - Activity types valid against AS2 allowed list
    - Retention policy honored (correct number of records)

    Args:
        data: Extracted provenance content from the instance.
        requirements: What the model requires. If None, uses defaults.

    Returns:
        ProvenanceResult with validation status and errors.
    """
    if requirements is None:
        requirements = ProvenanceRequirements()

    result = ProvenanceResult(data=data)

    # Check if audit records are required but missing
    if requirements.require_audit and not data.has_records:
        result.valid = False
        result.errors.append("Audit/provenance records required but none found in instance")
        return result

    # Validate each record individually
    for i, record in enumerate(data.records):
        prefix = f"Audit record {i + 1}"

        # system-id is required by the RM
        if not record.has_system_id:
            result.valid = False
            result.errors.append(f"{prefix}: system-id is required but missing")

        # timestamp is required by the RM
        if not record.has_timestamp:
            result.valid = False
            result.errors.append(f"{prefix}: timestamp is required but missing")

        # system-user when required by PROV-O bindings
        if requirements.require_system_user and not record.has_system_user:
            result.valid = False
            result.errors.append(f"{prefix}: system-user (prov:Agent) is required but missing")

        # Activity type filtering
        if (requirements.allowed_activity_types is not None
                and record.activity_type
                and record.activity_type not in requirements.allowed_activity_types):
            result.valid = False
            result.errors.append(
                f"{prefix}: activity type '{record.activity_type}' is not allowed. "
                f"Allowed types: {sorted(requirements.allowed_activity_types)}"
            )

    # Validate retention policy (only if audit is required and records exist)
    if requirements.require_audit and data.has_records:
        _validate_retention(data, requirements, result)

    return result


def record_provenance(
    activity_type: str,
    agent_name: str,
    entity_id: str = "",
    agent_ref: str = "",
    system_id: str = "",
    description: str = "",
    entity_hash_before: str = "",
    entity_hash_after: str = "",
) -> ProvRecord:
    """
    Generate a W3C PROV-O compliant provenance record.

    Creates a PROV record documenting a governance action. The record
    follows PROV-DM vocabulary: Activity (what happened), Agent (who),
    Entity (what was affected), temporal bounds.

    Args:
        activity_type: W3C Activity Streams 2.0 type (Create, Update, Accept, etc.)
        agent_name: Name of the agent performing the action.
        entity_id: ID of the entity being acted upon (DM.instance_id).
        agent_ref: URI reference for the agent.
        system_id: System that produced this record.
        description: Human-readable description of the action.
        entity_hash_before: SHA-256 hash of entity state before action.
        entity_hash_after: SHA-256 hash of entity state after action.

    Returns:
        ProvRecord with PROV-O compliant content.
    """
    now = datetime.now(timezone.utc).isoformat()

    return ProvRecord(
        activity_type=activity_type,
        agent_name=agent_name,
        agent_ref=agent_ref,
        entity_id=entity_id,
        entity_hash_before=entity_hash_before,
        entity_hash_after=entity_hash_after,
        started_at=now,
        ended_at=now,
        system_id=system_id,
        description=description,
    )


def provenance_to_rdf(
    records: list[ProvRecord],
    instance_id: str = "",
    source_instance_id: str = "",
    source_version_id: str = "",
) -> str:
    """
    Export provenance records as RDF/Turtle using W3C PROV-O vocabulary.

    Entity state hashes are modeled using the SDC4 RM XdFileType pattern
    (hash-function + hash-result), represented as structured blank nodes
    within a ValidationDetails container linked to each activity. This
    avoids extending the sdc4 namespace beyond what the RM defines.

    Args:
        records: List of ProvRecord objects to export.
        instance_id: DM.instance_id for the entity URI.
        source_instance_id: DM.source_instance_id, upstream source lineage.
            When present, adds prov:wasDerivedFrom to a source entity.
        source_version_id: DM.source_version_id, upstream source version.

    Returns:
        RDF/Turtle string. Returns empty string if rdflib is not installed.
    """
    if not HAS_RDFLIB:
        return ""

    PROV = Namespace("http://www.w3.org/ns/prov#")
    AS2 = Namespace("https://www.w3.org/ns/activitystreams#")
    SDC = Namespace("https://semanticdatacharter.com/ns/sdc4/")

    g = Graph()
    g.bind("prov", PROV)
    g.bind("as", AS2)
    g.bind("sdc4", SDC)

    entity_uri = SDC[instance_id] if instance_id else BNode()
    g.add((entity_uri, RDF.type, PROV.Entity))

    # Sovereign source lineage (Beale-Sovereignty): the SDC entity was derived
    # from an upstream source-system record. Modeled as prov:wasDerivedFrom to a
    # source entity carrying the RM-defined source identifiers.
    if source_instance_id:
        source_entity = BNode()
        g.add((source_entity, RDF.type, PROV.Entity))
        g.add((source_entity, SDC["source_instance_id"], Literal(source_instance_id)))
        if source_version_id:
            g.add((source_entity, SDC["source_version_id"], Literal(source_version_id)))
        g.add((entity_uri, PROV.wasDerivedFrom, source_entity))

    for i, rec in enumerate(records):
        activity = SDC[f"activity-{i}"]
        agent = SDC[rec.agent_ref] if rec.agent_ref else BNode()

        # Activity
        g.add((activity, RDF.type, PROV.Activity))
        if rec.activity_type:
            g.add((activity, PROV.type, Literal(rec.activity_type)))
        if rec.started_at:
            g.add((activity, PROV.startedAtTime, Literal(rec.started_at, datatype=RDF_XSD.dateTime)))
        if rec.ended_at:
            g.add((activity, PROV.endedAtTime, Literal(rec.ended_at, datatype=RDF_XSD.dateTime)))
        if rec.description:
            g.add((activity, RDFS.comment, Literal(rec.description)))

        # Agent
        g.add((agent, RDF.type, PROV.Agent))
        g.add((agent, RDFS.label, Literal(rec.agent_name)))
        g.add((activity, PROV.wasAssociatedWith, agent))

        # Entity relationships
        g.add((entity_uri, PROV.wasGeneratedBy, activity))
        g.add((activity, PROV.used, entity_uri))

        # Entity state hashes as XdFileType-pattern validation details.
        # Uses RM-defined properties (hash-function, hash-result) within
        # a validation-details container, not invented namespace extensions.
        if rec.entity_hash_before or rec.entity_hash_after:
            validation = BNode()
            g.add((activity, SDC["validation-details"], validation))
            if rec.entity_hash_before:
                hash_before = BNode()
                g.add((validation, SDC["entity-state-before"], hash_before))
                g.add((hash_before, SDC["hash-function"], Literal("SHA-256")))
                g.add((hash_before, SDC["hash-result"], Literal(rec.entity_hash_before)))
            if rec.entity_hash_after:
                hash_after = BNode()
                g.add((validation, SDC["entity-state-after"], hash_after))
                g.add((hash_after, SDC["hash-function"], Literal("SHA-256")))
                g.add((hash_after, SDC["hash-result"], Literal(rec.entity_hash_after)))

    return g.serialize(format="turtle")


def _validate_retention(
    data: ProvenanceData,
    requirements: ProvenanceRequirements,
    result: ProvenanceResult,
) -> None:
    """Validate retention policy compliance."""
    if requirements.retention_level == RetentionLevel.MOST_RECENT:
        if data.count < 1:
            result.valid = False
            result.errors.append(
                "Retention policy 'most_recent' requires at least 1 audit record"
            )
    elif requirements.retention_level == RetentionLevel.LAST_N:
        if data.count < requirements.retention_n:
            result.valid = False
            result.errors.append(
                f"Retention policy 'last_n' requires at least {requirements.retention_n} "
                f"audit records, but instance has {data.count}"
            )
    elif requirements.retention_level == RetentionLevel.FULL_CHAIN:
        if data.count < requirements.min_records:
            result.valid = False
            result.errors.append(
                f"Retention policy 'full_chain' requires at least {requirements.min_records} "
                f"audit records, but instance has {data.count}"
            )
        # Verify hash chain integrity for full chain
        if data.count >= 2:
            for i in range(1, data.count):
                prev_hash = data.records[i - 1].record_hash
                if not prev_hash:
                    result.valid = False
                    result.errors.append(
                        f"Audit record {i}: missing hash for chain integrity verification"
                    )


def _find_all_elements(root: etree._Element, local_name: str) -> list[etree._Element]:
    """Find all elements by local name, trying namespaced and bare."""
    elements = root.findall(f"{{{SDC4_NS}}}{local_name}")
    if not elements:
        elements = root.findall(local_name)
    return elements


def _find_child(parent: etree._Element, local_name: str) -> etree._Element | None:
    """Find child element by local name, trying namespaced and bare."""
    elem = parent.find(f"{{{SDC4_NS}}}{local_name}")
    if elem is None:
        elem = parent.find(local_name)
    return elem


def _parse_audit_record(audit_elem: etree._Element) -> AuditRecord:
    """Parse a single AuditType element into an AuditRecord."""
    record = AuditRecord()

    # label
    label_elem = _find_child(audit_elem, "label")
    if label_elem is not None and label_elem.text:
        record.label = label_elem.text.strip()

    # system-id (XdStringType, required)
    sysid_elem = _find_child(audit_elem, "system-id")
    if sysid_elem is not None:
        record.has_system_id = True
        val = _find_child(sysid_elem, "xdstring-value")
        if val is not None and val.text:
            record.system_id = val.text.strip()

    # system-user (PartyType, optional)
    sysuser_elem = _find_child(audit_elem, "system-user")
    if sysuser_elem is not None:
        record.has_system_user = True
        name_elem = _find_child(sysuser_elem, "party-name")
        if name_elem is not None and name_elem.text:
            record.system_user_name = name_elem.text.strip()
        ref_elem = _find_child(sysuser_elem, "party-ref")
        if ref_elem is not None:
            link_elem = _find_child(ref_elem, "link")
            if link_elem is not None and link_elem.text:
                record.system_user_ref = link_elem.text.strip()

    # location (ClusterType, optional)
    loc_elem = _find_child(audit_elem, "location")
    if loc_elem is not None:
        record.has_location = True
        loc_label = _find_child(loc_elem, "label")
        if loc_label is not None and loc_label.text:
            record.location_label = loc_label.text.strip()

    # timestamp (xs:dateTime, required)
    ts_elem = _find_child(audit_elem, "timestamp")
    if ts_elem is not None and ts_elem.text:
        record.has_timestamp = True
        record.timestamp = ts_elem.text.strip()

    return record
