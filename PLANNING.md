# W3C Standards-Based Execution Governance

## High-Level Planning Document

**Date**: 2026-04-22
**Status**: Planning

---

## Strategic Decision

Build governance enforcement as an instance validation library. Governance is validated by comparing the content of XML data instances against the governance components defined in the SDC data model. No framework dependency. No middleware. Just a function call.

**Core philosophy**: SDC's foundation is XML Schema 1.1 data models and XML instances. Governance components (workflow, attestation, party/role, provenance, audit) are optional parts of the data model. When they are defined, every instance that includes governed data must carry the governance content - the workflow state, the attestation, the provenance record - as part of the instance itself. Governance enforcement is instance validation: compare what the instance says against what the model defines.

**Why instance validation, not middleware:**
- Middleware is platform-layer governance - enforcement depends on Django, on the ORM, on the web framework lifecycle. Data extracted from Django loses enforcement.
- Instance validation is payload-bound governance - the governance IS the data. Any system that validates the instance enforces the governance. Platform-agnostic.
- This is the substrate argument applied to enforcement: governance travels with the data because the governance is in the data.

**Why W3C standards:**
- Interoperable with any system that speaks PROV, SHACL, or VC
- The Linked Data community has mature vocabularies waiting for a runtime implementation
- No proprietary execution vocabulary to learn or maintain
- Regulatory alignment: EU AI Act Article 12 and 15 map directly to PROV records and SHACL validation

---

## Architecture: sdcgovernance as Instance Validator

### Design Principle

`sdcgovernance` is a validation library. It takes an SDC data model (XSD) and an XML instance, examines whether the model defines governance components, and if so, validates the governance content in the instance against those definitions. It returns a validation result - pass/fail with details - just like sdcvalidator does for structural validation.

No Django. No middleware. No signals. No framework dependency. A function call.

### The Two-Layer Validation Model

```
Layer 1: sdcvalidator (structural)
    Does the instance conform to the XSD schema?
    Are the data types correct? Are required elements present?
    Are constraints satisfied?

Layer 2: sdcgovernance (governance)
    Does the data model define governance components?
    If yes:
    - Does the workflow transition exist in the state machine?
    - Is the attestation present and valid for the claimed authority?
    - Is the provenance chain intact?
    - Are party/role constraints satisfied?
    - Does the audit record meet the model's requirements?
    If the model does not define governance components: SKIP (pass)
```

### The sdcvalidator Hook

If `sdcgovernance` is installed, sdcvalidator calls it automatically after structural validation passes. The hook is optional - if sdcgovernance is not installed, sdcvalidator works exactly as it does today.

```python
# In sdcvalidator, after structural validation:
try:
    from sdcgovernance import validate_governance
    governance_result = validate_governance(schema, instance)
except ImportError:
    governance_result = None  # sdcgovernance not installed, skip
```

This means any system already using sdcvalidator gets governance enforcement for free by installing sdcgovernance. No code changes required.

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
│   ├── provenance.py        # Validate provenance records in instance + PROV generation
│   ├── audit.py             # Validate audit content in instance
│   ├── receipts.py          # Decision receipt chain (hash-chained)
│   ├── shacl_runtime.py     # SHACL validation for cross-entity constraints
│   └── mcp_server.py        # MCP server exposing governance tools to any agent
├── tests/
├── pyproject.toml
├── README.md
└── LICENSE                  # Apache 2.0
```

Pure Python library. No framework dependency. Dual interface: Python API for direct integration, MCP server for agent consumption.

### Two Interfaces, One Engine

sdcgovernance serves two audiences through the same underlying engine:

**1. Python API** - for direct integration (sdcvalidator hook, generated apps, custom code):

```python
from sdcgovernance import validate_governance

result = validate_governance(schema_path, instance_path)
# result.decision: EXECUTE | REFUSE | ESCALATE | SKIP
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
  Output: EXECUTE/REFUSE/ESCALATE + receipt + reasoning
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

```
Agent receives a task
  → calls get_allowed_transitions: "what can I do?"
  → selects a transition based on the task
  → calls evaluate_transition: "can I do this?"
  → if EXECUTE: agent performs the action
  → calls record_provenance: "here's what I did"
  → if REFUSE: agent reports the refusal
  → if ESCALATE: agent requests human review
```

This pattern works identically regardless of the agent framework. Any agent that speaks MCP gets governed behavior without framework-specific integration code.

### Relationship to SDC Agents

