# SDC Governance

W3C standards-based runtime governance for the Semantic Data Charter ecosystem.

A Python library that enforces governance at execution time - workflow state machines, attestation authority, provenance chains, and constraint validation - using W3C PROV, Verifiable Credentials patterns, and SHACL.

## Why This Exists

SDC models define what *should* happen: legitimate workflow transitions, attestation authority, provenance requirements. This library enforces whether it *can* happen at the moment of execution.

Every state change is verified against the governance model before it's allowed to commit. Every decision produces a tamper-evident receipt. Every action is provenance-recorded using W3C PROV. The enforcement is deterministic: same input replays to the same decision.

## Architecture

The library is framework-agnostic at the core, with an optional Django integration subpackage for SDCStudio AppGen-generated applications.

```
sdc_governance/
├── provenance.py      # W3C PROV record generation
├── workflow.py         # State machine enforcement
├── attestation.py      # Authority verification (VC pattern)
├── shacl_runtime.py    # Runtime SHACL validation
├── receipts.py         # Decision receipt chain (hash-chained)
└── django/
    ├── middleware.py   # Django middleware for automatic enforcement
    ├── signals.py      # Django model signals
    └── admin.py        # Governance dashboard
```

**Core modules** are pure Python. No Django dependency. Usable in any Python application.

**Django subpackage** provides middleware, signals, and admin integration for AppGen-generated apps and any Django project. Generated apps add `sdc-governance` to requirements.txt and wire up configuration - no governance logic in the generated code itself.

## Standards

- **W3C PROV** (PROV-O, PROV-DM) - provenance records for every state change
- **W3C Verifiable Credentials Data Model 2.0** - attestation authority pattern
- **W3C SHACL** - runtime constraint validation beyond XSD structural checks
- **SHA-256** - tamper-evident hash chains for decision receipts

## Integration with SDC Ecosystem

- **SDCStudio** compiles governance components (workflow, attestation, party/role, provenance) to a configuration file the library reads
- **AppGen** includes `sdc-governance` in generated app requirements and wires the Django middleware
- **sdcvalidator** handles structural validation (XSD); `sdc-governance` handles runtime governance enforcement
- **SDC Agents** can invoke governance checks as tool calls during agentic workflows

## Enforcement Decisions

Every governed state change produces one of:

| Decision | Meaning |
|---|---|
| **EXECUTE** | Transition is defined, all conditions met, action is allowed |
| **REFUSE** | Transition is not defined or conditions are not met, action is blocked |
| **ESCALATE** | Transition is defined but conditions are partially met, requires human review |

Every decision produces a W3C PROV record and a hash-chained receipt.

## Status

Pre-alpha. Planning phase. See [PLANNING.md](PLANNING.md) for the architecture and implementation roadmap.

## Dependencies

- `rdflib` - RDF/PROV record generation
- `pyshacl` - SHACL constraint validation
- `django` - optional, only for the django/ subpackage

## License

Apache 2.0
