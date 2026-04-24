# Provenance/Audit Validation

Audit and Provenance are the same governance dimension in SDC. Both answer: what happened, who did it, when, to what entity.

The SDC RM component is `sdc4:AuditType`. External documentation uses "Provenance" (W3C PROV-O vocabulary).

## AuditType Elements (PROV-O Mapping)

| Element | Type | Required | PROV-O Mapping |
|---|---|---|---|
| `system-id` | XdStringType | **Yes** | prov:Entity context |
| `timestamp` | xs:dateTime | **Yes** | prov:Activity temporal bounds |
| `system-user` | PartyType | No | prov:Agent |
| `location` | ClusterType | No | Provenance metadata |

## Extracting Provenance

```python
from sdcgovernance.provenance import extract_provenance

data = extract_provenance("instance.xml")

print(data.has_records)     # True
print(data.count)           # 2
print(data.most_recent)     # Last AuditRecord

r = data.records[0]
print(r.system_id)          # "epic-ehr-prod-01"
print(r.system_user_name)   # "Dr. Smith"
print(r.system_user_ref)    # "https://identity.example.com/providers/dr-smith"
print(r.location_label)     # "Porto Sereno General Hospital"
print(r.timestamp)          # "2026-04-24T08:00:00Z"
print(r.record_hash)        # SHA-256 hash of this record
```

## Validating Provenance

```python
from sdcgovernance.provenance import validate_provenance, ProvenanceRequirements, RetentionLevel

# Default: require audit, most recent retention
result = validate_provenance(data)
print(result.valid)   # True/False
print(result.errors)  # []

# Custom requirements
reqs = ProvenanceRequirements(
    require_audit=True,
    require_system_user=True,            # prov:Agent required
    retention_level=RetentionLevel.LAST_N,
    retention_n=3,                        # at least 3 records
    allowed_activity_types={"Create", "Update", "Accept"},  # AS2 filter
)
result = validate_provenance(data, reqs)
```

## Retention Policies (DPV-aligned)

| Policy | Description | Use Case |
|---|---|---|
| `MOST_RECENT` | Instance carries 1 record + hash | Long-lived records (patient records) |
| `LAST_N` | Instance carries N records + hash | Configurable per model |
| `FULL_CHAIN` | Instance carries complete history | Short-lived records (financial transactions) |

```python
# Most recent only
reqs = ProvenanceRequirements(retention_level=RetentionLevel.MOST_RECENT)

# Last 3 records
reqs = ProvenanceRequirements(retention_level=RetentionLevel.LAST_N, retention_n=3)

# Full chain
reqs = ProvenanceRequirements(retention_level=RetentionLevel.FULL_CHAIN, min_records=5)
```

## Activity Type Filtering (W3C Activity Streams 2.0)

```python
reqs = ProvenanceRequirements(
    allowed_activity_types={"Create", "Update", "Accept"},
)
# Instance with activity_type="Delete" returns DENY
```

## Generating PROV Records

```python
from sdcgovernance.provenance import record_provenance

rec = record_provenance(
    activity_type="Update",
    agent_name="Dr. Smith",
    entity_id="cuid2-abc123",
    system_id="sdc-studio-cloud",
    description="Approved patient encounter",
    entity_hash_before="abc...",
    entity_hash_after="def...",
)
print(rec.to_dict())
```

## RDF/Turtle Export

```python
from sdcgovernance.provenance import provenance_to_rdf

turtle = provenance_to_rdf([rec], instance_id="cuid2-abc123")
print(turtle)
# @prefix prov: <http://www.w3.org/ns/prov#> .
# ...prov:Activity, prov:Agent, prov:Entity relationships...
```

## Validation Outcomes

| Scenario | Result |
|---|---|
| All records have system-id + timestamp | PERMIT |
| Record missing system-id | DENY per record |
| Record missing timestamp | DENY per record |
| system-user required but missing | DENY per record |
| Activity type not in allowed set | DENY per record |
| Retention: fewer records than required | DENY |
| No records when audit required | DENY |
| No records when audit not required | PERMIT |
