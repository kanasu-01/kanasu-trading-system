"""M9.4q financial conservation and settlement regressions.

Repository-native transfer of the SHA-verified independent
Codex audit cases. The tests have no reviewer workspace
dependency and intentionally expose previously accepted
invalid financial histories.

M9.4q source implementation is the corrected local candidate under synchronization review; these regressions preserve the independent counterexamples.
"""

import copy
from datetime import datetime, timedelta, timezone

import pytest

from core.research.reproducibility import (
    BACKTEST_RESULT_SCHEMA,
    canonical_bytes,
    decode_stable_backtest_result_bytes as decode,
    validate_stable_backtest_result_payload as validate,
)

T = datetime(2026, 10, 1, 9, 15, tzinfo=timezone.utc)


def bar(i, cash=1000., pos=0, price=100., event=None, qty=None, fill=None):
    return dict(timestamp=T+timedelta(minutes=5*i),open=price,high=price+1,low=price-1,close=price,volume=1000.,strategy='fresh-review',state=None,signal=None,execution_event=event,execution_price=fill,execution_quantity=qty,decision_snapshot={},equity=cash+pos*price,cash=cash,position_size=pos,drawdown=0.)


def trade(entry=1,exit=2,q=1,ep=100.,xp=110.,cost=0.):
    return dict(symbol='RELIANCE',entry_time=T+timedelta(minutes=5*entry),exit_time=None if exit is None else T+timedelta(minutes=5*exit),entry_price=ep,exit_price=xp,stop_price=90.,quantity=q,direction='LONG',exit_reason='SELL',gross_pnl=(xp-ep)*q,transaction_cost=cost,pnl=(xp-ep)*q-cost,pnl_pct=(xp-ep)/ep*100)


def payload(bars,trades=()):
    return dict(trades=list(trades),bar_records=bars,equity_curve=[(b['timestamp'],b['equity']) for b in bars])


def cases():
    good=payload([bar(0),bar(1,900,1,event='BUY',qty=1,fill=100.),bar(2,1010,event='SELL',qty=1,fill=110.)],[trade()])
    nullable=copy.deepcopy(good); nullable['trades'][0]['exit_time']=None
    yield 'profit_control',good,True
    yield 'nullable_control',nullable,True
    yield 'cost_control',payload([bar(0),bar(1,899,1,event='BUY',qty=1,fill=100.),bar(2,1008,event='SELL',qty=1,fill=110.)],[trade(cost=2.)]),True
    yield 'open_control',payload([bar(0),bar(1,900,1,event='BUY',qty=1,fill=100.),bar(2,900,1)]),True
    yield 'zero_cash_control',payload([bar(0,100),bar(1,0,1,event='BUY',qty=1,fill=100.)]),True
    yield 'terminal_deposit_negative_control',payload([bar(0),bar(1,900,1),bar(2,2010,event='SELL',qty=1,fill=110.)],[trade()]),False
    yield 'first_bar_holdings_bypass',payload([bar(0,900,1),bar(1,5000,event='SELL',qty=1,fill=100.)],[trade(entry=0,exit=1,xp=100.)]),False
    yield 'unchanged_open_holdings_deposit',payload([bar(0),bar(1,900,1,event='BUY',qty=1,fill=100.),bar(2,5000,1)]),False
    yield 'unfunded_entry',payload([bar(0),bar(1,1000,1,event='BUY',qty=1,fill=100.)]),False
    yield 'free_extra_shares',payload([bar(0),bar(1,900,1,event='BUY',qty=1,fill=100.),bar(2,900,100)]),False
    yield 'nullable_transient_deposit',payload([bar(0),bar(1,900,1,event='BUY',qty=1,fill=100.),bar(2,5010,event='SELL',qty=1,fill=110.),bar(3,1010)],[trade(exit=None)]),False
    yield 'nullable_reused_for_two_reductions',payload([bar(0),bar(1,800,2,event='BUY',qty=2,fill=100.),bar(2,900,1,event='SELL',qty=1,fill=100.),bar(3,1000,event='SELL',qty=1,fill=100.)],[trade(exit=None,xp=100.)]),False
    yield 'nullable_same_bar_no_diagnostics',payload([bar(0),bar(1,1010)],[trade(entry=1,exit=None)]),False
    yield 'nullable_same_bar_wrong_event',payload([bar(0),bar(1,1010,event='BUY',qty=1,fill=110.)],[trade(entry=1,exit=None)]),False
    for field,value in [('execution_event','BUY'),('execution_price',109.),('execution_quantity',2)]:
        p=copy.deepcopy(nullable);p['bar_records'][2][field]=value
        yield 'nullable_bad_'+field,p,False
    p=copy.deepcopy(good);p['trades'][0]['quantity']=True;yield 'bool_quantity',p,False
    p=copy.deepcopy(good);p['trades'][0]['quantity']=10**400;yield 'huge_quantity',p,False
    p=copy.deepcopy(good);p['trades'][0]['entry_time']+=timedelta(seconds=1);yield 'unobserved_entry_time',p,False
    p=copy.deepcopy(good);p['bar_records'][1]['position_size']=1.5;yield 'fractional_holding',p,False
    p=copy.deepcopy(good);p['bar_records'][1]['timestamp']=p['bar_records'][1]['timestamp'].replace(tzinfo=None);yield 'mixed_bar_awareness',p,False
    p=copy.deepcopy(good);p['trades'][0]['exit_time']=p['trades'][0]['exit_time'].replace(tzinfo=None);yield 'mixed_trade_awareness',p,False
    p=copy.deepcopy(good);p['trades'][0]['entry_price']=1e-308;p['trades'][0]['exit_price']=1e308;yield 'derived_overflow',p,False



