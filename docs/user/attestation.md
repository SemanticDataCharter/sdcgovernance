# Attestation Validation

Validates `DM.attestation` (AttestationType) content in XML instances. Attestation is an identified entity (person or agent) asserting that the data instance is true or valid.

Attestation is **independent from workflow**. They compose optionally.

## AttestationType Elements

| Element | Type | Required | Description |
|---|---|---|---|
| `pending` | xs:boolean | **Yes** | True if outstanding, false if completed |
| `committer` | PartyType | No | Identity of person who committed the item (maps to W3C VC issuer) |
| `committed` | xs:dateTime | No | Timestamp of committal |
| `proof` | XdFileType | No | Cryptographic proof (e.g., GPG signature) |
| `reason` | XdStringType | No | Reason/type of attestation (ideally coded from standard vocabulary) |
| `view` | XdFileType | No | Visual representation of attested content |

## Extracting Attestation

```python
from sdcgovernance.attestation import extract_attestation

data = extract_attestation("instance.xml")

print(data.present)              # True if attestation element exists
print(data.pending)              # True/False/None
print(data.has_committer)        # True if committer present
print(data.committer_name)       # "Dr. Smith"
print(data.committer_ref)        # "https://identity.example.com/providers/dr-smith"
print(data.has_proof)            # True if proof present
print(data.has_reason)           # True if reason present
print(data.reason_value)         # "reviewed_and_approved"
print(data.has_committed)        # True if committed timestamp present
print(data.committed_timestamp)  # "2026-04-24T10:00:00Z"
```

## Validating Attestation

```python
from sdcgovernance.attestation import validate_attestation, AttestationRequirements

# Default requirements: completed + committer
result = validate_attestation(data)
print(result.valid)   # True/False
print(result.errors)  # [] or ["Attestation is still pending..."]

# Custom requirements
reqs = AttestationRequirements(
    require_completed=True,     # pending must be false
    require_committer=True,     # committer identity required
    require_proof=True,         # cryptographic proof required
    require_committed=True,     # timestamp required
    require_reason=True,        # reason required
)
result = validate_attestation(data, reqs)
```

## Validation Outcomes

| Scenario | Result |
|---|---|
| Complete attestation (pending=false, committer present) | PERMIT |
| Attestation pending (pending=true) | DENY: "Attestation is still pending" |
| Missing committer when required | DENY: "Attestation committer (authority) is missing" |
| Missing proof when required | DENY: "Attestation cryptographic proof is missing" |
| No attestation element in instance | DENY: "Attestation element missing from instance" |
| No requirements set (all False) | PERMIT (anything passes) |

## Independence from Workflow

Attestation can be validated without workflow, and vice versa:

```python
# Model has attestation but no workflow
model = inspect_model("dm-attestation-only.xsd")
assert model.attestation.present is True
assert model.workflow.present is False

# Attestation validation works independently
data = extract_attestation("instance.xml")
result = validate_attestation(data)
# No workflow involved
```