SDC Agents (SDC_AgentsSMB) provides reference implementations of governance tool usage. The existing `sdc-agents serve --mcp introspect` pattern is extended with governance:

```bash
# Existing SDC Agents MCP servers
sdc-agents serve --mcp introspect
sdc-agents serve --mcp catalog

# sdcgovernance MCP server (independent, any agent can consume)
sdcgovernance serve --mcp
```

SDC Agents shows practitioners how to use governance tools in agentic workflows. Customer agents connect to the same MCP server and use the tools however they want. No lock-in to the SDC Agents framework.

### Why MCP

MCP (Model Context Protocol) is becoming the standard interface between AI agents and external tools. By exposing sdcgovernance as an MCP server:

- Any agent framework can consume governance without custom integration code
- The governance tools are discoverable by the agent at runtime
- New governance capabilities (workflow, attestation, provenance) are available to agents immediately on upgrade
- Customer agents don't need to import a Python library - they connect to the MCP server
- The same governance engine serves both the sdcvalidator hook (Python API) and agent workflows (MCP)

### How It Works

**Step 1: Model Inspection** (`model_inspector.py`)

Read the SDC data model (XSD) and determine which governance components are defined:
- Are there Workflow components? If yes, extract the state machine (states, transitions, entry conditions)
- Are there Attestation components? If yes, extract the authority requirements
- Are there Party/Participation components? If yes, extract role constraints
- Are there Audit components? If yes, extract audit requirements
- Are there provenance requirements?

If no governance components are defined in the model, return SKIP. The model author chose not to include governance. That's a valid choice.

**Step 2: Instance Content Validation**

For each governance component defined in the model, examine the corresponding content in the XML instance:

**Workflow**: The model defines all possible states and legitimate transitions (the state machine). The instance carries previous state, current state, and allowed next state(s). sdcgovernance validates that the instance's claimed transition exists in the model's state machine. If the instance says A→D but the model only defines A→B and A→C, REFUSE. Exact data element structure for workflow instances TBD.

**Attestation**: Attestation is independent from workflow. An attestation is an identified entity (person or agent) asserting that the data instance is true or valid. If the model defines an Attestation component, the instance must contain a valid attestation element with the correct party reference and timestamp. If missing or invalid, REFUSE. Attestation is NOT automatically required for workflow transitions - they are independent governance dimensions that compose optionally.

**Party/Role**: The model says only parties with role "approver" can perform this action. The instance identifies the acting party. Validate that the party's role matches the requirement.

**Provenance**: The model says every state change must carry a provenance record. The instance must contain PROV-formatted content documenting the action, the agent, the entity, and the temporal bounds.

**Audit**: The model says audit records must include specific fields. Validate their presence and format in the instance.

**Step 3: Decision + Receipt**

Based on the validation results:
- All governance checks pass → EXECUTE + receipt
- Any governance check fails → REFUSE + receipt with error details
- Governance checks partially pass (configurable threshold) → ESCALATE + receipt

The receipt is a PROV-formatted record of the validation decision, hash-chained to the previous receipt for tamper evidence.

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
- State machine extraction from XSD workflow components
- Transition validity checking with EXECUTE / REFUSE / ESCALATE decisions
- GovernanceEngine advisory API: get_allowed_transitions, evaluate_transition
- Timeline: 3-4 weeks

### Phase 3: Attestation + Party/Role Validation
- attestation.py: validate attestation content in instance
- party_role.py: validate party/role constraints
- Authority chain verification
- W3C VC Data Model 2.0 pattern for structured claims
- Timeline: 2-3 weeks

### Phase 4: Provenance + Audit Validation
- provenance.py: validate provenance records in instance + generate PROV output
- audit.py: validate audit content against model requirements
- record_provenance engine method for agent audit trails
- W3C PROV-O compliant record generation
- RDF/Turtle export
- Timeline: 2-3 weeks

### Phase 5: sdcvalidator Hook + SHACL
- sdcvalidator integration: optional hook that calls sdcgovernance after structural validation
- End-to-end validation pipeline: structural → governance in one call
- shacl_runtime.py: cross-entity constraint validation via SHACL
- Timeline: 2 weeks

### Phase 6: MCP Server
- mcp_server.py: MCP stdio server exposing GovernanceEngine tools
- CLI entry point: sdcgovernance serve --mcp
- All five MCP tools: get_allowed_transitions, evaluate_transition, record_provenance, validate_governance, get_governance_status
- Session management for receipt chain continuity
- Reference implementation in SDC Agents showing governance tool usage
- Timeline: 2-3 weeks

---

