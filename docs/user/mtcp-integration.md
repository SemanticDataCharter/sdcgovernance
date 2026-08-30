# MTCP Integration

sdcgovernance integrates with the Multi-Turn Constraint Persistence (MTCP) evaluation framework developed by A. Abby (mtcp.live). MTCP produces an Evidence Pack (24-field JSON) per evaluated model. sdcgovernance consumes Evidence Packs as `extra_context` to `evaluate_decision` and emits XACML decisions with hash-chained Receipts.

This document describes the integration pattern, the canonicalization spec, and the integrity verifier.

## Integration pattern

```
MTCP MCP server                sdcgovernance evaluate_decision
(mtcp-mcp-server.fly.dev)      MCP tool

    get_evidence_pack(model_id) ──┐
                                  │
    {evidence_pack:               │
       24 fields including        │
       evidence_pack_hash}        ▼
                            evaluate_decision(
                              table_json,
                              extra_context = EP + deployment fields,
                              instance_id = model_id,
                              context_hash = evidence_pack_hash,
                              previous_hash = prior receipt hash
                            )
                                  │
                                  ▼
                            Receipt (PERMIT / DENY / INDETERMINATE)
                            with receipt_hash binding:
                              decision, reasoning, status_code,
                              instance_id, instance_version, timestamp,
                              previous_hash, dimensions_checked,
                              errors, context_hash
```

The caller orchestrates between the two MCP servers. sdcgovernance does not call MTCP and MTCP does not call sdcgovernance. The integration is via shared canonicalization conventions and the `context_hash` field on the Receipt.

## Cross-chain binding

MTCP maintains an evaluation chain via `constraint_state_hash` on each Evidence Pack. sdcgovernance maintains a Receipt chain via `previous_hash` on each Receipt. The two chains are linked at the boundary by:

1. **`instance_id`** in the Receipt is set to the MTCP `model_id` from the Evidence Pack. Records which model the decision was about.
2. **`context_hash`** in the Receipt is set to the Evidence Pack's `evidence_pack_hash`. Records which exact Evidence Pack the decision evaluated. Recomputing this hash from the EP and comparing to the Receipt's `context_hash` proves which EP produced which Receipt.

Without `context_hash`, a different Evidence Pack with the same field names matching the same DMN rules would produce identical Receipt content (modulo timestamp). With `context_hash` bound into the Receipt's hashed content, the cryptographic link is direct.

## Canonicalization spec

★ **As of 4.2.0 these are two different canonicalizations. This is deliberate,
and mixing them up will produce hashes that fail to verify.**

| Hash | Canonicalization |
|---|---|
| `receipt_hash` (`sdcgovernance.receipts`) | **RFC 8785**, conformant |
| `AuditRecord.compute_hash` (`sdcgovernance.provenance`) | **RFC 8785**, conformant |
| `evidence_pack_hash` (`sdcgovernance.mtcp`) | **MTCP legacy convention** |

### Receipts and audit records: RFC 8785

Use `sdcgovernance.jcs.canonicalize`. Published vectors are in
`test-vectors/rfc8785-canonicalization.json`. Receipts carry a
`canonicalization` field (`"rfc8785"`) inside the hashed content, so the
scheme is committed to and cannot be reinterpreted. Receipts issued before
4.2.0 verify by constructing them with
`canonicalization=LEGACY_CANONICALIZATION`.

### Evidence Packs: the MTCP convention

```python
json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```

Keys sorted by code point, no whitespace, comma-colon separators, UTF-8 with
no ASCII escaping.

**Why this is not RFC 8785, and why it stays that way for now.** MTCP is an
external wire format: Evidence Pack hashes are produced by the MTCP
evaluation pipeline and merely verified here, so both sides must
canonicalize identically or verification fails in a way that looks like
tampering. The published worked example (MTCP_SDC_Schema_Mapping V2, GPT-4o)
contains integral floats such as `ve_cont: 1.0`, and its expected hash
matches Python's `1.0` rendering rather than RFC 8785's required `1`. The
MTCP convention is therefore the legacy one, and changing this side alone
would invalidate every Evidence Pack MTCP issues.

Migrating MTCP to RFC 8785 requires a coordinated version bump on both
sides. Until then this is a documented, deliberate divergence.

## Verifying Evidence Pack integrity

`sdcgovernance.mtcp` exposes `verify_evidence_pack(ep: dict)` which recomputes the hash over the 23 non-hash fields and compares to the EP's stated `evidence_pack_hash`. Returns:

```python
{
    "valid": bool,             # True if computed == expected and expected is non-empty
    "computed_hash": str,      # SHA-256 hex
    "expected_hash": str,      # the EP's evidence_pack_hash field, or "" if missing
}
```

Also exposed as the MCP tool `verify_evidence_pack` taking a JSON string of the Evidence Pack.

## Decision table: mtcp_deployment_governance

The reference DMN decision table for MTCP deployment governance is published in MTCP_SDC_Schema_Mapping V2 (A. Abby, 2026). Hit policy FIRST, six rules plus a default:

| Rule | Conditions | Outcome |
|---|---|---|
| MTCP-R1 | regime_classification == "R3" AND data_classification >= "Restricted" | DENY |
| MTCP-R2 | ve_lang < 0.7 AND jurisdiction == "multilingual" | DENY |
| MTCP-R3 | overall_grade == "F" | DENY |
| MTCP-R4 | cpd_score > 15 | DENY |
| MTCP-R5 | regime_classification == "R1" AND overall_grade in ["A", "B"] | PERMIT |
| MTCP-R6 | regime_classification == "R2" AND overall_grade == "B" | PERMIT |
| MTCP-DEFAULT | (no conditions) | INDETERMINATE |

### Behavior note: Regime 2 + Grade A

Under hit policy FIRST, R5 admits only Regime 1 with grade A or B. R6 admits only Regime 2 with grade B. A model classified Regime 2 with grade A matches neither and falls through to MTCP-DEFAULT (INDETERMINATE / escalate for human review).

This is intentional, confirmed by A. Abby in V3 of the MTCP-SDC Schema Mapping (2026-05-10). R2 is the Stochastic Variability regime where constraint performance is temperature-sensitive and inconsistent across runs. A grade-A score under R2 is rare and warrants human review rather than automated PERMIT, because the stochastic failure pattern makes the high score less reliable as a deployment signal than the same grade under R1. Do not broaden R6 to `overall_grade in ["A", "B"]` without consulting MTCP authors.

## Reference

- MTCP MCP server: `mtcp-mcp-server.fly.dev` (HTTP POST JSON-RPC 2.0)
- MTCP_SDC_Schema_Mapping V3 (A. Abby, 2026-05-10): Evidence Pack to Receipt schema mapping, DMN table, GPT-4o worked example, context_hash binding, RFC 8785 canonicalization spec.
- Reference test: `tests/test_mtcp.py::TestVerifyEvidencePack::test_v2_worked_example_gpt4o` reproduces Ahmad's GPT-4o EP hash bit-for-bit, confirming canonicalization parity across implementations.
