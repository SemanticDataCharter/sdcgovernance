# PRD: W3C PROV-O Conformance Validation

**Date**: May 5, 2026
**Status**: COMPLETE - conformance validated, code fixed in 4.0.1, report ready
**Trigger**: Paul Groth (PROV-O specification co-editor, University of Amsterdam) reviewed sdcgovernance and directed us to the official conformance test cases.
**Priority**: High - standards author validation is credibility infrastructure

---

## 1. Context

Paul Groth, co-editor of the W3C PROV-O specification and Professor of Data Science at the University of Amsterdam, reviewed sdcgovernance and called it "really cool." He directed us to the official PROV-CONSTRAINTS conformance test cases for validation.

sdcgovernance already has positive reviews from:
- Bill Parducci, OASIS XACML TC Chair (XACML decision semantics)
- Jim Barnett, W3C SCXML TC Chair (state and transition concepts)

Adding PROV-O conformance verification from the specification's own co-editor completes the trifecta of standards body validation.

## 2. Scope of Conformance

sdcgovernance does NOT implement the full PROV-O specification. It implements the **PROV-O core pattern** mapped to SDC4 AuditType components. The scope of conformance must be honest.

### What sdcgovernance implements

| PROV-O Concept | sdcgovernance Mapping | Implementation |
|---|---|---|
| `prov:Entity` | AuditType.system-id (XdStringType) | Entity URI created from instance_id. Typed as `prov:Entity`. |
| `prov:Activity` | AuditType timestamp + activity type | Activity node with `prov:startedAtTime`, `prov:endedAtTime`. Activity type from W3C Activity Streams 2.0. |
| `prov:Agent` | AuditType.system-user (PartyType) | Agent node with `rdfs:label`. Typed as `prov:Agent`. |
| `prov:wasGeneratedBy` | Entity -> Activity | Entity `prov:wasGeneratedBy` Activity triple. |
| `prov:used` | Activity -> Entity | Activity `prov:used` Entity triple. |
| `prov:wasAssociatedWith` | Activity -> Agent | Activity `prov:wasAssociatedWith` Agent triple. |

### SDC validation details (not part of PROV-O)

Entity state hashes use the SDC4 RM XdFileType pattern (`hash-function` + `hash-result`) within structured `validation-details` containers linked to each activity. No namespace extensions beyond the RM specification are introduced.

| Property | Pattern | Purpose |
|---|---|---|
| `sdc4:validation-details` | Container on Activity | Groups validation information |
| `sdc4:entity-state-before` | XdFileType hash pattern | SHA-256 hash of entity state before the activity |
| `sdc4:entity-state-after` | XdFileType hash pattern | SHA-256 hash of entity state after the activity |
| `sdc4:hash-function` | XdFileType element | Hash algorithm ("SHA-256") |
| `sdc4:hash-result` | XdFileType element | Computed hash value |

**Note**: In 4.0.0, hashes were incorrectly modeled as invented namespace properties (`sdc4:entityHashBefore/After`). Fixed in 4.0.1 to use RM-defined XdFileType elements. SDC5 issue filed to add a `validation` slot to AuditType natively.

### What sdcgovernance does NOT implement