## Governance Configuration: The Model IS the Configuration

There is no separate configuration layer. The SDC data model defines what governance exists. The instance carries the governance content. sdcgovernance validates one against the other.

### Default Project Models (the starting point)

The SDCStudio Default project will contain pre-built, reusable governance components:
- Workflow component (W3C-aligned state machine)
- Attestation component (W3C VC-aligned authority assertion)
- Party/Participation components (role definitions)
- Audit component (record requirements)
- Provenance component (PROV-aligned tracking requirements)

These are standard SDC components in the public catalog. Users compose them into their data models the same way they compose any other component. The sdcgovernance library reads whatever governance components the user included - it does not hardcode governance rules.

### How users get governance

1. **Use the defaults**: Include the Default project's governance components in your data model as-is. Most users start here.
2. **Customize**: Copy a public governance component into your private project and modify it. SDCStudio supports this natively - copy, place in your project, modify to your needs. This is how users define governance rules outside the W3C standard defaults without needing an override mechanism.
3. **Build from scratch**: Model your own governance components for domain-specific requirements. sdcgovernance validates whatever governance components are in the model, regardless of whether they came from the Default project or were custom-built.

No override files. No YAML configuration. No separate governance config. The model is the single source of truth. Customization happens through the same modeling process practitioners already know.

### Independence of governance dimensions

Each governance dimension is independent. Including a Workflow component does not require including an Attestation component. Including Attestation does not require including Party/Role. Each dimension validates only if the model defines it. If the model defines Workflow but not Attestation, sdcgovernance validates workflow transitions and ignores attestation. This is by design.

The original SDC concept: Attestation is an identified entity asserting that the data instance is true/valid. Workflow is about valid states and routing. They CAN compose together but are not coupled.

### Open Design Questions

- Exact data elements for the Workflow component: previous state, current state, and allowed next state(s) are the minimum. The model defines all possible states and transitions. The instance carries the state history. Exact modeling structure TBD.
- How provenance requirements are expressed in the model vs what the instance must carry
- Whether the Default project governance models should ship as part of the sdcgovernance package or remain purely in the SDCStudio catalog
- How the extended sdcvalidator in SDCStudio/SDCStudioSov (with ExceptionalValues injection) integrates the hook differently from the open source sdcvalidator

---

## Dependencies and Integration

### Library dependencies
- rdflib (for PROV record generation and RDF export)
- pyshacl (for SHACL constraint validation in Phase 5)
- xmlschema or lxml (for XSD model inspection - may reuse sdcvalidator's dependency)
- No Django dependency. No web framework dependency. Pure Python.

### sdcvalidator hook (primary integration path)
The correct integration is a hook from sdcvalidator. sdcvalidator is already the accepted XSD validator and operates on the SDC instance data. When sdcgovernance is installed, sdcvalidator passes the instance and schema to `validate_governance()` after structural validation passes.

This hook must also be implemented in:
- **SDCStudio** (cloud) - uses an extended version of sdcvalidator that can inject ExceptionalValues
- **SDCStudioSov** (sovereign) - same extended version

The ExceptionalValues injection functionality does not exist in the open source sdcvalidator. The hook implementation may differ between the open source and extended versions, but the sdcgovernance API is the same in both cases - it receives an instance and a schema and returns a governance validation result.

## What This Means for Practitioners

- Governance enforcement is instance validation, explained in one sentence: "If the model defines governance, the instance must carry it"
- Practitioners don't configure middleware or wire signals - they model governance components in SDCStudio, and validation enforces them automatically
- The `pip install sdcgovernance` upgrade path adds governance to any system already using sdcvalidator
- Module 7 compliance toolset becomes: "install sdcgovernance alongside sdcvalidator"

## What This Means for the Market

- SDC is the only framework where governance enforcement is a property of the data instance, not the platform
- "Governance travels with the data" is literally true - the governance IS in the instance content
- Any system that validates SDC instances enforces governance - no vendor dependency, no middleware, no platform lock-in
- EU AI Act Article 12 compliance is a validation result, not a dashboard metric
- The W3C community gets a runtime where PROV, SHACL, and VC patterns are enforced at the instance level

## Prior Art and Inspiration

Multiple approaches to execution governance have been evaluated, including deterministic runtime gating, dual-gate execution boundaries, decision-theoretic scoring frameworks, and various proprietary execution engines. All of these operate at the platform or middleware layer - enforcement depends on the platform. None validate governance as instance content against a declarative model. This library fills that gap: governance enforcement that is a property of the data, not the infrastructure.
