"""
Governed home for decision tables (issue #3).

Until 4.3.0 a decision table was an ephemeral input: ``evaluate_decision``
took ``table_json`` on every call, built a ``DecisionTable`` and threw it
away, and the Receipt it produced named the evidence (``context_hash``) and
the decision but not the policy that made it. Two different tables giving the
same decision on the same evidence produced indistinguishable receipts.

This module gives a table an identity:

- ``decision_table_hash`` (in ``sdcgovernance.decision``): the SHA-256 of the
  table's RFC 8785 canonical JSON, the same convention as ``receipt_hash`` and
  ``evidence_pack_hash``. Two spellings of one table (key order, whitespace,
  a ``description`` left out) hash the same; one changed threshold does not.
- ``TableRegistry``: tables registered under a stable ``table_id`` and an
  immutable ``version``, each carrying its content hash and an optional
  domain and policy label. A registry lives in memory and can be loaded from
  and saved to a directory of JSON files, one per table version, so a
  deployment's policies are files under version control rather than blobs
  passed on every call.

Receipts carry ``table_id``, ``table_version`` and ``table_hash`` inside
``receipt_hash`` (``sdcgovernance.receipts``), so the audit chain is evidence,
policy, decision and outcome, each bound to the others. Inline ``table_json``
keeps working for ad-hoc evaluation; its receipts carry the hash alone.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from sdcgovernance.decision import (
    ComparisonOp,
    Condition,
    DecisionTable,
    HitPolicy,
    Rule,
    decision_table_hash,
    decision_table_to_dict,
)
from sdcgovernance.receipts import Decision

__all__ = [
    "RegisteredTable",
    "TableConflict",
    "TableNotFound",
    "TableRegistry",
    "parse_decision_table",
]

#: A table id or version: letters, digits, dot, underscore, hyphen. The pair
#: becomes a file name when a registry is saved, and a URI-safe token when a
#: receipt is quoted, so the character set is deliberately small.
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class TableNotFound(KeyError):
    """No table is registered under that id (and version)."""


class TableConflict(ValueError):
    """That id and version already hold a table with different content."""


_OP_MAP = {op.value: op for op in ComparisonOp}
_DECISION_MAP = {d.name: d for d in Decision}
_POLICY_MAP = {p.name: p for p in HitPolicy}


def parse_decision_table(data: dict[str, Any]) -> DecisionTable:
    """
    Build a ``DecisionTable`` from its JSON form.

    The JSON form is the one ``evaluate_decision`` documents::

        {"name": "...", "hit_policy": "FIRST|UNIQUE|COLLECT", "description": "...",
         "rules": [{"conditions": [{"field": "...", "op": "==", "value": ...}],
                    "outcome": "PERMIT|DENY|INDETERMINATE|NOT_APPLICABLE",
                    "description": "..."}]}

    Unknown operators, outcomes and hit policies are errors rather than
    defaults: a policy that silently evaluates differently from how it was
    written is worse than one that refuses to load.
    """
    if not isinstance(data, dict):
        raise ValueError("A decision table is a JSON object.")
    policy_name = data.get("hit_policy", "FIRST")
    if policy_name not in _POLICY_MAP:
        raise ValueError(f"Unknown hit_policy {policy_name!r}; expected one of {sorted(_POLICY_MAP)}.")
    rules_data = data.get("rules", [])
    if not isinstance(rules_data, list):
        raise ValueError("`rules` must be a list.")
    rules: list[Rule] = []
    for index, rule_data in enumerate(rules_data):
        if not isinstance(rule_data, dict):
            raise ValueError(f"Rule {index} must be an object.")
        outcome_name = rule_data.get("outcome")
        if outcome_name not in _DECISION_MAP:
            raise ValueError(
                f"Rule {index}: unknown outcome {outcome_name!r}; expected one of {sorted(_DECISION_MAP)}."
            )
        conditions: list[Condition] = []
        for c in rule_data.get("conditions", []) or []:
            if not isinstance(c, dict) or "field" not in c or "op" not in c or "value" not in c:
                raise ValueError(f"Rule {index}: a condition needs `field`, `op` and `value`.")
            if c["op"] not in _OP_MAP:
                raise ValueError(f"Rule {index}: unknown op {c['op']!r}; expected one of {sorted(_OP_MAP)}.")
            conditions.append(Condition(field=str(c["field"]), op=_OP_MAP[c["op"]], value=c["value"]))
        rules.append(Rule(
            conditions=conditions,
            outcome=_DECISION_MAP[outcome_name],
            description=str(rule_data.get("description", "") or ""),
        ))
    return DecisionTable(
        name=str(data.get("name", "") or ""),
        hit_policy=_POLICY_MAP[policy_name],
        rules=rules,
        description=str(data.get("description", "") or ""),
    )


def _version_key(version: str) -> tuple:
    """Order ``1.10`` after ``1.9``; fall back to text for anything else."""
    parts = version.split(".")
    if all(p.isdigit() for p in parts):
        return (0, tuple(int(p) for p in parts))
    return (1, version)


@dataclass(frozen=True)
class RegisteredTable:
    """One version of one table, with the hash that names its content."""
    table_id: str
    version: str
    table: DecisionTable
    table_hash: str
    domain: str = ""
    policy: str = ""
    registered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self, include_table: bool = True) -> dict[str, Any]:
        d: dict[str, Any] = {
            "table_id": self.table_id,
            "version": self.version,
            "table_hash": self.table_hash,
            "domain": self.domain,
            "policy": self.policy,
            "registered_at": self.registered_at,
        }
        if include_table:
            d["table"] = decision_table_to_dict(self.table)
        return d

    @property
    def file_name(self) -> str:
        return f"{self.table_id}--{self.version}.json"


class TableRegistry:
    """
    Decision tables by stable id and immutable version.

    ``register`` is idempotent for identical content and refuses different
    content under an existing id and version (``TableConflict``): a version,
    once registered, means one thing. ``get`` without a version returns the
    highest version (numeric dotted versions compare numerically).
    """

    def __init__(self) -> None:
        self._tables: dict[tuple[str, str], RegisteredTable] = {}

    # -- registration -----------------------------------------------------

    def register(
        self,
        table_id: str,
        version: str,
        table: DecisionTable | dict[str, Any],
        *,
        domain: str = "",
        policy: str = "",
    ) -> RegisteredTable:
        for label, value in (("table_id", table_id), ("version", version)):
            if not isinstance(value, str) or not _TOKEN.match(value):
                raise ValueError(
                    f"`{label}` must be 1-128 characters of letters, digits, '.', '_' or '-', "
                    f"starting with a letter or digit; got {value!r}."
                )
        parsed = table if isinstance(table, DecisionTable) else parse_decision_table(table)
        table_hash = decision_table_hash(parsed)
        existing = self._tables.get((table_id, version))
        if existing is not None:
            if existing.table_hash != table_hash:
                raise TableConflict(
                    f"{table_id} version {version} is already registered with hash "
                    f"{existing.table_hash}; register the changed table under a new version."
                )
            return existing
        entry = RegisteredTable(
            table_id=table_id, version=version, table=parsed, table_hash=table_hash,
            domain=domain or "", policy=policy or "",
        )
        self._tables[(table_id, version)] = entry
        return entry

    # -- lookup -----------------------------------------------------------

    def get(self, table_id: str, version: str | None = None) -> RegisteredTable:
        if version is not None:
            try:
                return self._tables[(table_id, version)]
            except KeyError:
                raise TableNotFound(f"No decision table {table_id!r} version {version!r} is registered.") from None
        versions = self.versions(table_id)
        if not versions:
            raise TableNotFound(f"No decision table {table_id!r} is registered.")
        return self._tables[(table_id, versions[-1])]

    def versions(self, table_id: str) -> list[str]:
        """Registered versions of a table, lowest first."""
        return sorted((v for (i, v) in self._tables if i == table_id), key=_version_key)

    def list(self, *, table_id: str | None = None, domain: str | None = None) -> list[RegisteredTable]:
        entries = [
            e for e in self._tables.values()
            if (table_id is None or e.table_id == table_id)
            and (domain is None or e.domain == domain)
        ]
        return sorted(entries, key=lambda e: (e.table_id, _version_key(e.version)))

    def find_by_hash(self, table_hash: str) -> list[RegisteredTable]:
        """Every registration whose content has that hash (a receipt's ``table_hash``)."""
        return [e for e in self.list() if e.table_hash == table_hash]

    def __len__(self) -> int:
        return len(self._tables)

    def clear(self) -> None:
        """Forget every registration (tests; a process restart does the same)."""
        self._tables.clear()

    def __contains__(self, key: object) -> bool:
        if isinstance(key, tuple):
            return key in self._tables
        return any(i == key for (i, _v) in self._tables)

    # -- files ------------------------------------------------------------

    def save(self, directory: str | Path) -> list[Path]:
        """Write one JSON file per registered version; returns the paths."""
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        written = []
        for entry in self.list():
            path = root / entry.file_name
            path.write_text(json.dumps(entry.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
            written.append(path)
        return written

    def save_one(self, directory: str | Path, entry: RegisteredTable) -> Path:
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        path = root / entry.file_name
        path.write_text(json.dumps(entry.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def load(self, directory: str | Path) -> list[RegisteredTable]:
        """
        Register every ``*.json`` file in ``directory`` (not recursive).

        A file holds one object ``{"table_id", "version", "table", "domain"?,
        "policy"?}`` or a list of them. A stored ``table_hash`` is checked
        against the content: a file whose table no longer matches its recorded
        hash was edited after registration and is refused.
        """
        root = Path(directory)
        if not root.is_dir():
            raise FileNotFoundError(f"Decision table directory {root} does not exist.")
        loaded: list[RegisteredTable] = []
        for path in sorted(root.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            records: Iterable[Any] = data if isinstance(data, list) else [data]
            for record in records:
                if not isinstance(record, dict) or "table_id" not in record or "version" not in record or "table" not in record:
                    raise ValueError(f"{path}: each record needs `table_id`, `version` and `table`.")
                entry = self.register(
                    record["table_id"], record["version"], record["table"],
                    domain=record.get("domain", ""), policy=record.get("policy", ""),
                )
                recorded = record.get("table_hash")
                if recorded and recorded != entry.table_hash:
                    raise ValueError(
                        f"{path}: table content hashes to {entry.table_hash} but the file records "
                        f"{recorded}; the table was changed after it was registered."
                    )
                loaded.append(entry)
        return loaded

    @classmethod
    def from_directory(cls, directory: str | Path) -> "TableRegistry":
        registry = cls()
        registry.load(directory)
        return registry
