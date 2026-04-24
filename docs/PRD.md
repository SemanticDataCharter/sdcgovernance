# sdcgovernance - Product Requirements Document

**Version**: 4.0.0
**Date**: 2026-04-24
**Status**: Pre-alpha
**License**: Apache 2.0
**Repository**: github.com/SemanticDataCharter/sdcgovernance

---

## 1. Purpose

sdcgovernance is a W3C standards-based governance advisory engine for SDC data instances. It validates governance content in XML instances against governance components defined in SDC data models, returning OASIS XACML decisions (PERMIT/DENY/INDETERMINATE) with hash-chained tamper-evident receipts.

It is the only governance library where enforcement is a structural property of the data instance, not the platform.

## 2. Problem Statement

Governance enforcement today is platform-bound. It depends on middleware, dashboards, policy engines, or LLM inference - all of which lose enforcement when data leaves the platform. Probabilistic governance (LLMs interpreting policies) cannot scale to machine-speed autonomous data exchange: every inference adds latency, uncertainty, and audit liability.

SDC instances carry their own meaning. sdcgovernance extends this to enforcement: the governance IS in the data. Deterministic, constant-time validation that produces a verifiable receipt on every decision.

## 3. Users

| User | How they interact |
|---|---|
| **AI agents** | Query governance via MCP tools during agentic workflows. Agent holds the loop. |
| **SDC Practitioners** | Model governance components in SDCStudio. Install sdcgovernance at client sites. |
| **Application developers** | Call Python API from generated apps or custom code. |
| **Standards reviewers** | Evaluate standards compliance via CordovaOS integration target. |
| **Enterprise architects** | Assess governance capabilities for EU AI Act, HIPAA, SOX compliance. |

## 4. Design Constraints

- Pure Python. No web framework, no middleware dependency.
- Two interfaces (Python API + MCP server), one engine.
- sdcvalidator and sdcgovernance are independent libraries. No hook, no chaining.
- Governance components discovered by vocabulary binding, not CUID2 identity.
- Each governance dimension is independent and composable.
- The model IS the configuration. No override files, no YAML, no separate config.
- Decision semantics are OASIS XACML (PERMIT/DENY/INDETERMINATE). No custom vocabulary.
- sdcgovernance advises. The agent decides what happens after the decision.

## 5. Standards Alignment

| Governance Need | Standard | Usage |
|---|---|---|
| Provenance / Audit | W3C PROV-O / PROV-DM | Provenance records follow PROV vocabulary. Audit and Provenance are one dimension. |
| Provenance retention | W3C Data Privacy Vocabulary (DPV) | Retention policies bound using DPV terms. Same vocabulary used for SDC access control. |
| Workflow sequencing | SDC native structure + W3C SCXML vocabulary | XdOrdinal components in cluster tree paths, labeled with SCXML semantics. |
| Attestation authority | W3C VC Data Model 2.0 | Issuer/holder/verifier pattern for authority assertions. |
| Constraint validation | W3C SHACL | Cross-entity constraints delegated to pyshacl. |
| Activity/event types | W3C Activity Streams 2.0 | Provenance activity types (Create, Update, Accept, Reject, etc.). |
| Decision outcomes | OASIS XACML | PERMIT/DENY/INDETERMINATE. |
| Conditional decision logic | OMG DMN | Decision tables for complex governance rules. |

## 6. Dependencies

| Package | Purpose | Phase |
|---|---|---|
| xmlschema or lxml | XSD model inspection | 1 |
| rdflib | PROV record generation, RDF/Turtle export | 4 |
| pyshacl | SHACL cross-entity constraint validation | 6 |
| mcp (optional) | MCP server SDK | 7 |


---

## 7. Phase 1: Model Inspector + Foundation

**Goal**: Read an SDC data model and detect which governance components are defined. Establish the receipt chain foundation.

**Implementation context**: Governance components are at known positions in the DMType root (see [RM_Reference.md](RM_Reference.md)). The model_inspector does not search arbitrarily through the model. It reads the DM root and checks which optional governance slots are populated:

- `DM.workflow` (ClusterType, 0..1) - Workflow dimension
- `DM.current-state` (xs:string, 0..1) - Workflow state tracking
- `DM.Audit[]` (AuditType, 0..*) - Provenance/Audit dimension
- `DM.attestation` (AttestationType, 0..1) - Attestation dimension
- `DM.subject` / `DM.provider` / `DM.Participation[]` - Party/Role dimension
- `DM.acs` (XdLinkType, 0..1) - Access control and retention policy (DPV bindings)

Vocabulary bindings on the components within these slots confirm which standards they conform to (SCXML, PROV-O, VC, DPV). The location is fixed by the RM; the vocabulary binding confirms the semantics.

### Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| P1-01 | model_inspector reads DM root and detects populated governance slots | Given a model with `DM.workflow` populated, returns workflow=True. Given a model with no governance slots populated, returns all dimensions as False. |
| P1-02 | model_inspector extracts Workflow cluster tree from `DM.workflow` | Given a DM.workflow ClusterType with 2 sub-clusters containing SCXML-bound XdOrdinal components, model_inspector extracts both paths with their ordinal sequences. |
| P1-03 | model_inspector detects Attestation from `DM.attestation` | Given a DM with AttestationType populated (pending, committer, reason, proof), model_inspector extracts authority requirements. Vocabulary bindings to VC terms confirm standard compliance. |
| P1-04 | model_inspector detects Provenance/Audit from `DM.Audit[]` | Given a DM with AuditType elements (system-id, system-user, location, timestamp), model_inspector extracts provenance requirements. Vocabulary bindings to PROV-O terms confirm standard compliance. |
| P1-05 | model_inspector extracts retention policy from `DM.acs` DPV bindings | Given a DM with acs linked to DPV-bound retention components, model_inspector extracts retention level (most recent + hash, last N, full chain). |
| P1-06 | model_inspector detects Party/Role from `DM.Participation[]` | Given a DM with ParticipationType elements containing function constraints, model_inspector extracts role requirements. |
| P1-07 | model_inspector reads `DM.current-state` | Given a DM instance with current-state populated, model_inspector returns the current workflow position. |
| P1-08 | GovernanceResult data structure | Contains: decision (PERMIT/DENY/INDETERMINATE), has_governance (bool), errors (list), receipt, dimensions_validated (dict mapping each dimension to its validation result). |
| P1-09 | Receipt data structure with SHA-256 hash chain | Each receipt contains: decision, reasoning, timestamp, PROV reference, SHA-256 hash of previous receipt. First receipt in chain has null previous hash. |
| P1-10 | Receipt chain is append-only | Receipts cannot be modified or deleted after creation. |
| P1-11 | Receipt chain is deterministic | Same inputs replay to the same decision and receipt (excluding timestamp). |
| P1-12 | validate_governance() returns PERMIT when no governance slots populated | Given a model with no governance slots populated in the DM root, validate_governance returns decision=PERMIT, has_governance=False. |
| P1-13 | PyPI package published | `pip install sdcgovernance` installs the library with model_inspector and receipts functional. |

### Test Strategy

- Test DM models with: no governance slots populated, workflow only, attestation only, audit only, all governance slots, mixed combinations.
- Test each DMType governance slot individually: workflow (ClusterType with sub-clusters), Audit (AuditType with required system-id and timestamp), attestation (AttestationType with pending flag), Participation (with function constraints).
- Test vocabulary bindings: components with correct SCXML/PROV-O/VC/DPV bindings vs components without bindings vs components with wrong bindings.
- Test receipt chain: create 3+ receipts, verify hash chain integrity, verify append-only constraint, verify deterministic replay.
- Test that custom models with the same DMType governance slots populated work identically to Default project models.

### Deliverables

- `model_inspector.py` - functional
- `receipts.py` - functional
- `__init__.py` - public API with validate_governance()
- Test suite
- PyPI 4.0.0a1 published

