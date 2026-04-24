# W3C Standards-Based Execution Governance

## High-Level Planning Document

**Date**: 2026-04-23
**Status**: Planning

---

## Strategic Decision

Build governance enforcement as an instance validation library. Governance is validated by comparing the content of XML data instances against the governance components defined in the SDC data model. No framework dependency. No middleware. Just a function call.

**Core philosophy**: SDC's foundation is XML Schema 1.1 data models and XML instances. Governance components (workflow, attestation, party/role, provenance, audit) are optional parts of the data model. When they are defined, every instance that includes governed data must carry the governance content - the workflow state, the attestation, the provenance record - as part of the instance itself. Governance enforcement is instance validation: compare what the instance says against what the model defines.

**Why instance validation, not middleware:**
- Middleware is platform-layer governance - enforcement depends on Django, on the ORM, on the web framework lifecycle. Data extracted from Django loses enforcement.
- Instance validation is payload-bound governance - the governance IS the data. Any system that validates the instance enforces the governance. Platform-agnostic.
- This is the substrate argument applied to enforcement: governance travels with the data because the governance is in the data.

**Standing on shoulders, not inventing:**

sdcgovernance does not invent governance semantics. It makes existing standards validatable at the instance level and consumable by agents via MCP.

| Governance Need | Standard | How sdcgovernance Uses It |
|---|---|---|
| Provenance / Audit | W3C PROV-O / PROV-DM | Provenance records in instances follow PROV vocabulary (Audit and Provenance are the same governance dimension in SDC) |
| Provenance retention | W3C Data Privacy Vocabulary (DPV) | Retention policies (duration, conditions) bound using DPV terms - same vocabulary already used for SDC access control (acs) |
| Workflow sequencing | SDC native structure + W3C SCXML vocabulary | Workflow states as XdOrdinal components in sub-cluster paths, labeled using SCXML semantics (states, transitions, conditions) |
| Attestation authority | W3C VC Data Model 2.0 | Attestation content follows VC issuer/holder/verifier pattern |
| Constraint validation | W3C SHACL | Cross-entity constraints delegated to pyshacl |
| Activity/event types | W3C Activity Streams 2.0 | Provenance activity types (Create, Update, Accept, Reject, etc.) from AS2 vocabulary |
| Decision outcomes | OASIS XACML | PERMIT/DENY/INDETERMINATE - standard XACML decision semantics |
| Conditional decision logic | OMG DMN (Decision Model and Notation) | Decision tables for complex governance rules beyond simple state matching |

**What is genuinely novel (no existing standard covers):**
- The "instance carries governance, validator checks it against the model" pattern - SDC's unique contribution
- Hash-chained tamper-evident decision receipts linking governance decisions into a verifiable chain
- MCP server exposing governance as tools for any agent framework
- DMN decision tables embedded in SDC data models as composable governance components

**Why this standards alignment matters:**
- Interoperable with any system that speaks these standards
- No proprietary governance vocabulary to learn or maintain
- Regulatory alignment: EU AI Act Article 12 and 15 map directly to PROV records and SHACL validation
- The W3C and OASIS communities have been waiting for a runtime that binds their vocabularies to actual data payloads
- Web3 settlement layer (Q4 2026 - Q1 2027) requires standards-based governance that can be verified by smart contracts and ZK proofs - proprietary governance vocabularies cannot cross that boundary

---

## Architecture: sdcgovernance as Governance Advisory Engine

### Design Principle

`sdcgovernance` is a governance advisory library. It takes an SDC data model (XSD) and an XML instance, examines whether the model defines governance components, and if so, validates the governance content in the instance against those definitions. It returns governance decisions using OASIS XACML semantics: PERMIT, DENY, or INDETERMINATE.

No Django. No middleware. No signals. No framework dependency. A function call.

### Two Independent Libraries

sdcvalidator and sdcgovernance are separate, independent libraries. They are not chained. There is no hook.

```
sdcvalidator (structural validation)
    Does the instance conform to the XSD schema?
    Are the data types correct? Are required elements present?
    Are constraints satisfied?
    Single-pass. Instance in, pass/fail out.

sdcgovernance (governance advisory)
    Does the data model define governance components?
    If yes:
    - Does the workflow transition exist in the state machine?
    - Is the attestation present and valid for the claimed authority?
    - Is the provenance chain intact?
    - Are party/role constraints satisfied?
    - Does the audit record meet the model's requirements?
    If the model does not define governance components: PERMIT (no governance to enforce)
    Conversational. Agents query multiple times during a workflow.
```

