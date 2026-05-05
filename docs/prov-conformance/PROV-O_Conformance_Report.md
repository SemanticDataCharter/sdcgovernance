# W3C PROV-O Conformance Report

## sdcgovernance 4.0.0

---

**Document**: PROV-O Core Conformance Report
**Library**: sdcgovernance 4.0.0 (Apache 2.0)
**Date**: May 5, 2026
**Author**: Timothy W. Cook, CEO, Axius SDC, Inc.
**Validator**: prov-check (Paul Groth, University of Amsterdam)
**Test Suite**: Southampton Provenance Suite (openprov/testcases)
**Specification**: W3C PROV-O (https://www.w3.org/TR/prov-o/)

---

## 1. Executive Summary

sdcgovernance 4.0.0 implements the W3C PROV-O Starting Point terms (Entity, Activity, Agent) with generation, usage, and association relationships. RDF/Turtle export was validated against prov-check, the PROV-CONSTRAINTS validator authored by Paul Groth, co-editor of the W3C PROV-O specification.

**Result**: All sdcgovernance PROV-O output passes prov-check validation. Core conformance confirmed.

---

## 2. Scope of Conformance

sdcgovernance implements the **PROV-O core pattern** mapped to SDC4 AuditType components. This report documents conformance with the Starting Point terms of the specification. It does not claim full PROV-O conformance.

### 2.1 Implemented PROV-O Terms

| PROV-O Term | Type | sdcgovernance Mapping | Status |
|---|---|---|---|
| `prov:Entity` | Starting Point | AuditType.system-id -> Entity URI | **Implemented** |
| `prov:Activity` | Starting Point | AuditType timestamp + activity type -> Activity node | **Implemented** |
| `prov:Agent` | Starting Point | AuditType.system-user (PartyType) -> Agent node | **Implemented** |
| `prov:wasGeneratedBy` | Starting Point | Entity -> Activity relationship | **Implemented** |
| `prov:used` | Starting Point | Activity -> Entity relationship | **Implemented** |
| `prov:wasAssociatedWith` | Starting Point | Activity -> Agent relationship | **Implemented** |
| `prov:startedAtTime` | Expanded | Activity temporal bound (start) | **Implemented** |
| `prov:endedAtTime` | Expanded | Activity temporal bound (end) | **Implemented** |

### 2.2 SDC-Specific Extensions

sdcgovernance adds two properties in the SDC namespace that extend the PROV-O record with tamper-evidence capabilities:

| Property | Namespace | Purpose |
|---|---|---|
| `sdc4:entityHashBefore` | `https://semanticdatacharter.com/ns/sdc4/` | SHA-256 hash of entity state before the activity |
| `sdc4:entityHashAfter` | `https://semanticdatacharter.com/ns/sdc4/` | SHA-256 hash of entity state after the activity |

These extensions are in a separate namespace and do not interfere with PROV-O conformance.

### 2.3 PROV-O Terms Not Implemented

The following PROV-O terms are out of scope for sdcgovernance's AuditType mapping:

| PROV-O Term | Category | Reason |
|---|---|---|
| `prov:wasDerivedFrom` | Starting Point | Derivation tracked via entity hash chain (sdc4:entityHashBefore/After) |
| `prov:wasAttributedTo` | Starting Point | Attribution implicit through Agent associated with Activity |
| `prov:wasInformedBy` | Expanded | Activity-to-Activity communication not modeled in AuditType |
| `prov:actedOnBehalfOf` | Expanded | Agent delegation modeled via SDC4 Participation/Party, not PROV |
| `prov:Bundle` | Qualified | SDC uses DM root structure |
| `prov:Collection` | Qualified | Out of scope |
| `prov:Dictionary` | Qualified | Out of scope |
| `prov:alternateOf` | Expanded | Out of scope |
| `prov:specializationOf` | Expanded | Out of scope |
| Qualified relations | Qualified | Only simple relations used |

---

## 3. Validation Methodology

### 3.1 Validator

**prov-check** by Paul Groth, Ph.D., Professor of Data Science, University of Amsterdam
- Repository: https://github.com/pgroth/prov-check
- Implementation: W3C PROV-CONSTRAINTS via SPARQL 1.1 queries
- Test record: 279/280 official W3C test cases passing
- Input format: PROV-O serializations (RDF/Turtle)

### 3.2 Test Procedure

1. Generate RDF/Turtle output from sdcgovernance's `provenance_to_rdf()` function using realistic provenance records
2. Feed the Turtle output into prov-check
3. Record pass/fail result
4. Repeat with edge cases (minimal record, blank node entity, 10-record chain)
5. Cross-validate by running prov-check against the Southampton Provenance Suite reference test cases to confirm the validator itself produces expected results

---

## 4. Test Results

### 4.1 sdcgovernance Output Tests

| Test Case | Description | Records | Entity Type | Result |
|---|---|---|---|---|
| Realistic 3-record | Healthcare scenario: Create, Update, Approve by two agents with entity hash chain | 3 | Named URI | **PASS** |
| Minimal single-record | Single Create activity by one agent | 1 | Named URI | **PASS** |
| Blank node entity | Single Create activity, no instance_id provided | 1 | Blank node | **PASS** |
| 10-record chain | Extended workflow: Create through Archive, 10 distinct agents, full hash chain | 10 | Named URI | **PASS** |

**Result: 4/4 sdcgovernance output tests pass prov-check validation.**

### 4.2 Sample Turtle Output (Realistic 3-Record Test)

```turtle
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix sdc4: <https://semanticdatacharter.com/ns/sdc4/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

sdc4:activity-0 a prov:Activity ;
    rdfs:comment "Initial patient record creation" ;
    prov:endedAtTime "2026-05-05T08:00:01+00:00"^^xsd:dateTime ;
    prov:startedAtTime "2026-05-05T08:00:00+00:00"^^xsd:dateTime ;
    prov:type "Create" ;
    prov:used sdc4:cordovaos-patient-001 ;
    prov:wasAssociatedWith sdc4:agent-maria-santos ;
    sdc4:entityHashAfter "a1b2c3d4e5f6" .

sdc4:activity-1 a prov:Activity ;
    rdfs:comment "Updated vital signs" ;
    prov:endedAtTime "2026-05-05T10:30:02+00:00"^^xsd:dateTime ;
    prov:startedAtTime "2026-05-05T10:30:00+00:00"^^xsd:dateTime ;
    prov:type "Update" ;
    prov:used sdc4:cordovaos-patient-001 ;
    prov:wasAssociatedWith sdc4:agent-nurse-thompson ;
    sdc4:entityHashAfter "f6e5d4c3b2a1" ;
    sdc4:entityHashBefore "a1b2c3d4e5f6" .

sdc4:activity-2 a prov:Activity ;
    rdfs:comment "Approved for discharge" ;
    prov:endedAtTime "2026-05-05T14:00:01+00:00"^^xsd:dateTime ;
    prov:startedAtTime "2026-05-05T14:00:00+00:00"^^xsd:dateTime ;
    prov:type "Approve" ;
    prov:used sdc4:cordovaos-patient-001 ;
    prov:wasAssociatedWith sdc4:agent-maria-santos ;
    sdc4:entityHashAfter "c3d4e5f6a1b2" ;
    sdc4:entityHashBefore "f6e5d4c3b2a1" .

sdc4:agent-nurse-thompson a prov:Agent ;
    rdfs:label "Nurse Thompson" .

sdc4:agent-maria-santos a prov:Agent ;
    rdfs:label "Dr. Maria Santos" .

sdc4:cordovaos-patient-001 a prov:Entity ;
    prov:wasGeneratedBy sdc4:activity-0,
        sdc4:activity-1,
        sdc4:activity-2 .
```

### 4.3 Reference Test Suite Cross-Validation

To confirm prov-check produces reliable results, the Southampton Provenance Suite reference test cases were also validated. These are the canonical test cases maintained by the PROV community.

| Test Category | Tests Run | Pass | Fail | Notes |
|---|---|---|---|---|
| Entity (test-entity*) | 13 | 13 | 0 | All pass |
| Activity (test-activity*) | 9 | 9 | 0 | All pass |
| Agent (test-agent*) | 8 | 8 | 0 | All pass |
| Generation (test-generation*) | 7 | 7 | 0 | All pass |
| Usage (test-usage*) | 7 | 6 | 1 | usage1 is a deliberate negative test (type constraint violation) - correctly rejected |
| Association (test-association*) | 9 | 8 | 1 | association2 is a deliberate negative test (type constraint violation) - correctly rejected |

**Result: 51/51 valid reference test cases pass. 2/2 deliberate negative test cases are correctly rejected.**

This confirms prov-check is functioning correctly and its validation of sdcgovernance output is reliable.

---

## 5. Architecture Notes

### 5.1 How sdcgovernance Maps PROV-O to SDC4

The SDC4 Reference Model component `sdc4:AuditType` provides the structural slots for provenance tracking:

```
AuditType
  ├── system-id    (XdStringType, required) -> prov:Entity context
  ├── system-user  (PartyType, optional)    -> prov:Agent
  ├── location     (ClusterType, optional)  -> provenance metadata
  └── timestamp    (xs:dateTime, required)  -> prov:Activity temporal bounds
```

The `provenance_to_rdf()` function reads these AuditType components and produces valid PROV-O triples. Activity types are drawn from the W3C Activity Streams 2.0 vocabulary (Create, Update, Delete, Accept, Reject, Approve, etc.).

### 5.2 Tamper Evidence

sdcgovernance extends the PROV-O record with SHA-256 entity hash values (`sdc4:entityHashBefore` and `sdc4:entityHashAfter`) that create a verifiable chain of entity states across activities. This enables detection of:

- Unauthorized modifications between recorded activities
- Gaps in the provenance chain
- Retroactive alteration of provenance records

These extensions use the SDC namespace (`https://semanticdatacharter.com/ns/sdc4/`) and do not modify or conflict with PROV-O vocabulary.

### 5.3 Retention Policies

sdcgovernance implements three retention levels for provenance records, aligned with the W3C Data Privacy Vocabulary (DPV):

| Level | Behavior | Use Case |
|---|---|---|
| Most Recent + Hash | Keep latest record, SHA-256 hash of previous | Performance-sensitive, low-regulation environments |
| Last N Records | Keep N most recent provenance records | Operational audit trails |
| Full Chain | Keep entire provenance history | Legal hold, regulatory compliance (HIPAA, CIPSEA, Title 13) |

---

## 6. Conformance Statement

sdcgovernance 4.0.0 implements the W3C PROV-O Starting Point terms (Entity, Activity, Agent) with generation (`prov:wasGeneratedBy`), usage (`prov:used`), and association (`prov:wasAssociatedWith`) relationships. Temporal bounds are represented using `prov:startedAtTime` and `prov:endedAtTime`. Activity types are drawn from W3C Activity Streams 2.0.

RDF/Turtle output produced by `provenance_to_rdf()` has been validated against prov-check, the PROV-CONSTRAINTS validator authored by Paul Groth, co-editor of the W3C PROV-O specification. All test cases pass.

sdcgovernance does not claim full PROV-O conformance. The Expanded and Qualified terms (derivation, attribution, delegation, bundles, collections) are out of scope. Derivation is tracked through SDC-specific entity hash chains rather than explicit `prov:wasDerivedFrom` triples.

---

## 7. Standards Context

sdcgovernance 4.0.0 implements 24 international standards from 6 standards bodies. The PROV-O implementation is one dimension of a broader governance engine:

| Standard | Body | sdcgovernance Dimension | Author Review |
|---|---|---|---|
| **PROV-O / PROV-DM** | **W3C** | **Provenance records** | **Paul Groth (co-editor) - prov-check validation** |
| XACML 3.0 | OASIS | Governance decisions (PERMIT/DENY/INDETERMINATE/NOT_APPLICABLE) | Bill Parducci (TC Chair) - reviewed implementation |
| SCXML | W3C | Workflow state and transition concepts | Jim Barnett (TC Chair) - reviewed vocabulary usage |
| DPV | W3C | Retention policies, access control tags | - |
| Activity Streams 2.0 | W3C | Provenance activity types | - |
| VC Data Model 2.0 | W3C | Attestation authority pattern | - |
| SHACL | W3C | Cross-entity constraint validation | - |
| DMN | OMG | Decision tables (FIRST/UNIQUE/COLLECT) | - |
| ISO 21090 | ISO | Exceptional Values (Null Flavors) | - |

---

## 8. References

- W3C PROV-O: https://www.w3.org/TR/prov-o/
- W3C PROV-DM: https://www.w3.org/TR/prov-dm/
- W3C PROV-CONSTRAINTS: https://www.w3.org/TR/prov-constraints/
- prov-check: https://github.com/pgroth/prov-check
- Southampton Provenance Suite: https://github.com/openprov/testcases
- sdcgovernance: https://github.com/SemanticDataCharter/sdcgovernance
- sdcgovernance provenance test harness: https://github.com/SemanticDataCharter/sdcgovernance/blob/main/docs/test-harness/provenance.md
- SDC Specification: https://semanticdatacharter.com/specs/index.html

---

**Axius SDC, Inc.**
https://semanticdatacharter.com | https://axius-sdc.com
Apache 2.0 Licensed