### Timeline: 2-3 weeks

---

## 8. Phase 2: GovernanceEngine + Workflow Validation

**Goal**: Validate workflow transitions in instances against the cluster tree defined in `DM.workflow`. Establish the GovernanceEngine advisory API.

**Implementation context**: `DM.workflow` is a ClusterType (0..1). Its sub-clusters define valid paths. Each sub-cluster contains XdOrdinal components defining sequenced states. `DM.current-state` (xs:string, 0..1) carries the current workflow position in the instance.

### Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| P2-01 | GovernanceEngine wraps model_inspector and validation modules | GovernanceEngine(schema_path) initializes with model inspection results cached. Reads DM root governance slots once. |
| P2-02 | Workflow cluster tree extraction from `DM.workflow` | Given a DM.workflow ClusterType with 2 sub-clusters (branching paths), engine extracts both paths with their XdOrdinal sequences. |
| P2-03 | Ordinal adjacency validation | Given `DM.current-state` at ordinal position N, engine validates that target state is at ordinal position N+1 in at least one valid path within DM.workflow. |
| P2-04 | Component reuse across paths | Given a component (same CUID2) appearing in sub-cluster A and sub-cluster B of DM.workflow, engine recognizes it as the same state in both paths. |
| P2-05 | get_allowed_transitions(instance) | Returns list of valid next states from current position, with the path(s) each belongs to. |
| P2-06 | evaluate_transition(instance, target_state, actor) | Returns PERMIT if transition exists in a valid path, DENY if not, INDETERMINATE if partially valid. Includes receipt. |
| P2-07 | SCXML vocabulary labels preserved | Workflow states carry SCXML vocabulary labels. These labels are included in transition results and receipts. |
| P2-08 | Invalid transition produces DENY with details | DENY result includes: current state, attempted target, valid alternatives, which paths were checked. |

### Test Strategy

- Linear workflow (A->B->C->D): test valid transitions, skip transitions (A->C = DENY), reverse transitions (C->B = DENY).
- Branching workflow (A->B->C, A->B->D): test both paths from B, verify component reuse.
- get_allowed_transitions from each state in a multi-path workflow.
- evaluate_transition with valid actor, invalid actor (deferred to Phase 3 for party/role).

### Deliverables

- `engine.py` - GovernanceEngine class, functional
- `workflow.py` - functional
- Test suite
- PyPI 4.0.0a2 published

### Timeline: 3-4 weeks

---

## 9. Phase 3: Attestation + Party/Role Validation

**Goal**: Validate `DM.attestation` (AttestationType) content and party/role constraints from `DM.subject` (PartyType), `DM.provider[]` (PartyType), and `DM.Participation[]` (ParticipationType) in instances.

**Implementation context**: AttestationType has one required element (`pending`: xs:boolean) and optional elements for committer (PartyType), proof (XdFileType), reason (XdStringType), committed (xs:dateTime), and view (XdFileType). Party/Role governance draws from three DM root slots: `DM.subject` (PartyType, 0..1) identifies the human subject (patient, customer); `DM.provider[]` (PartyType, 0..*) identifies information sources; `DM.Participation[]` (ParticipationType, 0..*) carries performer (PartyType) and function (XdStringType) - function is the role check target.

### Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| P3-01 | Attestation validation independent from workflow | DM.attestation populated without DM.workflow. validate_governance checks attestation only. |
| P3-02 | Attestation validates `pending` flag | AttestationType.pending=True means attestation is outstanding. Governance can require pending=False (completed) for certain transitions. |
| P3-03 | Attestation validates `committer` as authority | If model requires committer, instance with AttestationType.committer missing returns DENY. Committer maps to W3C VC issuer. |
| P3-04 | Attestation validates `committed` timestamp | If model requires committed timestamp, instance with AttestationType.committed missing returns DENY. |
| P3-05 | Attestation validates `proof` when required | If model requires cryptographic proof, instance with AttestationType.proof missing returns DENY. |
| P3-06 | Party/Role validates `Participation.function` | DM.Participation[] with ParticipationType.function constrained to "approver". Instance with performer whose function="approver" returns PERMIT. Instance with function="viewer" returns DENY. |
| P3-07 | Party/Role validates `DM.subject` | When model constrains subject, instance must have DM.subject (PartyType) populated with valid party identity. |
| P3-08 | Party/Role validates `DM.provider[]` | When model constrains provider, instance must have DM.provider[] (PartyType) populated. Multiple providers validated individually. |
| P3-09 | Party/Role integrates with evaluate_transition | evaluate_transition checks DM.Participation[].function, DM.subject, and DM.provider constraints when the model defines them for the target state. |
| P3-10 | Party identity resolved via `PartyType.party-ref` | When party-ref links to external identity system, governance validates the referenced party's role. Applies to subject, provider, and Participation.performer. |
| P3-11 | Attestation and Workflow compose optionally | DM with both DM.workflow and DM.attestation validates both. DM with only one validates only that dimension. |

### Test Strategy

- Attestation only (no workflow): valid attestation with pending=False, pending=True, missing committer, missing committed timestamp, missing proof when required.
- Party/Role via Participation: ParticipationType.function matching constraint, function not matching, function missing, multiple Participations with mixed roles.
- Party/Role via subject: DM.subject populated vs missing when model requires it.
- Party/Role via provider: DM.provider[] populated vs missing, multiple providers with different party-ref links.
- Combined: workflow transition that requires specific Participation.function, workflow transition that does not require attestation.
- Independence: adding DM.attestation to a model does not change DM.workflow validation results.
- AttestationType.reason with coded vocabulary binding vs uncoded.
- Cross-slot party identity: same PartyType.party-ref appearing in subject, provider, and Participation.performer.

### Deliverables

- `attestation.py` - functional
- `party_role.py` - functional
- Test suite
- PyPI 4.0.0a3 published

### Timeline: 2-3 weeks

---

## 10. Phase 4: Provenance Validation

**Goal**: Validate provenance/audit records in instances and generate W3C PROV-O compliant records. Enforce DPV retention policy.

**Implementation context**: `DM.Audit[]` is AuditType (0..*) at a known position in the DMType root. AuditType has two required elements (`system-id`: XdStringType, `timestamp`: xs:dateTime) and two optional elements (`system-user`: PartyType, `location`: ClusterType). PROV-O mapping: system-id -> prov:Entity context, system-user -> prov:Agent, timestamp -> prov:Activity temporal bounds, location -> provenance metadata. DPV retention policy accessed via `DM.acs` vocabulary bindings. External docs use "Provenance"; implementation works with AuditType at the DM root.

### Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| P4-01 | Provenance and Audit are one dimension | No separate audit validation. sdcgovernance reads `DM.Audit[]` (AuditType elements) from the DM root. |
| P4-02 | Validate AuditType required elements | Every AuditType element must have `system-id` (XdStringType) and `timestamp` (xs:dateTime). Instance with Audit record missing either returns DENY. |
| P4-03 | Validate AuditType.system-user when required by PROV-O bindings | If model requires Agent identification, instance with Audit record missing system-user (PartyType) returns DENY. |
| P4-04 | Validate Activity Streams 2.0 activity types | Model allows only (Create, Update, Accept). Instance with activity type "Delete" returns DENY. |
| P4-05 | Retention policy: most recent + hash | Model specifies "most recent only." Instance carries 1 provenance record + SHA-256 hash of previous. Validated. Instance carries 0 records returns DENY. |
| P4-06 | Retention policy: last N records | Model specifies N=3. Instance carries 3 records + hash. Validated. Instance carries 2 records returns DENY. |
| P4-07 | Retention policy: full chain | Model specifies full chain. Instance carries complete history. Hash chain verified end to end. |
| P4-08 | record_provenance() generates PROV-O record | Given an activity, agent, entity, and temporal bounds, generates a valid PROV record and appends to receipt chain. |
| P4-09 | RDF/Turtle export | Provenance records exportable as RDF/Turtle via rdflib. |
| P4-10 | Hash chain integrity | If any record in the provenance chain is tampered with, validation detects the break and returns DENY. |