Both libraries read the schema from the instance. The agent decides when to call which one, in what order, and how many times. An agent might validate structurally, check governance, perform operational logic, modify the instance, validate again, check governance again, and record provenance - all as separate calls at different points in a workflow. The two libraries serve different purposes at different times.

**Why no hook**: Governance is not a post-validation step. It is an ongoing conversation between agents and the governance engine that happens at multiple points during a workflow. Chaining sdcgovernance to sdcvalidator would force a single-pass sequence that does not reflect how agents actually interact with governed data.

### Library Structure

```
sdcgovernance/
├── src/sdcgovernance/
│   ├── __init__.py          # Public API: validate_governance(), GovernanceEngine
│   ├── engine.py            # GovernanceEngine - the decision engine agents query
│   ├── model_inspector.py   # Inspect SDC model for governance components
│   ├── workflow.py          # Validate workflow transitions in instance
│   ├── attestation.py       # Validate attestation content in instance
│   ├── party_role.py        # Validate party/role constraints in instance
│   ├── provenance.py        # Validate provenance/audit records in instance + PROV generation (Audit and Provenance are one dimension)
│   ├── receipts.py          # Decision receipt chain (hash-chained)
│   ├── shacl_runtime.py     # SHACL validation for cross-entity constraints
│   └── mcp_server.py        # MCP server exposing governance tools to any agent
├── examples/                # Reference implementations showing how to wire MCP tools into agent workflows
├── tests/
├── pyproject.toml
├── README.md
└── LICENSE                  # Apache 2.0
```

Pure Python library. No framework dependency. Dual interface: Python API for direct integration, MCP server for agent consumption.

### Reference Implementations (examples/)

Reference agent implementations live in the sdcgovernance repo as examples, not as a separate package or repo. SDC_Agents (SDC_AgentsSMB) remains focused on modeling - introspecting data sources and communicating with SDCStudio. Governance agents are execution, not modeling, and belong with the library they consume.

The examples directory will include real, runnable agent implementations - not stubs or mock APIs. These agents walk through CordovaOS Contagion narrative beats, making real MCP calls against real governance components in real domain models. A standards reviewer should be able to clone CordovaOS, start the sdcgovernance MCP server, run an example agent, and watch the standards enforced end to end.

Examples will cover:
- Querying allowed transitions at each Contagion beat
- Evaluating governed transitions (health officer triggering containment, law enforcement accessing health records)
- Handling PERMIT/DENY/INDETERMINATE responses with operational routing
- Recording provenance as W3C PROV records at every decision point
- Validating attestation when authorized officials assert data across domain boundaries

These are reference implementations, not a framework. Practitioners and customers build their own agents using whatever framework they prefer - the examples show how the conversation with sdcgovernance works against a realistic multi-domain scenario.

A separate agent suite may be warranted later once real usage patterns emerge. Until then, embedded examples tied to CordovaOS avoid committing to an abstraction prematurely while giving reviewers and practitioners something concrete.

### Two Interfaces, One Engine

sdcgovernance serves two audiences through the same underlying engine:

**1. Python API** - for direct integration (generated apps, custom code, any Python application):

```python
from sdcgovernance import validate_governance

result = validate_governance(schema_path, instance_path)
# result.decision: PERMIT | DENY | INDETERMINATE
# result.errors: list of governance validation errors
# result.receipt: tamper-evident decision receipt
```

**2. MCP Server** - for any agent framework (Claude Code, Cursor, LangGraph, CrewAI, Google ADK, custom agents):

```bash
sdcgovernance serve --mcp
```

The MCP server exposes governance as tools that agents call. The agent runs the loop. sdcgovernance is the governance advisor.

### MCP Tools

