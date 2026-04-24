"""
Attestation validation for SDC governance.

Validates DM.attestation (AttestationType) content in XML instances.
AttestationType has one required element (pending: xs:boolean) and
optional elements for committer, proof, reason, committed, and view.

Attestation is independent from workflow. They compose optionally.

Follows the W3C Verifiable Credentials Data Model 2.0 pattern
(issuer/holder/verifier) where committer maps to VC issuer.

Standards: W3C VC Data Model 2.0 (https://www.w3.org/TR/vc-data-model-2.0/)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lxml import etree

SDC4_NS = "https://semanticdatacharter.com/ns/sdc4/"


@dataclass
class AttestationData:
    """Extracted attestation content from an instance."""
    present: bool = False
    pending: bool | None = None
    has_committer: bool = False
    committer_name: str = ""
    committer_ref: str = ""
    has_proof: bool = False
    has_reason: bool = False
    reason_value: str = ""
    committed_timestamp: str = ""
    has_committed: bool = False


@dataclass
class AttestationRequirements:
    """What the model requires for attestation validation."""
    require_completed: bool = False  # pending must be false
    require_committer: bool = False
    require_proof: bool = False
    require_committed: bool = False
    require_reason: bool = False


@dataclass
class AttestationResult:
    """Result of attestation validation."""
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    data: AttestationData | None = None


def extract_attestation(instance_path: str) -> AttestationData:
    """
    Extract attestation content from an XML instance.

    Reads the DM.attestation element and extracts its content.
    Returns AttestationData with present=False if no attestation element exists.
    """
    tree = etree.parse(str(instance_path))
    root = tree.getroot()

    return extract_attestation_from_element(root)


def extract_attestation_from_element(root: etree._Element) -> AttestationData:
    """Extract attestation from a parsed XML root element."""
    data = AttestationData()

    # Find attestation element (try with and without namespace)
    att = root.find(f"{{{SDC4_NS}}}attestation")
    if att is None:
        att = root.find("attestation")
    if att is None:
        return data

    data.present = True

    # pending (required in AttestationType)
    pending_elem = att.find(f"{{{SDC4_NS}}}pending")
    if pending_elem is None:
        pending_elem = att.find("pending")
    if pending_elem is not None and pending_elem.text is not None:
        data.pending = pending_elem.text.strip().lower() == "true"

    # committer (PartyType, optional)
    committer = att.find(f"{{{SDC4_NS}}}committer")
    if committer is None:
        committer = att.find("committer")
    if committer is not None:
        data.has_committer = True
        name_elem = committer.find(f"{{{SDC4_NS}}}party-name")
        if name_elem is None:
            name_elem = committer.find("party-name")
        if name_elem is not None and name_elem.text:
            data.committer_name = name_elem.text.strip()

        ref_elem = committer.find(f"{{{SDC4_NS}}}party-ref")
        if ref_elem is None:
            ref_elem = committer.find("party-ref")
        if ref_elem is not None:
            link_elem = ref_elem.find(f"{{{SDC4_NS}}}link")
            if link_elem is None:
                link_elem = ref_elem.find("link")
            if link_elem is not None and link_elem.text:
                data.committer_ref = link_elem.text.strip()

    # proof (XdFileType, optional)
    proof = att.find(f"{{{SDC4_NS}}}proof")
    if proof is None:
        proof = att.find("proof")
    if proof is not None:
        data.has_proof = True

    # reason (XdStringType, optional)
    reason = att.find(f"{{{SDC4_NS}}}reason")
    if reason is None:
        reason = att.find("reason")
    if reason is not None:
        data.has_reason = True
        val_elem = reason.find(f"{{{SDC4_NS}}}xdstring-value")
        if val_elem is None:
            val_elem = reason.find("xdstring-value")
        if val_elem is not None and val_elem.text:
            data.reason_value = val_elem.text.strip()

    # committed (xs:dateTime, optional)
    committed = att.find(f"{{{SDC4_NS}}}committed")
    if committed is None:
        committed = att.find("committed")
    if committed is not None and committed.text:
        data.has_committed = True
        data.committed_timestamp = committed.text.strip()

    return data


def validate_attestation(
    data: AttestationData,
    requirements: AttestationRequirements | None = None,
) -> AttestationResult:
    """
    Validate attestation content against requirements.

    If no requirements are provided, uses defaults:
    - Attestation must be present
    - pending must be false (completed)
    - committer must be present

    Args:
        data: Extracted attestation content from the instance.
        requirements: What the model requires. If None, uses defaults.

    Returns:
        AttestationResult with validation status and errors.
    """
    if requirements is None:
        requirements = AttestationRequirements(
            require_completed=True,
            require_committer=True,
        )

    result = AttestationResult(data=data)

    if not data.present:
        result.valid = False
        result.errors.append("Attestation element missing from instance")
        return result

    # Check pending flag
    if requirements.require_completed:
        if data.pending is None:
            result.valid = False
            result.errors.append("Attestation pending flag is missing (required element)")
        elif data.pending is True:
            result.valid = False
            result.errors.append("Attestation is still pending (pending=true); must be completed (pending=false)")

    # Check committer
    if requirements.require_committer and not data.has_committer:
        result.valid = False
        result.errors.append("Attestation committer (authority) is missing")

    # Check proof
    if requirements.require_proof and not data.has_proof:
        result.valid = False
        result.errors.append("Attestation cryptographic proof is missing")

    # Check committed timestamp
    if requirements.require_committed and not data.has_committed:
        result.valid = False
        result.errors.append("Attestation committed timestamp is missing")

    # Check reason
    if requirements.require_reason and not data.has_reason:
        result.valid = False
        result.errors.append("Attestation reason is missing")

    return result