### Test Strategy

- AuditType with and without each element (system-id, system-user, location, timestamp).
- Multiple DM.Audit[] records - validate each individually.
- Each retention level with correct and incorrect number of Audit records in instance.
- Hash chain with tampered Audit record in the middle.
- Activity type filtering with valid and invalid AS2 types.
- AuditType.location (ClusterType) populated vs empty.
- RDF/Turtle export of Audit records as PROV-O and re-import verification.

### Deliverables

- `provenance.py` - functional (merged audit)
- `audit.py` - redirect stub documenting merge
- Test suite
- PyPI 4.0.0a4 published

### Timeline: 2-3 weeks

---

## 11. Phase 5: DMN Decision Tables

**Goal**: Evaluate conditional governance rules using OMG DMN semantics for complex governance logic beyond simple state matching.

### Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| P5-01 | Decision table evaluation | Given a decision table with 3 rules, engine evaluates instance data against all rules and returns the matching rule's outcome. |
| P5-02 | Multi-condition rules | Rule: "PERMIT if risk_score < 5 AND attestation_level >= 'senior'". Instance with risk_score=3, attestation_level='senior' returns PERMIT. |
| P5-03 | Decision tables composable as governance components | Decision table is an SDC component in the model, discovered by vocabulary binding. |
| P5-04 | No match returns INDETERMINATE | If no rule matches, the decision is INDETERMINATE. |
| P5-05 | Decision table results include receipt | Every evaluation produces a hash-chained receipt documenting which rules were checked and which matched. |

### Test Strategy

- Single rule match, multiple rule match (first-hit vs collect policies).
- No match returns INDETERMINATE.
- Decision tables combined with workflow transitions.
- Decision table as standalone governance (no workflow).

### Deliverables

- `decision.py` - functional
- Default project starter decision table components in SDCStudio
- Test suite
- PyPI 4.0.0a5 published

### Timeline: 3-4 weeks

---

## 12. Phase 6: SHACL Runtime

**Goal**: Validate cross-entity constraints using W3C SHACL via pyshacl.

### Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| P6-01 | SHACL shapes validated via pyshacl | Given a SHACL shape graph and an instance data graph, validation returns conformant/non-conformant. |
| P6-02 | SHACL results integrated into GovernanceEngine | SHACL non-conformance contributes to DENY decision. |
| P6-03 | Cross-entity constraints | A SHACL shape that references multiple entities (e.g., patient record + healthcare provider) validates the relationship between them. |

### Test Strategy

- Simple shape validation (single entity).
- Cross-entity constraint (two entities, valid and invalid relationships).
- SHACL failure integrated with other passing governance dimensions.

### Deliverables

- `shacl_runtime.py` - functional
- Test suite
- PyPI 4.0.0a6 published

### Timeline: 2 weeks

---

## 13. Phase 7: MCP Server + Examples

**Goal**: Expose GovernanceEngine as an MCP server. Ship real, runnable agent examples against CordovaOS.

### Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| P7-01 | MCP stdio server starts with CLI command | `sdcgovernance serve --mcp` starts an MCP server on stdio. |
| P7-02 | get_allowed_transitions tool | Agent calls tool, receives list of valid transitions from current state. |
| P7-03 | evaluate_transition tool | Agent calls tool with target state and actor, receives PERMIT/DENY/INDETERMINATE + receipt. |
| P7-04 | record_provenance tool | Agent calls tool with activity details, receives PROV record + receipt. |
| P7-05 | validate_governance tool | Agent calls tool with schema + instance, receives full governance validation result. |
| P7-06 | get_governance_status tool | Agent calls tool with schema, receives which governance dimensions the model defines. |
| P7-07 | Session management | Receipt chain maintained across multiple calls within a session. |
| P7-08 | CordovaOS example: Beat 5 (The Response) | Runnable agent script that walks through the health officer containment trigger with real MCP calls, real governance components, real PERMIT/DENY decisions. |
| P7-09 | CordovaOS example: Beat 6 (The Investigation) | Runnable agent script that walks through law enforcement accessing health records across domain boundaries. |
| P7-10 | CordovaOS example: provenance recording | Runnable agent script that records PROV provenance at every governed transition during the Contagion narrative. |
| P7-11 | Examples are real implementations | No stubs, no mock APIs. Standards reviewers can clone CordovaOS, start the MCP server, run an example, and watch standards enforced end to end. |