```
Tool: get_allowed_transitions
  Input: instance, current_state
  Output: list of allowed transitions with entry conditions for each
  Purpose: Agent asks "what can I do next?"

Tool: evaluate_transition
  Input: instance, target_state, actor
  Output: PERMIT/DENY/INDETERMINATE + receipt + reasoning
  Purpose: Agent asks "can I do this specific thing?"

Tool: record_provenance
  Input: instance, activity, agent, result
  Output: PROV record + hash-chained receipt
  Purpose: Agent reports what happened for the audit trail

Tool: validate_governance
  Input: schema, instance
  Output: full governance validation result
  Purpose: Complete governance validation (same as Python API)

Tool: get_governance_status
  Input: schema
  Output: which governance components the model defines
  Purpose: Agent asks "what governance exists for this model?"
```

### Agent Integration Pattern

sdcgovernance is the advisor. The agent is the orchestrator. The agent holds the loop.

Governance is conversational, not single-pass. A typical workflow involves multiple calls to both sdcvalidator and sdcgovernance at different points:

```
Agent receives a task involving a data instance
  → calls sdcvalidator: "is this instance structurally valid?"
  → calls get_governance_status: "what governance does this model define?"
  → calls get_allowed_transitions: "what can I do next?"
  → selects a transition based on the task
  → calls evaluate_transition: "can I do this specific thing?"
  → if PERMIT: agent performs the action, modifies the instance
    → calls sdcvalidator again: "is the modified instance still valid?"
    → calls record_provenance: "here's what I did"
  → if DENY: agent reports the refusal (what happens next is operational - page a supervisor, freeze the transaction, reroute, etc.)
  → if INDETERMINATE: agent requests human review
```

The agent decides the sequence. sdcgovernance and sdcvalidator are called independently, in whatever order the workflow requires. The operational response to DENY or INDETERMINATE is entirely the customer's business logic - sdcgovernance has no opinion about what happens after it issues a decision.

This pattern works identically regardless of the agent framework. Any agent that speaks MCP gets governed behavior without framework-specific integration code. SDC_Agents provides reference implementations using the Default project governance models, but every customer implementation will wire the responses into their own operational logic differently.

### Relationship to SDC Agents

SDC Agents (SDC_AgentsSMB) is the modeling pipeline - introspecting data sources and communicating with SDCStudio. It remains focused on that bounded purpose. Governance agents are execution, not modeling.

Reference implementations for governance agent workflows live in the sdcgovernance `examples/` directory, not in SDC_Agents. The two MCP servers are independent:

```bash
# SDC Agents MCP servers (modeling)
sdc-agents serve --mcp introspect
sdc-agents serve --mcp catalog

# sdcgovernance MCP server (execution governance)
sdcgovernance serve --mcp
```

Customer agents connect to whichever MCP servers their workflow requires. No lock-in to any framework.

### Why MCP

MCP (Model Context Protocol) is becoming the standard interface between AI agents and external tools. By exposing sdcgovernance as an MCP server:

- Any agent framework can consume governance without custom integration code
- The governance tools are discoverable by the agent at runtime
- New governance capabilities (workflow, attestation, provenance) are available to agents immediately on upgrade
- Customer agents don't need to import a Python library - they connect to the MCP server
- The same governance engine serves both the Python API and agent workflows (MCP)

### How It Works

**Step 1: Model Inspection** (`model_inspector.py`)

Read the DMType root and check which optional governance slots are populated. Governance components are at **known positions** in the DM root (see [RM_Reference.md](RM_Reference.md)) - not scattered arbitrarily in the model:

- `DM.workflow` (ClusterType, 0..1) → Workflow dimension. Extract cluster tree with XdOrdinal paths.
- `DM.current-state` (xs:string, 0..1) → Current workflow position.
- `DM.Audit[]` (AuditType, 0..*) → Provenance/Audit dimension. Extract provenance requirements.
- `DM.attestation` (AttestationType, 0..1) → Attestation dimension. Extract authority requirements.
- `DM.subject` / `DM.provider` / `DM.Participation[]` → Party/Role dimension. Extract role constraints from ParticipationType.function.
- `DM.acs` (XdLinkType, 0..1) → Access control and DPV retention policy bindings.

**Vocabulary bindings** on the components within these slots confirm which standards they conform to (SCXML labels on workflow XdOrdinals, PROV-O bindings on Audit elements, VC bindings on attestation, DPV bindings on acs). The location is fixed by the RM; the vocabulary binding confirms the semantics. This means custom governance components work identically to Default project components as long as they occupy the correct DM slots and carry the right vocabulary bindings.

