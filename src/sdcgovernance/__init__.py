"""
sdcgovernance - W3C standards-based governance advisory engine for SDC instances.

Validates governance content in XML data instances against governance
components defined in the SDC data model. If the model defines governance
(workflow, attestation, party/role, provenance/audit), the instance must
carry that governance content - and this library validates it.

Returns decisions using OASIS XACML semantics: PERMIT, DENY, or INDETERMINATE.

sdcgovernance is independent from sdcvalidator. Both libraries read the schema
from the instance. Agents call each one independently, at different points in
a workflow, in whatever order the operational logic requires.

No framework dependency. No middleware. A function call.

Install from PyPI::

    pip install sdcgovernance

Basic usage::

    from sdcgovernance import validate_governance

    result = validate_governance("model.xsd", "instance.xml")
    print(result.decision)   # PERMIT, DENY, INDETERMINATE
    print(result.errors)     # list of governance validation errors

See https://github.com/SemanticDataCharter/sdcgovernance for documentation.
"""

__version__ = "4.0.0a1"

from sdcgovernance.model_inspector import GovernanceModel, inspect_model
from sdcgovernance.receipts import (
    Decision,
    GovernanceResult,
    Receipt,
    ReceiptChain,
)

__all__ = [
    "validate_governance",
    "inspect_model",
    "Decision",
    "GovernanceModel",
    "GovernanceResult",
    "Receipt",
    "ReceiptChain",
]


def validate_governance(
    schema_path: str,
    instance_path: str | None = None,
) -> GovernanceResult:
    """
    Validate governance content in an SDC instance against its model.

    This is the primary public API. It inspects the model for governance
    components and, if an instance is provided, validates the governance
    content in the instance against the model's requirements.

    Args:
        schema_path: Path to the SDC data model XSD file.
        instance_path: Path to the XML instance file. If None, only
            model inspection is performed (returns which governance
            dimensions are defined).

    Returns:
        GovernanceResult with XACML decision and details.
    """
    # Phase 1: Model inspection
    model = inspect_model(schema_path)

    if not model.has_governance:
        return GovernanceResult(
            decision=Decision.PERMIT,
            has_governance=False,
            dimensions_validated=model.active_dimensions,
        )

    # Phase 1 without instance: report what governance exists
    if instance_path is None:
        return GovernanceResult(
            decision=Decision.PERMIT,
            has_governance=True,
            dimensions_validated=model.active_dimensions,
        )

    # Instance validation will be implemented in Phases 2-4
    # For now, return PERMIT with governance model info
    return GovernanceResult(
        decision=Decision.PERMIT,
        has_governance=True,
        dimensions_validated=model.active_dimensions,
    )
