# sdcgovernance Developer Documentation

For contributors to the sdcgovernance library itself.

## Contents

1. [Architecture](architecture.md) - module structure, data flow, design decisions
2. [Adding a Governance Dimension](adding-dimension.md) - how to add a new governance capability
3. [Testing](testing.md) - test conventions, fixtures, running tests
4. [Release Process](release.md) - versioning, PyPI publishing, CI/CD

## Quick Reference

```
src/sdcgovernance/
  __init__.py          # Public API, version, exports
  model_inspector.py   # DMType root slot detection
  engine.py            # GovernanceEngine (stateful advisory core)
  workflow.py          # Cluster tree extraction, ordinal adjacency
  attestation.py       # AttestationType validation
  party_role.py        # Subject/Provider/Participation validation
  provenance.py        # AuditType validation, PROV-O generation, RDF export
  decision.py          # DMN decision tables
  shacl_runtime.py     # SHACL cross-entity validation via pyshacl
  receipts.py          # XACML decisions, SHA-256 hash chain
  mcp_server.py        # JSON-RPC 2.0 stdio MCP server
  audit.py             # Redirect stub (merged into provenance.py)
```

## Key Design Decisions

- **No external MCP SDK** - raw JSON-RPC 2.0 for reliability
- **lxml for XML parsing** - fast, standard, well-maintained
- **Governance slots at known DMType positions** - no arbitrary search
- **Vocabulary binding for semantic discovery** - standards identify components, not CUID2
- **Each dimension is independent** - no coupling between governance modules
- **Engine caches model inspection** - inspect once, query many times
- **Receipt chain is append-only** - tamper-evident by design

## Dependencies

| Package | Purpose | Why This One |
|---|---|---|
| lxml | XML/XSD parsing | Fast C implementation, standard in Python XML ecosystem |
| rdflib | RDF graph, PROV-O export | W3C RDF standard library for Python |
| pyshacl | SHACL validation | Reference implementation of W3C SHACL |

No Django. No web framework. No MCP SDK. Pure Python library.