If no governance slots are populated in the DM root, return PERMIT. The model author chose not to include governance. That's a valid choice.

**Step 2: Instance Content Validation**

For each governance component defined in the model, examine the corresponding content in the XML instance:

**Workflow**: The Workflow cluster defines all valid paths as sub-clusters. Each sub-cluster contains XdOrdinal components that define the sequenced states within that path. A component that can appear in multiple paths (e.g., "Review") is the same component (same CUID2) reused across sub-clusters. The instance carries the current state as an XdOrdinal value. sdcgovernance validates that the proposed transition exists in at least one valid path by inspecting the cluster tree and checking ordinal adjacency. If the instance proposes a transition that does not exist in any sub-cluster's ordinal sequence, DENY.

**Attestation**: Attestation is independent from workflow. An attestation is an identified entity (person or agent) asserting that the data instance is true or valid. If the model defines an Attestation component, the instance must contain a valid attestation element with the correct party reference and timestamp. If missing or invalid, DENY. Attestation is NOT automatically required for workflow transitions - they are independent governance dimensions that compose optionally.

**Party/Role**: The model says only parties with role "approver" can perform this action. The instance identifies the acting party. Validate that the party's role matches the requirement.

**Provenance/Audit** (one dimension): The model defines provenance requirements via PROV-O vocabulary bindings and retention policy via DPV vocabulary bindings. The retention policy determines how much provenance the instance carries:

- **Most recent only + hash**: Instance carries the current provenance record (Agent, Activity, Entity, temporal bounds) plus a SHA-256 hash linking to the previous receipt in the chain. Full history lives in the receipt chain. Suitable for long-lived records with many changes (e.g., patient records).
- **Last N records**: Instance carries the N most recent provenance records plus a hash linking to the chain. Configurable per model.
- **Full chain**: Instance carries the complete provenance history. Suitable for short-lived records with few steps (e.g., financial transactions).

The model author chooses the retention policy in SDCStudio by configuring the DPV-bound retention component. sdcgovernance validates that the instance carries provenance content matching the model's requirements - correct PROV elements present, retention policy honored, hash chain intact.

Industry-specific agents can advise on retention policy during modeling: a healthcare agent knows HIPAA requires 6 years, a financial agent knows SOX requires 7 years, an EU compliance agent knows the AI Act requires lifetime retention. These agents advise on model configuration - sdcgovernance enforces whatever the model defines.

**Step 3: Decision + Receipt**

Based on the validation results, using OASIS XACML decision semantics:
- All governance checks pass → PERMIT + receipt
- Any governance check fails → DENY + receipt with error details
- Governance checks partially pass (configurable threshold) → INDETERMINATE + receipt

The receipt is a PROV-formatted record of the validation decision, hash-chained to the previous receipt for tamper evidence.

What happens after the decision is the agent's responsibility. sdcgovernance issues the decision and the receipt. The operational response - routing, escalation, notification, halting - is customer business logic that varies per implementation.

---

## Implementation Phases

### Phase 1: Model Inspector + Foundation
- model_inspector.py: read an SDC model and detect governance components
- Governance result data structure
- Receipt foundation with SHA-256 hash chain
- Basic test suite with models that include/exclude governance components
- PyPI package published
- Timeline: 2-3 weeks

### Phase 2: GovernanceEngine + Workflow Validation
- engine.py: GovernanceEngine class wrapping model_inspector + validation modules
- workflow.py: validate workflow transitions in instance against model
- Workflow modeled as cluster trees: Workflow cluster contains sub-clusters (valid paths), each containing XdOrdinal components (sequenced states)
- Components reusable across sub-clusters (same CUID2 in multiple paths = branching)
- Validation is ordinal adjacency checking within the cluster tree - no separate transition table, no graph traversal
- Decision outcomes using OASIS XACML semantics (PERMIT/DENY/INDETERMINATE)
- GovernanceEngine advisory API: get_allowed_transitions, evaluate_transition
- Timeline: 3-4 weeks

