#
# Copyright (c), 2025, Axius-SDC, Inc.
# All rights reserved.
# This file is distributed under the terms of the Apache 2.0 License.
#
"""
Tests for RFC 8785 JSON Canonicalization.

The curated vectors below target the three ways the previous
``json.dumps``-based canonicalization diverged from RFC 8785. Each one is a
case where the old code produced different bytes, and therefore a different
hash, from any conformant implementation.

``TestNodeDifferential`` is the load-bearing test: it checks agreement with
a real ECMAScript engine rather than with a second reading of the spec.
"""

import json
import shutil
import subprocess

import pytest

from sdcgovernance.jcs import (
    CANONICALIZATION_ID,
    JCSError,
    canonicalize,
    canonicalize_bytes,
)

# ---------------------------------------------------------------------------
# Numbers: RFC 8785 §3.2.2.3, ECMAScript Number::toString.
# The previous implementation failed every case in this table.
# ---------------------------------------------------------------------------
NUMBER_VECTORS = [
    (0, "0"),
    (0.0, "0"),
    (-0.0, "0"),           # ECMAScript renders negative zero as "0"
    (1, "1"),
    (1.0, "1"),            # the live bug: json.dumps gives "1.0"
    (-1.0, "-1"),
    (100.0, "100"),
    (1.5, "1.5"),
    (-1.5, "-1.5"),
    (123.456, "123.456"),
    (1e16, "10000000000000000"),   # json.dumps gives "1e+16"
    (1e21, "1e+21"),               # switches to exponential at 1e21
    (1e-6, "0.000001"),
    (1e-7, "1e-7"),                # json.dumps gives "1e-07"
    (5e-324, "5e-324"),            # smallest subnormal double
    (1.7976931348623157e308, "1.7976931348623157e+308"),
    (333333333.33333329, "333333333.3333333"),
    (0.1, "0.1"),
    (2**53 - 1, "9007199254740991"),
]

# ---------------------------------------------------------------------------
# Strings: RFC 8785 §3.2.2.2. Six two-character escapes, \u00xx lowercase
# for the remaining C0 controls, nothing else escaped.
# ---------------------------------------------------------------------------
STRING_VECTORS = [
    ("", '""'),
    ("plain", '"plain"'),
    ('"', r'"\""'),
    ("\\", r'"\\"'),
    ("/", '"/"'),                     # solidus is NOT escaped
    ("\b\t\n\f\r", r'"\b\t\n\f\r"'),
    ("\x00", '"\\u0000"'),
    ("\x1f", '"\\u001f"'),          # lowercase hex
    ("é", '"é"'),                     # non-ASCII emitted literally
    ("\U0001F600", '"\U0001F600"'),
]


