"""
SDC model inspector for governance components.

Reads an SDC data model (XSD) and determines which governance dimensions
are active by checking the known DMType root slots. Governance components
are at fixed positions in the DM root - no arbitrary search needed.

Slots inspected:
- DM.workflow (ClusterType, 0..1) -> Workflow dimension
- DM.current-state (xs:string, 0..1) -> Workflow state tracking
- DM.Audit[] (AuditType, 0..*) -> Provenance/Audit dimension
- DM.attestation (AttestationType, 0..1) -> Attestation dimension
- DM.subject (PartyType, 0..1) -> Party dimension
- DM.provider[] (PartyType, 0..*) -> Party dimension
- DM.Participation[] (ParticipationType, 0..*) -> Party/Role dimension
- DM.protocol (XdStringType, 0..1) -> DMN decision table input
- DM.acs (XdLinkType, 0..1) -> Access control / retention policy
- DM.XdLink[] (XdLinkType, 0..*) -> Governed relationships

Source of truth: SDCRM sdc4/schemas/sdc4.xsd
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lxml import etree

SDC4_NS = "https://semanticdatacharter.com/ns/sdc4/"
XSD_NS = "http://www.w3.org/2001/XMLSchema"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"

NSMAP = {
    "xsd": XSD_NS,
    "sdc4": SDC4_NS,
    "rdf": RDF_NS,
    "rdfs": RDFS_NS,
}

# Known DMType governance element names
GOVERNANCE_ELEMENTS = {
    "workflow",
    "current-state",
    "subject",
    "provider",
    "protocol",
    "acs",
    "attestation",
}

# Elements that use ref= instead of name= (substitution groups)
GOVERNANCE_REFS = {
    "sdc4:Audit",
    "sdc4:Participation",
    "sdc4:XdLink",
}


@dataclass
class WorkflowInfo:
    """Extracted workflow governance information."""
    present: bool = False
    current_state_defined: bool = False
    cluster_element: Any = None  # lxml element for the workflow ClusterType


@dataclass
class AuditInfo:
    """Extracted provenance/audit governance information."""
    present: bool = False
    max_occurs: str = "0"  # "unbounded" or a number


@dataclass
class AttestationInfo:
    """Extracted attestation governance information."""
    present: bool = False


@dataclass
class PartyRoleInfo:
    """Extracted party/role governance information."""
    subject_defined: bool = False
    provider_defined: bool = False
    participation_defined: bool = False


@dataclass
class GovernanceModel:
    """
    Result of inspecting an SDC data model for governance components.

    Each dimension is independent. A model may define any combination
    of governance dimensions, or none at all.
    """
    # Model identity
    model_id: str = ""
    model_label: str = ""

    # Instance identity fields (from DM root)
    instance_id_required: bool = False

    # Governance dimensions
    workflow: WorkflowInfo = field(default_factory=WorkflowInfo)
    audit: AuditInfo = field(default_factory=AuditInfo)
    attestation: AttestationInfo = field(default_factory=AttestationInfo)
    party_role: PartyRoleInfo = field(default_factory=PartyRoleInfo)

    # Additional governance-relevant elements
    protocol_defined: bool = False
    acs_defined: bool = False
    xdlink_defined: bool = False

    @property
    def has_governance(self) -> bool:
        """True if any governance dimension is active."""
        return (
            self.workflow.present
            or self.audit.present
            or self.attestation.present
            or self.party_role.subject_defined
            or self.party_role.provider_defined
            or self.party_role.participation_defined
        )

    @property
    def active_dimensions(self) -> dict[str, bool]:
        """Map of dimension names to their active status."""
        return {
            "workflow": self.workflow.present,
            "audit": self.audit.present,
            "attestation": self.attestation.present,
            "party_role": (
                self.party_role.subject_defined
                or self.party_role.provider_defined
                or self.party_role.participation_defined
            ),
            "protocol": self.protocol_defined,
            "acs": self.acs_defined,
            "xdlink": self.xdlink_defined,
        }


def inspect_model(schema_path: str | Path) -> GovernanceModel:
    """
    Inspect an SDC data model XSD and return governance component information.

    Reads the DMType restriction in the model and checks which optional
    governance slots are populated. The location of governance components
    is fixed by the RM structure - this function checks known positions.

    Args:
        schema_path: Path to the SDC data model XSD file.

    Returns:
        GovernanceModel describing which governance dimensions are defined.
    """
    schema_path = Path(schema_path)
    tree = etree.parse(str(schema_path))
    root = tree.getroot()

    result = GovernanceModel()

    # Find the DMType restriction - this is the model's complexType
    # that restricts sdc4:DMType
    dm_type = _find_dm_restriction(root)
    if dm_type is None:
        return result

    # Extract model identity from the schema annotation
    result.model_id = _extract_model_id(root)
    result.model_label = _extract_model_label(dm_type)

    # Get the sequence element containing all DM slots
    sequence = dm_type.find(
        f"{{{XSD_NS}}}complexContent/{{{XSD_NS}}}restriction/{{{XSD_NS}}}sequence"
    )
    if sequence is None:
        return result

    # Build a map of element name/ref -> element for the DM sequence
    elements = _map_sequence_elements(sequence)

    # Check each governance slot
    _inspect_instance_identity(elements, result)
    _inspect_workflow(elements, result)
    _inspect_audit(elements, result)
    _inspect_attestation(elements, result)
    _inspect_party_role(elements, result)
    _inspect_protocol(elements, result)
    _inspect_acs(elements, result)
    _inspect_xdlink(elements, result)

    return result


def _find_dm_restriction(root: etree._Element) -> etree._Element | None:
    """Find the complexType that restricts sdc4:DMType."""
    for ct in root.iter(f"{{{XSD_NS}}}complexType"):
        restriction = ct.find(
            f"{{{XSD_NS}}}complexContent/{{{XSD_NS}}}restriction"
        )
        if restriction is not None:
            base = restriction.get("base", "")
            if base == "sdc4:DMType":
                return ct
    return None


def _extract_model_id(root: etree._Element) -> str:
    """Extract the model CUID2 identifier from the schema annotation."""
    desc = root.find(
        f"{{{XSD_NS}}}annotation/{{{XSD_NS}}}appinfo"
        f"/{{{RDF_NS}}}RDF/{{{RDF_NS}}}Description"
    )
    if desc is not None:
        about = desc.get(f"{{{RDF_NS}}}about", "")
        return about
    return ""


def _extract_model_label(dm_type: etree._Element) -> str:
    """Extract the model label from the DMType annotation."""
    label = dm_type.find(
        f"{{{XSD_NS}}}annotation/{{{XSD_NS}}}appinfo"
        f"/{{{RDF_NS}}}Description/{{{RDFS_NS}}}label"
    )
    if label is not None and label.text:
        return label.text
    return ""


def _map_sequence_elements(sequence: etree._Element) -> dict[str, etree._Element]:
    """
    Build a map of element identifiers to elements.

    Named elements use their name attribute as key.
    Ref elements use the ref attribute value as key (e.g., "sdc4:Audit").
    """
    elements: dict[str, etree._Element] = {}
    for elem in sequence.findall(f"{{{XSD_NS}}}element"):
        name = elem.get("name")
        ref = elem.get("ref")
        if name:
            elements[name] = elem
        elif ref:
            elements[ref] = elem
    return elements


def _get_min_occurs(elem: etree._Element) -> int:
    """Get minOccurs as int, defaulting to 1 per XSD spec."""
    val = elem.get("minOccurs")
    if val is not None:
        return int(val)
    return 1  # XSD default


def _get_max_occurs(elem: etree._Element) -> str:
    """Get maxOccurs as string (may be 'unbounded')."""
    val = elem.get("maxOccurs")
    if val is not None:
        return val
    return "1"  # XSD default


def _inspect_instance_identity(
    elements: dict[str, etree._Element], result: GovernanceModel
) -> None:
    """Check instance_id cardinality."""
    elem = elements.get("instance_id")
    if elem is not None:
        result.instance_id_required = _get_min_occurs(elem) >= 1


def _inspect_workflow(
    elements: dict[str, etree._Element], result: GovernanceModel
) -> None:
    """Check DM.workflow and DM.current-state slots."""
    workflow_elem = elements.get("workflow")
    if workflow_elem is not None and _get_min_occurs(workflow_elem) >= 0:
        # workflow is present in the model definition (even if optional)
        result.workflow.present = True
        result.workflow.cluster_element = workflow_elem

    state_elem = elements.get("current-state")
    if state_elem is not None:
        result.workflow.current_state_defined = True


def _inspect_audit(
    elements: dict[str, etree._Element], result: GovernanceModel
) -> None:
    """Check DM.Audit[] slot."""
    audit_elem = elements.get("sdc4:Audit")
    if audit_elem is not None:
        result.audit.present = True
        result.audit.max_occurs = _get_max_occurs(audit_elem)


def _inspect_attestation(
    elements: dict[str, etree._Element], result: GovernanceModel
) -> None:
    """Check DM.attestation slot."""
    att_elem = elements.get("attestation")
    if att_elem is not None:
        result.attestation.present = True


def _inspect_party_role(
    elements: dict[str, etree._Element], result: GovernanceModel
) -> None:
    """Check DM.subject, DM.provider[], and DM.Participation[] slots."""
    if elements.get("subject") is not None:
        result.party_role.subject_defined = True

    if elements.get("provider") is not None:
        result.party_role.provider_defined = True

    if elements.get("sdc4:Participation") is not None:
        result.party_role.participation_defined = True


def _inspect_protocol(
    elements: dict[str, etree._Element], result: GovernanceModel
) -> None:
    """Check DM.protocol slot."""
    if elements.get("protocol") is not None:
        result.protocol_defined = True


def _inspect_acs(
    elements: dict[str, etree._Element], result: GovernanceModel
) -> None:
    """Check DM.acs slot."""
    if elements.get("acs") is not None:
        result.acs_defined = True


def _inspect_xdlink(
    elements: dict[str, etree._Element], result: GovernanceModel
) -> None:
    """Check DM.XdLink[] slot."""
    if elements.get("sdc4:XdLink") is not None:
        result.xdlink_defined = True
