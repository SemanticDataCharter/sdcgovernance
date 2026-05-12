"""
Generate reproducible test fixtures for the MTCP <-> sdcgovernance joint paper.

Each fixture captures the full JSON-RPC 2.0 request/response wire format for a
representative scenario from TestEvaluateDecisionReceipt. Timestamp is pinned
so receipt_hash values are reproducible: anyone running sdcgovernance 4.0.4
with the same input arguments and pinned timestamp will produce the identical
receipt_hash bit-for-bit.

Run: python generate_fixtures.py
Output: fixtures.json (one file with all scenarios) and fixture_<n>.json (one per scenario)

Reproducing in the wild:
  pip install sdcgovernance==4.0.4
  Construct a Receipt with the timestamp shown in the fixture.
  receipt.receipt_hash should match.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Allow running this script standalone; assumes sdcgovernance 4.0.4 is installed
# or available on the path.
from sdcgovernance import __version__
from sdcgovernance.receipts import Receipt, Decision, StatusCode

assert __version__ == "4.0.4", f"Expected sdcgovernance 4.0.4, got {__version__}"


# Pinned timestamp for reproducibility. Anyone constructing a Receipt with the
# same content fields and this timestamp will produce the same receipt_hash.
PINNED_TIMESTAMP = "2026-05-10T15:00:00Z"


def make_receipt(
    *,
    decision: Decision,
    reasoning: str,
    status_code: StatusCode = StatusCode.OK,
    instance_id: str = "",
    instance_version: str = "",
    previous_hash: str | None = None,
    dimensions_checked: list[str] | None = None,
    errors: list[str] | None = None,
    context_hash: str = "",
) -> Receipt:
    """Construct a Receipt with a pinned timestamp for reproducible hashes."""
    return Receipt(
        decision=decision,
        reasoning=reasoning,
        status_code=status_code,
        instance_id=instance_id,
        instance_version=instance_version,
        timestamp=PINNED_TIMESTAMP,
        previous_hash=previous_hash,
        dimensions_checked=dimensions_checked or [],
        errors=errors or [],
        context_hash=context_hash,
    )


# Reusable basic table referenced across multiple fixtures
BASIC_TABLE = {
    "name": "model_grade_check",
    "hit_policy": "FIRST",
    "rules": [
        {
            "conditions": [
                {"field": "model_grade", "op": "in", "value": ["D", "F"]}
            ],
            "outcome": "DENY",
            "description": "Low model grade rejected",
        },
        {"conditions": [], "outcome": "PERMIT"},
    ],
}


def fixture_1_basic_deny() -> dict:
    """Basic DENY decision with receipt. From test_response_includes_receipt."""
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "evaluate_decision",
            "arguments": {
                "table_json": json.dumps(BASIC_TABLE),
                "extra_context": json.dumps({"model_grade": "D"}),
            },
        },
    }
    receipt = make_receipt(
        decision=Decision.DENY,
        reasoning="First matching rule (#0): Low model grade rejected",
        status_code=StatusCode.OK,
        dimensions_checked=["model_grade"],
    )
    response = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "decision": "DENY",
            "matched_rules": [0],
            "reasoning": "First matching rule (#0): Low model grade rejected",
            "errors": [],
            "receipt": receipt.to_dict(),
        },
    }
    return {"name": "basic_deny", "request": request, "response": response}


def fixture_2_basic_permit() -> dict:
    """Basic PERMIT via DEFAULT (empty conditions) rule."""
    request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "evaluate_decision",
            "arguments": {
                "table_json": json.dumps(BASIC_TABLE),
                "extra_context": json.dumps({"model_grade": "A"}),
            },
        },
    }
    receipt = make_receipt(
        decision=Decision.PERMIT,
        reasoning="First matching rule (#1)",
        status_code=StatusCode.OK,
        dimensions_checked=[],
    )
    response = {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "decision": "PERMIT",
            "matched_rules": [1],
            "reasoning": "First matching rule (#1)",
            "errors": [],
            "receipt": receipt.to_dict(),
        },
    }
    return {"name": "basic_permit_via_default", "request": request, "response": response}


def fixture_3_with_instance_identity() -> dict:
    """Receipt records instance_id and instance_version."""
    request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "evaluate_decision",
            "arguments": {
                "table_json": json.dumps(BASIC_TABLE),
                "extra_context": json.dumps({"model_grade": "D"}),
                "instance_id": "gpt-4o",
                "instance_version": "2024-08-06",
            },
        },
    }
    receipt = make_receipt(
        decision=Decision.DENY,
        reasoning="First matching rule (#0): Low model grade rejected",
        status_code=StatusCode.OK,
        instance_id="gpt-4o",
        instance_version="2024-08-06",
        dimensions_checked=["model_grade"],
    )
    response = {
        "jsonrpc": "2.0",
        "id": 3,
        "result": {
            "decision": "DENY",
            "matched_rules": [0],
            "reasoning": "First matching rule (#0): Low model grade rejected",
            "errors": [],
            "receipt": receipt.to_dict(),
        },
    }
    return {"name": "with_instance_identity", "request": request, "response": response}


def fixture_4_multi_field_deny() -> dict:
    """Multi-field rule: dimensions_checked records both fields, in order."""
    table = {
        "name": "multi_field",
        "hit_policy": "FIRST",
        "rules": [
            {
                "conditions": [
                    {"field": "regime", "op": "==", "value": "R3"},
                    {"field": "data_class", "op": ">=", "value": "Restricted"},
                ],
                "outcome": "DENY",
            },
        ],
    }
    request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "evaluate_decision",
            "arguments": {
                "table_json": json.dumps(table),
                "extra_context": json.dumps({
                    "regime": "R3",
                    "data_class": "Restricted",
                }),
            },
        },
    }
    receipt = make_receipt(
        decision=Decision.DENY,
        reasoning="First matching rule (#0)",
        status_code=StatusCode.OK,
        dimensions_checked=["regime", "data_class"],
    )
    response = {
        "jsonrpc": "2.0",
        "id": 4,
        "result": {
            "decision": "DENY",
            "matched_rules": [0],
            "reasoning": "First matching rule (#0)",
            "errors": [],
            "receipt": receipt.to_dict(),
        },
    }
    return {"name": "multi_field_deny", "request": request, "response": response}


def fixture_5_no_match_not_applicable() -> dict:
    """No rules match: NOT_APPLICABLE, dimensions_checked empty."""
    table = {
        "name": "no_match",
        "hit_policy": "FIRST",
        "rules": [
            {"conditions": [{"field": "x", "op": "==", "value": "y"}], "outcome": "PERMIT"},
        ],
    }
    request = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "evaluate_decision",
            "arguments": {
                "table_json": json.dumps(table),
                "extra_context": json.dumps({"x": "z"}),
            },
        },
    }
    receipt = make_receipt(
        decision=Decision.NOT_APPLICABLE,
        reasoning="No rules matched in decision table 'no_match'",
        status_code=StatusCode.OK,
        dimensions_checked=[],
    )
    response = {
        "jsonrpc": "2.0",
        "id": 5,
        "result": {
            "decision": "NOT_APPLICABLE",
            "matched_rules": [],
            "reasoning": "No rules matched in decision table 'no_match'",
            "errors": [],
            "receipt": receipt.to_dict(),
        },
    }
    return {"name": "no_match_not_applicable", "request": request, "response": response}


def fixture_6_unique_violation_processing_error() -> dict:
    """UNIQUE hit policy violation: INDETERMINATE + PROCESSING_ERROR status."""
    table = {
        "name": "unique_conflict",
        "hit_policy": "UNIQUE",
        "rules": [
            {"conditions": [{"field": "x", "op": "==", "value": 1}], "outcome": "PERMIT"},
            {"conditions": [{"field": "x", "op": "==", "value": 1}], "outcome": "DENY"},
        ],
    }
    request = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "evaluate_decision",
            "arguments": {
                "table_json": json.dumps(table),
                "extra_context": json.dumps({"x": 1}),
            },
        },
    }
    receipt = make_receipt(
        decision=Decision.INDETERMINATE,
        reasoning="UNIQUE hit policy violated: 2 rules matched",
        status_code=StatusCode.PROCESSING_ERROR,
        dimensions_checked=["x"],
        errors=["UNIQUE hit policy requires exactly 1 match, but 2 rules matched: [0, 1]"],
    )
    response = {
        "jsonrpc": "2.0",
        "id": 6,
        "result": {
            "decision": "INDETERMINATE",
            "matched_rules": [0, 1],
            "reasoning": "UNIQUE hit policy violated: 2 rules matched",
            "errors": ["UNIQUE hit policy requires exactly 1 match, but 2 rules matched: [0, 1]"],
            "receipt": receipt.to_dict(),
        },
    }
    return {"name": "unique_violation_processing_error", "request": request, "response": response}


def fixture_7_chain_genesis_then_link() -> dict:
    """Chain genesis (previous_hash null) followed by linked receipt."""
    # First call: chain genesis
    first_request = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {
            "name": "evaluate_decision",
            "arguments": {
                "table_json": json.dumps(BASIC_TABLE),
                "extra_context": json.dumps({"model_grade": "D"}),
                "instance_id": "gpt-4o",
            },
        },
    }
    first_receipt = make_receipt(
        decision=Decision.DENY,
        reasoning="First matching rule (#0): Low model grade rejected",
        status_code=StatusCode.OK,
        instance_id="gpt-4o",
        previous_hash=None,
        dimensions_checked=["model_grade"],
    )
    first_response = {
        "jsonrpc": "2.0",
        "id": 7,
        "result": {
            "decision": "DENY",
            "matched_rules": [0],
            "reasoning": "First matching rule (#0): Low model grade rejected",
            "errors": [],
            "receipt": first_receipt.to_dict(),
        },
    }
    # Second call: chain link via previous_hash
    second_request = {
        "jsonrpc": "2.0",
        "id": 8,
        "method": "tools/call",
        "params": {
            "name": "evaluate_decision",
            "arguments": {
                "table_json": json.dumps(BASIC_TABLE),
                "extra_context": json.dumps({"model_grade": "B"}),
                "instance_id": "gpt-4o",
                "previous_hash": first_receipt.receipt_hash,
            },
        },
    }
    second_receipt = make_receipt(
        decision=Decision.PERMIT,
        reasoning="First matching rule (#1)",
        status_code=StatusCode.OK,
        instance_id="gpt-4o",
        previous_hash=first_receipt.receipt_hash,
        dimensions_checked=[],
    )
    second_response = {
        "jsonrpc": "2.0",
        "id": 8,
        "result": {
            "decision": "PERMIT",
            "matched_rules": [1],
            "reasoning": "First matching rule (#1)",
            "errors": [],
            "receipt": second_receipt.to_dict(),
        },
    }
    return {
        "name": "chain_genesis_then_link",
        "first": {"request": first_request, "response": first_response},
        "second": {"request": second_request, "response": second_response},
    }


def fixture_8_mtcp_gpt4o_full_worked_example() -> dict:
    """
    Full MTCP integration worked example. Mirrors V3 Section: Worked Example.
    Uses the actual GPT-4o Evidence Pack from V3, with context_hash binding.
    """
    mtcp_table = {
        "name": "mtcp_deployment_governance",
        "hit_policy": "FIRST",
        "rules": [
            {
                "conditions": [
                    {"field": "regime_classification", "op": "==", "value": "R3"},
                    {"field": "data_classification", "op": ">=", "value": "Restricted"},
                ],
                "outcome": "DENY",
                "description": "MTCP-R1: Regime 3 model denied for restricted data processing",
            },
            {
                "conditions": [
                    {"field": "ve_lang", "op": "<", "value": 0.7},
                    {"field": "jurisdiction", "op": "==", "value": "multilingual"},
                ],
                "outcome": "DENY",
                "description": "MTCP-R2: Language constraint failure rate unacceptable for multilingual deployment",
            },
            {
                "conditions": [{"field": "overall_grade", "op": "==", "value": "F"}],
                "outcome": "DENY",
                "description": "MTCP-R3: Model failed minimum constraint reliability threshold",
            },
            {
                "conditions": [{"field": "cpd_score", "op": ">", "value": 15}],
                "outcome": "DENY",
                "description": "MTCP-R4: Benchmark contamination too high for reliable evidence",
            },
            {
                "conditions": [
                    {"field": "regime_classification", "op": "==", "value": "R1"},
                    {"field": "overall_grade", "op": "in", "value": ["A", "B"]},
                ],
                "outcome": "PERMIT",
                "description": "MTCP-R5: Model meets deployment-ready threshold",
            },
            {
                "conditions": [
                    {"field": "regime_classification", "op": "==", "value": "R2"},
                    {"field": "overall_grade", "op": "==", "value": "B"},
                ],
                "outcome": "PERMIT",
                "description": "MTCP-R6: Stochastic failure manageable with operational controls",
            },
            {
                "conditions": [],
                "outcome": "INDETERMINATE",
                "description": "MTCP-DEFAULT: Insufficient evidence for automated decision escalate for human review",
            },
        ],
    }
    # Evidence Pack from V3 Section: Worked Example (Step 1 response)
    # plus deployment-side fields data_classification and jurisdiction
    extra_context = {
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
        "constraint_state_hash": "b2cf12b51e411ec3ca1bd28d856cef8c7c25705d893395c131d8c8764ee1e350",
        "eu_ai_act_art9": True,
        "eu_ai_act_art61": True,
        "nist_ai_rmf": True,
        "nca": False,
        "turn_count": 5600,
        "correction_count": 1950,
        "drift_detected": False,
        "evidence_pack_hash": "89586bf4507cca361db03bd9005d97ddaaec42d1b6dea61ad498965ae172d283",
        "data_classification": "Restricted",
        "jurisdiction": "multilingual",
    }
    ep_hash = "89586bf4507cca361db03bd9005d97ddaaec42d1b6dea61ad498965ae172d283"
    request = {
        "jsonrpc": "2.0",
        "id": 9,
        "method": "tools/call",
        "params": {
            "name": "evaluate_decision",
            "arguments": {
                "table_json": json.dumps(mtcp_table),
                "extra_context": json.dumps(extra_context),
                "instance_id": "gpt-4o",
                "instance_version": "2024-08-06",
                "previous_hash": None,
                "context_hash": ep_hash,
            },
        },
    }
    receipt = make_receipt(
        decision=Decision.DENY,
        reasoning="First matching rule (#0): MTCP-R1: Regime 3 model denied for restricted data processing",
        status_code=StatusCode.OK,
        instance_id="gpt-4o",
        instance_version="2024-08-06",
        previous_hash=None,
        dimensions_checked=["regime_classification", "data_classification"],
        context_hash=ep_hash,
    )
    response = {
        "jsonrpc": "2.0",
        "id": 9,
        "result": {
            "decision": "DENY",
            "matched_rules": [0],
            "reasoning": "First matching rule (#0): MTCP-R1: Regime 3 model denied for restricted data processing",
            "errors": [],
            "receipt": receipt.to_dict(),
        },
    }
    return {"name": "mtcp_gpt4o_full_worked_example", "request": request, "response": response}


def fixture_9_verify_evidence_pack() -> dict:
    """Standalone verify_evidence_pack tool call against V3 worked-example EP."""
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
        "constraint_state_hash": "b2cf12b51e411ec3ca1bd28d856cef8c7c25705d893395c131d8c8764ee1e350",
        "eu_ai_act_art9": True,
        "eu_ai_act_art61": True,
        "nist_ai_rmf": True,
        "nca": False,
        "turn_count": 5600,
        "correction_count": 1950,
        "drift_detected": False,
        "evidence_pack_hash": "89586bf4507cca361db03bd9005d97ddaaec42d1b6dea61ad498965ae172d283",
    }
    request = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {
            "name": "verify_evidence_pack",
            "arguments": {
                "evidence_pack": json.dumps(ep),
            },
        },
    }
    response = {
        "jsonrpc": "2.0",
        "id": 10,
        "result": {
            "valid": True,
            "computed_hash": "89586bf4507cca361db03bd9005d97ddaaec42d1b6dea61ad498965ae172d283",
            "expected_hash": "89586bf4507cca361db03bd9005d97ddaaec42d1b6dea61ad498965ae172d283",
        },
    }
    return {"name": "verify_evidence_pack_v3_worked_example", "request": request, "response": response}


def main():
    fixtures = [
        fixture_1_basic_deny(),
        fixture_2_basic_permit(),
        fixture_3_with_instance_identity(),
        fixture_4_multi_field_deny(),
        fixture_5_no_match_not_applicable(),
        fixture_6_unique_violation_processing_error(),
        fixture_7_chain_genesis_then_link(),
        fixture_8_mtcp_gpt4o_full_worked_example(),
        fixture_9_verify_evidence_pack(),
    ]

    out_dir = Path(__file__).parent
    bundle = {
        "sdcgovernance_version": __version__,
        "pinned_timestamp": PINNED_TIMESTAMP,
        "canonicalization": "RFC 8785: sort_keys=True, separators=(',', ':'), ensure_ascii=False",
        "notes": (
            "Each fixture is a JSON-RPC 2.0 request/response pair against the "
            "sdcgovernance MCP server. Timestamps in the response receipts are "
            "pinned to the value above so receipt_hash is reproducible. To "
            "verify: install sdcgovernance==4.0.4, construct a Receipt with "
            "the same content fields and the pinned timestamp, and check that "
            "receipt.receipt_hash matches."
        ),
        "fixtures": fixtures,
    }

    bundle_path = out_dir / "fixtures.json"
    with bundle_path.open("w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False)
    print(f"Wrote {bundle_path}")

    # Also write per-scenario files for easy consumption
    for fx in fixtures:
        fx_path = out_dir / f"fixture_{fx['name']}.json"
        with fx_path.open("w", encoding="utf-8") as f:
            json.dump(fx, f, indent=2, ensure_ascii=False)
        print(f"Wrote {fx_path}")


if __name__ == "__main__":
    main()
