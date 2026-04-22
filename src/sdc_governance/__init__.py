"""
SDC Governance - W3C standards-based governance validation for SDC instances.

Validates governance content in XML data instances against governance
components defined in the SDC data model. If the model defines governance
(workflow, attestation, party/role, provenance, audit), the instance must
carry that governance content - and this library validates it.

No framework dependency. No middleware. A function call.

Install from PyPI::

    pip install sdc-governance

Basic usage::

    from sdc_governance import validate_governance

    result = validate_governance("model.xsd", "instance.xml")
    print(result.decision)   # EXECUTE, REFUSE, ESCALATE, or SKIP
    print(result.errors)     # list of governance validation errors

If installed alongside sdcvalidator, governance validation is called
automatically after structural validation passes.

See https://github.com/SemanticDataCharter/SDC_Governance for documentation.
"""

__version__ = "4.0.0"
