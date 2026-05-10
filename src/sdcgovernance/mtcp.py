"""
MTCP (Multi-Turn Constraint Persistence) integration helpers.

MTCP is a model-evaluation framework developed by A. Abby (mtcp.live)
that produces an Evidence Pack (24-field JSON) per evaluated model.
sdcgovernance consumes Evidence Packs as extra_context to evaluate_decision
and emits XACML decisions with hash-chained Receipts.

This module provides the integrity verifier for Evidence Packs. The
canonicalization spec is RFC 8785-aligned (keys sorted, no whitespace,
comma-colon separators, UTF-8) and matches the canonicalization used
by Receipt._compute_hash, so the two hashes are produced under the
same convention.

Reference: MTCP_SDC_Schema_Mapping V2 (A. Abby, 2026-05-09).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


EVIDENCE_PACK_HASH_FIELD = "evidence_pack_hash"


def canonical_json(data: dict[str, Any]) -> str:
    """
    Canonical JSON encoding per the MTCP / sdcgovernance hash convention.

    Keys sorted alphabetically, no whitespace, comma-colon separators,
    UTF-8 (no ASCII escaping). RFC 8785-aligned.
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
