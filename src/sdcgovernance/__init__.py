"""
sdcgovernance - W3C standards-based governance advisory engine for SDC instances.

Validates governance content in XML data instances against governance
components defined in the SDC data model. If the model defines governance
(workflow, attestation, party/role, provenance, audit), the instance must
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

__version__ = "4.0.0"
