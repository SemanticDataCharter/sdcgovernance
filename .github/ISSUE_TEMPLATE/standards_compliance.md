---
name: Standards Compliance Issue
about: Report where sdcgovernance diverges from a W3C, OASIS, or OMG specification
title: '[STANDARDS] '
labels: standards, compliance
assignees: ''
---

## Standard

**Which standard is affected?**

- [ ] W3C PROV-O / PROV-DM (provenance records)
- [ ] W3C Activity Streams 2.0 (activity types)
- [ ] W3C Data Privacy Vocabulary (retention policy)
- [ ] W3C SCXML (workflow state vocabulary)
- [ ] W3C Verifiable Credentials Data Model 2.0 (attestation)
- [ ] W3C SHACL (constraint validation)
- [ ] OASIS XACML (decision semantics)
- [ ] OMG DMN (decision tables)
- [ ] Other (specify)

**Specification reference**: (URL to the specific section)

## The Divergence

**What does the standard specify?**

Quote or paraphrase the relevant section:

> 

**What does sdcgovernance do instead?**

Reference the relevant module and behavior:

- **Module**: (e.g., provenance.py, receipts.py)
- **Function/class**: (e.g., record_provenance, Receipt)
- **Test harness doc**: (e.g., docs/test-harness/provenance.md)
- **Current behavior**:

## Severity

- [ ] **Incorrect**: Implementation contradicts the specification
- [ ] **Incomplete**: Implementation is missing required behavior
- [ ] **Non-standard extension**: Implementation adds behavior not in the spec (may be intentional)
- [ ] **Ambiguous**: Specification is unclear and implementation chose one interpretation

## Proposed Fix

**How should sdcgovernance change to align with the standard?**

## Test Evidence

**If you reviewed the test harness documentation, which test(s) demonstrate the issue?**

- Test:
- Expected result per standard:
- Actual result:

## Context

**Are you:**
- [ ] An author/editor of this standard
- [ ] An implementer using this standard
- [ ] A reviewer evaluating compliance
- [ ] Other (specify):

## Additional Context

**Any other relevant information, links to related discussions, or prior art**
