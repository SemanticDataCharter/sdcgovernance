"""
MTCP (Multi-Turn Constraint Persistence) integration helpers.

MTCP is a model-evaluation framework developed by A. Abby (mtcp.live)
that produces an Evidence Pack (24-field JSON) per evaluated model.
sdcgovernance consumes Evidence Packs as extra_context to evaluate_decision
and emits XACML decisions with hash-chained Receipts.

This module provides the integrity verifier for Evidence Packs. The
canonicalization is RFC 8785 (see ``sdcgovernance.jcs``) and matches the
canonicalization used by Receipt._compute_hash, so the two hashes are
produced under the same convention.

★ The Evidence Pack hash is deliberately NOT RFC 8785, and must not be
"fixed" without coordinating with the MTCP side first.

MTCP is an external wire format. Its hashes are produced by A. Abby's
evaluation pipeline and verified here, so both sides must canonicalize
identically or verification fails for reasons that look like tampering.
The published worked example (MTCP_SDC_Schema_Mapping V2, GPT-4o) contains
integral floats such as ``ve_cont: 1.0``, and its expected hash matches
Python's ``json.dumps`` rendering of ``1.0``, not RFC 8785's required ``1``.
The MTCP convention is therefore the legacy one, and unilaterally moving
this module to RFC 8785 would invalidate every Evidence Pack MTCP issues.

Receipts, which are ours, DO use RFC 8785 (``sdcgovernance.receipts``).
Migrating MTCP requires a coordinated version bump on both sides; until
then this is a known, documented, deliberate divergence rather than an
oversight.

Reference: MTCP_SDC_Schema_Mapping V2 (A. Abby, 2026-05-09).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sdcgovernance.jcs import canonicalize_bytes


EVIDENCE_PACK_HASH_FIELD = "evidence_pack_hash"


def canonical_json(data: dict[str, Any]) -> str:
    """
    Canonical JSON encoding per the MTCP hash convention.

    Keys sorted by code point, no whitespace, comma-colon separators, UTF-8
    with no ASCII escaping. This is Python's ``json.dumps`` rendering and is
    **not** RFC 8785: notably it emits ``1.0`` where RFC 8785 requires ``1``.

    That is intentional. See the module docstring: this convention is fixed
    by the MTCP side, and changing it here alone would break verification of
    every Evidence Pack MTCP produces. Use ``sdcgovernance.jcs.canonicalize``
    for anything we own.
    """
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def compute_evidence_pack_hash(evidence_pack: dict[str, Any]) -> str:
    """
    Compute the SHA-256 hash of an Evidence Pack over its non-hash fields.

    The evidence_pack_hash field is excluded from the hash input, matching
    the MTCP spec: hash = SHA-256(canonical_json(EP minus its own hash)).
    """
    content = {k: v for k, v in evidence_pack.items() if k != EVIDENCE_PACK_HASH_FIELD}
    return hashlib.sha256(canonical_json(content).encode("utf-8")).hexdigest()


def compute_evidence_pack_hash_rfc8785(evidence_pack: dict[str, Any]) -> str:
    """
    Compute an Evidence Pack hash using conformant RFC 8785 canonicalization.

    Provided ahead of MTCP's own move to conformance (A. Abby, 2026-08-30) so
    both conventions can be verified without a flag day. Once MTCP emits only
    conformant hashes, this becomes the primary and ``canonical_json`` above
    can retire.
    """
    content = {k: v for k, v in evidence_pack.items() if k != EVIDENCE_PACK_HASH_FIELD}
    return hashlib.sha256(canonicalize_bytes(content)).hexdigest()


def verify_evidence_pack(evidence_pack: dict[str, Any]) -> dict[str, Any]:
    """
    Verify the integrity of an MTCP Evidence Pack.

    Recomputes evidence_pack_hash over the 23 non-hash fields and compares to
    the value carried in the Evidence Pack itself.

    **Accepts either canonicalization.** MTCP is migrating from the legacy
    convention to conformant RFC 8785, and the two produce different hashes
    for the same Evidence Pack whenever it contains an integral float. Trying
    both means an Evidence Pack verifies whichever side has migrated, so
    neither implementation needs a flag day. Which one matched is reported
    rather than hidden, because "it verified" and "it verified under the
    scheme we expected" are different facts.

    Returns a dict with:
      - valid: bool
      - computed_hash: str (the hash under ``canonicalization``)
      - expected_hash: str (the hash carried in the Evidence Pack, or empty
        string if the field is missing)
      - canonicalization: str ("rfc8785", "mtcp-legacy", or "" when the pack
        did not verify under either)
    """
    expected = evidence_pack.get(EVIDENCE_PACK_HASH_FIELD, "")

    conformant = compute_evidence_pack_hash_rfc8785(evidence_pack)
    legacy = compute_evidence_pack_hash(evidence_pack)

    if expected and expected == conformant:
        return {
            "valid": True,
            "computed_hash": conformant,
            "expected_hash": expected,
            "canonicalization": "rfc8785",
        }
    if expected and expected == legacy:
        return {
            "valid": True,
            "computed_hash": legacy,
            "expected_hash": expected,
            "canonicalization": "mtcp-legacy",
        }

    # Report the legacy hash on failure: it is still what MTCP publishes, so
    # it is the more useful value to show when diagnosing a mismatch.
    return {
        "valid": False,
        "computed_hash": legacy,
        "expected_hash": expected,
        "canonicalization": "",
    }
