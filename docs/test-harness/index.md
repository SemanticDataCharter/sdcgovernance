# sdcgovernance Test Harness - Standards Compliance Evidence

This documentation presents the complete test suite for sdcgovernance with inputs, expected outputs, and mappings to the W3C/OASIS/OMG standards each test validates.

**Purpose**: Enable standards authors and reviewers to evaluate compliance by reading the test evidence, without needing to clone the repository or run Python.

**Test suite**: 225 tests, all passing, executing in 0.22 seconds.

## Contents

1. [Model Inspector Tests](model-inspector.md) - DMType governance slot detection
2. [Receipt Chain Tests](receipts.md) - SHA-256 hash-chained tamper-evident receipts (OASIS XACML decisions)
3. [Workflow Tests](workflow.md) - Cluster tree paths, ordinal adjacency (W3C SCXML vocabulary)
4. [Attestation Tests](attestation.md) - Authority assertions (W3C VC Data Model 2.0)
5. [Party/Role Tests](party-role.md) - ParticipationType function constraints
6. [Provenance Tests](provenance.md) - AuditType validation, retention policy, PROV-O export (W3C PROV-O/PROV-DM, W3C Activity Streams 2.0, W3C DPV)
7. [Decision Table Tests](decision-tables.md) - DMN conditional evaluation (OMG DMN)
8. [SHACL Tests](shacl.md) - Cross-entity constraint validation (W3C SHACL)
9. [MCP Server Tests](mcp-server.md) - JSON-RPC 2.0 MCP protocol and tool invocation

## Standards Coverage

| Standard | Module | Tests | What is Validated |
|---|---|---|---|
| OASIS XACML | receipts.py | 26 | PERMIT/DENY/INDETERMINATE decision semantics, receipt chain |
| W3C SCXML (vocabulary) | workflow.py | 28 | State labels, ordinal sequencing, transition validation |
| W3C VC Data Model 2.0 | attestation.py | 13 | Committer/issuer, pending flag, proof, committed timestamp |
| W3C PROV-O / PROV-DM | provenance.py | 19 | Entity/Activity/Agent relationships, PROV record generation, RDF/Turtle export |
| W3C Activity Streams 2.0 | provenance.py | 4 | Activity type filtering (Create, Update, Accept, etc.) |
| W3C DPV | provenance.py | 6 | Retention policy enforcement (most_recent, last_n, full_chain) |
| W3C SHACL | shacl_runtime.py | 14 | Shape validation, cross-entity constraints, violation reporting |
| OMG DMN | decision.py | 33 | Decision tables, hit policies, condition evaluation, determinism |

## Test Fixture Files

All test fixtures are in `tests/fixtures/`:

**XSD Model Fixtures** (governance slot combinations):
- `dm-no-governance.xsd` - No governance slots populated
- `dm-all-governance.xsd` - All governance slots populated
- `dm-workflow-only.xsd` - Only workflow governance
- `dm-audit-only.xsd` - Only audit/provenance governance
- `dm-attestation-only.xsd` - Only attestation governance
- `dm-ftluo2nybgxmn7mawttoos20.xsd` - Real CordovaOS Healthcare Record model

**XML Instance Fixtures** (governance content):
- `instance-linear-workflow.xml` - Linear 4-state workflow (draft->review->approved->published)
- `instance-branching-workflow.xml` - Branching 2-path workflow with shared states
- `instance-attestation-complete.xml` - Complete attestation (pending=false, committer, proof, reason)
- `instance-attestation-pending.xml` - Pending attestation
- `instance-attestation-no-committer.xml` - Attestation without committer
- `instance-no-attestation.xml` - No attestation element
- `instance-party-role.xml` - Subject, providers, participations with roles
- `instance-audit-complete.xml` - Two audit records with all elements
- `instance-audit-missing-systemid.xml` - Audit record missing required system-id
- `instance-audit-missing-timestamp.xml` - Audit record missing required timestamp
- `instance-audit-single.xml` - Single audit record
- `instance-no-audit.xml` - No audit records
- `instance-decision-context.xml` - Protocol, XdLinks, current-state for decision tables

## How to Read These Documents

Each test harness document follows this pattern:

1. **Standard reference** - which W3C/OASIS/OMG specification is being validated
2. **Test fixture** - the exact XSD model or XML instance used as input
3. **Test code** - the Python test that exercises the functionality
4. **Expected output** - the exact return values, decisions, and error messages
5. **Standards mapping** - how the test output maps to the standard's requirements

If you are a standards author reviewing this implementation, focus on the **Standards mapping** sections. They explain how sdcgovernance interprets and implements your specification.
