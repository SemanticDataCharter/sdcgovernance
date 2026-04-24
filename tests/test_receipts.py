"""
Tests for decision receipt chain - Phase 1.

Tests the tamper-evident, append-only, hash-chained receipt system.
"""

import pytest
from sdcgovernance.receipts import Decision, Receipt, ReceiptChain, GovernanceResult


class TestDecisionEnum:
    """OASIS XACML decision values."""

    def test_permit(self):
        assert Decision.PERMIT.value == "PERMIT"

    def test_deny(self):
        assert Decision.DENY.value == "DENY"

    def test_indeterminate(self):
        assert Decision.INDETERMINATE.value == "INDETERMINATE"


class TestReceipt:
    """Individual receipt creation and hashing."""

    def test_receipt_has_hash(self):
        r = Receipt(decision=Decision.PERMIT)
        assert r.receipt_hash != ""
        assert len(r.receipt_hash) == 64  # SHA-256 hex

    def test_receipt_has_timestamp(self):
        r = Receipt(decision=Decision.PERMIT)
        assert r.timestamp != ""

    def test_receipt_hash_changes_with_decision(self):
        r1 = Receipt(decision=Decision.PERMIT, timestamp="2026-04-24T12:00:00Z")
        r2 = Receipt(decision=Decision.DENY, timestamp="2026-04-24T12:00:00Z")
        assert r1.receipt_hash != r2.receipt_hash

    def test_receipt_hash_changes_with_reasoning(self):
        r1 = Receipt(decision=Decision.DENY, reasoning="missing attestation", timestamp="2026-04-24T12:00:00Z")
        r2 = Receipt(decision=Decision.DENY, reasoning="invalid role", timestamp="2026-04-24T12:00:00Z")
        assert r1.receipt_hash != r2.receipt_hash

    def test_receipt_verify_hash_passes(self):
        r = Receipt(decision=Decision.PERMIT, reasoning="all checks pass")
        assert r.verify_hash() is True

    def test_receipt_verify_hash_detects_tampering(self):
        r = Receipt(decision=Decision.PERMIT, reasoning="all checks pass")
        r.reasoning = "tampered"
        assert r.verify_hash() is False

    def test_receipt_instance_identity(self):
        r = Receipt(
            decision=Decision.PERMIT,
            instance_id="cuid2_test_123",
            instance_version="1",
        )
        assert r.instance_id == "cuid2_test_123"
        assert r.instance_version == "1"

    def test_receipt_to_dict(self):
        r = Receipt(decision=Decision.DENY, errors=["missing attestation"])
        d = r.to_dict()
        assert d["decision"] == "DENY"
        assert d["errors"] == ["missing attestation"]
        assert "receipt_hash" in d

    def test_receipt_dimensions_checked(self):
        r = Receipt(
            decision=Decision.PERMIT,
            dimensions_checked=["workflow", "attestation"],
        )
        assert r.dimensions_checked == ["workflow", "attestation"]


class TestReceiptChain:
    """Append-only, hash-chained receipt sequence."""

    def test_empty_chain(self):
        chain = ReceiptChain()
        assert chain.length == 0
        assert chain.last_hash is None

    def test_append_first_receipt(self):
        chain = ReceiptChain()
        r = chain.append(Decision.PERMIT, reasoning="initial")
        assert chain.length == 1
        assert r.previous_hash is None
        assert r.receipt_hash != ""

    def test_append_chains_hashes(self):
        chain = ReceiptChain()
        r1 = chain.append(Decision.PERMIT, reasoning="first")
        r2 = chain.append(Decision.DENY, reasoning="second")
        assert r2.previous_hash == r1.receipt_hash

    def test_three_receipt_chain(self):
        chain = ReceiptChain()
        r1 = chain.append(Decision.PERMIT)
        r2 = chain.append(Decision.DENY)
        r3 = chain.append(Decision.INDETERMINATE)
        assert r1.previous_hash is None
        assert r2.previous_hash == r1.receipt_hash
        assert r3.previous_hash == r2.receipt_hash

    def test_verify_chain_intact(self):
        chain = ReceiptChain()
        chain.append(Decision.PERMIT, instance_id="test-1")
        chain.append(Decision.DENY, instance_id="test-1")
        chain.append(Decision.PERMIT, instance_id="test-1")
        assert chain.verify_chain() is True

    def test_verify_chain_detects_tampered_hash(self):
        chain = ReceiptChain()
        chain.append(Decision.PERMIT)
        chain.append(Decision.DENY)
        # Tamper with first receipt's reasoning
        chain._receipts[0].reasoning = "tampered"
        assert chain.verify_chain() is False

    def test_verify_chain_detects_broken_link(self):
        chain = ReceiptChain()
        chain.append(Decision.PERMIT)
        chain.append(Decision.DENY)
        # Break the chain link
        chain._receipts[1].previous_hash = "wrong_hash"
        assert chain.verify_chain() is False

    def test_verify_empty_chain(self):
        chain = ReceiptChain()
        assert chain.verify_chain() is True

    def test_receipts_are_read_only_copy(self):
        chain = ReceiptChain()
        chain.append(Decision.PERMIT)
        receipts = chain.receipts
        assert len(receipts) == 1
        # Modifying the returned list doesn't affect the chain
        receipts.append(Receipt(decision=Decision.DENY))
        assert chain.length == 1

    def test_chain_to_list(self):
        chain = ReceiptChain()
        chain.append(Decision.PERMIT, instance_id="test-1")
        chain.append(Decision.DENY, errors=["missing attestation"])
        result = chain.to_list()
        assert len(result) == 2
        assert result[0]["decision"] == "PERMIT"
        assert result[1]["decision"] == "DENY"
        assert result[1]["errors"] == ["missing attestation"]

    def test_append_with_dimensions(self):
        chain = ReceiptChain()
        r = chain.append(
            Decision.PERMIT,
            instance_id="test-1",
            instance_version="v2",
            dimensions_checked=["workflow", "audit", "attestation"],
        )
        assert r.instance_id == "test-1"
        assert r.instance_version == "v2"
        assert r.dimensions_checked == ["workflow", "audit", "attestation"]


class TestGovernanceResult:
    """GovernanceResult data structure."""

    def test_permit_no_governance(self):
        result = GovernanceResult(
            decision=Decision.PERMIT,
            has_governance=False,
        )
        assert result.decision == Decision.PERMIT
        assert result.has_governance is False
        assert result.errors == []

    def test_deny_with_errors(self):
        result = GovernanceResult(
            decision=Decision.DENY,
            errors=["attestation missing", "invalid role"],
        )
        assert result.decision == Decision.DENY
        assert len(result.errors) == 2

    def test_with_receipt(self):
        receipt = Receipt(decision=Decision.PERMIT)
        result = GovernanceResult(
            decision=Decision.PERMIT,
            receipt=receipt,
        )
        assert result.receipt is not None
        assert result.receipt.decision == Decision.PERMIT
