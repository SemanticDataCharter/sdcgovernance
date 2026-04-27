# Receipt Chain Tests - XACML Decision Values + SDC Tamper Evidence

**Standard**: OASIS XACML (eXtensible Access Control Markup Language)
**Module**: `sdcgovernance/receipts.py`
**Tests**: 26

## XACML Decision Semantics

sdcgovernance uses OASIS XACML decision values directly:

| XACML Decision | sdcgovernance Usage |
|---|---|
| PERMIT | All governance checks pass - action is authorized |
| DENY | One or more governance checks fail - action is refused |
| INDETERMINATE | Governance checks partially pass or cannot be evaluated - requires review |

### Test: Decision enum values

```python
def test_permit():
    assert Decision.PERMIT.value == "PERMIT"

def test_deny():
    assert Decision.DENY.value == "DENY"

def test_indeterminate():
    assert Decision.INDETERMINATE.value == "INDETERMINATE"
```

**Result**: All three XACML decision values are represented exactly as specified.

## Receipt Data Structure

Every governance decision produces a tamper-evident receipt containing:

| Field | Type | Description |
|---|---|---|
| `decision` | Decision | XACML PERMIT/DENY/INDETERMINATE |
| `reasoning` | str | Why this decision was made |
| `instance_id` | str | DM.instance_id (CUID2) for lineage binding |
| `instance_version` | str | DM.instance_version for version tracking |
| `timestamp` | str | ISO 8601 UTC timestamp |
| `previous_hash` | str/None | SHA-256 hash of prior receipt (None for first) |
| `receipt_hash` | str | SHA-256 hash of this receipt's content |
| `dimensions_checked` | list[str] | Which governance dimensions were evaluated |
| `errors` | list[str] | Error details for DENY/INDETERMINATE |

### Test: Receipt has SHA-256 hash

```python
def test_receipt_has_hash():
    r = Receipt(decision=Decision.PERMIT)
    assert r.receipt_hash != ""
    assert len(r.receipt_hash) == 64  # SHA-256 hex
```

**Result**: Every receipt automatically computes a 64-character SHA-256 hex hash on creation.

### Test: Hash changes with decision

```python
def test_receipt_hash_changes_with_decision():
    r1 = Receipt(decision=Decision.PERMIT, timestamp="2026-04-24T12:00:00Z")
    r2 = Receipt(decision=Decision.DENY, timestamp="2026-04-24T12:00:00Z")
    assert r1.receipt_hash != r2.receipt_hash
```

**Result**: Different decisions produce different hashes. The hash covers all receipt content.

### Test: Tamper detection

```python
def test_receipt_verify_hash_detects_tampering():
    r = Receipt(decision=Decision.PERMIT, reasoning="all checks pass")
    r.reasoning = "tampered"
    assert r.verify_hash() is False
```

**Result**: Modifying any field after creation causes `verify_hash()` to return False.

## Hash Chain Integrity

Receipts are linked in an append-only chain. Each receipt's `previous_hash` points to the prior receipt's `receipt_hash`.

### Test: Chain linkage

```python
def test_append_chains_hashes():
    chain = ReceiptChain()
    r1 = chain.append(Decision.PERMIT, reasoning="first")
    r2 = chain.append(Decision.DENY, reasoning="second")
    assert r2.previous_hash == r1.receipt_hash
```

**Result**: Each receipt's `previous_hash` equals the prior receipt's `receipt_hash`.

### Test: First receipt has null previous hash

```python
def test_append_first_receipt():
    chain = ReceiptChain()
    r = chain.append(Decision.PERMIT, reasoning="initial")
    assert r.previous_hash is None
```

**Result**: The first receipt in a chain has `previous_hash = None`.

### Test: Three-receipt chain

```python
def test_three_receipt_chain():
    chain = ReceiptChain()
    r1 = chain.append(Decision.PERMIT)
    r2 = chain.append(Decision.DENY)
    r3 = chain.append(Decision.INDETERMINATE)
    assert r1.previous_hash is None
    assert r2.previous_hash == r1.receipt_hash
    assert r3.previous_hash == r2.receipt_hash
```

**Result**: Chain links are maintained across all three XACML decision types.

### Test: Chain integrity verification

```python
def test_verify_chain_intact():
    chain = ReceiptChain()
    chain.append(Decision.PERMIT, instance_id="test-1")
    chain.append(Decision.DENY, instance_id="test-1")
    chain.append(Decision.PERMIT, instance_id="test-1")
    assert chain.verify_chain() is True
```

**Result**: `verify_chain()` validates all hash links and receipt content integrity.

### Test: Tampered chain detected

```python
def test_verify_chain_detects_tampered_hash():
    chain = ReceiptChain()
    chain.append(Decision.PERMIT)
    chain.append(Decision.DENY)
    chain._receipts[0].reasoning = "tampered"
    assert chain.verify_chain() is False
```

**Result**: Tampering with any receipt in the chain causes `verify_chain()` to return False.

### Test: Broken chain link detected

```python
def test_verify_chain_detects_broken_link():
    chain = ReceiptChain()
    chain.append(Decision.PERMIT)
    chain.append(Decision.DENY)
    chain._receipts[1].previous_hash = "wrong_hash"
    assert chain.verify_chain() is False
```

**Result**: A broken `previous_hash` link is detected as chain corruption.

## Instance Identity Binding

Receipts bind to the data instance via `instance_id` and `instance_version`, ensuring the provenance trail belongs to the correct lineage.

### Test: Instance identity in receipt

```python
def test_receipt_instance_identity():
    r = Receipt(
        decision=Decision.PERMIT,
        instance_id="cuid2_test_123",
        instance_version="1",
    )
    assert r.instance_id == "cuid2_test_123"
    assert r.instance_version == "1"
```

**Result**: Instance identity fields are preserved in the receipt and included in the hash computation.

## GovernanceResult

The top-level result object returned by `validate_governance()`:

### Test: PERMIT with no governance

```python
def test_permit_no_governance():
    result = GovernanceResult(decision=Decision.PERMIT, has_governance=False)
    assert result.decision == Decision.PERMIT
    assert result.has_governance is False
    assert result.errors == []
```

### Test: DENY with errors

```python
def test_deny_with_errors():
    result = GovernanceResult(
        decision=Decision.DENY,
        errors=["attestation missing", "invalid role"],
    )
    assert result.decision == Decision.DENY
    assert len(result.errors) == 2
```

**Result**: GovernanceResult carries XACML decisions with error details and optional receipt attachment.
