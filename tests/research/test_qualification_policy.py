"""M9.5 passive immutable policy tests: no activation or database changes."""

from dataclasses import FrozenInstanceError
from decimal import Decimal, Inexact, Rounded, localcontext

import pytest

from core.research.models.qualification_policy import (
    QUALIFICATION_POLICY_SCHEMA_ID,
    QualificationPolicy,
)


@pytest.mark.parametrize("threshold", ["0", "50", "50.25", "100"])
def test_policy_accepts_valid_boundaries(threshold):
    policy = QualificationPolicy(1, Decimal(threshold))
    assert policy.net_profitable_trade_rate_threshold_pct == Decimal(threshold)
    assert policy.policy_id.startswith("sha256:")
    assert len(policy.policy_id) == len("sha256:") + 64


@pytest.mark.parametrize("version", [0, -1, True, 1.0, "1"])
def test_policy_rejects_invalid_versions(version):
    with pytest.raises(ValueError, match="positive integer"):
        QualificationPolicy(version, Decimal("50"))


@pytest.mark.parametrize(
    "threshold",
    [
        Decimal("-0.0001"), Decimal("100.0001"),
        Decimal("NaN"), Decimal("sNaN"),
        Decimal("Infinity"), Decimal("-Infinity"),
        50, 50.0, "50", True,
    ],
)
def test_policy_rejects_invalid_thresholds(threshold):
    with pytest.raises(ValueError, match="threshold"):
        QualificationPolicy(1, threshold)


def test_policy_is_immutable():
    policy = QualificationPolicy(1, Decimal("50"))
    with pytest.raises(FrozenInstanceError):
        policy.version = 2
    with pytest.raises(FrozenInstanceError):
        policy.net_profitable_trade_rate_threshold_pct = Decimal("60")
    with pytest.raises(FrozenInstanceError):
        policy.policy_id = "changed"


def test_policy_identity_is_deterministic_and_versioned():
    first = QualificationPolicy(1, Decimal("50.00"))
    same = QualificationPolicy(1, Decimal("5E+1"))
    next_version = QualificationPolicy(2, Decimal("50"))
    next_threshold = QualificationPolicy(1, Decimal("50.0001"))
    assert first.policy_id == same.policy_id
    assert first.policy_id != next_version.policy_id
    assert first.policy_id != next_threshold.policy_id
    assert QUALIFICATION_POLICY_SCHEMA_ID == "kanasu.qualification-policy.v1"


def test_threshold_is_mandatory_no_default():
    with pytest.raises(TypeError):
        QualificationPolicy(version=1)


def test_high_precision_near_values_have_distinct_identity():
    p1 = QualificationPolicy(1, Decimal("50.12345678901234567890123456781"))
    p2 = QualificationPolicy(1, Decimal("50.12345678901234567890123456782"))
    assert p1.policy_id != p2.policy_id


def test_identity_is_independent_of_decimal_precision():
    with localcontext() as ctx:
        ctx.prec = 2
        low_precision = QualificationPolicy(1, Decimal("50.25"))
    with localcontext() as ctx:
        ctx.prec = 80
        high_precision = QualificationPolicy(1, Decimal("50.25"))
    assert low_precision.policy_id == high_precision.policy_id


def test_positive_and_negative_zero_identical():
    a = QualificationPolicy(1, Decimal("0"))
    b = QualificationPolicy(1, Decimal("-0E-1000000"))
    assert a.policy_id == b.policy_id


def test_identity_does_not_invoke_inexact_or_rounded_traps():
    with localcontext() as ctx:
        ctx.prec = 2
        ctx.traps[Inexact] = True
        ctx.traps[Rounded] = True
        p1 = QualificationPolicy(1, Decimal("50.25"))
    p2 = QualificationPolicy(1, Decimal("50.250"))
    assert p1.policy_id == p2.policy_id


def test_trailing_zeros_and_scientific_notation_canonical():
    representations = ["5E1", "50", "50.00000", "5000E-2"]
    assert len({QualificationPolicy(1, Decimal(x)).policy_id for x in representations}) == 1


def test_tiny_nonzero_precision_is_retained():
    a = QualificationPolicy(1, Decimal("0.0000000000000000000000001"))
    b = QualificationPolicy(1, Decimal("0.0000000000000000000000002"))
    assert a.policy_id != b.policy_id