### Phase 3: Attestation + Party/Role Validation (VC-based)
- attestation.py: validate attestation content in instance
- party_role.py: validate party/role constraints
- Authority chain verification
- W3C VC Data Model 2.0 pattern for structured claims
- Timeline: 2-3 weeks

### Phase 4: Provenance Validation (PROV + Activity Streams + DPV)
- provenance.py: validate provenance/audit records in instance + generate PROV output (Audit and Provenance merged - same governance dimension)
- Retention policy validation: model defines how much provenance the instance carries (most recent + hash, last N, or full chain) via DPV vocabulary bindings
- record_provenance engine method for agent audit trails
- Activity types from W3C Activity Streams 2.0 vocabulary
- W3C PROV-O compliant record generation
- DPV vocabulary for retention policy (same vocabulary already used for SDC access control)
- RDF/Turtle export
- Timeline: 2-3 weeks

### Phase 5: DMN Decision Tables
- decision.py: evaluate conditional governance rules using OMG DMN semantics
- Decision tables for governance rules that go beyond simple state matching
- Example: "allow this transition only if risk score < threshold AND attestation level >= required"
- SDCStudio Default project includes starter decision table components
- Critical foundation for Web3 settlement layer (Q4 2026 - Q1 2027) where smart contracts need deterministic, standards-based decision logic to verify
- Timeline: 3-4 weeks

### Phase 6: SHACL Runtime
- shacl_runtime.py: cross-entity constraint validation via SHACL
- Integration with GovernanceEngine for constraints that span multiple entities
- Timeline: 2 weeks

### Phase 7: MCP Server
- mcp_server.py: MCP stdio server exposing GovernanceEngine tools
- CLI entry point: sdcgovernance serve --mcp
- All MCP tools: get_allowed_transitions, evaluate_transition, evaluate_decision, record_provenance, validate_governance, get_governance_status (all decisions use XACML PERMIT/DENY/INDETERMINATE)
- Session management for receipt chain continuity
- Reference agent examples in sdcgovernance examples/ directory
- Timeline: 2-3 weeks

### Integration Target: CordovaOS

CordovaOS (github.com/Axius-SDC/CordovaOS) is the integration test target for sdcgovernance. It models a fictional nation's entire government - 10 domains, 25,000 synthetic citizens, zero integration code - and includes a 7-beat Contagion crisis narrative that traverses all domains.

The Contagion narrative is a natural governance scenario:
- **Beat 5 (The Response)**: The Provincial Health Officer triggers cross-domain containment. With sdcgovernance, this becomes a governed transition - PERMIT/DENY/INDETERMINATE based on the officer's party/role, with attestation, provenance, and a hash-chained receipt.
- **Beat 6 (The Investigation)**: Law enforcement opens an incident tied to health records. Governance validates that the party has the right role to access health data across domain boundaries.
- **Cross-domain governance**: The governance is in the instance, not in middleware between the domains. When data crosses from healthcare to law enforcement, the governance travels with it.

CordovaOS governance extension work begins after sdcgovernance reaches alpha (Phase 1-2 complete). The work includes:
- Adding governance components (Workflow, Attestation, Party/Role, Provenance) to the CordovaOS domain models in SDCStudio
- Extending the Contagion narrative beats with governed transitions
- Adding governance agent examples that query sdcgovernance MCP tools during the crisis workflow
- SPARQL queries that traverse the governance graph alongside the domain graph

This gives the W3C/OASIS standards authors a running system where their standards are enforced on realistic data in a realistic scenario - not a toy example, but a 10-domain government with a crisis narrative.

---

## Governance Configuration: The Model IS the Configuration

There is no separate configuration layer. The SDC data model defines what governance exists. The instance carries the governance content. sdcgovernance validates one against the other.

### Default Project Models (the starting point)

The SDCStudio Default project will contain pre-built, reusable governance components:
- Workflow cluster (sub-clusters define valid paths, XdOrdinal components define sequenced states within each path, SCXML vocabulary labels)
- Attestation component (W3C VC-aligned authority assertion)
- Party/Participation components (role definitions)
- Provenance/Audit component (W3C PROV-O vocabulary bindings, with DPV retention policy)

All governance components carry vocabulary bindings to their respective standards. sdcgovernance discovers governance components by vocabulary binding, not by CUID2. This means custom governance components work identically to Default project components as long as they bind to the right standard vocabularies.

