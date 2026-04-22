# W3C Standards-Based Execution Governance

## High-Level Planning Document

**Date**: 2026-04-22
**Status**: Planning
**Decision context**: Veritas partnership confirmed a clean integration boundary (SDC models governance, Veritas enforces at runtime). However, the same enforcement can be built natively into SDCStudio-generated applications using W3C standards, eliminating partner dependency and making governance a default property of every deployment.

---

## Strategic Decision

Build execution-time governance directly into the AppGen templates using W3C standards rather than depending on an external execution engine. Every generated Django app ships with runtime enforcement built in.

**Why this over Veritas:**
- No partner dependency on a two-person pre-commercial team
- No adapter layer between SDC models and the enforcement engine
- Every practitioner deployment gets governance by default, not as an add-on
- W3C standards make the enforcement interoperable, not proprietary
- The generated app IS the execution boundary - data enters there, governance enforces there
- Aligns with "governance travels with the data" thesis
- The W3C community has been waiting for a runtime that binds their vocabularies to payloads

**Veritas relationship**: Not adversarial. Their models can still be published to the catalog as an alternative execution pattern. But SDC's native path uses open standards, not a proprietary engine.

---

## Architecture: sdc-governance Library

### Design Principle

Governance enforcement is a **separate open-source library** (`sdc-governance`), not embedded code in generated apps. Generated apps import and configure the library. The library does the enforcement.

This follows the same pattern as `sdcvalidator` (structural validation on PyPI) and `form2sdc` (form conversion on PyPI) - thin, focused libraries that any project can import.

**Why a library, not generated code:**
- One codebase to maintain - bug fixes and features reach every deployment on `pip install --upgrade`
- Testable independently with its own test suite
- Versioned separately from AppGen templates
- Pluggable - works in non-AppGen Django projects, or non-Django projects entirely
- Lighter generated code - AppGen templates just add `sdc-governance` to requirements.txt and wire up configuration

### Library Structure

```
sdc-governance/
├── sdc_governance/
│   ├── __init__.py
│   ├── provenance.py      # W3C PROV record generation (framework-agnostic)
│   ├── workflow.py         # State machine enforcement (framework-agnostic)
│   ├── attestation.py      # Authority verification, VC pattern (framework-agnostic)
│   ├── shacl_runtime.py    # Runtime SHACL validation (framework-agnostic)
│   ├── receipts.py         # Decision receipt chain (framework-agnostic)
│   ├── django/
│   │   ├── __init__.py
│   │   ├── middleware.py   # Django middleware for automatic enforcement
│   │   ├── signals.py      # Django model signals for state change interception
│   │   └── admin.py        # Governance dashboard for Django admin
│   └── settings.py         # Configuration defaults
├── tests/
├── pyproject.toml
├── README.md
└── LICENSE                 # Apache 2.0
```

The core modules (provenance, workflow, attestation, receipts, shacl_runtime) are framework-agnostic Python. The `django/` subpackage provides optional integration for AppGen-generated apps and any other Django project.

Published to PyPI as `sdc-governance`. Apache 2.0.

### Core Modules

**1. provenance.py - W3C PROV Records**

Every state change produces a PROV record:
- `prov:Activity` - the action taken (create, update, delete, transition)
- `prov:Agent` - who/what performed it (user, API client, agent)
- `prov:Entity` - the data entity affected
- `prov:wasGeneratedBy` / `prov:used` - the relationships
- `prov:startedAtTime` / `prov:endedAtTime` - temporal bounds
- SHA-256 hash of the entity state before and after

PROV records are queryable via SPARQL and exportable as RDF/Turtle.

**2. workflow.py - State Machine Enforcement**

SDC workflow components define legitimate state transitions and entry conditions. The library enforces these at runtime:
- Before any state change, checks whether the transition is defined in the workflow model
- Entry conditions must be satisfied (required attestations present, required party/role authorized)
- If the transition is not defined or conditions are not met: REFUSE
- If the transition is defined and conditions are met: EXECUTE
- If the transition is defined but conditions are partially met: ESCALATE (configurable)
- Every decision produces a PROV record

**3. attestation.py - Authority Verification (W3C VC pattern)**

SDC attestation components define who has authority to assert what. The library verifies:
- The acting party has the required role (from party/role components)
- The attestation is structurally present (not just assumed from session auth)
- The authority chain is traceable (who delegated, under what conditions)

Follows the VC Data Model 2.0 pattern (issuer/holder/verifier) without requiring full DID infrastructure. The attestation is a structured JSON-LD claim bound to the data record.

**4. shacl_runtime.py - Runtime SHACL Validation**

Beyond XSD structural validation (which sdcvalidator handles), adds SHACL shapes validation:
- Constraints from the SDC model compiled to SHACL shapes
- Validated at write time against the graph representation
- Violation reports follow the SHACL validation report format
- Enables complex cross-field and cross-entity constraints that XSD alone cannot express

