# Attestation Tests - W3C Verifiable Credentials Data Model 2.0

**Standard**: W3C VC Data Model 2.0 (https://www.w3.org/TR/vc-data-model-2.0/)
**Module**: `sdcgovernance/attestation.py`
**Tests**: 13

## VC Mapping

| AttestationType Element | VC Data Model Concept |
|---|---|
| `committer` (PartyType) | Issuer - who makes the assertion |
| `pending` (xs:boolean) | Credential status (outstanding vs completed) |
| `proof` (XdFileType) | Proof mechanism (e.g., GPG signature) |
| `reason` (XdStringType) | Credential type / claim |
| `committed` (xs:dateTime) | Issuance date |

## Test Results Summary

| Test | Input | Decision | Errors |
|---|---|---|---|
| Complete attestation | pending=false, committer, proof, reason, committed | PERMIT | [] |
| Pending attestation | pending=true | DENY | "Attestation is still pending" |
| Missing committer | pending=false, no committer | DENY | "Attestation committer (authority) is missing" |
| Missing proof (when required) | pending=false, no proof | DENY | "Attestation cryptographic proof is missing" |
| Missing attestation element | no attestation in instance | DENY | "Attestation element missing from instance" |
| No requirements set | pending=true (all reqs False) | PERMIT | [] |
| Multiple failures | pending=true, no committer, no proof | DENY | 3+ errors |

## Independence from Workflow

```python
def test_attestation_without_workflow():
    data = extract_attestation("instance-attestation-complete.xml")
    result = validate_attestation(data)
    assert result.valid is True
```

**Standards mapping**: Attestation is an independent governance dimension. A model can define attestation without workflow, and vice versa. This follows the VC model where credentials exist independently of business processes.
