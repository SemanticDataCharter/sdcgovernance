# SDC Governance

W3C standards-based governance validation for Semantic Data Charter instances.

A Python library that validates governance content in XML data instances against governance components defined in the SDC data model. If the model defines governance (workflow, attestation, party/role, provenance, audit), the instance must carry that content - and this library validates it.

No framework dependency. No middleware. A function call.

## How It Works

SDC data models (XSD) can optionally include governance components: Workflow state machines, Attestation authority requirements, Party/Role constraints, Provenance requirements, and Audit definitions. These are part of the data model, not a separate governance layer.

When governance components are defined, every XML data instance must carry the corresponding governance content. This library validates that content against the model:

```python
from sdc_governance import validate_governance

result = validate_governance("model.xsd", "instance.xml")

print(result.decision)      # EXECUTE, REFUSE, ESCALATE, or SKIP
print(result.has_governance) # True if model defines governance components
print(result.errors)         # list of governance validation errors
print(result.receipt)        # tamper-evident decision receipt
```

If the model does not define governance components, the result is `SKIP` - no governance validation needed.

## The Two-Layer Validation Model

```
Layer 1: sdcvalidator (structural)
    Does the instance conform to the XSD schema?

Layer 2: sdc-governance (governance)
    Does the model define governance components?
    If yes: does the instance carry valid governance content?
```

If `sdc-governance` is installed alongside `sdcvalidator`, governance validation is called automatically after structural validation passes. No code changes required.

## What Gets Validated

| Component | What the model defines | What the instance must carry |
|---|---|---|
| **Workflow** | States, transitions, entry conditions | Current state, proposed transition, satisfied conditions |
| **Attestation** | Authority requirements per action | Attestation with correct role, party reference, timestamp |
| **Party/Role** | Role constraints for governed actions | Acting party identification with required role |
| **Provenance** | Provenance requirements | PROV-formatted record of action, agent, entity, temporal bounds |
| **Audit** | Audit record requirements | Audit content meeting the model's format and field requirements |

## Enforcement Decisions

| Decision | Meaning |
|---|---|
| **EXECUTE** | All governance checks pass - instance is valid |
| **REFUSE** | One or more governance checks fail - instance is rejected |
| **ESCALATE** | Governance checks partially pass - requires review (configurable) |
| **SKIP** | Model does not define governance components - no validation needed |

Every decision produces a W3C PROV record and a SHA-256 hash-chained receipt.

## Standards

- **W3C PROV** (PROV-O, PROV-DM) - provenance records
- **W3C Verifiable Credentials Data Model 2.0** - attestation authority pattern
- **W3C SHACL** - cross-entity constraint validation
- **SHA-256** - tamper-evident hash chains for decision receipts

## Architecture

```
src/sdc_governance/
├── __init__.py          # Public API: validate_governance()
├── model_inspector.py   # Inspect SDC model for governance components
├── workflow.py          # Validate workflow transitions in instance
├── attestation.py       # Validate attestation content in instance
├── party_role.py        # Validate party/role constraints in instance
├── provenance.py        # Validate provenance records + PROV generation
├── audit.py             # Validate audit content in instance
├── receipts.py          # Decision receipt chain (hash-chained)
└── shacl_runtime.py     # SHACL cross-entity constraint validation
```

Pure Python. No Django. No middleware. No web framework dependency.

## Installation

```bash
pip install sdc-governance
```

## Integration with SDC Ecosystem

- **sdcvalidator** - structural validation (Layer 1). If sdc-governance is installed, sdcvalidator calls it automatically after structural validation passes.
- **SDCStudio** - models governance components visually. The XSD output includes governance definitions that sdc-governance validates against.
- **AppGen** - generated applications can call `validate_governance()` at data entry boundaries.
- **SDC Agents** - agents can invoke governance validation as a tool call during agentic workflows.

## Status

Pre-alpha. Planning phase. See [PLANNING.md](PLANNING.md) for the architecture and implementation roadmap.

## Dependencies

- `rdflib` - RDF/PROV record generation
- `pyshacl` - SHACL constraint validation

## License

Apache 2.0