class TestNumbers:
    @pytest.mark.parametrize("value,expected", NUMBER_VECTORS)
    def test_number_vector(self, value, expected):
        assert canonicalize(value) == expected

    def test_integral_floats_lose_the_decimal_point(self):
        """
        The divergence that was live in production.

        json.dumps renders 1.0; RFC 8785 requires 1. Any float in a hashed
        document was therefore enough to make our hash disagree with every
        conformant implementation, and the disagreement is silent.
        """
        legacy = json.dumps({"score": 1.0}, separators=(",", ":"))
        assert legacy == '{"score":1.0}'
        assert canonicalize({"score": 1.0}) == '{"score":1}'

    def test_nan_and_infinity_are_refused(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with pytest.raises(JCSError):
                canonicalize(bad)

    def test_unsafe_integers_are_refused(self):
        """
        JSON numbers are IEEE 754 doubles, so an integer past 2**53 cannot
        round trip. Refusing beats emitting bytes another implementation
        would read back as a different number.
        """
        with pytest.raises(JCSError, match="safe range"):
            canonicalize(2**53)
        assert canonicalize(2**53 - 1) == "9007199254740991"


class TestStrings:
    @pytest.mark.parametrize("value,expected", STRING_VECTORS)
    def test_string_vector(self, value, expected):
        assert canonicalize(value) == expected

    def test_output_is_utf8_bytes(self):
        assert canonicalize_bytes("é") == b'"\xc3\xa9"'


class TestKeyOrdering:
    def test_sorts_by_utf16_code_unit_not_code_point(self):
        """
        RFC 8785 §3.2.3 sorts by UTF-16 code unit. An astral character is a
        surrogate pair beginning at U+D800, so it sorts BEFORE U+E000..U+FFFF
        in UTF-16 but AFTER them by code point. Python's sort_keys=True uses
        code point and therefore gets this backwards.
        """
        data = {"\U0001F600": 1, "ﬀ": 2}

        assert list(sorted(data)) == ["ﬀ", "\U0001F600"]        # code point
        assert canonicalize(data).index('"\U0001F600"') < canonicalize(data).index('"ﬀ"')

    def test_ascii_ordering_is_unchanged(self):
        assert canonicalize({"b": 1, "a": 2, "A": 3}) == '{"A":3,"a":2,"b":1}'


class TestStructures:
    @pytest.mark.parametrize("value,expected", [
        (None, "null"),
        (True, "true"),
        (False, "false"),
        ({}, "{}"),
        ([], "[]"),
        ([1, 2.0, "x", None], '[1,2,"x",null]'),
        ({"a": {"b": [1.0]}}, '{"a":{"b":[1]}}'),
    ])
    def test_structure_vector(self, value, expected):
        assert canonicalize(value) == expected

    def test_booleans_are_not_treated_as_integers(self):
        """bool subclasses int in Python; order of checks matters."""
        assert canonicalize({"t": True, "f": False}) == '{"f":false,"t":true}'

    def test_non_string_keys_are_refused(self):
        with pytest.raises(JCSError, match="keys must be strings"):
            canonicalize({1: "a"})

    def test_unsupported_types_are_refused(self):
        with pytest.raises(JCSError):
            canonicalize({"when": object()})


class TestReceiptIntegration:
    def test_new_receipts_commit_to_the_scheme(self):
        from sdcgovernance.receipts import Decision, Receipt

        r = Receipt(decision=Decision.PERMIT, reasoning="x")
        assert r.canonicalization == CANONICALIZATION_ID
        assert r.verify_hash()

    def test_legacy_receipts_still_verify(self):
        """
        Receipts issued before conformance must keep verifying. Otherwise
        the change looks like tampering on every artifact already in the
        wild, which is the failure mode this whole exercise is about.
        """
        from sdcgovernance.receipts import (
            LEGACY_CANONICALIZATION,
            Decision,
            Receipt,
        )

        legacy = Receipt(
            decision=Decision.PERMIT,
            reasoning="x",
            timestamp="2026-04-24T12:00:00Z",
            canonicalization=LEGACY_CANONICALIZATION,
        )
        assert legacy.verify_hash()

        modern = Receipt(
            decision=Decision.PERMIT,
            reasoning="x",
            timestamp="2026-04-24T12:00:00Z",
        )
        assert modern.verify_hash()
        # Same content, different scheme, therefore different hash. That is
        # the point of carrying the field.
        assert legacy.receipt_hash != modern.receipt_hash


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
class TestNodeDifferential:
    """
    Agreement with a real ECMAScript engine.

    JSON.stringify already implements Number::toString and the JCS escape
    set, and Array.prototype.sort orders strings by UTF-16 code unit, so
    canonicalization in JS is stringify plus sorted keys. Agreeing with it
    is the closest thing to agreeing with an independent verifier.
    """

    ORACLE = """
    function canon(v) {
      if (v === null) return 'null';
      const t = typeof v;
      if (t === 'boolean' || t === 'number' || t === 'string') return JSON.stringify(v);
      if (Array.isArray(v)) return '[' + v.map(canon).join(',') + ']';
      return '{' + Object.keys(v).sort()
        .map(k => JSON.stringify(k) + ':' + canon(v[k])).join(',') + '}';
    }
    const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));
    process.stdout.write(cases.map(canon).join('\\n'));
    """

    def _node(self, cases):
        proc = subprocess.run(
            ["node", "-e", self.ORACLE],
            input=json.dumps(cases, ensure_ascii=False).encode("utf-8"),
            capture_output=True,
            check=True,
        )
        return proc.stdout.decode("utf-8").split("\n")

    def test_agrees_with_node_on_every_vector(self):
        cases = (
            [v for v, _ in NUMBER_VECTORS if abs(v) <= 2**53 - 1]
            + [v for v, _ in STRING_VECTORS]
            + [
                {"a": 1.0, "b": [1e21, 1e-7, 1e16]},
                {"\U0001F600": 1, "ﬀ": 2},
                {"decision": "PERMIT", "score": 1.0, "errors": []},
            ]
        )
        assert [canonicalize(c) for c in cases] == self._node(cases)

    def test_agrees_with_node_on_random_doubles(self):
        """
        Random IEEE 754 bit patterns, which is what finds presentation bugs
        that hand-picked numbers miss.
        """
        import random
        import struct

        random.seed(20260830)
        cases = []
        while len(cases) < 500:
            f = struct.unpack("<d", struct.pack("<Q", random.getrandbits(64)))[0]
            if f == f and abs(f) != float("inf"):
                cases.append(f)

        assert [canonicalize(c) for c in cases] == self._node(cases)


class TestPublishedVectors:
    """
    The vectors in test-vectors/ are what third parties check against, so
    they must not drift from the implementation they claim to describe.
    """

    def _load(self):
        import pathlib

        path = (
            pathlib.Path(__file__).parent.parent
            / "test-vectors"
            / "rfc8785-canonicalization.json"
        )
        return json.loads(path.read_text(encoding="utf-8"))

    def test_every_published_vector_still_holds(self):
        doc = self._load()
        for vector in doc["vectors"]:
            assert canonicalize(vector["input"]) == vector["output"], (
                vector["description"]
            )

    def test_vector_count_matches_the_manifest(self):
        doc = self._load()
        assert doc["vector_count"] == len(doc["vectors"])

    def test_declared_id_matches_the_module(self):
        assert self._load()["canonicalization_id"] == CANONICALIZATION_ID