def _check_boundary(result, boundary):
    result = copy.deepcopy(result)
    if boundary == "direct":
        return validate(result)
    return decode(
        canonical_bytes(result, schema=BACKTEST_RESULT_SCHEMA)
    )


@pytest.mark.parametrize("boundary", ("direct", "decoder"))
@pytest.mark.parametrize(
    "name,result,expected",
    list(cases()),
    ids=[item[0] for item in cases()],
)
def test_m94q_financial_contract(name, result, expected, boundary):
    if expected:
        _check_boundary(result, boundary)
    else:
        with pytest.raises((ValueError, TypeError)):
            _check_boundary(result, boundary)


@pytest.mark.parametrize("boundary", ("direct", "decoder"))
@pytest.mark.parametrize(
    "two_trades",
    (True, False),
    ids=("valid_two_trades", "reused_single_trade"),
)
def test_m94q_nullable_two_round_trips(two_trades, boundary):
    bars = [
        bar(0),
        bar(1, 900, 1, event="BUY", qty=1, fill=100.),
        bar(2, 1000, event="SELL", qty=1, fill=100.),
        bar(3, 900, 1, event="BUY", qty=1, fill=100.),
        bar(4, 1000, event="SELL", qty=1, fill=100.),
    ]

    valid_result = payload(
        bars,
        [
            trade(entry=1, exit=None, xp=100.),
            trade(entry=3, exit=None, xp=100.),
        ],
    )

    if two_trades:
        _check_boundary(valid_result, boundary)
    else:
        invalid_result = copy.deepcopy(valid_result)
        invalid_result["trades"].pop()
        with pytest.raises((ValueError, TypeError)):
            _check_boundary(invalid_result, boundary)
def test_m94q_rereview_unchanged_holding_cash_creation_rejected():
    """REREVIEW-01: a diagnostic label is not cash authority."""

    result = payload(
        [
            bar(0),
            bar(
                1,
                cash=800.0,
                pos=2,
                event="BUY",
                qty=2,
                fill=100.0,
            ),
            bar(
                2,
                cash=900.0,
                pos=2,
                event="SELL",
                qty=1,
                fill=100.0,
            ),
        ]
    )

    with pytest.raises(ValueError):
        validate(result)


def test_m94q_rereview_nullable_intermediate_flat_reconciles():
    """REREVIEW-02: nullable time cannot suppress a flat checkpoint."""

    result = payload(
        [
            bar(0),
            bar(
                1,
                cash=800.0,
                pos=2,
                event="BUY",
                qty=2,
                fill=100.0,
            ),
            bar(
                2,
                cash=1010.0,
                pos=0,
                event="SELL",
                qty=2,
                fill=110.0,
            ),
            bar(
                3,
                cash=810.0,
                pos=2,
                event="BUY",
                qty=2,
                fill=100.0,
            ),
        ],
        [
            trade(
                entry=1,
                exit=None,
                q=2,
                ep=100.0,
                xp=110.0,
                cost=0.0,
            )
        ],
    )

    # The completed trade declares +20 net P&L.
    # Therefore the observed flat account at bar 2 must be 1020.
    with pytest.raises(ValueError):
        validate(result)


