"""
SHACL validation for SDC governance.

Validates cross-entity and cross-field constraints that XSD structural
validation alone cannot express. Uses W3C SHACL shapes validated via
pyshacl against RDF data graphs.

SDC data models generate SHACL shapes as part of their output
(the _shacl.ttl files). This module validates instance data graphs
against those shapes and integrates the results into governance
decisions (SHACL non-conformance contributes to DENY).

Standards: W3C SHACL (https://www.w3.org/TR/shacl/)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from pyshacl import validate as shacl_validate
    HAS_PYSHACL = True
except ImportError:
    HAS_PYSHACL = False

try:
    from rdflib import Graph
    HAS_RDFLIB = True
except ImportError:
    HAS_RDFLIB = False

from sdcgovernance.receipts import Decision


@dataclass
class ShaclViolation:
    """A single SHACL constraint violation."""
    focus_node: str = ""
    result_path: str = ""
    message: str = ""
    severity: str = ""
    source_shape: str = ""


@dataclass
class ShaclResult:
    """Result of SHACL validation."""
    conforms: bool = True
    violations: list[ShaclViolation] = field(default_factory=list)
    decision: Decision = Decision.PERMIT
    report_text: str = ""
    errors: list[str] = field(default_factory=list)


def validate_shacl(
    data_graph: str | Path | Graph,
    shapes_graph: str | Path | Graph,
) -> ShaclResult:
    """
    Validate an RDF data graph against SHACL shapes.

    Args:
        data_graph: Path to RDF/Turtle data file, Turtle string, or rdflib Graph.
        shapes_graph: Path to SHACL shapes file, Turtle string, or rdflib Graph.

    Returns:
        ShaclResult with conformance status, violations, and governance decision.
    """
    if not HAS_PYSHACL:
        return ShaclResult(
            conforms=False,
            decision=Decision.INDETERMINATE,
            errors=["pyshacl is not installed. Install with: pip install pyshacl"],
        )

    if not HAS_RDFLIB:
        return ShaclResult(
            conforms=False,
            decision=Decision.INDETERMINATE,
            errors=["rdflib is not installed. Install with: pip install rdflib"],
        )

    # Load graphs
    data_g = _load_graph(data_graph)
    shapes_g = _load_graph(shapes_graph)

    if data_g is None:
        return ShaclResult(
            conforms=False,
            decision=Decision.INDETERMINATE,
            errors=["Failed to load data graph"],
        )

    if shapes_g is None:
        return ShaclResult(
            conforms=False,
            decision=Decision.INDETERMINATE,
            errors=["Failed to load shapes graph"],
        )

    # Run pyshacl validation
    try:
        conforms, results_graph, results_text = shacl_validate(
            data_graph=data_g,
            shacl_graph=shapes_g,
            inference="none",
            abort_on_first=False,
        )
    except Exception as exc:
        return ShaclResult(
            conforms=False,
            decision=Decision.INDETERMINATE,
            errors=[f"SHACL validation error: {exc}"],
        )

    result = ShaclResult(
        conforms=conforms,
        decision=Decision.PERMIT if conforms else Decision.DENY,
        report_text=results_text or "",
    )

    # Extract violations from the results graph
    if not conforms and results_graph is not None:
        result.violations = _extract_violations(results_graph)
        result.errors = [v.message for v in result.violations if v.message]

    return result


def validate_shacl_from_strings(
    data_turtle: str,
    shapes_turtle: str,
) -> ShaclResult:
    """
    Validate SHACL using Turtle strings directly.

    Convenience method for testing and programmatic use.

    Args:
        data_turtle: RDF/Turtle string for the data graph.
        shapes_turtle: RDF/Turtle string for the shapes graph.

    Returns:
        ShaclResult with conformance status and violations.
    """
    if not HAS_RDFLIB:
        return ShaclResult(
            conforms=False,
            decision=Decision.INDETERMINATE,
            errors=["rdflib is not installed"],
        )

    data_g = Graph()
    data_g.parse(data=data_turtle, format="turtle")

    shapes_g = Graph()
    shapes_g.parse(data=shapes_turtle, format="turtle")

    return validate_shacl(data_g, shapes_g)


def _load_graph(source: str | Path | Graph) -> Graph | None:
    """Load an RDF graph from a file path, string, or existing Graph."""
    if isinstance(source, Graph):
        return source

    g = Graph()
    source_str = str(source)

    # Check if it's a file path
    if Path(source_str).exists():
        try:
            g.parse(source_str)
            return g
        except Exception:
            return None

    # Try parsing as Turtle string
    try:
        g.parse(data=source_str, format="turtle")
        return g
    except Exception:
        pass

    return None


def _extract_violations(results_graph: Graph) -> list[ShaclViolation]:
    """Extract violation details from a SHACL validation results graph."""
    from rdflib.namespace import SH

    violations = []

    for result_node in results_graph.subjects(
        predicate=SH.resultSeverity, object=None
    ):
        violation = ShaclViolation()

        # Focus node
        for obj in results_graph.objects(result_node, SH.focusNode):
            violation.focus_node = str(obj)

        # Result path
        for obj in results_graph.objects(result_node, SH.resultPath):
            violation.result_path = str(obj)

        # Message
        for obj in results_graph.objects(result_node, SH.resultMessage):
            violation.message = str(obj)

        # Severity
        for obj in results_graph.objects(result_node, SH.resultSeverity):
            violation.severity = str(obj)

        # Source shape
        for obj in results_graph.objects(result_node, SH.sourceShape):
            violation.source_shape = str(obj)

        violations.append(violation)

    return violations
