# sdcgovernance User Documentation

W3C standards-based governance advisory engine for SDC data instances.

## What sdcgovernance Does

sdcgovernance validates governance content in XML data instances against governance components defined in SDC data models. If the model defines governance (workflow, attestation, party/role, provenance/audit), the instance must carry that governance content - and this library validates it.

Returns decisions using OASIS XACML semantics: **PERMIT**, **DENY**, or **INDETERMINATE**.

## Contents

1. [Installation](installation.md) - install and verify
2. [Quick Start](quickstart.md) - first governance validation in 5 minutes
3. [Model Inspector](model-inspector.md) - detecting governance dimensions in a model
4. [Workflow Validation](workflow.md) - cluster tree paths, ordinal adjacency, transitions
5. [Attestation](attestation.md) - authority assertions, committer, proof
6. [Party/Role](party-role.md) - subject, provider, participation function constraints
7. [Provenance/Audit](provenance.md) - AuditType records, retention policy, PROV-O export
8. [Decision Tables](decision-tables.md) - DMN conditional governance rules
9. [SHACL Validation](shacl.md) - cross-entity constraint validation
10. [MCP Server](mcp-server.md) - JSON-RPC 2.0 stdio server for agent integration
11. [GovernanceEngine](engine.md) - the advisory API agents query

## Key Concepts

- **sdcgovernance and sdcvalidator are independent libraries.** No hook, no chaining. Agents call each one separately, at different points in a workflow.
- **Governance is conversational, not single-pass.** Agents query multiple times during a workflow: check allowed transitions, evaluate a specific transition, record provenance.
- **The model IS the configuration.** Governance components are at known positions in the DMType root. No override files, no YAML, no separate config.
- **Each governance dimension is independent.** Including workflow does not require attestation. Including attestation does not require party/role. They compose optionally.
- **Decisions use OASIS XACML semantics.** PERMIT, DENY, INDETERMINATE. No custom vocabulary.
- **sdcgovernance advises. The agent decides what happens after the decision.** The operational response to DENY or INDETERMINATE is the customer's business logic.
