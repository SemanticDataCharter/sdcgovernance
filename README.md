# sdcgovernance

W3C standards-based governance advisory engine for Semantic Data Charter instances.

A Python library that validates governance content in XML data instances against governance components defined in the SDC data model. If the model defines governance (workflow, attestation, party/role, provenance, audit), the instance must carry that content - and this library validates it.

Returns decisions using OASIS XACML semantics: PERMIT, DENY, or INDETERMINATE.

No framework dependency. No middleware. A function call.

## How It Works

SDC data models (XSD) can optionally include governance components: Workflow state machines, Attestation authority requirements, Party/Role constraints, Provenance requirements, and Audit definitions. These are part of the data model, not a separate governance layer.

When governance components are defined, every XML data instance must carry the corresponding governance content. This library validates that content against the model:

```python
from sdcgovernance import validate_governance

result = validate_governance("model.xsd", "instance.xml")

print(result.decision)      # PERMIT, DENY, or INDETERMINATE
print(result.has_governance) # True if model defines governance components
print(result.errors)         # list of governance validation errors
print(result.receipt)        # tamper-evident decision receipt
```

If the model does not define governance components, the result is `PERMIT` - no governance to enforce.

## Two Independent Libraries

sdcvalidator and sdcgovernance are separate, independent libraries. There is no hook, no chaining, no automatic invocation of one from the other.

```
sdcvalidator (structural validation)
    Does the instance conform to the XSD schema?
    Single-pass. Instance in, pass/fail out.

sdcgovernance (governance advisory)
    Does the model define governance components?
    If yes: does the instance carry valid governance content?
    Conversational. Agents query multiple times during a workflow.
```

Both libraries read the schema from the instance. Agents call each one independently, at different points in a workflow, in whatever order the operational logic requires. A single workflow may involve multiple calls to both libraries.

## What Gets Validated

| Component | What the model defines | What the instance must carry |
|---|---|---|
| **Workflow** | Cluster tree of valid paths (sub-clusters with XdOrdinal states) | Current XdOrdinal state, proposed transition validated against ordinal adjacency in valid paths |
| **Attestation** | Authority requirements per action | Attestation with correct role, party reference, timestamp |
| **Party/Role** | Role constraints for governed actions | Acting party identification with required role |
| **Provenance/Audit** | Provenance requirements (PROV-O) + retention policy (DPV) | PROV-formatted record(s) per retention policy: most recent + hash, last N, or full chain |

Governance components are discovered by **vocabulary binding**, not by CUID2 identity. Any component bound to the right standard vocabulary (PROV-O, SCXML, VC, DPV) is recognized as a governance component - whether it comes from the Default project or was custom-built.

## Enforcement Decisions (OASIS XACML)

| Decision | Meaning |
|---|---|
| **PERMIT** | All governance checks pass - action is authorized |
| **DENY** | One or more governance checks fail - action is refused |
| **INDETERMINATE** | Governance checks partially pass - requires review (configurable) |

Every decision produces a W3C PROV record and a SHA-256 hash-chained receipt.

What happens after the decision is the agent's responsibility. sdcgovernance issues the decision and the receipt. The operational response - routing, escalation, notification, halting - is customer business logic that varies per implementation.

## Two Interfaces, One Engine

**Python API** - for direct integration:

```python
from sdcgovernance import validate_governance

result = validate_governance("model.xsd", "instance.xml")
```

**MCP Server** - for any agent framework:

```bash
sdcgovernance serve --mcp
```

The MCP server exposes governance as tools that agents call. The agent runs the loop. sdcgovernance advises.

## Standards

- **OASIS XACML** - decision semantics (PERMIT/DENY/INDETERMINATE)
- **SDC native structure + W3C SCXML vocabulary** - workflow sequencing via XdOrdinal components in sub-cluster paths, labeled using SCXML semantics
- **W3C PROV** (PROV-O, PROV-DM) - provenance/audit records (one governance dimension)
- **W3C Data Privacy Vocabulary (DPV)** - provenance retention policy (same vocabulary used for SDC access control)
- **W3C Activity Streams 2.0** - activity/event type vocabulary
- **W3C Verifiable Credentials Data Model 2.0** - attestation authority pattern
- **W3C SHACL** - cross-entity constraint validation
- **OMG DMN** - decision tables for complex governance rules
- **SHA-256** - tamper-evident hash chains for decision receipts

## Architecture

```
src/sdcgovernance/
├── __init__.py          # Public API: validate_governance()
├── engine.py            # GovernanceEngine - the decision engine agents query
├── model_inspector.py   # Inspect SDC model for governance components
├── workflow.py          # Validate workflow transitions in instance
├── attestation.py       # Validate attestation content in instance
├── party_role.py        # Validate party/role constraints in instance
├── provenance.py        # Validate provenance/audit records + PROV generation + DPV retention policy
├── decision.py          # DMN decision table evaluation
├── receipts.py          # Decision receipt chain (hash-chained)
├── shacl_runtime.py     # SHACL cross-entity constraint validation
└── mcp_server.py        # MCP server exposing governance tools to any agent
```

Pure Python. No Django. No middleware. No web framework dependency.

## Installation

```bash
pip install sdcgovernance
```

## Integration with SDC Ecosystem

- **sdcvalidator** - independent structural validation library. Agents call it separately from sdcgovernance, at different points in a workflow.
- **SDCStudio** - models governance components visually. The XSD output includes governance definitions that sdcgovernance validates against.
- **AppGen** - generated applications can call `validate_governance()` at data entry boundaries.
- **SDC Agents** - reference implementations showing how to wire governance MCP tools into agentic workflows using Default project governance models. Customer agents connect to the same MCP server and use the tools however they want.

## Status

Pre-alpha. Planning phase. See [PLANNING.md](PLANNING.md) for the architecture and implementation roadmap.

## Dependencies

- `rdflib` - RDF/PROV record generation
- `pyshacl` - SHACL constraint validation

## License

Apache 2.0
