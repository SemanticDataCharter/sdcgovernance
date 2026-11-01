"""
Build the decision-table and governance-Receipt vectors from this library.

    PYTHONPATH=src python test-vectors/build_governance_vectors.py

Every expected value is what sdcgovernance itself computes, so the files say
what the reference does, and ``tests/test_governance_vectors.py`` fails if the
library and the files ever disagree. The cases are chosen where another
language reads the same JSON differently: Python's ``True == 1``, ``in`` as a
substring test on strings and a key test on objects, string order by code
point, comparisons across types, and the legacy ``json.dumps`` rendering.

Nothing here is random and every timestamp is fixed, so a rebuild without a
library change writes identical files.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from sdcgovernance import __version__
from sdcgovernance.decision import decision_table_hash, evaluate_decision_table
from sdcgovernance.receipts import LEGACY_CANONICALIZATION, Decision, Obligation, Receipt, StatusCode
from sdcgovernance.tables import TableConflict, TableRegistry, parse_decision_table

HERE = Path(__file__).parent

RISK = {
    "name": "shipment-risk",
    "hit_policy": "FIRST",
    "description": "Release on risk and attestation",
    "rules": [
        {"conditions": [{"field": "risk_score", "op": ">=", "value": 7}], "outcome": "DENY", "description": "high risk"},
        {"conditions": [{"field": "risk_score", "op": ">=", "value": 3}, {"field": "attestation_level", "op": "==", "value": "senior"}],
         "outcome": "PERMIT", "description": "medium risk, senior attestation"},
        {"conditions": [{"field": "risk_score", "op": "<", "value": 3}], "outcome": "PERMIT", "description": "low risk"},
    ],
}

PROTOCOL = {
    "name": "protocol-unique",
    "hit_policy": "UNIQUE",
    "rules": [
        {"conditions": [{"field": "protocol", "op": "in", "value": ["HIPAA", "GDPR"]}], "outcome": "PERMIT", "description": "recognised protocol"},
        {"conditions": [{"field": "current_state", "op": "==", "value": "review"}], "outcome": "INDETERMINATE"},
        {"conditions": [{"field": "protocol", "op": "not_in", "value": ["HIPAA", "GDPR"]}, {"field": "current_state", "op": "!=", "value": "review"}],
         "outcome": "DENY", "description": "unrecognised protocol"},
    ],
}

COLLECT = {
    "name": "collect-restrictive",
    "hit_policy": "COLLECT",
    "rules": [
        {"conditions": [{"field": "amount", "op": "<=", "value": 1000}], "outcome": "PERMIT", "description": "within limit"},
        {"conditions": [{"field": "region", "op": "==", "value": "EU"}], "outcome": "NOT_APPLICABLE", "description": "no EU rule"},
        {"conditions": [{"field": "flagged", "op": "==", "value": True}], "outcome": "INDETERMINATE", "description": "flagged for review"},
        {"conditions": [{"field": "amount", "op": ">", "value": 5000}], "outcome": "DENY", "description": "over hard limit"},
        {"conditions": [], "outcome": "PERMIT"},
    ],
}

# Where two languages read one JSON value differently.
SEMANTICS = {
    "name": "cross-language-semantics",
    "hit_policy": "COLLECT",
    "rules": [
        {"conditions": [{"field": "n", "op": "==", "value": 1}], "outcome": "PERMIT", "description": "n == 1 (true == 1 in Python)"},
        {"conditions": [{"field": "word", "op": "in", "value": "shipped,paid"}], "outcome": "PERMIT", "description": "substring of a string"},
        {"conditions": [{"field": "key", "op": "in", "value": {"a": 1, "b": 2}}], "outcome": "PERMIT", "description": "key of an object"},
        {"conditions": [{"field": "flag", "op": "in", "value": [1, 2]}], "outcome": "PERMIT", "description": "true in [1, 2]"},
        {"conditions": [{"field": "s", "op": ">", "value": "￿"}], "outcome": "PERMIT", "description": "code point order"},
        {"conditions": [{"field": "tags", "op": "==", "value": ["a", "b"]}], "outcome": "PERMIT", "description": "list equality"},
        {"conditions": [{"field": "tags", "op": "<", "value": ["a", "c"]}], "outcome": "PERMIT", "description": "list order"},
        {"conditions": [{"field": "mixed", "op": "<", "value": 3}], "outcome": "DENY", "description": "order across types is false"},
        {"conditions": [{"field": "mixed", "op": "!=", "value": 3}], "outcome": "INDETERMINATE", "description": "inequality across types is true"},
        {"conditions": [{"field": "obj", "op": "==", "value": {"x": [1, 2.5]}}], "outcome": "PERMIT", "description": "object equality"},
    ],
}

EVALUATIONS = {
    "RISK": (RISK, [
        {"risk_score": 8},
        {"risk_score": 5, "attestation_level": "senior"},
        {"risk_score": 5, "attestation_level": "junior"},
        {"risk_score": 2.5},
        {"risk_score": 7.0},
        {"risk_score": "8"},
        {"risk_score": None},
        {},
        {"risk_score": True},
    ]),
    "PROTOCOL": (PROTOCOL, [
        {"protocol": "HIPAA", "current_state": "approved"},
        {"protocol": "HIPAA", "current_state": "review"},
        {"protocol": "FERPA", "current_state": "approved"},
        {"protocol": "FERPA", "current_state": "review"},
        {"current_state": "approved"},
    ]),
    "COLLECT": (COLLECT, [
        {"amount": 500},
        {"amount": 500, "region": "EU"},
        {"amount": 500, "flagged": True},
        {"amount": 9000, "flagged": True},
        {"flagged": 1},
        {},
    ]),
    "SEMANTICS": (SEMANTICS, [
        {"n": True},
        {"n": 1.0},
        {"n": "1"},
        {"word": "ship"},
        {"word": "refunded"},
        {"key": "a"},
        {"key": "x"},
        {"flag": True},
        {"s": "\U0001F600"},
        {"s": ""},
        {"tags": ["a", "b"]},
        {"tags": ["a", "b", "z"]},
        {"tags": ["b"]},
        {"mixed": "x"},
        {"mixed": [3]},
        {"obj": {"x": [1, 2.5]}},
        {"obj": {"x": [1, 2]}},
    ]),
}

# Two spellings of one table hash the same; one changed threshold does not.
SPELLINGS = [
    {"description": "key order and whitespace do not matter",
     "tables": [RISK, json.loads(json.dumps(RISK, sort_keys=True))], "same_hash": True},
    {"description": "an absent description, an empty one and null are the same",
     "tables": [{"rules": [{"conditions": [], "outcome": "PERMIT"}]},
                {"name": "", "description": "", "hit_policy": "FIRST", "rules": [{"conditions": None, "outcome": "PERMIT", "description": None}]}],
     "same_hash": True},
    {"description": "a non-string field name is read as Python str() reads it",
     "tables": [{"name": "t", "rules": [{"conditions": [{"field": 1, "op": "==", "value": 1}], "outcome": "PERMIT"}]},
                {"name": "t", "rules": [{"conditions": [{"field": "1", "op": "==", "value": 1}], "outcome": "PERMIT"}]}],
     "same_hash": True},
    {"description": "one changed threshold changes the hash",
     "tables": [RISK, {**RISK, "rules": [{**RISK["rules"][0], "conditions": [{"field": "risk_score", "op": ">=", "value": 8}]}] + RISK["rules"][1:]}],
     "same_hash": False},
]

REFUSED = [
    {"description": "not an object", "table": ["rules"]},
    {"description": "unknown hit policy", "table": {"hit_policy": "ANY", "rules": []}},
    {"description": "a null hit policy", "table": {"hit_policy": None, "rules": []}},
    {"description": "rules not a list", "table": {"rules": {"0": {}}}},
    {"description": "a rule not an object", "table": {"rules": ["PERMIT"]}},
    {"description": "unknown outcome", "table": {"rules": [{"conditions": [], "outcome": "ALLOW"}]}},
    {"description": "unknown operator", "table": {"rules": [{"conditions": [{"field": "a", "op": "=", "value": 1}], "outcome": "PERMIT"}]}},
    {"description": "a condition without a value", "table": {"rules": [{"conditions": [{"field": "a", "op": "=="}], "outcome": "PERMIT"}]}},
]

# Evaluations that raise in the reference rather than decide: `in` against a
# value that is not a container is a TypeError in Python and is not caught.
RAISES = [
    {"description": "`in` against a number", "table": {"rules": [{"conditions": [{"field": "a", "op": "in", "value": 5}], "outcome": "PERMIT"}]},
     "context": {"a": 5}},
]


def evaluation(table: dict, context: dict) -> dict:
    result = evaluate_decision_table(parse_decision_table(table), context)
    return {"context": context, "decision": result.decision.name, "matched_rules": result.matched_rules,
            "reasoning": result.reasoning, "errors": result.errors}


def registry_vectors() -> dict:
    registry = TableRegistry()
    order = ["1.10", "1.9", "2", "1.2.3", "beta", "1.9.0", "alpha"]
    for v in order:
        registry.register("risk", v, RISK)
    try:
        registry.register("risk", "2", {**RISK, "name": "changed"})
        conflict = False
    except TableConflict:
        conflict = True
    return {
        "registered_in_order": order,
        "versions": registry.versions("risk"),
        "latest": registry.get("risk").version,
        "same_content_again_is_accepted": registry.register("risk", "2", RISK).version == "2",
        "different_content_same_version_is_refused": conflict,
        "invalid_tokens": [t for t in ["", ".hidden", "a b", "a/b", "x" * 129] if not _accepts_token(t)],
    }


def _accepts_token(token: str) -> bool:
    try:
        TableRegistry().register(token, "1", RISK)
        return True
    except ValueError:
        return False


def decision_tables() -> dict:
    cases = []
    for name, (table, contexts) in EVALUATIONS.items():
        cases.append({"name": name.lower(), "table": table, "table_hash": decision_table_hash(parse_decision_table(table)),
                      "evaluations": [evaluation(table, c) for c in contexts]})
    spellings = [{**s, "hashes": [decision_table_hash(parse_decision_table(t)) for t in s["tables"]]} for s in SPELLINGS]
    for s in spellings:
        assert (len(set(s["hashes"])) == 1) == s["same_hash"], s["description"]
    refused = []
    for r in REFUSED:
        try:
            parse_decision_table(r["table"])
        except ValueError:
            refused.append(r)
            continue
        raise AssertionError(f"not refused: {r['description']}")
    raises = []
    for r in RAISES:
        try:
            evaluate_decision_table(parse_decision_table(r["table"]), r["context"])
        except TypeError:
            raises.append(r)
            continue
        raise AssertionError(f"did not raise: {r['description']}")
    return {
        "$comment": "Built by build_governance_vectors.py from sdcgovernance itself; tests/test_governance_vectors.py holds the library to it.",
        "specification": "sdcgovernance decision tables: parse_decision_table, decision_table_hash, evaluate_decision_table, TableRegistry",
        "sdcgovernance_version": __version__,
        "cases": cases,
        "spellings": spellings,
        "refused": refused,
        "raises": raises,
        "registry": registry_vectors(),
    }


def governance_receipts() -> dict:
    ts = "2026-11-01T12:00:00+00:00"
    table = parse_decision_table(RISK)
    built = [
        ("a PERMIT, nothing optional", Receipt(decision=Decision.PERMIT, reasoning="workflow transition permitted", instance_id="i-1",
                                                 instance_version="1", timestamp=ts, dimensions_checked=["workflow"])),
        ("a DENY with errors and a previous hash", Receipt(decision=Decision.DENY, reasoning="role missing", instance_id="i-1", instance_version="2",
                                                            timestamp=ts, previous_hash="ab" * 32, dimensions_checked=["workflow", "party_role"],
                                                            errors=["party lacks role approver"], status_code=StatusCode.OK)),
        ("obligations are inside the hash", Receipt(decision=Decision.PERMIT, instance_id="i-2", timestamp=ts, obligations=[
            Obligation(obligation_id="notify", description="tell the buyer", attributes={"within_hours": 24, "rate": 1.5, "to": ["buyer"]}),
            Obligation(obligation_id="log", is_obligation=False)])),
        ("source lineage is inside the hash when present", Receipt(decision=Decision.PERMIT, instance_id="i-3", timestamp=ts,
                                                                    source_instance_id="EPIC-998", source_version_id="7")),
        ("the policy is inside the hash", Receipt(decision=Decision.DENY, reasoning="First matching rule (#0): high risk", instance_id="i-4",
                                                   timestamp=ts, context_hash="cd" * 32, table_id="shipment-risk", table_version="1.2",
                                                   table_hash=decision_table_hash(table))),
        ("non-ASCII and astral text", Receipt(decision=Decision.NOT_APPLICABLE, reasoning="No rules matched in decision table 'café \U0001F69A'",
                                               instance_id="i-5", timestamp=ts, status_code=StatusCode.MISSING_ATTRIBUTE)),
        ("legacy canonicalization, no numbers", Receipt(decision=Decision.PERMIT, reasoning="legacy", instance_id="i-6", timestamp=ts,
                                                         canonicalization=LEGACY_CANONICALIZATION, errors=["tab\there", "quote\" and \\"])),
    ]
    vectors = []
    for description, receipt in built:
        wire = receipt.to_dict()
        if receipt.canonicalization == LEGACY_CANONICALIZATION:
            # Receipts hashed before RFC 8785 carry no `canonicalization` on the wire.
            del wire["canonicalization"]
        vectors.append({"description": description, "receipt": wire, "verifies": True})
    tampered = json.loads(json.dumps(vectors[2]["receipt"]))
    tampered["obligations"][0]["attributes"]["within_hours"] = 48
    vectors.append({"description": "an obligation changed after hashing", "receipt": tampered, "verifies": False})
    swapped = json.loads(json.dumps(vectors[4]["receipt"]))
    swapped["table_version"] = "1.3"
    vectors.append({"description": "the policy version changed after hashing", "receipt": swapped, "verifies": False})
    return {
        "$comment": "Built by build_governance_vectors.py from sdcgovernance itself; tests/test_governance_vectors.py holds the library to it.",
        "specification": "sdcgovernance governance Receipts: receipt_hash over the content Receipt._compute_hash names",
        "sdcgovernance_version": __version__,
        "legacy_canonicalization": LEGACY_CANONICALIZATION,
        "vectors": vectors,
    }


def write(name: str, doc: dict) -> None:
    (HERE / name).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write("decision-tables.json", decision_tables())
    write("governance-receipts.json", governance_receipts())
    print("wrote decision-tables.json and governance-receipts.json")