These are standard SDC components in the public catalog. Users compose them into their data models the same way they compose any other component. The sdcgovernance library reads whatever governance components the user included - it does not hardcode governance rules.

### How users get governance

1. **Use the defaults**: Include the Default project's governance components in your data model as-is. Most users start here.
2. **Customize**: Copy a public governance component into your private project and modify it. SDCStudio supports this natively - copy, place in your project, modify to your needs. This is how users define governance rules outside the W3C standard defaults without needing an override mechanism.
3. **Build from scratch**: Model your own governance components for domain-specific requirements. As long as the components carry the right vocabulary bindings (PROV-O, SCXML, VC, DPV), sdcgovernance discovers and validates them - regardless of which project they came from or who modeled them.

No override files. No YAML configuration. No separate governance config. The model is the single source of truth. Customization happens through the same modeling process practitioners already know.

### Independence of governance dimensions

Each governance dimension is independent. Including a Workflow component does not require including an Attestation component. Including Attestation does not require including Party/Role. Each dimension validates only if the model defines it. If the model defines Workflow but not Attestation, sdcgovernance validates workflow transitions and ignores attestation. This is by design.

The original SDC concept: Attestation is an identified entity asserting that the data instance is true/valid. Workflow is about valid states and routing. They CAN compose together but are not coupled.

### Workflow Modeling (resolved)

Workflow states are modeled as XdOrdinal components, not XdString enumerations. XdOrdinal carries both a value and an ordinal position, giving defined sequencing structurally within the data type.

A Workflow cluster contains sub-clusters, each representing a valid path through the workflow. Each sub-cluster contains XdOrdinal components defining the sequenced states in that path. Branching is modeled by having multiple sub-clusters in the Workflow cluster. Components that appear in multiple paths (e.g., a "Review" state shared by two branches) are the same component (same CUID2) reused across sub-clusters.

The state machine IS the cluster tree. No separate transition table. No graph data structure. sdcgovernance reads the cluster tree, inspects ordinal positions, and validates that a proposed transition exists in at least one valid path via ordinal adjacency.

The labels on XdOrdinal components and clusters use W3C SCXML vocabulary (states, transitions, conditions). The structure is native SDC. The vocabulary is SCXML. This keeps the workflow semantics interoperable with any system that speaks SCXML while the modeling structure remains what practitioners already know.

### Default Project Governance Models (resolved)

Governance components are created in SDCStudio and remain part of the Default project in the SDCStudio catalog. They do not ship with the sdcgovernance package. sdcgovernance is a validation library - it reads whatever governance components are in the model. The models themselves live where all SDC models live: in SDCStudio.

### Provenance/Audit Modeling (resolved)

Audit and Provenance are the same governance dimension in SDC. Both answer the same question: what happened, who did it, when, to what entity. This maps directly to W3C PROV-DM vocabulary (Entity, Activity, Agent, temporal bounds).

