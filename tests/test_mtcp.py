"""Tests for MTCP integration helpers."""

import json

from sdcgovernance.mtcp import (
    canonical_json,
    compute_evidence_pack_hash,
    verify_evidence_pack,
)


class TestCanonicalJSON:
    """RFC 8785-aligned canonicalization."""

    def test_keys_sorted(self):
        out = canonical_json({"b": 1, "a": 2})
        assert out == '{"a":2,"b":1}'

    def test_no_whitespace(self):
        out = canonical_json({"a": 1, "b": [1, 2]})
        assert " " not in out
        assert "\n" not in out

    def test_utf8_not_ascii_escaped(self):
        out = canonical_json({"label": "café"})
        assert "café" in out
        assert "\\u" not in out

    def test_nested_keys_sorted(self):
        out = canonical_json({"outer": {"z": 1, "a": 2}})
        assert out == '{"outer":{"a":2,"z":1}}'


class TestComputeEvidencePackHash:
    """SHA-256 of canonical JSON over EP minus its own hash field."""

    def test_excludes_hash_field(self):
        ep = {"model_id": "gpt-4o", "evidence_pack_hash": "ignored"}
        h = compute_evidence_pack_hash(ep)
        ep_no_hash = {"model_id": "gpt-4o"}
        h_direct = compute_evidence_pack_hash(ep_no_hash)
        assert h == h_direct

    def test_deterministic(self):
        ep = {"model_id": "gpt-4o", "score": 0.7}
        assert compute_evidence_pack_hash(ep) == compute_evidence_pack_hash(ep)

    def test_returns_64_char_hex(self):
        ep = {"model_id": "gpt-4o"}
        h = compute_evidence_pack_hash(ep)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestVerifyEvidencePack:
    """End-to-end EP integrity verification."""

    def test_valid_pack(self):
        ep = {"model_id": "gpt-4o", "score": 0.95}
        ep["evidence_pack_hash"] = compute_evidence_pack_hash(ep)
        result = verify_evidence_pack(ep)
        assert result["valid"] is True
        assert result["computed_hash"] == result["expected_hash"]

    def test_tampered_value_detected(self):
        ep = {"model_id": "gpt-4o", "score": 0.95}
        ep["evidence_pack_hash"] = compute_evidence_pack_hash(ep)
        ep["score"] = 0.10  # tamper
        result = verify_evidence_pack(ep)
        assert result["valid"] is False
        assert result["computed_hash"] != result["expected_hash"]

    def test_missing_hash_field(self):
        ep = {"model_id": "gpt-4o"}
        result = verify_evidence_pack(ep)
        assert result["valid"] is False
        assert result["expected_hash"] == ""
        assert result["computed_hash"]  # still computed for inspection

    def test_returns_all_fields(self):
        ep = {"model_id": "gpt-4o"}
        ep["evidence_pack_hash"] = compute_evidence_pack_hash(ep)
        result = verify_evidence_pack(ep)
        assert "valid" in result
        assert "computed_hash" in result
        assert "expected_hash" in result

    def test_v2_worked_example_gpt4o(self):
        """
        Cross-implementation reproducibility check.

        EP and expected hash from MTCP_SDC_Schema_Mapping V2, Section
        "Worked Example: GPT-4o Evidence Pack to DENY Receipt"
        (A. Abby, 2026-05-09). The hash was produced by the MTCP
        evaluation pipeline. This test confirms sdcgovernance's
        canonicalization reproduces it bit-for-bit.
        """
        ep = {
            "model_id": "gpt-4o",
            "evaluation_timestamp": "2026-04-02T22:05:36.586110Z",
            "ve_cont": 1.0,
            "ve_form": 0.9929,
            "ve_dom": 0.6071,
            "ve_scope": 0.0071,
            "ve_lang": 0.0,
            "ve_decay_rate": 0.9929,
            "regime_classification": "R3",
            "cpd_score": 10.7,
            "overall_grade": "C",
            "bis_t0": 65.1,
            "bis_t03": 65.0,
            "bis_t07": 64.6,
            "bis_t10": 66.0,
            "constraint_state_hash": (
                "b2cf12b51e411ec3ca1bd28d856cef8c7c25705d893395c131d8c8764ee1e350"
            ),
            "eu_ai_act_art9": True,
            "eu_ai_act_art61": True,
            "nist_ai_rmf": True,
            "nca": False,
            "turn_count": 5600,
            "correction_count": 1950,
            "drift_detected": False,
            "evidence_pack_hash": (
                "89586bf4507cca361db03bd9005d97ddaaec42d1b6dea61ad498965ae172d283"
            ),
        }
        result = verify_evidence_pack(ep)
        assert result["valid"] is True
        assert result["computed_hash"] == result["expected_hash"]


class TestDualCanonicalizationAcceptance:
    """
    MTCP is migrating to conformant RFC 8785 (A. Abby, 2026-08-30). Until it
    lands, Evidence Packs may arrive under either convention, and the two
    disagree whenever a pack contains an integral float. Accepting both means
    neither side needs a flag day.
    """

    # The published worked example, minus its hash.
    EP = {
        "model_id": "gpt-4o",
        "evaluation_timestamp": "2026-04-02T22:05:36.586110Z",
        "ve_cont": 1.0,          # integral floats: these are what diverge
        "ve_form": 0.9929,
        "ve_lang": 0.0,
        "bis_t03": 65.0,
        "bis_t10": 66.0,
        "regime_classification": "R3",
        "turn_count": 5600,
        "drift_detected": False,
    }

    def _pack(self, hash_value):
        return {**self.EP, "evidence_pack_hash": hash_value}

    def test_legacy_pack_verifies_and_is_labelled(self):
        from sdcgovernance.mtcp import compute_evidence_pack_hash

        result = verify_evidence_pack(
            self._pack(compute_evidence_pack_hash(self.EP))
        )
        assert result["valid"] is True
        assert result["canonicalization"] == "mtcp-legacy"

    def test_conformant_pack_verifies_and_is_labelled(self):
        from sdcgovernance.mtcp import compute_evidence_pack_hash_rfc8785

        result = verify_evidence_pack(
            self._pack(compute_evidence_pack_hash_rfc8785(self.EP))
        )
        assert result["valid"] is True
        assert result["canonicalization"] == "rfc8785"

    def test_the_two_conventions_actually_differ_here(self):
        """
        Guards the premise. If these ever coincide, the dual-acceptance path
        is untested by the two tests above.
        """
        from sdcgovernance.mtcp import (
            compute_evidence_pack_hash,
            compute_evidence_pack_hash_rfc8785,
        )

        assert compute_evidence_pack_hash(self.EP) != (
            compute_evidence_pack_hash_rfc8785(self.EP)
        )

    def test_a_tampered_pack_still_fails_under_both(self):
        result = verify_evidence_pack(self._pack("0" * 64))
        assert result["valid"] is False
        assert result["canonicalization"] == ""

    def test_missing_hash_field_fails(self):
        result = verify_evidence_pack(dict(self.EP))
        assert result["valid"] is False
        assert result["expected_hash"] == ""
