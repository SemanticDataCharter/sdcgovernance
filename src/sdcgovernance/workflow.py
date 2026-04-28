"""
Workflow validation for SDC governance.

Validates that workflow transitions in the XML instance are legitimate
according to the Workflow cluster tree defined in the SDC data model.

Workflow states are modeled as XdOrdinal components within sub-clusters
of a Workflow cluster. Each sub-cluster defines a valid path. Components
can be reused across sub-clusters (same CUID2) to model branching.
Validation is ordinal adjacency checking within the cluster tree.
Borrows the concepts of state and transition from automata theory,
as specified in W3C SCXML.

Returns OASIS XACML decisions: PERMIT, DENY, or INDETERMINATE with a
decision receipt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lxml import etree

SDC4_NS = "https://semanticdatacharter.com/ns/sdc4/"
XSD_NS = "http://www.w3.org/2001/XMLSchema"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
SDC4_META_NS = "https://semanticdatacharter.com/ontology/sdc4-meta/"


@dataclass
class WorkflowState:
    """A single state in a workflow path."""
    ordinal: float
    symbol: str
    label: str
    component_id: str = ""  # CUID2 from the model component name (mc-xxx)


@dataclass
class WorkflowPath:
    """A valid path through the workflow (one sub-cluster)."""
    label: str = ""
    states: list[WorkflowState] = field(default_factory=list)

    @property
    def state_symbols(self) -> list[str]:
        """Ordered list of state symbols in this path."""
        return [s.symbol for s in sorted(self.states, key=lambda s: s.ordinal)]

    def state_at_ordinal(self, ordinal: float) -> WorkflowState | None:
        """Find state at a specific ordinal position."""
        for s in self.states:
            if s.ordinal == ordinal:
                return s
        return None

    def next_states(self, current_ordinal: float) -> list[WorkflowState]:
        """Get valid next states from a given ordinal position."""
        sorted_states = sorted(self.states, key=lambda s: s.ordinal)
        for i, s in enumerate(sorted_states):
            if s.ordinal == current_ordinal and i + 1 < len(sorted_states):
                return [sorted_states[i + 1]]
        return []

    def contains_ordinal(self, ordinal: float) -> bool:
        """Check if this path contains a state at the given ordinal."""
        return any(s.ordinal == ordinal for s in self.states)


@dataclass
class WorkflowTree:
    """
    Complete workflow definition extracted from the model.

    Contains all valid paths (sub-clusters) with their XdOrdinal states.
    """
    label: str = ""
    paths: list[WorkflowPath] = field(default_factory=list)

    def find_current_state(self, symbol: str) -> list[tuple[WorkflowPath, WorkflowState]]:
        """Find all (path, state) pairs where the state matches the given symbol."""
        results = []
        for path in self.paths:
            for state in path.states:
                if state.symbol == symbol:
                    results.append((path, state))
        return results

    def get_allowed_transitions(self, current_symbol: str) -> list[dict[str, Any]]:
        """
        Get all valid next states from the current state.

        Returns a list of dicts with target state info and which path(s) it belongs to.
        """
        matches = self.find_current_state(current_symbol)
        if not matches:
            return []

        transitions: dict[str, dict[str, Any]] = {}
        for path, state in matches:
            next_states = path.next_states(state.ordinal)
            for ns in next_states:
                key = ns.symbol
                if key not in transitions:
                    transitions[key] = {
                        "target_symbol": ns.symbol,
                        "target_label": ns.label,
                        "target_ordinal": ns.ordinal,
                        "target_component_id": ns.component_id,
                        "paths": [],
                    }
                transitions[key]["paths"].append(path.label)

        return list(transitions.values())

    def is_valid_transition(self, current_symbol: str, target_symbol: str) -> bool:
        """Check if transitioning from current to target is valid in any path."""
        allowed = self.get_allowed_transitions(current_symbol)
        return any(t["target_symbol"] == target_symbol for t in allowed)


def extract_workflow_from_model(schema_path: str) -> WorkflowTree | None:
    """
    Extract the workflow cluster tree from an SDC data model XSD.

    Reads the model, finds the workflow ClusterType, and extracts
    sub-clusters with their XdOrdinal state definitions.

    Returns None if the model does not define a workflow.
    """
    tree = etree.parse(str(schema_path))
    root = tree.getroot()

    # Find the DMType restriction
    dm_type = _find_dm_restriction(root)
    if dm_type is None:
        return None

    # Find the workflow element in the DM sequence
    sequence = dm_type.find(
        f"{{{XSD_NS}}}complexContent/{{{XSD_NS}}}restriction/{{{XSD_NS}}}sequence"
    )
    if sequence is None:
        return None

    workflow_elem = None
    for elem in sequence.findall(f"{{{XSD_NS}}}element"):
        if elem.get("name") == "workflow":
            workflow_elem = elem
            break

    if workflow_elem is None:
        return None

    # The workflow element type is ClusterType. We need to find the
    # model components that define the workflow states.
    # In a real model, the workflow would reference specific components
    # via the cluster structure. For now, we extract any XdOrdinal
    # components in the model that are workflow-related.
    workflow_tree = WorkflowTree()

    # Look for workflow-specific component definitions in the schema
    # These are complexTypes that restrict ClusterType and are used
    # within the workflow structure
    _extract_workflow_components(root, workflow_tree)

    return workflow_tree if workflow_tree.paths else None


def extract_workflow_from_instance(instance_path: str) -> tuple[str, WorkflowTree | None]:
    """
    Extract workflow state from an XML instance.

    Returns (current_state, workflow_tree) where workflow_tree contains
    the paths defined in the instance's workflow element.

    The workflow element in the instance carries the cluster tree with
    actual ordinal values. current-state carries the current position.
    """
    tree = etree.parse(str(instance_path))
    root = tree.getroot()

    # Get current-state
    current_state = ""
    cs_elem = root.find(f"{{{SDC4_NS}}}current-state")
    if cs_elem is None:
        # Try without namespace (some instances use local names)
        cs_elem = root.find("current-state")
    if cs_elem is not None and cs_elem.text:
        current_state = cs_elem.text.strip()

    # Get workflow element
    workflow_elem = root.find(f"{{{SDC4_NS}}}workflow")
    if workflow_elem is None:
        workflow_elem = root.find("workflow")

    if workflow_elem is None:
        return current_state, None

    workflow_tree = _parse_workflow_cluster(workflow_elem)
    return current_state, workflow_tree


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


def _extract_workflow_components(
    root: etree._Element, workflow_tree: WorkflowTree
) -> None:
    """
    Extract workflow-related components from the model schema.

    Looks for complexTypes that are annotated as workflow components
    (identified by vocabulary bindings or naming conventions).
    """
    # Find complexTypes that restrict XdOrdinalType - these are potential
    # workflow state definitions
    ordinal_components: dict[str, list[WorkflowState]] = {}

    for ct in root.iter(f"{{{XSD_NS}}}complexType"):
        ct_name = ct.get("name", "")
        if not ct_name.startswith("mc-"):
            continue

        # Check if this restricts XdOrdinalType
        restriction = ct.find(
            f"{{{XSD_NS}}}complexContent/{{{XSD_NS}}}restriction"
        )
        if restriction is None:
            continue
        if restriction.get("base") != "sdc4:XdOrdinalType":
            continue

        # Check annotation for workflow-related vocabulary binding
        appinfo = ct.find(f"{{{XSD_NS}}}annotation/{{{XSD_NS}}}appinfo")
        if appinfo is None:
            continue

        # Extract component info
        component_id = ct_name  # mc-xxx CUID2
        label = ""
        is_workflow = False

        desc = appinfo.find(f"{{{RDF_NS}}}Description")
        if desc is not None:
            label_elem = desc.find(f"{{{RDFS_NS}}}label")
            if label_elem is not None and label_elem.text:
                label = label_elem.text

            # Check for workflow vocabulary binding
            for see_also in desc.findall(f"{{{RDFS_NS}}}seeAlso"):
                resource = see_also.get(f"{{{RDF_NS}}}resource", "")
                if "scxml" in resource.lower() or "workflow" in resource.lower():
                    is_workflow = True

            # Also check isDefinedBy for SCXML references
            for defined_by in desc.findall(f"{{{RDFS_NS}}}isDefinedBy"):
                resource = defined_by.get(f"{{{RDF_NS}}}resource", "")
                if "scxml" in resource.lower() or "workflow" in resource.lower():
                    is_workflow = True

        # Extract ordinal enumerations
        states = _extract_ordinal_enumerations(restriction, component_id, label)
        if states:
            ordinal_components[component_id] = states

    # If we found workflow-tagged ordinal components, build paths
    # For now, each ordinal component with workflow binding becomes a path
    # In practice, the cluster tree structure defines paths
    for comp_id, states in ordinal_components.items():
        path = WorkflowPath(label=comp_id, states=states)
        workflow_tree.paths.append(path)


def _extract_ordinal_enumerations(
    restriction: etree._Element, component_id: str, label: str
) -> list[WorkflowState]:
    """Extract ordinal enumeration values from an XdOrdinalType restriction."""
    states: list[WorkflowState] = []

    # Find the ordinal element with enumerations
    sequence = restriction.find(f"{{{XSD_NS}}}sequence")
    if sequence is None:
        return states

    for elem in sequence.findall(f"{{{XSD_NS}}}element"):
        if elem.get("name") != "ordinal":
            continue

        simple_type = elem.find(f"{{{XSD_NS}}}simpleType")
        if simple_type is None:
            continue

        inner_restriction = simple_type.find(f"{{{XSD_NS}}}restriction")
        if inner_restriction is None:
            continue

        for enum in inner_restriction.findall(f"{{{XSD_NS}}}enumeration"):
            value = enum.get("value", "")
            doc = ""
            doc_elem = enum.find(
                f"{{{XSD_NS}}}annotation/{{{XSD_NS}}}documentation"
            )
            if doc_elem is not None and doc_elem.text:
                doc = doc_elem.text.strip()

            try:
                ordinal_val = float(value)
            except (ValueError, TypeError):
                continue

            states.append(WorkflowState(
                ordinal=ordinal_val,
                symbol=doc or value,
                label=label,
                component_id=component_id,
            ))

    return states


def _parse_workflow_cluster(workflow_elem: etree._Element) -> WorkflowTree:
    """
    Parse a workflow ClusterType element from an XML instance.

    The workflow element contains sub-clusters (paths) with
    XdOrdinal items (states). This function extracts the tree structure.
    """
    workflow_tree = WorkflowTree()

    # Get workflow label
    label_elem = workflow_elem.find(f"{{{SDC4_NS}}}label")
    if label_elem is None:
        label_elem = workflow_elem.find("label")
    if label_elem is not None and label_elem.text:
        workflow_tree.label = label_elem.text.strip()

    # Look for sub-clusters (Cluster elements within the workflow)
    for cluster in workflow_elem.iter():
        tag = etree.QName(cluster.tag).localname if isinstance(cluster.tag, str) else ""
        if tag == "Cluster" or (cluster.tag and "Cluster" in str(cluster.tag)):
            path = _parse_path_cluster(cluster)
            if path.states:
                workflow_tree.paths.append(path)

    # If no sub-clusters found, treat the workflow itself as a single path
    if not workflow_tree.paths:
        path = _parse_path_cluster(workflow_elem)
        if path.states:
            workflow_tree.paths.append(path)

    return workflow_tree


def _parse_path_cluster(cluster_elem: etree._Element) -> WorkflowPath:
    """Parse a single path cluster, extracting XdOrdinal states."""
    path = WorkflowPath()

    label_elem = cluster_elem.find(f"{{{SDC4_NS}}}label")
    if label_elem is None:
        label_elem = cluster_elem.find("label")
    if label_elem is not None and label_elem.text:
        path.label = label_elem.text.strip()

    # Find XdOrdinal elements
    for elem in cluster_elem.iter():
        tag = etree.QName(elem.tag).localname if isinstance(elem.tag, str) else ""
        if tag == "XdOrdinal" or (elem.tag and "XdOrdinal" in str(elem.tag)):
            state = _parse_ordinal_state(elem)
            if state is not None:
                path.states.append(state)

    return path


def _parse_ordinal_state(ordinal_elem: etree._Element) -> WorkflowState | None:
    """Parse a single XdOrdinal element into a WorkflowState."""
    label = ""
    ordinal_val = None
    symbol = ""

    for child in ordinal_elem:
        local = etree.QName(child.tag).localname if isinstance(child.tag, str) else ""
        text = (child.text or "").strip()

        if local == "label":
            label = text
        elif local == "ordinal":
            try:
                ordinal_val = float(text)
            except (ValueError, TypeError):
                return None
        elif local == "symbol":
            symbol = text

    if ordinal_val is None:
        return None

    return WorkflowState(
        ordinal=ordinal_val,
        symbol=symbol or str(ordinal_val),
        label=label,
    )
