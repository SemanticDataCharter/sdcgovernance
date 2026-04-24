# Model Inspector

The model inspector reads an SDC data model XSD and detects which governance dimensions are active by checking known positions in the DMType root.

## Governance Slots in DMType

Governance components are at fixed positions in the DM root - no arbitrary search:

| DM Slot | Type | Cardinality | Governance Dimension |
|---|---|---|---|
| `workflow` | ClusterType | 0..1 | Workflow (state transitions) |
| `current-state` | xs:string | 0..1 | Workflow state tracking |
| `Audit[]` | AuditType | 0..* | Provenance/Audit |
| `attestation` | AttestationType | 0..1 | Attestation (authority) |
| `subject` | PartyType | 0..1 | Party (human subject) |
| `provider[]` | PartyType | 0..* | Party (information source) |
| `Participation[]` | ParticipationType | 0..* | Party/Role (function constraints) |
| `protocol` | XdStringType | 0..1 | DMN decision table input |
| `acs` | XdLinkType | 0..1 | Access control / retention policy |
| `XdLink[]` | XdLinkType | 0..* | Governed relationships |

## Usage

```python
from sdcgovernance import inspect_model

model = inspect_model("path/to/model.xsd")
```

## GovernanceModel Fields

```python
model.model_id              # CUID2 identifier from schema annotation
model.model_label           # Human-readable label (e.g., "Healthcare Record")
model.has_governance         # True if any governance dimension is active
model.instance_id_required   # True if instance_id is mandatory (minOccurs=1)

# Governance dimensions
model.workflow.present              # DM.workflow slot populated
model.workflow.current_state_defined # DM.current-state slot populated
model.audit.present                 # DM.Audit[] slot populated
model.audit.max_occurs              # "unbounded" or a number
model.attestation.present           # DM.attestation slot populated
model.party_role.subject_defined    # DM.subject slot populated
model.party_role.provider_defined   # DM.provider[] slot populated
model.party_role.participation_defined # DM.Participation[] slot populated

# Additional governance-relevant elements
model.protocol_defined      # DM.protocol slot populated
model.acs_defined            # DM.acs slot populated
model.xdlink_defined         # DM.XdLink[] slot populated

# Convenience
model.active_dimensions      # Dict mapping dimension names to active status
```

## Example: No Governance

A model with only data content and no governance slots:

```python
model = inspect_model("dm-no-governance.xsd")
assert model.has_governance is False
assert model.workflow.present is False
assert model.audit.present is False
assert model.attestation.present is False
```

## Example: All Governance

A model with all governance slots populated:

```python
model = inspect_model("dm-all-governance.xsd")
assert model.has_governance is True
assert model.active_dimensions == {
    "workflow": True,
    "audit": True,
    "attestation": True,
    "party_role": True,
    "protocol": True,
    "acs": True,
    "xdlink": True,
}
```

## Example: Selective Governance

Models can include any combination of governance dimensions:

```python
# Workflow only
model = inspect_model("dm-workflow-only.xsd")
assert model.workflow.present is True
assert model.attestation.present is False  # independent

# Attestation only
model = inspect_model("dm-attestation-only.xsd")
assert model.attestation.present is True
assert model.workflow.present is False  # independent
```
