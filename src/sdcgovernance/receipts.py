"""
Tamper-evident decision receipt chain for SDC governance.

Every enforcement decision (EXECUTE, REFUSE, ESCALATE) produces a
receipt containing the decision, reasoning, PROV record, attestation
state, workflow state, and a SHA-256 hash linking to the previous
receipt. The chain is deterministic: same input replays to the same
decision.
"""

# TODO: Phase 1 implementation (foundation with provenance)
# - Receipt data structure (decision, reasoning, PROV ref, hashes)
# - SHA-256 hash chain linking receipts
# - Append-only storage interface
# - Deterministic replay verification
# - PROV-formatted receipt records
# - Export as RDF/Turtle
