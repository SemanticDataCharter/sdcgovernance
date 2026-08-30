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


def verify_evidence_pack(evidence_pack: dict[str, Any]) -> dict[str, Any]:
    """
    Verify the integrity of an MTCP Evidence Pack.

    Recomputes evidence_pack_hash over the 23 non-hash fields and compares
    to the value carried in the Evidence Pack itself.

    Returns a dict with:
      - valid: bool
      - computed_hash: str (the recomputed hash)
      - expected_hash: str (the hash carried in the Evidence Pack, or
        empty string if the field is missing)
    """
    expected = evidence_pack.get(EVIDENCE_PACK_HASH_FIELD, "")
    computed = compute_evidence_pack_hash(evidence_pack)
    return {
        "valid": expected != "" and computed == expected,
        "computed_hash": computed,
        "expected_hash": expected,
    }