**5. receipts.py - Decision Receipts**

Every enforcement decision (EXECUTE, REFUSE, ESCALATE) produces a tamper-evident receipt:
- The decision and reasoning
- The PROV record of the action
- The attestation that was verified (or missing)
- The workflow state before and after
- SHA-256 hash linking to the previous receipt (hash chain)
- Deterministic: same input replays to the same decision

Append-only receipt log, PROV-formatted, hash-chained.

### Django Integration (optional subpackage)

**django/middleware.py**: Intercepts save/update operations on workflow-governed entities. Calls the core workflow, attestation, and provenance modules. Configurable per model.

**django/signals.py**: Alternative to middleware - uses Django model signals for finer-grained control.

**django/admin.py**: Governance dashboard showing provenance chains, decision receipts, attestation history. Optional SPARQL endpoint for provenance queries.

---

## What This Changes in AppGen

### Template Modifications (minimal)

**Both lightweight and enterprise templates:**
- Add `sdc-governance` to `requirements.txt`
- Add `sdc_governance.django` to `INSTALLED_APPS` in settings
- Add `sdc_governance.django.middleware.GovernanceMiddleware` to `MIDDLEWARE`
- Add governance configuration in settings pointing to the SDC model's governance components
- No governance logic in the generated code itself

### SDCStudio Changes

- Governance components (workflow, attestation, party/role, provenance) compile to a governance configuration file included in the generated app bundle
- The configuration file tells `sdc-governance` which models are governed, which transitions are allowed, who can attest, and what provenance is captured
- AppGen does not generate enforcement code - it generates configuration that the library reads

---

## Implementation Phases

### Phase 1: Library scaffolding + PROV Provenance
- Create `sdc-governance` repo (SemanticDataCharter org, Apache 2.0)
- Core provenance module with W3C PROV record generation
- Hash-chained receipt foundation
- Exportable as RDF/Turtle
- Basic test suite
- PyPI package published
- Timeline: 2-3 weeks

### Phase 2: Workflow State Machine Enforcement
- Core workflow module (framework-agnostic)
- Django middleware + signals subpackage
- EXECUTE / REFUSE / ESCALATE decisions with PROV records
- Configuration reader for SDC governance components
- Timeline: 3-4 weeks

### Phase 3: Attestation Verification
- Core attestation module (framework-agnostic)
- Party/role verification
- Authority chain tracing
- VC Data Model 2.0 pattern for structured claims
- Timeline: 2-3 weeks

### Phase 4: SHACL Runtime Validation
- Core SHACL runtime module (framework-agnostic)
- pyshacl integration
- Violation reports in standard SHACL format
- Timeline: 2 weeks

### Phase 5: AppGen Integration + Governance Dashboard
- Update AppGen templates: add sdc-governance to requirements, wire middleware
- Governance configuration file generation from SDC model components
- Django admin governance dashboard
- Optional SPARQL endpoint for provenance queries
- Receipt chain verification CLI tool
- Timeline: 2-3 weeks

---

## Dependencies

- pyshacl (already in SDCStudio requirements)
- rdflib (already in SDCStudio requirements)
- No new external dependencies required for the core library
- Django is an optional dependency (only for the django/ subpackage)
- All W3C standards already have Python implementations in the existing stack

## What This Means for Practitioners

- Module 7 compliance toolset reference becomes real
- Module 8 deployment includes governance by default
- The Maturity Map Governance dimension (Level 5: "Governance integrated with provenance and constraint layers. Policy-as-code.") becomes a deliverable, not an aspiration
- Practitioners can tell clients: "Your generated application enforces governance at runtime using W3C standards. Every decision is traceable, every action is provenance-recorded, every state change is verified."

## What This Means for the Market

- SDC is the only open-source framework where governance enforcement is a default property of generated applications
- No dashboard, no separate engine, no vendor dependency
- "Governance travels with the app" is the natural extension of "governance travels with the data"
- Direct answer to the Palantir FDE dependency: the generated app enforces governance without vendor engineers on site
- EU AI Act Article 12 (runtime logging) and Article 15 (robustness) are satisfied structurally, not by bolting on compliance tools

---

## Relationship to Veritas

This plan does not prevent Veritas from publishing execution-aware components to the SDCStudio catalog. Their dual-gate pattern (semantic gate + execution gate) can exist as an alternative enforcement approach for customers who want it.

The difference: SDC's native approach uses W3C standards and is built into every generated app by default. Veritas's approach uses proprietary execution verbs and requires a separate engine. Both can coexist. The customer chooses.

If Samantha responds to the partnership framing email positively, their models still have a home in the catalog. If she doesn't, SDC has no dependency on them.