| PROV-O Concept | Status | Reason |
|---|---|---|
| `prov:wasDerivedFrom` | Not implemented | SDC tracks derivation through the hash chain (entityHashBefore/After), not through explicit PROV derivation triples |
| `prov:wasAttributedTo` | Not implemented | Attribution is implicit through the Agent associated with the Activity |
| `prov:wasInformedBy` | Not implemented | Activity-to-Activity communication not modeled in AuditType |
| `prov:actedOnBehalfOf` | Not implemented | Agent delegation not modeled in AuditType (covered by SDC's Participation/Party model instead) |
| `prov:Bundle` | Not implemented | SDC uses its own DM root structure, not PROV bundles |
| `prov:Collection` / `prov:Dictionary` | Not implemented | Out of scope |
| `prov:alternateOf` / `prov:specializationOf` | Not implemented | Out of scope |
| Qualified relations (prov:Influence, prov:Usage, etc.) | Not implemented | Only simple relations used |

## 3. Conformance Claim

The target conformance claim is:

> "sdcgovernance implements the W3C PROV-O Starting Point terms (Entity, Activity, Agent) with generation, usage, and association relationships. RDF/Turtle export produces valid PROV-O triples verified against prov-check, the conformance validator authored by the PROV-O specification co-editor."

This is **core conformance**, not full conformance. The claim must be stated precisely.

## 4. Validation Approach

### 4.1 Tool: prov-check

Paul Groth's own PROV-CONSTRAINTS validator:
- Repository: https://github.com/pgroth/prov-check
- Implementation: SPARQL 1.1 queries against PROV-O data
- Test record: 279/280 official test cases passing
- Accepts: PROV-O serializations (RDF/Turtle)
- Status: alpha but comprehensive

**Steps:**
1. Clone prov-check
2. Generate RDF/Turtle from sdcgovernance's `provenance_to_rdf()` function
3. Feed the Turtle output into prov-check
4. Document which constraints pass/fail
5. Fix any failures that are within scope
6. Document any failures that are out of scope with justification

### 4.2 Test Cases: openprov/testcases

Southampton Provenance Suite:
- Repository: https://github.com/openprov/testcases
- ~480 test directories
- Formats: PROV-N, PROV-O Turtle, TriG, PROV-XML, PROV-JSON
- Coverage: entities, activities, agents, associations, attributions, delegations, derivations, bundles

**Steps:**
1. Clone the test case repo
2. Identify test cases that exercise ONLY the core pattern (Entity, Activity, Agent, generation, usage, association)
3. Attempt to load each relevant Turtle file
4. Verify sdcgovernance can correctly interpret the PROV relationships
5. Document pass/fail per test case
6. Categorize failures as "in scope" (should fix) vs "out of scope" (expected, documented)

### 4.3 Round-Trip Test

The most important test for sdcgovernance's specific use case:

1. Create an SDC XML instance with AuditType components populated
2. Extract provenance via `extract_provenance()`
3. Generate PROV records via `record_provenance()`
4. Export to RDF/Turtle via `provenance_to_rdf()`
5. Validate the Turtle output with prov-check
6. Load the Turtle into rdflib and verify SPARQL queries return correct Entity/Activity/Agent relationships

This round-trip proves that the SDC AuditType -> PROV-O export pipeline produces valid, queryable provenance.

## 5. Known Issues - Resolution

### 5.1 prov:type usage
**Status**: PASS - prov-check accepts `prov:type` as a literal string. No change needed for core conformance. Future enhancement: consider using AS2 URI references for activity types.

### 5.2 prov:wasGeneratedBy - multiple activities on same entity
**Status**: PASS - prov-check accepts multiple `wasGeneratedBy` relationships from the same entity to different activities. This correctly models "the same data instance was modified by multiple activities." No change needed.

### 5.3 prov:used - same entity used by every activity
**Status**: PASS - prov-check accepts this pattern. Activity timestamps are non-overlapping in our test data, so no ordering constraint violations. No change needed.

### 5.4 Missing prov:wasAttributedTo
**Status**: OUT OF SCOPE - attribution is implicit through the Agent associated with the Activity via `wasAssociatedWith`. Adding `wasAttributedTo` is a future enhancement, not a conformance requirement for the core pattern.

### 5.5 Entity hash namespace violation (FIXED in 4.0.1)
**Status**: FIXED - entity state hashes were incorrectly modeled as invented sdc4 namespace properties (`entityHashBefore/After`). Fixed to use RM-defined XdFileType pattern (`hash-function` + `hash-result`) within `validation-details` containers.

## 6. Deliverables

1. **Conformance report** (`docs/prov-conformance/conformance-report.md`): which PROV-O terms are implemented, which constraints pass prov-check, which test cases pass, scope boundaries with justification
2. **Fixed export** (if needed): any corrections to `provenance_to_rdf()` based on prov-check results
3. **Test script** (`tests/test_prov_conformance.py`): automated round-trip test that generates PROV-O output and validates it
4. **Updated documentation**: `docs/test-harness/provenance.md` updated with conformance results
5. **Reply to Paul Groth**: conformance results shared with the specification co-editor

## 7. Success Criteria - Results

1. **PASS** - prov-check validates sdcgovernance's RDF/Turtle output (4 test cases: realistic 3-record, minimal, blank node, 10-record chain)
2. **PASS** - 51/51 openprov reference test cases validated by prov-check (entity, activity, agent, generation, usage, association)
3. **DONE** - Conformance claim precisely scoped in PROV-O_Conformance_Report.md
4. **PENDING** - Reply to Paul Groth with conformance report

## 8. Completion

Completed May 5, 2026. Entity hash namespace violation discovered and fixed during review (4.0.1). SDC5 issue filed for native AuditType validation slot.

Remaining: send conformance report PDF to Paul Groth, add automated prov-check test to CI (optional).

---

*Conformance validation initiated at the direction of Paul Groth, co-editor of the W3C PROV-O specification.*
