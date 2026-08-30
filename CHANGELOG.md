# Changelog

All notable changes to `sdcgovernance` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.2.0] - 2026-08-30

### Changed

- **★ Canonicalization is now RFC 8785 conformant, not "RFC 8785-aligned."**
  Receipt and audit-record hashes previously used
  `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
  That is the right shape but not the standard, and it diverges in three
  places, each silently: the bytes differ, so the hash differs, and the
  artifact looks tampered with rather than misencoded.

  1. **Numbers.** RFC 8785 requires ECMAScript `Number::toString`. Python
     emits `1.0` where the standard requires `1`, `1e+16` where it requires
     `10000000000000000`, and `1e-07` where it requires `1e-7`. **A single
     float anywhere in a hashed document was enough to disagree with every
     conformant implementation.**
  2. **Key ordering.** RFC 8785 sorts by UTF-16 code unit; `sort_keys=True`
     sorts by Unicode code point. These disagree for astral-plane characters.
  3. **String escaping.** The escape set for C0 control characters was not
     pinned.

  A hash only means something if an independent implementation derives the
  same bytes, so this is a correctness fix rather than a tidy-up.

- **`Receipt` carries a `canonicalization` field**, defaulting to `"rfc8785"`,
  and includes it in the hashed content so a receipt cannot be reinterpreted
  under the legacy scheme. **Receipts issued before this release still
  verify**: construct them with `canonicalization=LEGACY_CANONICALIZATION` and
  the previous bytes are reproduced exactly.

- **MCP server advertises `2025-11-25`** (was `2024-11-05`) and now
  **negotiates** rather than answering with a fixed revision: a client asking
  for a version in `SUPPORTED_PROTOCOL_VERSIONS` gets that version back, any
  other client gets our newest and decides for itself.

  `2026-07-28` is deliberately not claimed. It removes the `initialize`
  handshake in favour of per-request `_meta.io.modelcontextprotocol/*` fields,
  which is a different architecture rather than a larger number, and it
  defines a compatibility path for initialization-based servers such as this
  one. `2024-11-05` and `2025-03-26` are also not claimed, because both
  require servers to accept JSON-RPC batches and this server reads one JSON
  object per line.

- **Tool failures are returned as tool errors** (`isError: true` in the
  result) rather than JSON-RPC protocol errors, per SEP-1303, so a calling
  model can see the failure and correct itself. Unknown tool names remain
  protocol errors.

### Added

- **`sdcgovernance.jcs`** — RFC 8785 implementation. `canonicalize()` and
  `canonicalize_bytes()`. Refuses `NaN`, `Infinity`, and integers beyond
  ±(2^53 − 1), which cannot round-trip through a conformant implementation;
  refusing beats emitting a hash that fails only in someone else's verifier.
- **`test-vectors/rfc8785-canonicalization.json`** — 21 published vectors so
  third parties can check an implementation without reading our source. Every
  vector was cross-checked against Node.js before publication.
- **Differential test against Node.js.** Node is a real ECMAScript engine and
  RFC 8785 number formatting is defined in ECMAScript terms, so agreement with
  it is stronger evidence than agreement with our own reading of the spec.
  4,043 cases including 4,000 randomly generated IEEE 754 bit patterns: zero
  disagreements.

### Added

- **`verify_evidence_pack` accepts either canonicalization** and reports which
  one matched, via a new `canonicalization` key (`"rfc8785"`, `"mtcp-legacy"`,
  or `""` on failure). MTCP is moving to conformance (A. Abby, 2026-08-30);
  accepting both means neither implementation needs a flag day. Strictly
  additive: nothing that verified before stops verifying.
- **`compute_evidence_pack_hash_rfc8785`** for callers that want the
  conformant hash explicitly.

### Unchanged, deliberately

- **MTCP Evidence Pack *emission* stays on the legacy convention** until MTCP
  publishes its conformant implementation. MTCP is an
  external wire format whose hashes are produced by the MTCP evaluation
  pipeline, and its published worked example (GPT-4o, V2) contains integral
  floats whose expected hash matches Python's `1.0` rendering, not RFC 8785's
  `1`. Moving this side alone would invalidate every Evidence Pack MTCP
  issues. Migration needs a coordinated change on both sides; see the note in
  `src/sdcgovernance/mtcp.py`.

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