def test_m94q_rereview_nullable_samebar_real_m4_remains_valid():
    """REREVIEW-03: preserve M4's final-diagnostic same-bar contract."""

    result = payload(
        [
            bar(0),
            bar(
                1,
                cash=1010.0,
                pos=0,
                event="SELL",
                qty=1,
                fill=110.0,
            ),
        ],
        [
            trade(
                entry=1,
                exit=None,
                q=1,
                ep=100.0,
                xp=110.0,
                cost=0.0,
            )
        ],
    )

    # M4 BarRecord carries the final execution diagnostic for the bar.
    # A same-bar entry followed by an exit can therefore remain flat
    # while the final diagnostic is the exit.
    validate(result)


def test_m94q_rereview_float_fromhex_overflow_is_controlled():
    """REREVIEW-04: malformed encoded float must raise ValueError."""

    import json

    valid = payload(
        [
            bar(0),
            bar(
                1,
                cash=900.0,
                pos=1,
                event="BUY",
                qty=1,
                fill=100.0,
            ),
            bar(
                2,
                cash=1010.0,
                pos=0,
                event="SELL",
                qty=1,
                fill=110.0,
            ),
        ],
        [trade()],
    )

    tagged = json.loads(
        canonical_bytes(
            valid,
            schema=BACKTEST_RESULT_SCHEMA,
        ).decode("utf-8")
    )

    def replace_first_float(value):
        if isinstance(value, dict):
            if value.get("type") == "float":
                value["value"] = "0x1.0p+999999"
                return True

            return any(
                replace_first_float(child)
                for child in value.values()
            )

        if isinstance(value, list):
            return any(
                replace_first_float(child)
                for child in value
            )

        return False

    assert replace_first_float(tagged)

    malformed = json.dumps(
        tagged,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    with pytest.raises(ValueError):
        decode(malformed)


def test_m94q_rereview_explicit_trade_must_bind_observed_fill():
    """REREVIEW-05: explicit prices must match observed settlement."""

    result = payload(
        [
            bar(0),
            bar(
                1,
                cash=900.0,
                pos=1,
                event="BUY",
                qty=1,
                fill=100.0,
            ),
            bar(
                2,
                cash=1010.0,
                pos=0,
                event="SELL",
                qty=1,
                fill=110.0,
            ),
        ],
        [
            trade(
                entry=1,
                exit=2,
                q=1,
                ep=90.0,
                xp=100.0,
                cost=0.0,
            )
        ],
    )

    # Claimed trade has the same +10 P&L but contradicts
    # the actual observed BUY 100 / SELL 110 settlement.
    with pytest.raises(ValueError):
        validate(result)


def test_m94q_rereview_duplicate_trade_cannot_reuse_one_settlement():
    """REREVIEW-05: one observed exit cannot satisfy two trades."""

    completed = trade(
        entry=1,
        exit=2,
        q=1,
        ep=100.0,
        xp=100.0,
        cost=0.0,
    )

    result = payload(
        [
            bar(0),
            bar(
                1,
                cash=900.0,
                pos=1,
                event="BUY",
                qty=1,
                fill=100.0,
            ),
            bar(
                2,
                cash=1000.0,
                pos=0,
                event="SELL",
                qty=1,
                fill=100.0,
            ),
        ],
        [
            completed,
            copy.deepcopy(completed),
        ],
    )

    with pytest.raises(ValueError):
        validate(result)


@pytest.mark.parametrize("boundary", ("direct", "decoder"))
def test_m94q_rereview_first_bar_execution_evidence_rejected(boundary):
    """REREVIEW-06: the pre-execution snapshot cannot claim a fill."""

    result = payload(
        [
            bar(
                0,
                cash=1000.0,
                pos=0,
                event="BUY",
                qty=1,
                fill=100.0,
            ),
        ]
    )

    with pytest.raises(
        ValueError,
        match="first.*pre-execution|pre-execution.*first",
    ):
        _check_boundary(result, boundary)


@pytest.mark.parametrize("boundary", ("direct", "decoder"))
def test_m94q_rereview_first_bar_holding_without_execution_remains_compatible(
    boundary,
):
    """REREVIEW-07: first-bar holdings remain structurally compatible."""

    result = payload(
        [
            bar(
                0,
                cash=900.0,
                pos=1,
                price=100.0,
            ),
        ]
    )

    verified = _check_boundary(result, boundary)

    assert verified["bar_records"][0]["position_size"] == 1
    assert verified["bar_records"][0]["execution_event"] is None

# M94Q-FRESH-20261020-01 PERMANENT RED REGRESSION
#
# Ordinary flat-to-long BUY evidence must obey the same exact
# unlevered affordability predicate as physical M4 execution.
@pytest.mark.parametrize("boundary", ("direct", "decoder"))
def test_m94q_fresh_ordinary_buy_tiny_overspend_fails_closed(
    boundary,
):
    import math

    entry_fill = math.nextafter(100.0, math.inf)

    result = payload(
        [
            bar(
                0,
                cash=100.0,
                pos=0,
                price=100.0,
            ),
            bar(
                1,
                cash=0.0,
                pos=1,
                price=100.0,
                event="BUY",
                qty=1,
                fill=entry_fill,
            ),
        ]
    )

    assert entry_fill > result["bar_records"][0]["cash"]

    assert (
        entry_fill
        - result["bar_records"][0]["cash"]
        < 1e-7
    )

    with pytest.raises(
        ValueError,
        match="fund|cash|afford",
    ):
        _check_boundary(
            result,
            boundary,
        )


@pytest.mark.parametrize("boundary", ("direct", "decoder"))
def test_m94q_fresh_ordinary_buy_exact_cash_control(
    boundary,
):
    result = payload(
        [
            bar(
                0,
                cash=100.0,
                pos=0,
                price=100.0,
            ),
            bar(
                1,
                cash=0.0,
                pos=1,
                price=100.0,
                event="BUY",
                qty=1,
                fill=100.0,
            ),
        ]
    )

    verified = _check_boundary(
        result,
        boundary,
    )

    assert verified["bar_records"][1]["position_size"] == 1


# M94Q-FRESH-20261020-02 PERMANENT RED REGRESSION
#
# A completed trade cannot reuse the observed BUY settlement
# already claimed by another completed trade.
def _m94q_fresh_two_round_trip_entry_payload(
    *,
    second_trade_entry: int,
):
    return payload(
        [
            bar(0),
            bar(
                1,
                cash=900.0,
                pos=1,
                event="BUY",
                qty=1,
                fill=100.0,
            ),
            bar(
                2,
                cash=1000.0,
                pos=0,
                event="SELL",
                qty=1,
                fill=100.0,
            ),
            bar(
                3,
                cash=900.0,
                pos=1,
                event="BUY",
                qty=1,
                fill=100.0,
            ),
            bar(
                4,
                cash=1000.0,
                pos=0,
                event="SELL",
                qty=1,
                fill=100.0,
            ),
        ],
        [
            trade(
                entry=1,
                exit=2,
                q=1,
                ep=100.0,
                xp=100.0,
                cost=0.0,
            ),
            trade(
                entry=second_trade_entry,
                exit=4,
                q=1,
                ep=100.0,
                xp=100.0,
                cost=0.0,
            ),
        ],
    )


@pytest.mark.parametrize("boundary", ("direct", "decoder"))
def test_m94q_fresh_duplicate_entry_settlement_fails_closed(
    boundary,
):
    result = _m94q_fresh_two_round_trip_entry_payload(
        second_trade_entry=1,
    )

    assert (
        result["trades"][0]["entry_time"]
        == result["trades"][1]["entry_time"]
    )

    with pytest.raises(
        ValueError,
        match="entry.*unique|unique.*entry|entry settlement",
    ):
        _check_boundary(
            result,
            boundary,
        )


@pytest.mark.parametrize("boundary", ("direct", "decoder"))
def test_m94q_fresh_distinct_entry_settlements_control(
    boundary,
):
    result = _m94q_fresh_two_round_trip_entry_payload(
        second_trade_entry=3,
    )

    assert (
        result["trades"][0]["entry_time"]
        != result["trades"][1]["entry_time"]
    )

    verified = _check_boundary(
        result,
        boundary,
    )

    assert len(verified["trades"]) == 2
