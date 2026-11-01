"""Immutable M9.5 qualification policy value and exact numeric identity."""

from dataclasses import dataclass, field
from decimal import Decimal
import hashlib
import json


QUALIFICATION_POLICY_SCHEMA_ID = "kanasu.qualification-policy.v1"


def _decimal_identity(value: Decimal) -> dict[str, str | int]:
    """Canonical numeric value without changing the active Decimal context."""
    if value.is_zero():
        return {"digits": "0", "exponent": 0}

    parts = value.as_tuple()
    digits = list(parts.digits)
    exponent = parts.exponent
    while digits[-1] == 0:
        digits.pop()
        exponent += 1
    return {"digits": "".join(map(str, digits)), "exponent": exponent}


@dataclass(frozen=True)
class QualificationPolicy:
    """Unactivated, immutable historical Backtest qualification threshold."""

    version: int
    net_profitable_trade_rate_threshold_pct: Decimal
    policy_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.version) is not int or self.version <= 0:
            raise ValueError("version must be a positive integer")

        threshold = self.net_profitable_trade_rate_threshold_pct
        if not isinstance(threshold, Decimal) or not threshold.is_finite():
            raise ValueError("threshold must be a finite Decimal")
        if threshold < Decimal("0") or threshold > Decimal("100"):
            raise ValueError("threshold must be between 0 and 100 inclusive")

        payload = {
            "schema": QUALIFICATION_POLICY_SCHEMA_ID,
            "version": self.version,
            "threshold_pct": _decimal_identity(threshold),
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        object.__setattr__(
            self,
            "policy_id",
            "sha256:" + hashlib.sha256(encoded).hexdigest(),
        )
