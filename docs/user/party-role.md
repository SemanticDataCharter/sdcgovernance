# Party/Role Validation

Validates party identity and role constraints from three DM root slots:

- `DM.subject` (PartyType, 0..1) - human subject identity (patient, customer)
- `DM.provider[]` (PartyType, 0..*) - information source identity
- `DM.Participation[]` (ParticipationType, 0..*) - role-constrained participations

## ParticipationType Elements

| Element | Type | Description |
|---|---|---|
| `performer` | PartyType | Identity of the participant |
| `function` | XdStringType | Role/function (the role check target) |
| `mode` | XdStringType | How participation happened (present, telephone, email) |
| `start` | xs:dateTime | When participation began |
| `end` | xs:dateTime | When participation ended |

## PartyType Elements

| Element | Type | Description |
|---|---|---|
| `party-name` | xs:string | Human-readable name |
| `party-ref` | XdLinkType | Link to external identity system |
| `party-details` | ClusterType | Structured party information |

## Extracting Party/Role

```python
from sdcgovernance.party_role import extract_party_role

data = extract_party_role("instance.xml")

# Subject
print(data.has_subject)         # True
print(data.subject.name)        # "John Doe"
print(data.subject.ref_link)    # "https://identity.example.com/patients/john-doe"

# Providers
print(data.has_providers)       # True
print(len(data.providers))      # 2
print(data.providers[0].name)   # "Dr. Smith"

# Participations
print(data.has_participations)  # True
approvers = data.participations_with_function("approver")
print(len(approvers))           # 1
print(approvers[0].performer.name)  # "Dr. Jones"
print(approvers[0].mode)       # "present"
```

## Validating Party/Role

```python
from sdcgovernance.party_role import validate_party_role, PartyRoleRequirements

# Require subject + approver role
reqs = PartyRoleRequirements(
    require_subject=True,
    require_provider=True,
    required_functions=["approver"],
)
result = validate_party_role(data, reqs)
print(result.valid)   # True/False
print(result.errors)  # [] or ["Required participation function 'approver' not found..."]
```

## Checking a Specific Actor's Role

```python
from sdcgovernance.party_role import check_actor_role

# By name
result = check_actor_role(data, actor="Dr. Jones", required_function="approver")
print(result.valid)  # True

# By party-ref link
result = check_actor_role(
    data,
    actor="https://identity.example.com/providers/dr-jones",
    required_function="approver",
)
print(result.valid)  # True

# Wrong role
result = check_actor_role(data, actor="Nurse Williams", required_function="approver")
print(result.valid)   # False
print(result.errors)  # ["Actor 'Nurse Williams' has function(s) ['viewer'], but 'approver' is required"]
```

## Validation Outcomes

| Scenario | Result |
|---|---|
| Required function present | PERMIT |
| Required function missing | DENY with available functions listed |
| Actor not found in any participation | DENY: "Actor not found" |
| Actor found but wrong role | DENY with actual vs required role |
| Subject required but missing | DENY: "DM.subject is required but missing" |
| No requirements set | PERMIT (anything passes) |
