#
# Copyright (c), 2025, Axius-SDC, Inc.
# All rights reserved.
# This file is distributed under the terms of the Apache 2.0 License.
#
"""
RFC 8785 JSON Canonicalization Scheme (JCS).

Every hash in this library commits to *bytes*, so a hash is only meaningful
if an independent implementation derives the same bytes from the same data.
Before this module, canonicalization was::

    json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

which is the right shape but is not RFC 8785. It diverges in three places,
and each divergence is silent: the signature simply fails to verify, and the
failure is indistinguishable from tampering.

1. **Numbers.** JCS requires ECMAScript ``Number::toString`` (RFC 8785
   §3.2.2.3). Python's ``json`` emits ``1.0`` where ECMAScript emits ``1``,
   ``1e+16`` where ECMAScript emits ``10000000000000000``, and ``1e-07``
   where ECMAScript emits ``1e-7``. Any float anywhere in a document is
   enough to break agreement.
2. **Key ordering.** JCS sorts by UTF-16 code unit (RFC 8785 §3.2.3);
   ``sort_keys=True`` sorts by Unicode code point. These disagree for
   astral-plane characters, because a surrogate pair begins at U+D800 and
   therefore sorts *before* U+E000..U+FFFF in UTF-16 but *after* them by
   code point.
3. **String escaping.** JCS fixes the escape set (RFC 8785 §3.2.2.2):
   the two-character forms for the six characters that have them, ``\\u00xx``
   with lowercase hex for the remaining C0 controls, and nothing else
   escaped. ``ensure_ascii=False`` is close but does not pin the control
   character forms.

Interoperability is verified by differential testing against Node.js, which
is a real ECMAScript implementation rather than a second reading of the
same spec. See ``tests/test_jcs.py``.
"""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any

__all__ = [
    "CANONICALIZATION_ID",
    "JCSError",
    "canonicalize",
    "canonicalize_bytes",
]

#: Value for the ``canonicalization`` field carried on artifacts produced
#: under this scheme. Receipts written before RFC 8785 conformance have no
#: such field, which is what keeps the two eras distinguishable.
CANONICALIZATION_ID = "rfc8785"

#: Largest integer exactly representable as an IEEE 754 double. JSON numbers
#: are doubles (RFC 8785 §3.2.2.3), so an integer beyond this cannot survive
#: a round trip through a conformant implementation.
_MAX_SAFE_INTEGER = 2**53 - 1

# RFC 8785 §3.2.2.2. Only these six take a two-character form.
_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
}


class JCSError(ValueError):
    """
    Raised when a value has no interoperable canonical form.

    Deliberately an error rather than a best effort. Emitting bytes that a
    conformant implementation would not reproduce is worse than refusing,
    because the resulting hash looks valid and fails only at verification
    time, in someone else's hands.
    """


def _serialize_string(value: str) -> str:
    """Serialize a string per RFC 8785 §3.2.2.2."""
    out = ['"']
    for ch in value:
        escape = _ESCAPES.get(ch)
        if escape is not None:
            out.append(escape)
        elif ch < "\x20":
            out.append(f"\\u{ord(ch):04x}")
        else:
            # Non-ASCII is emitted literally; the output is UTF-8.
            out.append(ch)
    out.append('"')
    return "".join(out)


def _es_number_to_string(value: float) -> str:
    """
    Format a positive, finite float per ECMAScript ``Number::toString``.

    Python's ``repr`` already yields the shortest digit string that round
    trips, which is the same digit selection ECMAScript makes. What differs
    is the *presentation*, so this takes those digits and applies the
    ECMAScript layout rules: fixed notation while the decimal exponent stays
    within (-7, 21], exponential outside it.
    """
    _, digits, exponent = Decimal(repr(value)).as_tuple()

    # Trailing zeros are presentation, not significance: repr(100.0) is
    # "100.0", whose digits are (1, 0, 0, 0). Fold them into the exponent so
    # `k` below is the true significant-digit count.
    significant = list(digits)
    while len(significant) > 1 and significant[-1] == 0:
        significant.pop()
        exponent += 1

    s = "".join(str(d) for d in significant)
    k = len(s)          # number of significant digits
    n = exponent + k    # position of the decimal point, ECMAScript's `n`

    if k <= n <= 21:
        # Integer with trailing zeros: 1e16 -> "10000000000000000"
        return s + "0" * (n - k)
    if 0 < n <= 21:
        # Decimal point inside the digits: 1.5 -> "1.5"
        return f"{s[:n]}.{s[n:]}"
    if -6 < n <= 0:
        # Small magnitude, still fixed notation: 1e-6 -> "0.000001"
        return f"0.{'0' * -n}{s}"

    # Exponential. ECMAScript writes the exponent with an explicit sign and
    # no zero padding, so 1e-7 is "1e-7" and not "1e-07".
    e = n - 1
    mantissa = s if k == 1 else f"{s[0]}.{s[1:]}"
    return f"{mantissa}e{'+' if e >= 0 else '-'}{abs(e)}"


def _serialize_number(value: int | float) -> str:
    """Serialize a number per RFC 8785 §3.2.2.3."""
    if isinstance(value, int):
        if abs(value) > _MAX_SAFE_INTEGER:
            raise JCSError(
                f"Integer {value} exceeds the IEEE 754 double safe range, so a "
                "conformant implementation would read back a different value. "
                "Carry it as a string."
            )
        return str(value)

    if math.isnan(value) or math.isinf(value):
        raise JCSError(
            f"{value!r} has no JSON representation and cannot be canonicalized."
        )
    if value == 0:
        # Covers -0.0, which ECMAScript renders as "0".
        return "0"
    if value < 0:
        return f"-{_es_number_to_string(-value)}"
    return _es_number_to_string(value)


def _serialize(value: Any) -> str:
    """Serialize any supported value per RFC 8785 §3.2."""
    if value is None:
        return "null"
    # Checked before int: bool is a subclass of int in Python.
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _serialize_string(value)
    if isinstance(value, (int, float)):
        return _serialize_number(value)
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise JCSError(
                    f"Object keys must be strings; got {type(key).__name__}."
                )
        # RFC 8785 §3.2.3: sort by UTF-16 code unit, not code point.
        # Encoding to UTF-16-BE and comparing bytes gives exactly that order.
        items = sorted(value.items(), key=lambda kv: kv[0].encode("utf-16-be"))
        body = ",".join(
            f"{_serialize_string(k)}:{_serialize(v)}" for k, v in items
        )
        return f"{{{body}}}"
    if isinstance(value, (list, tuple)):
        return f"[{','.join(_serialize(v) for v in value)}]"

    raise JCSError(
        f"{type(value).__name__} has no JSON representation. Convert it before "
        "canonicalizing rather than relying on a default coercion, which would "
        "not be reproducible by another implementation."
    )


def canonicalize(data: Any) -> str:
    """
    Return the RFC 8785 canonical form of ``data``.

    Args:
        data: JSON-compatible value (dict, list, str, int, float, bool, None).

    Returns:
        The canonical serialization as ``str``.

    Raises:
        JCSError: If any value has no interoperable canonical form.
    """
    return _serialize(data)


def canonicalize_bytes(data: Any) -> bytes:
    """
    Return the RFC 8785 canonical form of ``data`` as UTF-8 bytes.

    This is what should be hashed or signed. RFC 8785 output is defined as
    UTF-8, so encoding is part of canonicalization rather than a caller
    detail.
    """
    return canonicalize(data).encode("utf-8")