**Important implementation note**: In the SDC Reference Model, the underlying component is `sdc4:AuditType` (see [AuditType documentation](https://semanticdatacharter.com/docs/sdc4/sdc4_xsd_Complex_Type_sdc4_AuditType.html)). AuditType provides who/where/when tracking of instances as they move from system to system, with these elements:

- `system-id` (XdStringType, required) - identifier of the system that handled the item → maps to prov:Entity context
- `system-user` (PartyType, optional) - user/agent who handled the item → maps to prov:Agent
- `location` (ClusterType, optional) - location of the handling site → provenance metadata
- `timestamp` (xs:dateTime, required) - when the item was handled → maps to prov:Activity temporal bounds

In external-facing documentation and standards discussions, we use "Provenance" because that is the W3C vocabulary (PROV-O/PROV-DM) and what standards reviewers expect. In implementation, the model component is AuditType. sdcgovernance's model_inspector discovers AuditType components by their vocabulary bindings to PROV-O terms, bridging the SDC RM naming to the W3C standard.

The model defines provenance requirements through two vocabulary bindings:
- **W3C PROV-O** bindings on AuditType components define which provenance elements are required (Agent, Activity, Entity, temporal bounds) and which W3C Activity Streams 2.0 activity types are valid
- **W3C DPV** bindings define the retention policy - how much provenance the instance carries

DPV is already used in the SDC ecosystem for access control (acs on the data model). Using it for provenance retention means practitioners apply one vocabulary they already know to two governance concerns.

The retention policy is modeled as a constraint on the Provenance component:
- Most recent record + hash (long-lived records, e.g., patient records)
- Last N records (configurable)
- Full chain (short-lived records, e.g., financial transactions)

sdcgovernance validates whatever the model defines. Industry-specific agents advise on model configuration during the modeling phase - a healthcare agent knows HIPAA requires 6 years, a financial agent knows SOX requires 7 years, an EU compliance agent knows the AI Act requires lifetime retention. These agents bring domain-specific retention knowledge via additional vocabularies. sdcgovernance remains generic.

### Open Design Questions

No open design questions remain. All governance dimensions have resolved modeling approaches:
- **Workflow**: XdOrdinal components in cluster trees, SCXML vocabulary labels
- **Attestation**: W3C VC Data Model 2.0 pattern, independent from workflow
- **Party/Role**: Role constraints on governed actions
- **Provenance/Audit**: W3C PROV-O + DPV retention policy, three retention levels
- **Discovery**: Vocabulary binding, not CUID2 identity
- **Default models**: SDCStudio Default project, not shipped with sdcgovernance
- **Independence**: sdcvalidator and sdcgovernance are separate libraries, no hook

---

## Dependencies and Integration

### Library dependencies
- rdflib (for PROV record generation and RDF export)
- pyshacl (for SHACL constraint validation in Phase 6)
- xmlschema or lxml (for XSD model inspection - may reuse sdcvalidator's dependency)

### Relationship to sdcvalidator

sdcvalidator and sdcgovernance are independent libraries. There is no hook, no chaining, no automatic invocation of one from the other.

Both libraries read the schema identifier from the XML instance to locate the data model. Both operate on instances. But they serve different purposes:
- sdcvalidator: single-pass structural validation (types, constraints, required elements)
- sdcgovernance: conversational governance advisory (workflow state, attestation, provenance, party/role)

Agents call each library independently, at different points in a workflow, in whatever order the operational logic requires. A single workflow may involve multiple calls to both libraries as the instance is validated, modified, governed, and re-validated.

## What This Means for Practitioners

- Governance enforcement is instance validation, explained in one sentence: "If the model defines governance, the instance must carry it"
- Practitioners don't configure middleware or wire signals - they model governance components in SDCStudio, and the governance engine validates them on demand
- `pip install sdcgovernance` gives any system governance advisory capabilities via Python API or MCP server
- Module 7 compliance toolset becomes: "install sdcgovernance, connect agents via MCP"
- Every customer implementation wires PERMIT/DENY/INDETERMINATE into their own operational logic - sdcgovernance advises, the customer's system acts

## What This Means for the Market

- SDC is the only framework where governance enforcement is a property of the data instance, not the platform
- "Governance travels with the data" is literally true - the governance IS in the instance content
- Any system that validates SDC instances enforces governance - no vendor dependency, no middleware, no platform lock-in
- EU AI Act Article 12 compliance is a validation result, not a dashboard metric
- The W3C community gets a runtime where PROV, SHACL, and VC patterns are enforced at the instance level
- **Only deterministic validation and governance can move at the speed of the agentic internet.** Probabilistic governance - LLMs interpreting policies, inferring compliance, guessing at provenance - cannot scale to machine-speed autonomous data exchange. Every inference adds latency, uncertainty, and audit liability. SDC validation is structural comparison: instance against model, ordinal against cluster tree, content against constraint. It is deterministic, constant-time relative to model complexity, and produces a verifiable receipt on every decision. When agents exchange data across trust boundaries at machine speed, the governance must be as fast and as certain as the data exchange itself. Probabilistic governance becomes the bottleneck. Deterministic governance becomes the infrastructure.

## Prior Art and Inspiration

Multiple approaches to execution governance have been evaluated, including deterministic runtime gating, dual-gate execution boundaries, decision-theoretic scoring frameworks, and various proprietary execution engines. All of these operate at the platform or middleware layer - enforcement depends on the platform. None validate governance as instance content against a declarative model. This library fills that gap: governance enforcement that is a property of the data, not the infrastructure.
