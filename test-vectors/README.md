# Canonicalization test vectors

`sdcgovernance` hashes commit to *bytes*. A hash is only worth something if an
independent implementation derives the same bytes from the same data, so the
canonicalization has to be a published, checkable thing rather than a claim.

These vectors exist so anyone can check their implementation against ours
without reading our source.

## `rfc8785-canonicalization.json`

21 vectors covering [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785)
(JSON Canonicalization Scheme). Each entry is:

```json
{
  "description": "integral float loses the decimal point",
  "input": { "score": 1.0 },
  "output": "{\"score\":1}"
}
```

Canonicalize `input`, compare to `output` as a string, then hash the **UTF-8
encoding** of that string.

Every vector was cross-checked against Node.js before publication. Node is a
real ECMAScript engine, and RFC 8785 number formatting is defined in terms of
ECMAScript `Number::toString`, so agreement with it is stronger evidence than
agreement with a second reading of the spec.

### What the vectors are chosen to catch

Sorting keys and stripping whitespace gets you most of the way to RFC 8785 and
still leaves three ways to disagree. All three fail silently: the bytes differ,
so the hash differs, and the artifact looks tampered with rather than
misencoded.

| Divergence | Naive output | RFC 8785 |
|---|---|---|
| Integral floats | `1.0` | `1` |
| Fixed vs exponential | `1e+16` | `10000000000000000` |
| Exponent padding | `1e-07` | `1e-7` |
| Key order, astral vs BMP | code point | UTF-16 code unit |
| C0 controls | varies | `\u00xx`, lowercase |

The number cases are the ones that bite in practice, because a single float
anywhere in a document is enough.

### Two things that are deliberately errors

- **Integers beyond ±(2^53 − 1).** JSON numbers are IEEE 754 doubles, so a
  larger integer cannot round-trip. Carry it as a string.
- **`NaN` and `Infinity`.** No JSON representation.

Emitting something for these would produce a hash that looks fine and fails
only in someone else's verifier.

## Scope

Receipts (`sdcgovernance.receipts`) use RFC 8785 and carry
`canonicalization: "rfc8785"` so the scheme is committed to inside the hash.

**MTCP Evidence Packs do not.** That is an external wire format whose hashes are
produced by the MTCP side, and its published worked example fixes the legacy
Python `json.dumps` rendering. Moving it needs a coordinated change on both
sides; see the note in `src/sdcgovernance/mtcp.py`.
