# SHACL Validation

Validates cross-entity constraints using W3C SHACL shapes via pyshacl. Complements sdcvalidator's XSD structural checks with graph-level relationship validation.

## When to Use SHACL

SHACL validates constraints that span multiple entities - relationships that XSD cannot express:

- "Every patient must have at least one provider"
- "A provider must have a name"
- "An encounter must reference both a patient and a provider"

## Usage

```python
from sdcgovernance.shacl_runtime import validate_shacl_from_strings

shapes = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <http://example.org/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:PatientShape a sh:NodeShape ;
    sh:targetClass ex:Patient ;
    sh:property [
        sh:path ex:hasProvider ;
        sh:minCount 1 ;
        sh:class ex:Provider ;
        sh:message "Patient must have at least one Provider" ;
    ] .
"""

data = """
@prefix ex: <http://example.org/> .
ex:patient1 a ex:Patient ;
    ex:hasProvider ex:provider1 .
ex:provider1 a ex:Provider .
"""

result = validate_shacl_from_strings(data, shapes)
print(result.conforms)   # True
print(result.decision)   # Decision.PERMIT
```

## Validation from Files

```python
from sdcgovernance.shacl_runtime import validate_shacl

result = validate_shacl("data.ttl", "shapes.ttl")
```

Also accepts rdflib `Graph` objects:

```python
from rdflib import Graph

data_g = Graph()
data_g.parse("data.ttl")

shapes_g = Graph()
shapes_g.parse("shapes.ttl")

result = validate_shacl(data_g, shapes_g)
```

## Violation Details

On non-conformance, violations are extracted with full details:

```python
result = validate_shacl_from_strings(invalid_data, shapes)
print(result.conforms)    # False
print(result.decision)    # Decision.DENY

for v in result.violations:
    print(v.focus_node)     # "http://example.org/patient1"
    print(v.result_path)    # "http://example.org/hasProvider"
    print(v.message)        # "Patient must have at least one Provider"
    print(v.severity)       # "http://www.w3.org/ns/shacl#Violation"
    print(v.source_shape)   # shape node URI

# Errors populated from violation messages
print(result.errors)  # ["Patient must have at least one Provider"]
```

## Governance Integration

| SHACL Result | Governance Decision |
|---|---|
| Conforms | PERMIT |
| Non-conformant | DENY |
| pyshacl not installed | INDETERMINATE |
| Parse error | INDETERMINATE |

## SDC SHACL Files

SDC data models generate `_shacl.ttl` files as part of their output. These contain SHACL shapes derived from the model's component constraints. Use these directly:

```python
result = validate_shacl("instance_data.ttl", "dm-healthcare_shacl.ttl")
```
