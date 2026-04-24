# SHACL Tests - W3C SHACL Compliance

**Standard**: W3C SHACL (https://www.w3.org/TR/shacl/)
**Module**: `sdcgovernance/shacl_runtime.py`
**Tests**: 14

## Test Shapes

### PersonShape (single entity)

```turtle
ex:PersonShape a sh:NodeShape ;
    sh:targetClass ex:Person ;
    sh:property [
        sh:path ex:name ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
        sh:message "Person must have a name" ;
    ] ;
    sh:property [
        sh:path ex:age ;
        sh:minCount 1 ;
        sh:datatype xsd:integer ;
        sh:minInclusive 0 ;
        sh:message "Person must have a non-negative age" ;
    ] .
```

### Cross-Entity Shape (patient-provider)

```turtle
ex:PatientShape a sh:NodeShape ;
    sh:targetClass ex:Patient ;
    sh:property [
        sh:path ex:hasProvider ;
        sh:minCount 1 ;
        sh:class ex:Provider ;
        sh:message "Patient must have at least one Provider" ;
    ] .

ex:ProviderShape a sh:NodeShape ;
    sh:targetClass ex:Provider ;
    sh:property [
        sh:path ex:providerName ;
        sh:minCount 1 ;
        sh:message "Provider must have a name" ;
    ] .
```

## Test Results

### Single Entity Validation

| Data | Conforms | Decision | Violations |
|---|---|---|---|
| Person with name + age | True | PERMIT | 0 |
| Person missing name | False | DENY | 1: "Person must have a name" |
| Person missing age | False | DENY | 1: "Person must have a non-negative age" |
| Person missing both | False | DENY | 2+ violations |
| Empty data graph (no targets) | True | PERMIT | 0 |

### Cross-Entity Validation (P6-03)

| Data | Conforms | Decision | Violations |
|---|---|---|---|
| Patient with Provider (named) | True | PERMIT | 0 |
| Patient without Provider | False | DENY | "Patient must have at least one Provider" |
| Patient with unnamed Provider | False | DENY | "Provider must have a name" |
| Patient with 2 named Providers | True | PERMIT | 0 |

### Violation Details

```python
for v in result.violations:
    v.focus_node     # "http://example.org/patient1"
    v.result_path    # "http://example.org/hasProvider"
    v.message        # "Patient must have at least one Provider"
    v.severity       # "http://www.w3.org/ns/shacl#Violation"
    v.source_shape   # shape node URI
```

### Governance Integration

| SHACL Result | Governance Decision |
|---|---|
| `conforms=True` | `Decision.PERMIT` |
| `conforms=False` | `Decision.DENY` |
| pyshacl not installed | `Decision.INDETERMINATE` |
| Parse error | `Decision.INDETERMINATE` |

**Standards mapping**: pyshacl performs the SHACL validation. sdcgovernance maps the conformance result to XACML decisions and extracts violation details from the SHACL validation report graph.
