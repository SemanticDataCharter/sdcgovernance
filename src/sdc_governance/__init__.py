"""
SDC Governance - W3C standards-based runtime governance for the SDC ecosystem.

Enforces governance at execution time using W3C PROV, Verifiable Credentials
patterns, and SHACL. Framework-agnostic core with optional Django integration.

Install from PyPI::

    pip install sdc-governance

For Django integration::

    pip install sdc-governance[django]

Basic usage::

    from sdc_governance.workflow import WorkflowEnforcer
    from sdc_governance.provenance import ProvenanceRecorder
    from sdc_governance.receipts import ReceiptChain

See https://github.com/SemanticDataCharter/SDC_Governance for documentation.
"""

__version__ = "4.0.0"
