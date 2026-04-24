# Party/Role Tests

**Module**: `sdcgovernance/party_role.py`
**Tests**: 25

## Test Fixture (instance-party-role.xml)

```
DM.subject: John Doe (ref: .../patients/john-doe)
DM.provider[0]: Dr. Smith (ref: .../providers/dr-smith)
DM.provider[1]: Lab System A (ref: .../devices/lab-system-a)
DM.Participation[0]: Dr. Jones, function="approver", mode="present", start/end
DM.Participation[1]: Nurse Williams, function="viewer"
```

## Extraction Results

| Assertion | Result |
|---|---|
| `subject.name` | "John Doe" |
| `subject.ref_link` | contains "john-doe" |
| `len(providers)` | 2 |
| `providers[0].name` | "Dr. Smith" |
| `len(participations)` | 2 |
| `participations_with_function("approver")` | 1 match (Dr. Jones) |
| `participations_with_function("viewer")` | 1 match (Nurse Williams) |
| approver mode | "present" |
| approver start | "2026-04-24T09:00:00Z" |

## Validation Results

| Requirement | Input | Decision | Error |
|---|---|---|---|
| require_subject=True | subject present | PERMIT | - |
| require_subject=True | subject absent | DENY | "DM.subject is required but missing" |
| require_provider=True | providers present | PERMIT | - |
| require_provider=True | providers absent | DENY | "DM.provider is required but missing" |
| required_functions=["approver"] | approver present | PERMIT | - |
| required_functions=["admin"] | admin absent | DENY | "Required participation function 'admin' not found. Available functions: ['approver', 'viewer']" |
| required_functions=["approver", "viewer"] | both present | PERMIT | - |
| required_functions=["approver", "supervisor"] | supervisor absent | DENY | lists available functions |

## Actor Role Checking

| Actor | Required Function | Decision | Error |
|---|---|---|---|
| "Dr. Jones" (by name) | "approver" | PERMIT | - |
| "Nurse Williams" (by name) | "approver" | DENY | "has function(s) ['viewer'], but 'approver' is required" |
| "Unknown Person" | "approver" | DENY | "Actor not found in any participation" |
| ".../providers/dr-jones" (by ref) | "approver" | PERMIT | - |
| ".../providers/dr-jones" (by ref) | "viewer" | DENY | has 'approver', needs 'viewer' |
