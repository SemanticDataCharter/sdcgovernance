# Model Inspector Tests

**Module**: `sdcgovernance/model_inspector.py`
**Tests**: 27

## Purpose

The model inspector reads DMType root slots at known positions to detect governance dimensions. No arbitrary search - governance is at fixed positions in the XSD.

## Test Results Summary

### No Governance Model (dm-no-governance.xsd)

| Assertion | Result |
|---|---|
| `has_governance` | False |
| `workflow.present` | False |
| `audit.present` | False |
| `attestation.present` | False |
| `party_role.subject_defined` | False |
| `party_role.provider_defined` | False |
| `party_role.participation_defined` | False |
| `model_id` contains "dm-test-no-governance" | True |
| `model_label` | "Test No Governance" |
| `instance_id_required` | True |

### All Governance Model (dm-all-governance.xsd)

| Assertion | Result |
|---|---|
| `has_governance` | True |
| `workflow.present` | True |
| `workflow.current_state_defined` | True |
| `audit.present` | True |
| `audit.max_occurs` | "unbounded" |
| `attestation.present` | True |
| `party_role.subject_defined` | True |
| `party_role.provider_defined` | True |
| `party_role.participation_defined` | True |
| `protocol_defined` | True |
| `acs_defined` | True |
| `xdlink_defined` | True |

### Selective Governance

| Model | Active Dimensions | Inactive Dimensions |
|---|---|---|
| dm-workflow-only.xsd | workflow, current-state | audit, attestation, party_role |
| dm-audit-only.xsd | audit | workflow, attestation, party_role |
| dm-attestation-only.xsd | attestation | workflow, audit, party_role |

### Real CordovaOS Model (dm-ftluo2nybgxmn7mawttoos20.xsd)

```python
def test_real_model_inspects(healthcare_model):
    result = inspect_model(healthcare_model)
    assert result.model_label == "Healthcare Record"
    assert result.workflow.present is True
    assert result.audit.present is True
    assert result.attestation.present is True
    assert result.party_role.subject_defined is True
    assert result.party_role.provider_defined is True
    assert result.instance_id_required is True
```

**Result**: Real-world CordovaOS Healthcare Record model correctly detected with all governance slots.
