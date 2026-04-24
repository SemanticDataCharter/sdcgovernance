"""
Party/role constraint validation for SDC governance.

Validates party identity and role constraints from three DM root slots:
- DM.subject (PartyType, 0..1) - human subject identity
- DM.provider[] (PartyType, 0..*) - information source identity
- DM.Participation[] (ParticipationType, 0..*) - role-constrained participations

ParticipationType.function (XdStringType) is the role check target.
PartyType.party-ref (XdLinkType) resolves party identity across systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lxml import etree

SDC4_NS = "https://semanticdatacharter.com/ns/sdc4/"


@dataclass
class PartyInfo:
    """Extracted party information."""
    name: str = ""
    ref_link: str = ""
    ref_relation: str = ""


@dataclass
class ParticipationInfo:
    """Extracted participation with role."""
    label: str = ""
    performer: PartyInfo | None = None
    function: str = ""  # The role
    mode: str = ""
    start: str = ""
    end: str = ""


@dataclass
class PartyRoleData:
    """Extracted party/role content from an instance."""
    subject: PartyInfo | None = None
    providers: list[PartyInfo] = field(default_factory=list)
    participations: list[ParticipationInfo] = field(default_factory=list)

    @property
    def has_subject(self) -> bool:
        return self.subject is not None

    @property
    def has_providers(self) -> bool:
        return len(self.providers) > 0

    @property
    def has_participations(self) -> bool:
        return len(self.participations) > 0

    def participations_with_function(self, function: str) -> list[ParticipationInfo]:
        """Find all participations with a specific function/role."""
        return [p for p in self.participations if p.function == function]


@dataclass
class PartyRoleRequirements:
    """What the model requires for party/role validation."""
    require_subject: bool = False
    require_provider: bool = False
    required_functions: list[str] = field(default_factory=list)  # e.g., ["approver"]


@dataclass
class PartyRoleResult:
    """Result of party/role validation."""
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    data: PartyRoleData | None = None


def extract_party_role(instance_path: str) -> PartyRoleData:
    """
    Extract party/role content from an XML instance.

    Reads DM.subject, DM.provider[], and DM.Participation[] elements.
    """
    tree = etree.parse(str(instance_path))
    root = tree.getroot()

    return extract_party_role_from_element(root)


def extract_party_role_from_element(root: etree._Element) -> PartyRoleData:
    """Extract party/role from a parsed XML root element."""
    data = PartyRoleData()

    # Subject (PartyType, 0..1)
    subject_elem = _find_element(root, "subject")
    if subject_elem is not None:
        data.subject = _parse_party(subject_elem)

    # Provider[] (PartyType, 0..*)
    for provider_elem in _find_all_elements(root, "provider"):
        party = _parse_party(provider_elem)
        if party is not None:
            data.providers.append(party)

    # Participation[] (ParticipationType, 0..*)
    for part_elem in _find_all_elements(root, "Participation"):
        participation = _parse_participation(part_elem)
        if participation is not None:
            data.participations.append(participation)

    return data


def validate_party_role(
    data: PartyRoleData,
    requirements: PartyRoleRequirements | None = None,
) -> PartyRoleResult:
    """
    Validate party/role content against requirements.

    Args:
        data: Extracted party/role content from the instance.
        requirements: What the model requires. If None, no validation
            is performed (PERMIT).

    Returns:
        PartyRoleResult with validation status and errors.
    """
    if requirements is None:
        return PartyRoleResult(data=data)

    result = PartyRoleResult(data=data)

    # Check subject
    if requirements.require_subject and not data.has_subject:
        result.valid = False
        result.errors.append("DM.subject is required but missing from instance")

    # Check provider
    if requirements.require_provider and not data.has_providers:
        result.valid = False
        result.errors.append("DM.provider is required but missing from instance")

    # Check required functions/roles
    for required_function in requirements.required_functions:
        matches = data.participations_with_function(required_function)
        if not matches:
            available = [p.function for p in data.participations if p.function]
            result.valid = False
            result.errors.append(
                f"Required participation function '{required_function}' not found. "
                f"Available functions: {available}"
            )

    return result


def check_actor_role(
    data: PartyRoleData,
    actor: str,
    required_function: str,
) -> PartyRoleResult:
    """
    Check if a specific actor has the required function/role.

    The actor is matched against party-name or party-ref link in
    Participation.performer.

    Args:
        data: Extracted party/role content.
        actor: Actor identifier (name or ref link).
        required_function: Required function/role string.

    Returns:
        PartyRoleResult with validation status.
    """
    result = PartyRoleResult(data=data)

    matching_participations = []
    for p in data.participations:
        if p.performer is None:
            continue
        if (p.performer.name == actor or p.performer.ref_link == actor):
            matching_participations.append(p)

    if not matching_participations:
        result.valid = False
        result.errors.append(f"Actor '{actor}' not found in any participation")
        return result

    for p in matching_participations:
        if p.function == required_function:
            return result  # valid=True

    actual_functions = [p.function for p in matching_participations if p.function]
    result.valid = False
    result.errors.append(
        f"Actor '{actor}' has function(s) {actual_functions}, "
        f"but '{required_function}' is required"
    )
    return result


def _find_element(root: etree._Element, local_name: str) -> etree._Element | None:
    """Find element by local name, trying namespaced and bare."""
    elem = root.find(f"{{{SDC4_NS}}}{local_name}")
    if elem is None:
        elem = root.find(local_name)
    return elem


def _find_all_elements(root: etree._Element, local_name: str) -> list[etree._Element]:
    """Find all elements by local name, trying namespaced and bare."""
    elements = root.findall(f"{{{SDC4_NS}}}{local_name}")
    if not elements:
        elements = root.findall(local_name)
    return elements


def _parse_party(elem: etree._Element) -> PartyInfo | None:
    """Parse a PartyType element."""
    party = PartyInfo()

    name_elem = _find_child(elem, "party-name")
    if name_elem is not None and name_elem.text:
        party.name = name_elem.text.strip()

    ref_elem = _find_child(elem, "party-ref")
    if ref_elem is not None:
        link_elem = _find_child(ref_elem, "link")
        if link_elem is not None and link_elem.text:
            party.ref_link = link_elem.text.strip()
        relation_elem = _find_child(ref_elem, "relation")
        if relation_elem is not None and relation_elem.text:
            party.ref_relation = relation_elem.text.strip()

    return party


def _parse_participation(elem: etree._Element) -> ParticipationInfo | None:
    """Parse a ParticipationType element."""
    part = ParticipationInfo()

    label_elem = _find_child(elem, "label")
    if label_elem is not None and label_elem.text:
        part.label = label_elem.text.strip()

    performer_elem = _find_child(elem, "performer")
    if performer_elem is not None:
        part.performer = _parse_party(performer_elem)

    function_elem = _find_child(elem, "function")
    if function_elem is not None:
        val = _find_child(function_elem, "xdstring-value")
        if val is not None and val.text:
            part.function = val.text.strip()

    mode_elem = _find_child(elem, "mode")
    if mode_elem is not None:
        val = _find_child(mode_elem, "xdstring-value")
        if val is not None and val.text:
            part.mode = val.text.strip()

    start_elem = _find_child(elem, "start")
    if start_elem is not None and start_elem.text:
        part.start = start_elem.text.strip()

    end_elem = _find_child(elem, "end")
    if end_elem is not None and end_elem.text:
        part.end = end_elem.text.strip()

    return part


def _find_child(parent: etree._Element, local_name: str) -> etree._Element | None:
    """Find child element by local name, trying namespaced and bare."""
    elem = parent.find(f"{{{SDC4_NS}}}{local_name}")
    if elem is None:
        elem = parent.find(local_name)
    return elem
