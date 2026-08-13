# Changelog

All notable changes to `sdcgovernance` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.1.1] - 2026-08-13

### Added

- **MCP registry publishing metadata.** Added a `server.json` (official MCP
  registry format, schema `2025-12-11`) describing the built-in MCP server, and
  an `mcp-name` ownership marker in the README so the package can be published to
  the official MCP registry. No code or API changes; the MCP server itself is
  unchanged (`uvx sdcgovernance`).

## [4.1.0] - 2026-07-20

### Added

**Sovereign source lineage in receipts and provenance (aligns with SDCRM 4.0.0 Beale-Sovereignty).**
The SDCRM added `source_instance_id` and `source_version_id` to DMType (0..1 each) to preserve
the upstream identifier and version from the originating source system (e.g. Epic, SAP), decoupled
from the sovereign SDC `instance_id`. This release captures that lineage through the governance path:

- `Receipt` now carries `source_instance_id` and `source_version_id`. They are included in the
  tamper-evident hash **only when present**, so receipts without source fields hash identically to
  4.0.x, keeping existing receipt chains verifiable (backward-compatible).
- `ReceiptChain.append()` and `GovernanceEngine.evaluate_transition()` accept the two source fields
  and thread them onto every receipt.
- `mcp_server` extracts `source_instance_id`/`source_version_id` from the instance root alongside
  `instance_id`/`instance_version`.
- `decision.extract_context()` surfaces the source fields in the decision context.
- `provenance_to_rdf()` emits `prov:wasDerivedFrom` to a source entity carrying the RM-defined
  `sdc4:source_instance_id` / `sdc4:source_version_id`, so the PROV-O export records complete
  cross-boundary lineage.

### Changed

- `model_inspector` docstring "source of truth" reference genericized from an absolute local path to
  `SDCRM sdc4/schemas/sdc4.xsd`.

### Notes

- Not affected by the sdcvalidator 4.4.x XSD 1.1 restriction fix: `sdcgovernance` reads schemas with
  lxml and validates instances with pyshacl and DMN logic; it never builds an `XMLSchema11`, so it does
  not encounter the substitution-group restriction false positive.

## [4.0.4] - 2026

- MTCP cross-chain integration with Evidence Packs; reproducible JSON-RPC fixtures.

## [4.0.3] - 2026

- `evaluate_decision` returns a tamper-evident `Receipt`.

## [4.0.2] - 2026

- `evaluate_decision` `instance_path` made optional.

## [4.0.1] - 2026

- Entity hash modeling uses the RM `XdFileType` pattern; conformance report version alignment.

## [4.0.0] - 2026

- Initial release: DMN-based governance decisions, XACML 3.0 decision values, tamper-evident
  receipt chain, W3C PROV-O provenance, SHACL runtime validation, MCP server.