### Test Strategy

- MCP server starts and responds to tool discovery.
- Each tool called individually with valid and invalid inputs.
- Multi-call session: get_allowed -> evaluate -> record_provenance, verify receipt chain continuity.
- CordovaOS examples run end to end against governance-extended domain models.

### Deliverables

- `mcp_server.py` - functional
- CLI entry point registered in pyproject.toml
- `examples/` directory with 3+ runnable CordovaOS agent scripts
- Test suite
- PyPI 4.0.0 GA published

### Timeline: 2-3 weeks

---

## 14. CordovaOS Integration

**Prerequisite**: Phase 1-2 complete (alpha).
**Full integration**: After Phase 7 (GA).

| Work Item | Description |
|---|---|
| Governance model components | Add Workflow, Attestation, Party/Role, Provenance components to CordovaOS domain models in SDCStudio |
| Contagion narrative extension | Extend Beats 5-7 with governed transitions |
| Governance agent examples | Real agents querying sdcgovernance MCP tools during crisis workflow |
| Governance SPARQL queries | Queries that traverse governance graph alongside domain graph |
| Standards reviewer walkthrough | Documentation for W3C/OASIS reviewers to evaluate standards compliance on running system |

## 15. Out of Scope

- Django integration or middleware. sdcgovernance is a library and MCP server.
- Operational response logic (what happens after DENY). That is the customer's business logic.
- Industry-specific retention agents. sdcgovernance validates retention policy; industry agents that advise on configuration are a separate concern.
- Web3 settlement layer integration. That is Q4 2026 - Q1 2027 work that builds on sdcgovernance but is a separate project.
- GUI or dashboard. sdcgovernance is CLI + API + MCP.

## 16. Success Criteria

| Milestone | Criteria |
|---|---|
| Alpha (Phase 1-2) | model_inspector discovers governance by vocabulary binding. Workflow validation returns correct XACML decisions. Receipt chain is tamper-evident. PyPI alpha published. |
| Beta (Phase 3-6) | All governance dimensions validate. Provenance retention policy enforced. DMN decision tables evaluate. SHACL cross-entity constraints work. |
| GA (Phase 7) | MCP server exposes all tools. CordovaOS examples run end to end. Standards reviewers can evaluate compliance on running system. PyPI 4.0.0 published. |
| Market validation | W3C/OASIS standards authors review and file issues. At least one external system consumes governance via MCP. CordovaOS governance demo shown to prospects. |

## 17. Risks

| Risk | Mitigation |
|---|---|
| Vocabulary binding discovery is ambiguous in complex models | Phase 1 test suite covers edge cases. model_inspector fails loudly on ambiguous bindings rather than guessing. |
| XdOrdinal cluster tree modeling proves insufficient for complex workflows | The modeling pattern supports branching via sub-clusters and component reuse. If edge cases emerge, custom Workflow components can define explicit transition tables while using the same vocabulary bindings. |
| MCP SDK changes before Phase 7 | MCP server is Phase 7 (last). SDK changes are absorbed before implementation begins. |
| CordovaOS governance models require SDCStudio changes | SDCStudio already supports all component types needed. Governance components are standard SDC components with specific vocabulary bindings. |
| Practitioner program launch (May 1) competes for time | Phase 1 is independent of practitioner work. Implementation begins after launch stabilizes. |
