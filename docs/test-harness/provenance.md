# Provenance Tests - W3C PROV-O/PROV-DM, Activity Streams 2.0, DPV Compliance

**Standards**:
- W3C PROV-O (https://www.w3.org/TR/prov-o/)
- W3C PROV-DM (https://www.w3.org/TR/prov-dm/)
- W3C Activity Streams 2.0 (https://www.w3.org/TR/activitystreams-core/)
- W3C Data Privacy Vocabulary (https://w3c.github.io/dpv/dpv/)

**Module**: `sdcgovernance/provenance.py`
**Tests**: 29

## SDC RM Mapping

The SDC component `sdc4:AuditType` maps to PROV-DM:

| AuditType Element | PROV-DM Concept | Required |
|---|---|---|
| `system-id` (XdStringType) | prov:Entity context | **Yes** |
| `timestamp` (xs:dateTime) | prov:Activity temporal bounds | **Yes** |
| `system-user` (PartyType) | prov:Agent | No |
| `location` (ClusterType) | Provenance metadata | No |

## Extraction Tests

### Test: Complete audit records

**Input**: `instance-audit-complete.xml` - two audit records with all elements.

```xml
<sdc4:Audit>
  <label>Initial Creation</label>
  <system-id><xdstring-value>epic-ehr-prod-01</xdstring-value></system-id>
  <system-user>
    <party-name>Dr. Smith</party-name>
    <party-ref><link>https://identity.example.com/providers/dr-smith</link></party-ref>
  </system-user>
  <location><label>Porto Sereno General Hospital</label></location>
  <timestamp>2026-04-24T08:00:00Z</timestamp>
</sdc4:Audit>
```

```python
def test_first_record_content():
    data = extract_provenance("instance-audit-complete.xml")
    r = data.records[0]
    assert r.system_id == "epic-ehr-prod-01"        # prov:Entity context
    assert r.system_user_name == "Dr. Smith"         # prov:Agent
    assert r.location_label == "Porto Sereno..."     # metadata
    assert r.timestamp == "2026-04-24T08:00:00Z"     # prov:Activity temporal
```

**Standards mapping**: AuditType elements correctly map to PROV-DM Entity (system-id), Agent (system-user), and Activity temporal bounds (timestamp).

### Test: Missing required system-id

**Input**: `instance-audit-missing-systemid.xml` - audit record without system-id.

```python
def test_missing_system_id_fails():
    data = extract_provenance("instance-audit-missing-systemid.xml")
    result = validate_provenance(data)
    assert result.valid is False
    assert any("system-id" in e for e in result.errors)
```

**Result**: `Audit record 1: system-id is required but missing`

**Standards mapping**: prov:Entity context is mandatory. Every provenance record must identify the system that produced it.

### Test: Missing required timestamp

```python
def test_missing_timestamp_fails():
    data = extract_provenance("instance-audit-missing-timestamp.xml")
    result = validate_provenance(data)
    assert result.valid is False
    assert any("timestamp" in e for e in result.errors)
```

**Result**: `Audit record 1: timestamp is required but missing`

**Standards mapping**: prov:Activity temporal bounds are mandatory per PROV-DM.

## Activity Streams 2.0 Type Filtering

### Test: Allowed activity type passes

```python
def test_allowed_activity_type():
    data = ProvenanceData(records=[AuditRecord(
        has_system_id=True, system_id="test",
        has_timestamp=True, timestamp="2026-01-01T00:00:00Z",
        activity_type="Create",
    )])
    reqs = ProvenanceRequirements(allowed_activity_types={"Create", "Update"})
    result = validate_provenance(data, reqs)
    assert result.valid is True
```

### Test: Disallowed activity type denied

```python
def test_disallowed_activity_type():
    data = ProvenanceData(records=[AuditRecord(
        ..., activity_type="Delete",
    )])
    reqs = ProvenanceRequirements(allowed_activity_types={"Create", "Update"})
    result = validate_provenance(data, reqs)
    assert result.valid is False
```

**Result**: `Audit record 1: activity type 'Delete' is not allowed. Allowed types: ['Create', 'Update']`

**Standards mapping**: Activity types from W3C Activity Streams 2.0 vocabulary. The model defines which AS2 types are valid for this governance context.

## DPV Retention Policy

Three retention levels aligned with W3C Data Privacy Vocabulary:

### Test: Most recent + hash

```python
def test_most_recent_passes_with_one():
    data = extract_provenance("instance-audit-single.xml")  # 1 record
    reqs = ProvenanceRequirements(retention_level=RetentionLevel.MOST_RECENT)
    result = validate_provenance(data, reqs)
    assert result.valid is True
```

### Test: Last N records

```python
def test_last_n_fails_insufficient():
    data = extract_provenance("instance-audit-single.xml")  # 1 record
    reqs = ProvenanceRequirements(retention_level=RetentionLevel.LAST_N, retention_n=3)
    result = validate_provenance(data, reqs)
    assert result.valid is False
```

**Result**: `Retention policy 'last_n' requires at least 3 audit records, but instance has 1`

### Test: Full chain

```python
def test_full_chain_passes():
    data = extract_provenance("instance-audit-complete.xml")  # 2 records
    reqs = ProvenanceRequirements(retention_level=RetentionLevel.FULL_CHAIN, min_records=2)
    result = validate_provenance(data, reqs)
    assert result.valid is True
```

**Standards mapping**: DPV StorageDuration/StorageCondition concepts applied to provenance record retention. The same vocabulary used for SDC access control (DM.acs).

## PROV-O Record Generation

### Test: Generate PROV record

```python
def test_create_record():
    rec = record_provenance(
        activity_type="Create",
        agent_name="Dr. Smith",
        entity_id="cuid2-test-001",
        system_id="sdc-studio-cloud",
        description="Created patient encounter",
    )
    assert rec.activity_type == "Create"     # prov:Activity type (AS2)
    assert rec.agent_name == "Dr. Smith"     # prov:Agent
    assert rec.entity_id == "cuid2-test-001" # prov:Entity
    assert rec.started_at != ""             # prov:startedAtTime
```

**Standards mapping**: Generated record follows PROV-DM with Activity (what), Agent (who), Entity (what was affected), and temporal bounds.

## RDF/Turtle Export

### Test: Export as RDF/Turtle

```python
def test_export_single_record():
    rec = record_provenance(activity_type="Create", agent_name="Dr. Smith", entity_id="test-001")
    turtle = provenance_to_rdf([rec], instance_id="test-001")
    assert len(turtle) > 0
```

**Standards mapping**: Output uses rdflib with PROV-O namespace. Contains prov:Activity, prov:Agent, prov:Entity, prov:wasAssociatedWith, prov:wasGeneratedBy, prov:used, prov:startedAtTime, prov:endedAtTime triples.

## Hash Integrity

### Test: Record hash deterministic

```python
def test_hash_deterministic():
    r = AuditRecord(system_id="test", has_system_id=True, timestamp="2026-01-01", has_timestamp=True)
    h1 = r.compute_hash()
    h2 = r.compute_hash()
    assert h1 == h2
```

### Test: Different content produces different hash

```python
def test_hash_changes_with_content():
    r1 = AuditRecord(system_id="system-a", ...)
    r2 = AuditRecord(system_id="system-b", ...)
    assert r1.compute_hash() != r2.compute_hash()
```

**Standards mapping**: SHA-256 hash per record enables tamper detection in the provenance chain.
