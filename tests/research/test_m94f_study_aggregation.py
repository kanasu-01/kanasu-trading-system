from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from core.research.models.registered_study import (
    ResearchJobCompletionKind,
    ResearchJobState,
    TrialDisposition,
)
from core.research.models.research_catalog import (
    ResearchArtifact,
    ResearchArtifactKind,
    RunAttemptState,
)
from core.backtest.backtest_result import BacktestResult
from core.backtest.bar_record import BarRecord
from core.research.reproducibility import (
    BACKTEST_RESULT_SCHEMA,
    canonical_bytes,
    decode_canonical_bytes,
    decode_stable_backtest_result_bytes,
    stable_backtest_result_bytes,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
)
from core.research.study_aggregation import (
    StudyAggregationError,
    StudyAggregationService,
)


NOW = datetime(
    2026,
    10,
    2,
    12,
    0,
    tzinfo=timezone.utc,
)

REVISION_ID = "sha256:" + ("a" * 64)
EXECUTED_TRIAL_ID = "sha256:" + ("1" * 64)
REUSED_TRIAL_ID = "sha256:" + ("2" * 64)
FAILED_TRIAL_ID = "sha256:" + ("3" * 64)
CANCELLED_TRIAL_ID = "sha256:" + ("4" * 64)
PENDING_TRIAL_ID = "sha256:" + ("5" * 64)

EXECUTED_ARTIFACT_ID = "sha256:" + ("b" * 64)
REUSED_ARTIFACT_ID = "sha256:" + ("c" * 64)


def _trial(
    trial_id,
    disposition,
):
    return SimpleNamespace(
        trial_id=trial_id,
        study_revision_id=REVISION_ID,
        disposition=disposition,
        reused_attempt_id=(
            "attempt-reused"
            if disposition is TrialDisposition.REUSED
            else None
        ),
    )


def _executed_job():
    return SimpleNamespace(
        job_id="job-executed",
        trial_id=EXECUTED_TRIAL_ID,
        state=ResearchJobState.SUCCEEDED,
        completion_kind=(
            ResearchJobCompletionKind.EXECUTED
        ),
        attempt_id="attempt-executed",
        reused_attempt_id=None,
        reused_result_artifact_id=None,
    )


def _reused_job():
    return SimpleNamespace(
        job_id="job-reused",
        trial_id=REUSED_TRIAL_ID,
        state=ResearchJobState.SUCCEEDED,
        completion_kind=(
            ResearchJobCompletionKind.REUSED
        ),
        attempt_id=None,
        reused_attempt_id="attempt-reused",
        reused_evidence_id="evidence-reused",
        reused_result_artifact_id=(
            REUSED_ARTIFACT_ID
        ),
    )


def _terminal_event(
    *,
    trial_id,
    disposition,
    job_id,
):
    return SimpleNamespace(
        trial_id=trial_id,
        new_disposition=disposition,
        causing_job_id=job_id,
    )


def _attempt():
    return SimpleNamespace(
        attempt_id="attempt-executed",
        state=RunAttemptState.SUCCEEDED,
        result_artifact_id=EXECUTED_ARTIFACT_ID,
    )


def _artifact(artifact_id):
    return ResearchArtifact(
        artifact_id=artifact_id,
        artifact_kind=(
            ResearchArtifactKind.BACKTEST_RESULT
        ),
        schema_id=BACKTEST_RESULT_SCHEMA,
        relative_path=(
            artifact_id.removeprefix("sha256:")
            + ".json"
        ),
        byte_count=1,
        created_at=NOW,
    )


def _result_bytes(
    *,
    equities,
):
    records = [
        BarRecord(
            timestamp=(
                NOW
                + timedelta(
                    minutes=index,
                )
            ),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1000.0,
            strategy="aggregation-fixture",
            state=None,
            signal=None,
            execution_event=None,
            execution_price=None,
            execution_quantity=None,
            decision_snapshot={},
            equity=float(equity),
            cash=float(equity),
            position_size=0.0,
            drawdown=0.0,
        )
        for index, equity in enumerate(
            equities
        )
    ]

    return stable_backtest_result_bytes(
        BacktestResult(
            trades=[],
            bar_records=records,
            session_id="aggregation-fixture",
        )
    )



def _financial_result_bytes(
    *,
    equities,
):
    """Economically coherent open long for positive aggregation tests."""
    values = tuple(float(value) for value in equities)
    assert len(values) >= 2
    initial = values[0]
    assert initial > 1.0
    assert all(value > 1.0 for value in values)

    records = []
    peak = initial

    for index, equity in enumerate(values):
        previous_close = (
            initial if index == 0 else values[index - 1]
        )
        open_price = previous_close
        close_price = equity
        peak = max(peak, equity)

        records.append(
            BarRecord(
                timestamp=NOW + timedelta(minutes=index),
                open=open_price,
                high=max(open_price, close_price) + 1.0,
                low=min(open_price, close_price) - 1.0,
                close=close_price,
                volume=1000.0,
                strategy="aggregation-financial-control",
                state=None,
                signal=None,
                execution_event="BUY" if index == 1 else None,
                execution_price=initial if index == 1 else None,
                execution_quantity=1 if index == 1 else None,
                decision_snapshot={},
                equity=equity,
                cash=initial if index == 0 else 0.0,
                position_size=0.0 if index == 0 else 1.0,
                drawdown=(equity - peak) / peak,
            )
        )

    return stable_backtest_result_bytes(
        BacktestResult(
            trades=[],
            bar_records=records,
            session_id="aggregation-financial-control",
        )
    )


def _mutated_result_bytes(
    mutate,
    *,
    equities=(100.0, 110.0),
):
    payload = decode_canonical_bytes(
        _result_bytes(
            equities=equities,
        ),
        schema=BACKTEST_RESULT_SCHEMA,
    )

    mutate(payload)

    return canonical_bytes(
        payload,
        schema=BACKTEST_RESULT_SCHEMA,
    )


class CatalogStub:
    def __init__(self):
        self.trials = (
            _trial(
                EXECUTED_TRIAL_ID,
                TrialDisposition.EXECUTED,
            ),
            _trial(
                REUSED_TRIAL_ID,
                TrialDisposition.REUSED,
            ),
            _trial(
                FAILED_TRIAL_ID,
                TrialDisposition.FAILED,
            ),
            _trial(
                CANCELLED_TRIAL_ID,
                TrialDisposition.CANCELLED,
            ),
            _trial(
                PENDING_TRIAL_ID,
                TrialDisposition.PENDING,
            ),
        )

        self.jobs = {
            EXECUTED_TRIAL_ID: (
                _executed_job(),
            ),
            REUSED_TRIAL_ID: (
                _reused_job(),
            ),
            FAILED_TRIAL_ID: (),
            CANCELLED_TRIAL_ID: (),
            PENDING_TRIAL_ID: (),
        }

        self.events = {
            EXECUTED_TRIAL_ID: (
                _terminal_event(
                    trial_id=EXECUTED_TRIAL_ID,
                    disposition=TrialDisposition.EXECUTED,
                    job_id="job-executed",
                ),
            ),
            REUSED_TRIAL_ID: (
                _terminal_event(
                    trial_id=REUSED_TRIAL_ID,
                    disposition=TrialDisposition.REUSED,
                    job_id="job-reused",
                ),
            ),
            FAILED_TRIAL_ID: (),
            CANCELLED_TRIAL_ID: (),
            PENDING_TRIAL_ID: (),
        }

        self.attempts = {
            "attempt-executed": _attempt(),
            "attempt-reused": SimpleNamespace(
                attempt_id="attempt-reused",
                state=RunAttemptState.SUCCEEDED,
                evidence_id="evidence-reused",
                result_artifact_id=REUSED_ARTIFACT_ID,
            ),
        }

        self.artifacts = {
            EXECUTED_ARTIFACT_ID: _artifact(
                EXECUTED_ARTIFACT_ID
            ),
            REUSED_ARTIFACT_ID: _artifact(
                REUSED_ARTIFACT_ID
            ),
        }

    def load_study_revision(
        self,
        study_revision_id,
    ):
        if study_revision_id != REVISION_ID:
            return None

        return object()

    def list_trials_for_revision(
        self,
        study_revision_id,
    ):
        assert study_revision_id == REVISION_ID
        return self.trials

    def list_research_jobs_for_trial(
        self,
        trial_id,
    ):
        return self.jobs[trial_id]

    def load_trial_disposition_events(
        self,
        trial_id,
    ):
        return self.events.get(
            trial_id,
            (),
        )

    def load_research_job(
        self,
        job_id,
    ):
        for jobs in self.jobs.values():
            for job in jobs:
                if job.job_id == job_id:
                    return job

        return None

    def load_run_attempt(
        self,
        attempt_id,
    ):
        return self.attempts.get(
            attempt_id
        )

    def load_artifact(
        self,
        artifact_id,
    ):
        return self.artifacts.get(
            artifact_id
        )


class ArtifactStoreStub:
    def __init__(self):
        self.payloads = {
            EXECUTED_ARTIFACT_ID: _financial_result_bytes(
                equities=(100.0, 120.0, 108.0),
            ),
            REUSED_ARTIFACT_ID: _financial_result_bytes(
                equities=(100.0, 95.0, 95.0),
            ),
        }

    def load_bytes(
        self,
        artifact_id,
    ):
        return self.payloads[
            artifact_id
        ]


def _aggregate_real_executed_payload(
    tmp_path,
    payload_bytes,
    *,
    lineage="EXECUTED",
):
    store = ContentAddressedResearchArtifactStore(
        tmp_path / "m94k-artifacts"
    )

    artifact = store.persist_bytes(
        payload_bytes,
        artifact_kind=(
            ResearchArtifactKind.BACKTEST_RESULT
        ),
        schema_id=BACKTEST_RESULT_SCHEMA,
        created_at=NOW,
    )

    catalog = CatalogStub()

    catalog.trials = (
        _trial(
            EXECUTED_TRIAL_ID,
            TrialDisposition.EXECUTED,
        ),
    )

    catalog.jobs = {
        EXECUTED_TRIAL_ID: (
            _executed_job(),
        ),
    }

    catalog.events = {
        EXECUTED_TRIAL_ID: (
            _terminal_event(
                trial_id=EXECUTED_TRIAL_ID,
                disposition=TrialDisposition.EXECUTED,
                job_id="job-executed",
            ),
        ),
    }

    catalog.attempts = {
        "attempt-executed": SimpleNamespace(
            attempt_id="attempt-executed",
            state=RunAttemptState.SUCCEEDED,
            result_artifact_id=(
                artifact.artifact_id
            ),
        ),
    }

    catalog.artifacts = {
        artifact.artifact_id: artifact,
    }

    if lineage == "REUSED":
        reused_job = _reused_job()
        reused_job.reused_result_artifact_id = (
            artifact.artifact_id
        )

        catalog.trials = (
            _trial(
                REUSED_TRIAL_ID,
                TrialDisposition.REUSED,
            ),
        )
        catalog.jobs = {
            REUSED_TRIAL_ID: (reused_job,),
        }
        catalog.events = {
            REUSED_TRIAL_ID: (
                _terminal_event(
                    trial_id=REUSED_TRIAL_ID,
                    disposition=TrialDisposition.REUSED,
                    job_id="job-reused",
                ),
            ),
        }
        catalog.attempts = {
            "attempt-reused": SimpleNamespace(
                attempt_id="attempt-reused",
                state=RunAttemptState.SUCCEEDED,
                evidence_id="evidence-reused",
                result_artifact_id=artifact.artifact_id,
            ),
        }
    elif lineage != "EXECUTED":
        raise AssertionError("Unsupported test lineage")

    return StudyAggregationService(
        catalog_store=catalog,
        artifact_store=store,
    ).aggregate_revision(
        REVISION_ID
    )


def test_aggregation_reports_explicit_denominators_and_partial_failures():
    result = StudyAggregationService(
        catalog_store=CatalogStub(),
        artifact_store=ArtifactStoreStub(),
    ).aggregate_revision(
        REVISION_ID
    )

    assert result.study_revision_id == REVISION_ID
    assert result.aggregation_basis == (
        "INDEPENDENT_TRIAL_ACCOUNT_DISTRIBUTION"
    )

    assert result.total_registered_trials == 5
    assert result.result_bearing_trials == 2
    assert result.excluded_trials == 3

    assert result.executed_trials == 1
    assert result.reused_trials == 1
    assert result.pending_trials == 1
    assert result.failed_trials == 1
    assert result.cancelled_trials == 1
    assert result.invalid_trials == 0
    assert result.insufficient_trials == 0
    assert result.interrupted_trials == 0

    returns = result.account_return_pct

    assert returns.count == 2
    assert returns.mean == pytest.approx(
        1.5
    )
    assert returns.median == pytest.approx(
        1.5
    )
    assert returns.minimum == pytest.approx(
        -5.0
    )
    assert returns.maximum == pytest.approx(
        8.0
    )
    assert returns.positive_count == 1
    assert (
        returns.positive_proportion
        == pytest.approx(0.5)
    )

    drawdown = result.max_equity_drawdown_pct

    assert drawdown.count == 2
    assert drawdown.mean == pytest.approx(
        7.5
    )
    assert drawdown.median == pytest.approx(
        7.5
    )
    assert drawdown.minimum == pytest.approx(
        5.0
    )
    assert drawdown.maximum == pytest.approx(
        10.0
    )

    assert "portfolio_pnl" not in result.__dict__
    assert "portfolio_return" not in result.__dict__
    assert "total_pnl" not in result.__dict__


def test_aggregation_resolves_executed_and_reused_result_lineage():
    catalog = CatalogStub()
    artifact_store = ArtifactStoreStub()

    service = StudyAggregationService(
        catalog_store=catalog,
        artifact_store=artifact_store,
    )

    result = service.aggregate_revision(
        REVISION_ID
    )

    assert result.result_bearing_trials == 2

    assert set(
        result.result_artifact_ids
    ) == {
        EXECUTED_ARTIFACT_ID,
        REUSED_ARTIFACT_ID,
    }


def test_result_bearing_trial_requires_one_truthful_success_lineage():
    catalog = CatalogStub()
    catalog.jobs[
        EXECUTED_TRIAL_ID
    ] = ()

    with pytest.raises(
        StudyAggregationError,
        match="result-bearing Trial",
    ):
        StudyAggregationService(
            catalog_store=catalog,
            artifact_store=ArtifactStoreStub(),
        ).aggregate_revision(
            REVISION_ID
        )


def test_result_artifact_must_be_canonical_backtest_result():
    catalog = CatalogStub()

    catalog.artifacts[
        EXECUTED_ARTIFACT_ID
    ] = ResearchArtifact(
        artifact_id=EXECUTED_ARTIFACT_ID,
        artifact_kind=(
            ResearchArtifactKind.DATASET_REFERENCE
        ),
        schema_id="kanasu.dataset-reference.v1",
        relative_path="fixture.json",
        byte_count=1,
        created_at=NOW,
    )

    with pytest.raises(
        StudyAggregationError,
        match="canonical Backtest result",
    ):
        StudyAggregationService(
            catalog_store=catalog,
            artifact_store=ArtifactStoreStub(),
        ).aggregate_revision(
            REVISION_ID
        )


def test_missing_revision_is_rejected():
    with pytest.raises(
        StudyAggregationError,
        match="StudyRevision does not exist",
    ):
        StudyAggregationService(
            catalog_store=CatalogStub(),
            artifact_store=ArtifactStoreStub(),
        ).aggregate_revision(
            "sha256:" + ("f" * 64)
        )

def test_retry_history_does_not_make_current_result_lineage_ambiguous():
    catalog = CatalogStub()

    historical_job = SimpleNamespace(
        job_id="job-executed-historical",
        trial_id=EXECUTED_TRIAL_ID,
        state=ResearchJobState.SUCCEEDED,
        completion_kind=(
            ResearchJobCompletionKind.EXECUTED
        ),
        attempt_id="attempt-historical",
        reused_attempt_id=None,
        reused_result_artifact_id=None,
    )

    catalog.jobs[
        EXECUTED_TRIAL_ID
    ] = (
        historical_job,
        *catalog.jobs[
            EXECUTED_TRIAL_ID
        ],
    )

    catalog.attempts[
        "attempt-historical"
    ] = SimpleNamespace(
        attempt_id="attempt-historical",
        state=RunAttemptState.SUCCEEDED,
        result_artifact_id=(
            "sha256:" + ("d" * 64)
        ),
    )

    result = StudyAggregationService(
        catalog_store=catalog,
        artifact_store=ArtifactStoreStub(),
    ).aggregate_revision(
        REVISION_ID
    )

    assert result.result_bearing_trials == 2
    assert set(
        result.result_artifact_ids
    ) == {
        EXECUTED_ARTIFACT_ID,
        REUSED_ARTIFACT_ID,
    }


def test_zero_result_aggregation_preserves_all_excluded_denominators():
    catalog = CatalogStub()

    dispositions = (
        TrialDisposition.INVALID,
        TrialDisposition.INSUFFICIENT,
        TrialDisposition.FAILED,
        TrialDisposition.CANCELLED,
        TrialDisposition.INTERRUPTED,
    )

    catalog.trials = tuple(
        _trial(
            "sha256:"
            + str(index + 6) * 64,
            disposition,
        )
        for index, disposition
        in enumerate(dispositions)
    )

    result = StudyAggregationService(
        catalog_store=catalog,
        artifact_store=ArtifactStoreStub(),
    ).aggregate_revision(
        REVISION_ID
    )

    assert result.total_registered_trials == 5
    assert result.result_bearing_trials == 0
    assert result.excluded_trials == 5

    assert result.pending_trials == 0
    assert result.executed_trials == 0
    assert result.reused_trials == 0
    assert result.invalid_trials == 1
    assert result.insufficient_trials == 1
    assert result.failed_trials == 1
    assert result.cancelled_trials == 1
    assert result.interrupted_trials == 1

    for distribution in (
        result.account_return_pct,
        result.max_equity_drawdown_pct,
    ):
        assert distribution.count == 0
        assert distribution.mean is None
        assert distribution.median is None
        assert distribution.minimum is None
        assert distribution.maximum is None
        assert distribution.positive_count == 0
        assert distribution.positive_proportion is None

    assert result.result_artifact_ids == ()


def _aggregate_with_executed_payload(
    payload_bytes,
):
    catalog = CatalogStub()
    store = ArtifactStoreStub()

    store.payloads[
        EXECUTED_ARTIFACT_ID
    ] = payload_bytes

    return StudyAggregationService(
        catalog_store=catalog,
        artifact_store=store,
    ).aggregate_revision(
        REVISION_ID
    )


def test_m94g3_real_canonical_serialized_backtest_result_is_accepted():
    result = _aggregate_with_executed_payload(
        _financial_result_bytes(
            equities=(100.0, 120.0, 108.0),
        )
    )

    assert result.executed_trials == 1
    assert result.result_bearing_trials == 2


@pytest.mark.parametrize(
    "case",
    (
        "trade_quantity_zero",
        "trade_direction_short",
        "execution_quantity_zero",
        "positive_drawdown",
        "positive_position_without_equity_value",
        "negative_transaction_cost",
        "drawdown_below_minus_one",
        "incomplete_execution_fields",
    ),
)
def test_m94k_real_canonical_artifact_rejects_long_only_counterexamples(
    tmp_path,
    case,
):
    def mutate(payload):
        if case in {
            "trade_quantity_zero",
            "trade_direction_short",
            "negative_transaction_cost",
        }:
            payload["trades"].append(
                {
                    "symbol": "NSE:A",
                    "entry_time": NOW,
                    "entry_price": 100.0,
                    "exit_time": (
                        NOW + timedelta(minutes=1)
                    ),
                    "exit_price": 101.0,
                    "stop_price": 99.0,
                    "quantity": 1,
                    "direction": "LONG",
                    "exit_reason": "fixture",
                    "pnl": 1.0,
                    "gross_pnl": 1.0,
                    "transaction_cost": 0.0,
                    "pnl_pct": 1.0,
                }
            )

            if case == "trade_quantity_zero":
                payload["trades"][0][
                    "quantity"
                ] = 0
            elif case == "trade_direction_short":
                payload["trades"][0][
                    "direction"
                ] = "SHORT"
            else:
                payload["trades"][0][
                    "transaction_cost"
                ] = -100.0

            return

        record = payload["bar_records"][0]

        if case == "execution_quantity_zero":
            record["execution_price"] = 100.0
            record["execution_quantity"] = 0
            return

        if case == "positive_drawdown":
            record["drawdown"] = 0.01
            return

        if (
            case
            == "positive_position_without_equity_value"
        ):
            record["position_size"] = 1.0
            record["cash"] = record["equity"]
            return

        if case == "drawdown_below_minus_one":
            assert record["equity"] > 0
            record["drawdown"] = -2.0
            return

        if case == "incomplete_execution_fields":
            record["execution_event"] = None
            record["execution_price"] = None
            record["execution_quantity"] = 1
            return

        raise AssertionError(
            f"unknown fixture case: {case}"
        )

    payload_bytes = _mutated_result_bytes(
        mutate
    )

    with pytest.raises(
        StudyAggregationError,
        match="canonical Backtest result artifact",
    ):
        _aggregate_real_executed_payload(
            tmp_path,
            payload_bytes,
        )


def test_m94g3_missing_required_bar_field_is_rejected():
    def mutate(payload):
        payload["bar_records"][0].pop(
            "cash"
        )

    with pytest.raises(
        StudyAggregationError,
        match="canonical Backtest result",
    ):
        _aggregate_with_executed_payload(
            _mutated_result_bytes(
                mutate
            )
        )


def test_m94g3_malformed_trade_shape_is_rejected():
    def mutate(payload):
        payload["trades"].append(
            {
                "symbol": "NSE:INVALID",
            }
        )

    with pytest.raises(
        StudyAggregationError,
        match="canonical Backtest result",
    ):
        _aggregate_with_executed_payload(
            _mutated_result_bytes(
                mutate
            )
        )


def test_m94g3_malformed_timestamp_is_rejected():
    def mutate(payload):
        payload["bar_records"][0][
            "timestamp"
        ] = "not-a-canonical-datetime"

    with pytest.raises(
        StudyAggregationError,
        match="canonical Backtest result",
    ):
        _aggregate_with_executed_payload(
            _mutated_result_bytes(
                mutate
            )
        )


def test_m94g3_curve_bar_timestamp_mismatch_is_rejected():
    def mutate(payload):
        timestamp, equity = (
            payload["equity_curve"][0]
        )

        payload["equity_curve"][0] = (
            timestamp
            + timedelta(
                seconds=1,
            ),
            equity,
        )

    with pytest.raises(
        StudyAggregationError,
        match="canonical Backtest result",
    ):
        _aggregate_with_executed_payload(
            _mutated_result_bytes(
                mutate
            )
        )


def test_m94g3_invalid_financial_numeric_type_is_rejected():
    def mutate(payload):
        payload["bar_records"][0][
            "equity"
        ] = "100.0"

    with pytest.raises(
        StudyAggregationError,
        match="canonical Backtest result",
    ):
        _aggregate_with_executed_payload(
            _mutated_result_bytes(
                mutate
            )
        )


@pytest.mark.parametrize(
    "invalid_equity",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_m94g3_nonfinite_financial_data_is_rejected(
    invalid_equity,
):
    from core.research.reproducibility import (
        validate_stable_backtest_result_payload,
    )

    payload = decode_canonical_bytes(
        _result_bytes(
            equities=(100.0, 110.0),
        ),
        schema=BACKTEST_RESULT_SCHEMA,
    )

    payload["bar_records"][0][
        "equity"
    ] = invalid_equity

    with pytest.raises(
        ValueError,
        match="finite numeric value",
    ):
        validate_stable_backtest_result_payload(
            payload
        )


def test_m94g3_nonchronological_bar_records_are_rejected():
    def mutate(payload):
        first = payload[
            "bar_records"
        ][0]["timestamp"]

        payload["bar_records"][1][
            "timestamp"
        ] = first

        _, equity = (
            payload["equity_curve"][1]
        )

        payload["equity_curve"][1] = (
            first,
            equity,
        )

    with pytest.raises(
        StudyAggregationError,
        match="canonical Backtest result",
    ):
        _aggregate_with_executed_payload(
            _mutated_result_bytes(
                mutate
            )
        )



def test_m94j_validator_rejects_impossible_financial_states():
    from copy import deepcopy

    from core.research.reproducibility import (
        validate_stable_backtest_result_payload,
    )

    baseline = decode_canonical_bytes(
        _result_bytes(
            equities=(100.0, 110.0),
        ),
        schema=BACKTEST_RESULT_SCHEMA,
    )

    cases = []

    invalid = deepcopy(baseline)
    invalid["bar_records"][0]["high"] = (
        invalid["bar_records"][0]["open"] - 1.0
    )
    cases.append(
        (
            invalid,
            "OHLC envelope",
        )
    )

    invalid = deepcopy(baseline)
    invalid["bar_records"][0]["volume"] = -1.0
    cases.append(
        (
            invalid,
            "volume cannot be negative",
        )
    )

    invalid = deepcopy(baseline)
    invalid["bar_records"][0]["open"] = 0.0
    cases.append(
        (
            invalid,
            "open must be positive",
        )
    )

    invalid = deepcopy(baseline)
    invalid["bar_records"][0]["position_size"] = -1.0
    cases.append(
        (
            invalid,
            "position_size cannot be negative",
        )
    )

    invalid = deepcopy(baseline)
    invalid["bar_records"][0]["position_size"] = 0.0
    invalid["bar_records"][0]["cash"] = (
        invalid["bar_records"][0]["equity"] - 1.0
    )
    cases.append(
        (
            invalid,
            "zero position requires equity to equal cash",
        )
    )

    invalid = deepcopy(baseline)
    invalid["bar_records"][0]["execution_price"] = 0.0
    cases.append(
        (
            invalid,
            "execution_price must be positive",
        )
    )

    if baseline["trades"]:
        invalid = deepcopy(baseline)
        invalid["trades"][0]["entry_price"] = 0.0
        cases.append(
            (
                invalid,
                "entry_price must be positive",
            )
        )

    for payload, message in cases:
        with pytest.raises(
            ValueError,
            match=message,
        ):
            validate_stable_backtest_result_payload(
                payload
            )



@pytest.mark.parametrize(
    "case",
    (
        "inconsistent_net_pnl",
        "inconsistent_gross_pnl",
        "inconsistent_return_pct",
        "incorrect_marked_equity",
    ),
)
def test_m94m_hash_valid_financial_contradictions_block_aggregation(
    tmp_path,
    case,
):
    def mutate(payload):
        if case in {
            "inconsistent_net_pnl",
            "inconsistent_gross_pnl",
            "inconsistent_return_pct",
        }:
            payload["trades"].append(
                {
                    "symbol": "NSE:A",
                    "entry_time": NOW,
                    "entry_price": 100.0,
                    "exit_time": NOW + timedelta(minutes=1),
                    "exit_price": 101.0,
                    "stop_price": 99.0,
                    "quantity": 1,
                    "direction": "LONG",
                    "exit_reason": "fixture",
                    "pnl": 1.0,
                    "gross_pnl": 1.0,
                    "transaction_cost": 0.0,
                    "pnl_pct": 1.0,
                }
            )
            trade = payload["trades"][0]
            if case == "inconsistent_net_pnl":
                trade["pnl"] = 2.0
            elif case == "inconsistent_gross_pnl":
                trade["gross_pnl"] = 2.0
                trade["pnl"] = 2.0
            else:
                trade["pnl_pct"] = 99.0
        elif case == "incorrect_marked_equity":
            record = payload["bar_records"][0]
            record["position_size"] = 1.0
            record["cash"] = record["equity"] - 1.0
        else:
            raise AssertionError(case)

    with pytest.raises(
        StudyAggregationError,
        match="canonical Backtest result artifact",
    ):
        _aggregate_real_executed_payload(
            tmp_path,
            _mutated_result_bytes(mutate),
        )


@pytest.mark.parametrize(
    "case",
    (
        "valid_cost_adjusted_trade",
        "valid_loss_trade",
        "valid_close_marked_holding",
    ),
)
def test_m94m_valid_direct_financial_relationships_are_accepted(
    tmp_path,
    case,
):
    def mutate(payload):
        if case in {
            "valid_cost_adjusted_trade",
            "valid_loss_trade",
        }:
            entry_price = (
                101.0
                if case == "valid_cost_adjusted_trade"
                else 102.0
            )
            exit_price = (
                102.0
                if case == "valid_cost_adjusted_trade"
                else 101.0
            )
            quantity = 3
            gross = (
                (exit_price - entry_price)
                * quantity
            )
            cost = 0.25

            payload["trades"].append(
                {
                    "symbol": "NSE:A",
                    "entry_time": NOW,
                    "entry_price": entry_price,
                    "exit_time": NOW + timedelta(minutes=1),
                    "exit_price": exit_price,
                    "stop_price": 99.0,
                    "quantity": quantity,
                    "direction": "LONG",
                    "exit_reason": "fixture",
                    "pnl": gross - cost,
                    "gross_pnl": gross,
                    "transaction_cost": cost,
                    "pnl_pct": (
                        (exit_price - entry_price)
                        / entry_price
                    ) * 100,
                }
            )
        elif case == "valid_close_marked_holding":
            record = payload["bar_records"][0]
            record["position_size"] = 1.0
            record["cash"] = (
                record["equity"] - record["close"]
            )
        else:
            raise AssertionError(case)

        if case in {
            "valid_cost_adjusted_trade",
            "valid_loss_trade",
        }:
            _m94q_reconcile_synthetic_closed_trade(payload)
        elif case == "valid_close_marked_holding":
            _m94q_reconcile_synthetic_open_holding(payload)

    result = _aggregate_real_executed_payload(
        tmp_path,
        _mutated_result_bytes(mutate),
    )

    assert result.executed_trials == 1
    assert result.result_bearing_trials == 1


@pytest.mark.parametrize(
    "exit_time",
    (None, NOW + timedelta(minutes=1)),
)
@pytest.mark.parametrize(
    "case",
    (
        "valid_profitable_trade",
        "valid_losing_trade",
        "inconsistent_gross_pnl",
        "inconsistent_return_pct",
    ),
)
def test_m94o_canonical_decoder_enforces_trade_prices_with_optional_exit_time(
    case,
    exit_time,
):
    def mutate(payload):
        entry_price = (
            102.0
            if case == "valid_losing_trade"
            else 101.0
        )
        exit_price = (
            101.0
            if case == "valid_losing_trade"
            else 102.0
        )
        quantity = 3
        transaction_cost = 0.25

        gross_pnl = (
            (exit_price - entry_price)
            * quantity
        )

        payload["trades"].append(
            {
                "symbol": "NSE:A",
                "entry_time": NOW,
                "entry_price": entry_price,
                "exit_time": exit_time,
                "exit_price": exit_price,
                "stop_price": 99.0,
                "quantity": quantity,
                "direction": "LONG",
                "exit_reason": "fixture",
                "pnl": gross_pnl - transaction_cost,
                "gross_pnl": gross_pnl,
                "transaction_cost": transaction_cost,
                "pnl_pct": (
                    (exit_price - entry_price)
                    / entry_price
                ) * 100,
            }
        )

        trade = payload["trades"][0]

        if case == "inconsistent_gross_pnl":
            trade["gross_pnl"] += 1.0
            trade["pnl"] += 1.0

        elif case == "inconsistent_return_pct":
            trade["pnl_pct"] = 99.0

        if case in {
            "valid_profitable_trade",
            "valid_losing_trade",
        }:
            _m94q_reconcile_synthetic_closed_trade(payload)

    payload_bytes = _mutated_result_bytes(mutate)

    if case in {
        "valid_profitable_trade",
        "valid_losing_trade",
    }:
        decoded = decode_stable_backtest_result_bytes(
            payload_bytes
        )

        trade = decoded["trades"][0]

        assert trade["quantity"] == 3
        assert trade["transaction_cost"] == 0.25

        if case == "valid_losing_trade":
            assert trade["gross_pnl"] < 0
            assert trade["pnl"] < 0
            assert trade["pnl_pct"] < 0
        else:
            assert trade["gross_pnl"] > 0
            assert trade["pnl"] > 0
            assert trade["pnl_pct"] > 0

    else:
        message = (
            "gross_pnl must"
            if case == "inconsistent_gross_pnl"
            else "pnl_pct must"
        )

        with pytest.raises(
            ValueError,
            match=message,
        ):
            decode_stable_backtest_result_bytes(
                payload_bytes
            )

@pytest.mark.parametrize(
    "lineage",
    ("EXECUTED", "REUSED"),
)
@pytest.mark.parametrize(
    "case",
    (
        "inconsistent_gross_pnl",
        "inconsistent_return_pct",
        "valid_cost_adjusted_trade",
        "valid_losing_trade",
    ),
)
def test_m94o_nullable_exit_time_evidence_aggregation(
    tmp_path,
    lineage,
    case,
):
    def mutate(payload):
        entry_price = (
            102.0 if case == "valid_losing_trade"
            else 101.0
        )
        exit_price = (
            101.0 if case == "valid_losing_trade"
            else 102.0
        )
        quantity = 3
        transaction_cost = 0.25

        gross = (
            (exit_price - entry_price) * quantity
        )

        payload["trades"].append(
            {
                "symbol": "NSE:A",
                "entry_time": NOW,
                "entry_price": entry_price,
                "exit_time": None,
                "exit_price": exit_price,
                "stop_price": 99.0,
                "quantity": quantity,
                "direction": "LONG",
                "exit_reason": "fixture",
                "pnl": gross - transaction_cost,
                "gross_pnl": gross,
                "transaction_cost": transaction_cost,
                "pnl_pct": (
                    (exit_price - entry_price)
                    / entry_price
                ) * 100,
            }
        )

        trade = payload["trades"][0]

        if case == "inconsistent_gross_pnl":
            trade["gross_pnl"] += 1.0
            trade["pnl"] += 1.0
        elif case == "inconsistent_return_pct":
            trade["pnl_pct"] = 99.0

        if case in {
            "valid_cost_adjusted_trade",
            "valid_losing_trade",
        }:
            _m94q_reconcile_synthetic_closed_trade(payload)

    payload_bytes = _mutated_result_bytes(mutate)

    if case.startswith("inconsistent_"):
        with pytest.raises(
            StudyAggregationError,
            match="canonical Backtest result artifact",
        ):
            _aggregate_real_executed_payload(
                tmp_path,
                payload_bytes,
                lineage=lineage,
            )
    else:
        result = _aggregate_real_executed_payload(
            tmp_path,
            payload_bytes,
            lineage=lineage,
        )

        assert result.result_bearing_trials == 1

        if lineage == "EXECUTED":
            assert result.executed_trials == 1
        else:
            assert result.reused_trials == 1

@pytest.mark.parametrize(
    "lineage",
    ("EXECUTED", "REUSED"),
)
@pytest.mark.parametrize(
    "exit_time",
    (None, NOW + timedelta(minutes=1)),
)
@pytest.mark.parametrize(
    "exit_price",
    (0.0, -1.0),
)
def test_m94o_c01_nonpositive_exit_price_is_never_authoritative(
    tmp_path,
    lineage,
    exit_time,
    exit_price,
):
    def mutate(payload):
        entry_price = 101.0
        quantity = 3
        transaction_cost = 0.25
        gross = (exit_price - entry_price) * quantity

        payload["trades"].append(
            {
                "symbol": "NSE:A",
                "entry_time": NOW,
                "entry_price": entry_price,
                "exit_time": exit_time,
                "exit_price": exit_price,
                "stop_price": 99.0,
                "quantity": quantity,
                "direction": "LONG",
                "exit_reason": "fixture",
                "pnl": gross - transaction_cost,
                "gross_pnl": gross,
                "transaction_cost": transaction_cost,
                "pnl_pct": (
                    (exit_price - entry_price)
                    / entry_price
                ) * 100,
            }
        )

    payload_bytes = _mutated_result_bytes(mutate)

    with pytest.raises(
        ValueError,
        match="exit_price must be positive",
    ):
        decode_stable_backtest_result_bytes(
            payload_bytes
        )

    with pytest.raises(
        StudyAggregationError,
        match="canonical Backtest result artifact",
    ):
        _aggregate_real_executed_payload(
            tmp_path,
            payload_bytes,
            lineage=lineage,
        )


@pytest.mark.parametrize(
    "position_size",
    (
        0,
        0.0,
        1,
        1.0,
        2.0,
    ),
)
def test_m94q_position_size_accepts_whole_share_values_without_normalization(
    position_size,
):
    from core.research.reproducibility import (
        validate_stable_backtest_result_payload,
    )

    payload = decode_canonical_bytes(
        _result_bytes(
            equities=(300.0,),
        ),
        schema=BACKTEST_RESULT_SCHEMA,
    )

    record = payload["bar_records"][0]
    record["position_size"] = position_size

    if position_size == 0:
        record["cash"] = record["equity"]
    else:
        record["cash"] = (
            record["equity"]
            - position_size * record["close"]
        )

    validated = validate_stable_backtest_result_payload(
        payload
    )

    validated_position_size = validated[
        "bar_records"
    ][0]["position_size"]

    assert validated_position_size == position_size
    assert type(validated_position_size) is type(
        position_size
    )


def test_m94q_zero_cash_fully_funded_whole_share_holding_is_valid():
    from core.research.reproducibility import (
        validate_stable_backtest_result_payload,
    )

    payload = decode_canonical_bytes(
        _result_bytes(
            equities=(200.0, 210.0),
        ),
        schema=BACKTEST_RESULT_SCHEMA,
    )

    record = payload["bar_records"][0]
    record["position_size"] = 2.0
    record["cash"] = 0.0

    assert record["equity"] == (
        record["cash"]
        + record["position_size"] * record["close"]
    )


    next_record = payload["bar_records"][1]
    next_record.update(
        position_size=2.0,
        cash=0.0,
        high=106.0,
        close=105.0,
    )
    validated = validate_stable_backtest_result_payload(
        payload
    )

    validated_record = validated["bar_records"][0]

    assert validated_record["cash"] == 0.0
    assert validated_record["position_size"] == 2.0

    decoded = decode_stable_backtest_result_bytes(
        canonical_bytes(
            payload,
            schema=BACKTEST_RESULT_SCHEMA,
        )
    )

    decoded_record = decoded["bar_records"][0]

    assert decoded_record["cash"] == 0.0
    assert decoded_record["position_size"] == 2.0


def test_m94q_negative_cash_with_open_holding_is_rejected():
    from core.research.reproducibility import (
        validate_stable_backtest_result_payload,
    )

    payload = decode_canonical_bytes(
        _result_bytes(
            equities=(100.0, 110.0),
        ),
        schema=BACKTEST_RESULT_SCHEMA,
    )

    record = payload["bar_records"][0]
    record["position_size"] = 2.0
    record["cash"] = -100.0

    assert record["equity"] == (
        record["cash"]
        + record["position_size"] * record["close"]
    )

    with pytest.raises(
        ValueError,
        match="cash cannot be negative for unlevered research",
    ):
        validate_stable_backtest_result_payload(payload)


def test_m94q_stable_decoder_rejects_negative_cash_with_open_holding():
    def mutate(payload):
        record = payload["bar_records"][0]
        record["position_size"] = 2.0
        record["cash"] = -100.0

        assert record["equity"] == (
            record["cash"]
            + record["position_size"] * record["close"]
        )

    with pytest.raises(
        ValueError,
        match="cash cannot be negative for unlevered research",
    ):
        decode_stable_backtest_result_bytes(
            _mutated_result_bytes(mutate)
        )


@pytest.mark.parametrize(
    ("position_size", "message"),
    (
        (0.5, "whole-share quantity"),
        (1.5, "whole-share quantity"),
        (2.0000001, "whole-share quantity"),
        (-1.0, "position_size cannot be negative"),
        (True, "finite numeric value"),
        (float("nan"), "finite numeric value"),
        (float("inf"), "finite numeric value"),
        (float("-inf"), "finite numeric value"),
    ),
)
def test_m94q_position_size_rejects_fractional_and_preserves_numeric_guards(
    position_size,
    message,
):
    from core.research.reproducibility import (
        validate_stable_backtest_result_payload,
    )

    payload = decode_canonical_bytes(
        _result_bytes(
            equities=(300.0, 310.0),
        ),
        schema=BACKTEST_RESULT_SCHEMA,
    )

    record = payload["bar_records"][0]
    record["position_size"] = position_size

    if (
        isinstance(position_size, (int, float))
        and not isinstance(position_size, bool)
        and position_size > 0
        and position_size != float("inf")
    ):
        record["cash"] = (
            record["equity"]
            - position_size * record["close"]
        )

    with pytest.raises(
        ValueError,
        match=message,
    ):
        validate_stable_backtest_result_payload(
            payload
        )




@pytest.mark.parametrize(
    "lineage",
    (
        "EXECUTED",
        "REUSED",
    ),
)
def test_m94q_aggregation_accepts_whole_share_position_for_executed_and_reused(
    tmp_path,
    lineage,
):
    def mutate(payload):
        record = payload["bar_records"][0]
        record["position_size"] = 1.0
        record["cash"] = (
            record["equity"]
            - record["position_size"] * record["close"]
        )

        # Keep the positive whole-share holding open; a
        # disappearance without a trade is not settlement.
        followup = payload["bar_records"][1]
        followup.update(
            position_size=1.0,
            cash=record["cash"],
            close=110.0,
            high=111.0,
        )

    result = _aggregate_real_executed_payload(
        tmp_path,
        _mutated_result_bytes(mutate),
        lineage=lineage,
    )

    assert result.result_bearing_trials == 1

    if lineage == "EXECUTED":
        assert result.executed_trials == 1
        assert result.reused_trials == 0
    else:
        assert result.executed_trials == 0
        assert result.reused_trials == 1


@pytest.mark.parametrize(
    "lineage",
    (
        "EXECUTED",
        "REUSED",
    ),
)
def test_m94q_aggregation_rejects_fractional_position_for_executed_and_reused(
    tmp_path,
    lineage,
):
    def mutate(payload):
        record = payload["bar_records"][0]
        record["position_size"] = 1.5
        record["cash"] = (
            record["equity"]
            - record["position_size"] * record["close"]
        )

    with pytest.raises(
        StudyAggregationError,
        match="canonical Backtest result artifact",
    ):
        _aggregate_real_executed_payload(
            tmp_path,
            _mutated_result_bytes(mutate),
            lineage=lineage,
        )




@pytest.mark.parametrize(
    "lineage",
    (
        "EXECUTED",
        "REUSED",
    ),
)
def test_m94q_aggregation_rejects_negative_cash_for_executed_and_reused(
    tmp_path,
    lineage,
):
    def mutate(payload):
        record = payload["bar_records"][0]
        record["position_size"] = 2.0
        record["cash"] = -100.0

        assert record["equity"] == (
            record["cash"]
            + record["position_size"] * record["close"]
        )

    with pytest.raises(
        StudyAggregationError,
        match="canonical Backtest result artifact",
    ):
        _aggregate_real_executed_payload(
            tmp_path,
            _mutated_result_bytes(mutate),
            lineage=lineage,
        )


@pytest.mark.parametrize(
    "quantity",
    (
        1.0,
        True,
    ),
)
def test_m94q_neighboring_trade_quantity_remains_strict_integer(
    quantity,
):
    from core.research.reproducibility import (
        validate_stable_backtest_result_payload,
    )

    payload = decode_canonical_bytes(
        _result_bytes(
            equities=(100.0, 110.0),
        ),
        schema=BACKTEST_RESULT_SCHEMA,
    )

    payload["trades"].append(
        {
            "symbol": "NSE:A",
            "entry_time": NOW,
            "entry_price": 100.0,
            "exit_time": NOW + timedelta(minutes=1),
            "exit_price": 101.0,
            "stop_price": 99.0,
            "quantity": quantity,
            "direction": "LONG",
            "exit_reason": "fixture",
            "pnl": 1.0,
            "gross_pnl": 1.0,
            "transaction_cost": 0.0,
            "pnl_pct": 1.0,
        }
    )

    with pytest.raises(
        ValueError,
        match="quantity must be an integer",
    ):
        validate_stable_backtest_result_payload(
            payload
        )


@pytest.mark.parametrize(
    "quantity",
    (
        1.0,
        True,
    ),
)
def test_m94q_neighboring_execution_quantity_remains_strict_integer(
    quantity,
):
    from core.research.reproducibility import (
        validate_stable_backtest_result_payload,
    )

    payload = decode_canonical_bytes(
        _result_bytes(
            equities=(100.0, 110.0),
        ),
        schema=BACKTEST_RESULT_SCHEMA,
    )

    record = payload["bar_records"][0]
    record["execution_event"] = "BUY"
    record["execution_price"] = 100.0
    record["execution_quantity"] = quantity

    with pytest.raises(
        ValueError,
        match="execution_quantity must be an integer",
    ):
        validate_stable_backtest_result_payload(
            payload
        )


def _m94q_trade_outside_authoritative_bar_history():
    from core.research.reproducibility import (
        validate_stable_backtest_result_payload,
    )

    payload = decode_canonical_bytes(
        _result_bytes(
            equities=(100.0, 110.0),
        ),
        schema=BACKTEST_RESULT_SCHEMA,
    )

    payload["trades"].append(
        {
            "symbol": "NSE:A",
            "entry_time": NOW,
            "entry_price": 100.0,
            "exit_time": NOW + timedelta(minutes=1),
            "exit_price": 101.0,
            "stop_price": 99.0,
            "quantity": 1,
            "direction": "LONG",
            "exit_reason": "fixture",
            "pnl": 1.0,
            "gross_pnl": 1.0,
            "transaction_cost": 0.0,
            "pnl_pct": 1.0,
        }
    )

    # An otherwise structurally valid trade fits the bar history.

    _m94q_reconcile_synthetic_closed_trade(payload)
    validate_stable_backtest_result_payload(payload)

    after_last_bar = (
        payload["bar_records"][-1]["timestamp"]
        + timedelta(days=1)
    )

    payload["trades"][0]["entry_time"] = after_last_bar
    payload["trades"][0]["exit_time"] = (
        after_last_bar + timedelta(minutes=1)
    )

    return payload


def test_m94q_trade_outside_bar_history_is_rejected_by_decoder():
    payload = _m94q_trade_outside_authoritative_bar_history()

    with pytest.raises(
        ValueError,
        match="trade|timestamp|bar",
    ):
        decode_stable_backtest_result_bytes(
            canonical_bytes(
                payload,
                schema=BACKTEST_RESULT_SCHEMA,
            )
        )


@pytest.mark.parametrize(
    "lineage",
    (
        "EXECUTED",
        "REUSED",
    ),
)
def test_m94q_trade_outside_bar_history_is_rejected_by_aggregation(
    tmp_path,
    lineage,
):
    payload = _m94q_trade_outside_authoritative_bar_history()

    with pytest.raises(
        StudyAggregationError,
        match="canonical Backtest result artifact",
    ):
        _aggregate_real_executed_payload(
            tmp_path,
            canonical_bytes(
                payload,
                schema=BACKTEST_RESULT_SCHEMA,
            ),
            lineage=lineage,
        )


def test_m94q_oversized_integer_is_rejected_by_direct_validator():
    from core.research.reproducibility import (
        validate_stable_backtest_result_payload,
    )

    payload = decode_canonical_bytes(
        _result_bytes(
            equities=(100.0, 110.0),
        ),
        schema=BACKTEST_RESULT_SCHEMA,
    )

    payload["bar_records"][0]["position_size"] = 10 ** 400

    with pytest.raises(
        ValueError,
        match="finite numeric",
    ):
        validate_stable_backtest_result_payload(payload)


def test_m94q_oversized_integer_is_rejected_by_decoder():
    payload = decode_canonical_bytes(
        _result_bytes(
            equities=(100.0, 110.0),
        ),
        schema=BACKTEST_RESULT_SCHEMA,
    )

    payload["bar_records"][0]["position_size"] = 10 ** 400

    with pytest.raises(
        ValueError,
        match="finite numeric",
    ):
        decode_stable_backtest_result_bytes(
            canonical_bytes(
                payload,
                schema=BACKTEST_RESULT_SCHEMA,
            )
        )


def _m94q_followup_valid_closed_trade_payload():
    from core.research.reproducibility import (
        validate_stable_backtest_result_payload,
    )

    payload = _m94q_trade_outside_authoritative_bar_history()

    # Restore a known-valid closed trade to actual observed bars.
    payload["trades"][0]["entry_time"] = NOW
    payload["trades"][0]["exit_time"] = (
        NOW + timedelta(minutes=1)
    )

    validate_stable_backtest_result_payload(payload)
    return payload


@pytest.mark.parametrize(
    "boundary",
    ("direct", "decoder"),
)
def test_m94q_followup_trade_quantity_overflow_fails_closed(
    boundary,
):
    from core.research.reproducibility import (
        validate_stable_backtest_result_payload,
    )

    payload = _m94q_followup_valid_closed_trade_payload()
    payload["trades"][0]["quantity"] = 10 ** 400

    with pytest.raises(ValueError, match="quantity"):
        if boundary == "direct":
            validate_stable_backtest_result_payload(payload)
        else:
            decode_stable_backtest_result_bytes(
                canonical_bytes(
                    payload,
                    schema=BACKTEST_RESULT_SCHEMA,
                )
            )


@pytest.mark.parametrize(
    "field",
    ("entry_time", "exit_time"),
)
def test_m94q_followup_trade_timestamp_requires_observed_bar(
    field,
):
    payload = _m94q_followup_valid_closed_trade_payload()

    if field == "entry_time":
        payload["trades"][0][field] = (
            NOW + timedelta(seconds=1)
        )
    else:
        payload["trades"][0][field] = (
            NOW + timedelta(minutes=1, seconds=-1)
        )

    assert (
        payload["trades"][0][field]
        not in {
            record["timestamp"]
            for record in payload["bar_records"]
        }
    )

    with pytest.raises(
        ValueError,
        match="trade|timestamp|bar",
    ):
        decode_stable_backtest_result_bytes(
            canonical_bytes(
                payload,
                schema=BACKTEST_RESULT_SCHEMA,
            )
        )


def test_m94q_followup_distribution_mean_large_finite():
    from math import isfinite
    from core.research.study_aggregation import (
        StudyMetricDistribution,
    )

    result = StudyMetricDistribution.from_values(
        (1e308, 1e308)
    )

    assert isfinite(result.mean)
    assert result.mean == pytest.approx(1e308)


def test_m94q_followup_distribution_median_large_finite():
    from math import isfinite
    from core.research.study_aggregation import (
        StudyMetricDistribution,
    )

    result = StudyMetricDistribution.from_values(
        (-1.7e308, 1e308, 1e308, 1e308)
    )

    assert isfinite(result.mean)
    assert isfinite(result.median)
    assert result.median == pytest.approx(1e308)


@pytest.mark.parametrize(
    "n",
    (2, 3, 4, 5, 6, 7, 9),
)
def test_m94q_fresh_mean_representable_finite_maximum(n):
    import sys

    from core.research.study_aggregation import (
        StudyMetricDistribution,
    )

    maximum = sys.float_info.max
    distribution = StudyMetricDistribution.from_values(
        [maximum] * n
    )

    assert distribution.mean == maximum
    assert distribution.median == maximum
    assert distribution.minimum == maximum
    assert distribution.maximum == maximum
    assert distribution.count == n


def test_m94q_fresh_mean_preserves_subnormal_remainder():
    import math
    import sys
    from fractions import Fraction

    from core.research.study_aggregation import (
        StudyMetricDistribution,
    )

    maximum = sys.float_info.max
    tiny = math.ulp(0.0)

    values = [
        maximum,
        maximum,
        -maximum,
        -maximum,
    ] + [tiny] * 5

    exact = sum(
        (Fraction.from_float(value) for value in values),
        start=Fraction(0),
    )

    expected_mean = float(exact / len(values))

    assert expected_mean == tiny

    distribution = StudyMetricDistribution.from_values(
        values
    )

    assert distribution.mean == expected_mean
    assert distribution.count == 9


def test_m94q_fresh_mean_ordinary_positive_control():
    from core.research.study_aggregation import (
        StudyMetricDistribution,
    )

    distribution = StudyMetricDistribution.from_values(
        [100.0, 120.0, 108.0]
    )

    assert distribution.count == 3
    assert distribution.mean == pytest.approx(
        109.33333333333333
    )
    assert distribution.median == 108.0
    assert distribution.minimum == 100.0
    assert distribution.maximum == 120.0
    assert distribution.positive_count == 3
    assert distribution.positive_proportion == 1.0


def _m94q_final_cash_payload(case, *, valid):
    """Three-bar account histories for cash-conservation tests."""
    from core.research.reproducibility import (
        BACKTEST_RESULT_SCHEMA,
        decode_canonical_bytes,
    )

    payload = decode_canonical_bytes(
        _result_bytes(
            equities=(100000.0, 100000.0, 100000.0),
        ),
        schema=BACKTEST_RESULT_SCHEMA,
    )

    first, second, third = payload["bar_records"]

    for record in (first, second, third):
        record.update(
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
        )

    if case == "closed_loss":
        # Accepted M4 same-bar protective-exit shape.
        second.update(
            low=97.0,
            execution_event="PROTECTIVE_EXIT",
            execution_price=98.0,
            execution_quantity=1,
        )

        payload["trades"] = [
            {
                "symbol": "NSE:A",
                "entry_time": second["timestamp"],
                "exit_time": second["timestamp"],
                "entry_price": 100.0,
                "exit_price": 98.0,
                "stop_price": 98.0,
                "quantity": 1,
                "direction": "LONG",
                "exit_reason": "STOP_LOSS",
                "pnl": -2.0,
                "gross_pnl": -2.0,
                "transaction_cost": 0.0,
                "pnl_pct": -2.0,
            }
        ]

        if valid:
            second["cash"] = 99998.0
            third["cash"] = 99998.0
        else:
            third["cash"] = 101000.0

    elif case == "closed_profit":
        second.update(
            cash=99900.0,
            position_size=1.0,
            execution_event="BUY",
            execution_price=100.0,
            execution_quantity=1,
        )

        third.update(
            open=101.0,
            high=102.0,
            low=100.0,
            close=101.0,
            execution_event="SELL",
            execution_price=101.0,
            execution_quantity=1,
            cash=(100001.0 if valid else 101000.0),
        )

        payload["trades"] = [
            {
                "symbol": "NSE:A",
                "entry_time": second["timestamp"],
                "exit_time": third["timestamp"],
                "entry_price": 100.0,
                "exit_price": 101.0,
                "stop_price": 98.0,
                "quantity": 1,
                "direction": "LONG",
                "exit_reason": "SIGNAL",
                "pnl": 1.0,
                "gross_pnl": 1.0,
                "transaction_cost": 0.0,
                "pnl_pct": 1.0,
            }
        ]

    elif case == "holding_disappears":
        if valid:
            # Genuine open holding remains funded and marked.
            second.update(
                cash=99900.0,
                position_size=1.0,
                execution_event="BUY",
                execution_price=100.0,
                execution_quantity=1,
            )
            third.update(
                cash=99900.0,
                position_size=1.0,
            )
        else:
            second.update(
                cash=99900.0,
                position_size=1.0,
                execution_event="BUY",
                execution_price=100.0,
                execution_quantity=1,
            )
            third.update(
                cash=101000.0,
                position_size=0.0,
            )
    else:
        raise AssertionError("unknown financial case")

    peak = 100000.0

    for record in payload["bar_records"]:
        record["equity"] = (
            record["cash"]
            + record["position_size"] * record["close"]
        )
        peak = max(peak, record["equity"])
        record["drawdown"] = (
            (record["equity"] - peak) / peak
        )

    payload["equity_curve"] = [
        (record["timestamp"], record["equity"])
        for record in payload["bar_records"]
    ]

    return payload


@pytest.mark.parametrize(
    "case",
    ("closed_loss", "closed_profit", "holding_disappears"),
)
@pytest.mark.parametrize(
    "boundary",
    ("direct", "decoder", "aggregation"),
)
def test_m94q_final_cash_unreconciled_is_rejected(
    tmp_path,
    case,
    boundary,
):
    from core.research.reproducibility import (
        BACKTEST_RESULT_SCHEMA,
        canonical_bytes,
        validate_stable_backtest_result_payload,
    )

    payload = _m94q_final_cash_payload(
        case,
        valid=False,
    )

    assert payload["bar_records"][-1]["cash"] == 101000.0

    if boundary == "direct":
        with pytest.raises(ValueError):
            validate_stable_backtest_result_payload(payload)

    elif boundary == "decoder":
        with pytest.raises(ValueError):
            decode_stable_backtest_result_bytes(
                canonical_bytes(
                    payload,
                    schema=BACKTEST_RESULT_SCHEMA,
                )
            )

    elif boundary == "aggregation":
        with pytest.raises(StudyAggregationError):
            _aggregate_real_executed_payload(
                tmp_path,
                canonical_bytes(
                    payload,
                    schema=BACKTEST_RESULT_SCHEMA,
                ),
            )

    else:
        raise AssertionError("unknown validation boundary")


@pytest.mark.parametrize(
    "case",
    ("closed_loss", "closed_profit", "holding_disappears"),
)
@pytest.mark.parametrize(
    "boundary",
    ("direct", "decoder", "aggregation"),
)
def test_m94q_final_cash_legitimate_accounts_stay_valid(
    tmp_path,
    case,
    boundary,
):
    from core.research.reproducibility import (
        BACKTEST_RESULT_SCHEMA,
        canonical_bytes,
        validate_stable_backtest_result_payload,
    )

    payload = _m94q_final_cash_payload(
        case,
        valid=True,
    )

    if boundary == "direct":
        assert validate_stable_backtest_result_payload(
            payload
        ) == payload

    elif boundary == "decoder":
        assert decode_stable_backtest_result_bytes(
            canonical_bytes(
                payload,
                schema=BACKTEST_RESULT_SCHEMA,
            )
        ) == payload

    elif boundary == "aggregation":
        result = _aggregate_real_executed_payload(
            tmp_path,
            canonical_bytes(
                payload,
                schema=BACKTEST_RESULT_SCHEMA,
            ),
        )

        assert result.executed_trials == 1
        assert result.result_bearing_trials == 1

    else:
        raise AssertionError("unknown validation boundary")


def _m94q_reconcile_synthetic_closed_trade(payload):
    """Give one completed long trade its own M4-style cash history."""
    from copy import deepcopy

    assert len(payload["trades"]) == 1
    assert len(payload["bar_records"]) == 2

    trade = payload["trades"][0]
    assert trade["direction"] == "LONG"
    assert trade["entry_time"] == NOW
    assert trade["exit_time"] in (
        None,
        NOW + timedelta(minutes=1),
    )

    quantity = trade["quantity"]
    entry_price = trade["entry_price"]
    exit_price = trade["exit_price"]
    total_cost = trade["transaction_cost"]

    assert isinstance(quantity, int) and quantity > 0
    assert 0 <= total_cost < 100000.0
    assert entry_price * quantity + total_cost < 100000.0

    initial_cash = 100000.0
    entry_cost = total_cost / 2.0

    first, second = payload["bar_records"]
    initial = deepcopy(first)
    entry = deepcopy(first)
    closed = deepcopy(second)

    initial.update(
        timestamp=NOW - timedelta(minutes=1),
        open=100.0,
        high=100.0,
        low=100.0,
        close=100.0,
        position_size=0.0,
        cash=initial_cash,
        equity=initial_cash,
        drawdown=0.0,
        execution_event=None,
        execution_price=None,
        execution_quantity=None,
    )

    entry_cash = (
        initial_cash
        - entry_price * quantity
        - entry_cost
    )
    entry.update(
        timestamp=NOW,
        open=entry_price,
        high=entry_price,
        low=entry_price,
        close=entry_price,
        position_size=float(quantity),
        cash=entry_cash,
        equity=entry_cash + entry_price * quantity,
        execution_event="BUY",
        execution_price=entry_price,
        execution_quantity=quantity,
    )

    closed_cash = initial_cash + trade["pnl"]
    closed.update(
        timestamp=NOW + timedelta(minutes=1),
        open=exit_price,
        high=exit_price,
        low=exit_price,
        close=exit_price,
        position_size=0.0,
        cash=closed_cash,
        equity=closed_cash,
        execution_event="SELL",
        execution_price=exit_price,
        execution_quantity=quantity,
    )

    payload["bar_records"] = [initial, entry, closed]

    peak = initial_cash
    for record in payload["bar_records"]:
        peak = max(peak, record["equity"])
        record["drawdown"] = (
            (record["equity"] - peak) / peak
        )

    payload["equity_curve"] = [
        (record["timestamp"], record["equity"])
        for record in payload["bar_records"]
    ]


def _m94q_reconcile_synthetic_open_holding(payload):
    """Fund one long holding and retain it at the terminal bar."""
    assert not payload["trades"]
    assert len(payload["bar_records"]) == 2

    initial, holding = payload["bar_records"]
    initial.update(
        cash=1000.0,
        equity=1000.0,
        position_size=0.0,
        drawdown=0.0,
        execution_event=None,
        execution_price=None,
        execution_quantity=None,
    )
    holding.update(
        cash=900.0,
        position_size=1.0,
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        equity=1001.0,
        drawdown=0.0,
        execution_event="BUY",
        execution_price=100.0,
        execution_quantity=1,
    )

    payload["equity_curve"] = [
        (record["timestamp"], record["equity"])
        for record in payload["bar_records"]
    ]


@pytest.mark.parametrize(
    "boundary",
    ("direct", "decoder"),
)
@pytest.mark.parametrize(
    "case",
    (
        "valid_sell",
        "valid_stop_exit",
        "missing_exit_event",
        "incorrect_buy_event",
        "incorrect_exit_price",
        "incorrect_exit_quantity",
        "forged_terminal_cash",
        "missing_completed_trade",
    ),
)
def test_m94q_nullable_exit_requires_observed_settlement_evidence(
    boundary, case,
):
    """A nullable exit needs real bar settlement, not merely a trade."""
    from core.research.reproducibility import (
        validate_stable_backtest_result_payload,
    )

    payload = decode_canonical_bytes(
        _result_bytes(equities=(100.0, 100.0)),
        schema=BACKTEST_RESULT_SCHEMA,
    )

    payload["trades"].append({
        "symbol": "NSE:A",
        "entry_time": NOW,
        "entry_price": 100.0,
        "exit_time": None,
        "exit_price": 101.0,
        "stop_price": 99.0,
        "quantity": 1,
        "direction": "LONG",
        "exit_reason": "fixture",
        "pnl": 1.0,
        "gross_pnl": 1.0,
        "transaction_cost": 0.0,
        "pnl_pct": 1.0,
    })

    _m94q_reconcile_synthetic_closed_trade(payload)

    exit_record = payload["bar_records"][-1]

    if case == "valid_stop_exit":
        exit_record["execution_event"] = "STOP_EXIT"

    elif case == "missing_exit_event":
        exit_record["execution_event"] = None
        exit_record["execution_price"] = None
        exit_record["execution_quantity"] = None

    elif case == "incorrect_buy_event":
        exit_record["execution_event"] = "BUY"

    elif case == "incorrect_exit_price":
        exit_record["execution_price"] = 100.5

    elif case == "incorrect_exit_quantity":
        exit_record["execution_quantity"] = 2

    elif case == "forged_terminal_cash":
        exit_record["cash"] += 10.0
        exit_record["equity"] += 10.0
        payload["equity_curve"][-1] = (
            exit_record["timestamp"],
            exit_record["equity"],
        )

    elif case == "missing_completed_trade":
        payload["trades"].clear()

    else:
        assert case == "valid_sell"

    def verify():
        if boundary == "direct":
            return validate_stable_backtest_result_payload(
                payload
            )

        return decode_stable_backtest_result_bytes(
            canonical_bytes(
                payload,
                schema=BACKTEST_RESULT_SCHEMA,
            )
        )

    if case in ("valid_sell", "valid_stop_exit"):
        verified = verify()
        assert verified["bar_records"][-1]["cash"] == 100001.0
        assert verified["trades"][0]["exit_time"] is None
        assert verified["trades"][0]["pnl"] == 1.0
    else:
        expected_message = (
            "terminal flat cash"
            if case == "forged_terminal_cash"
            else "holding decreased without"
        )
        with pytest.raises(
            ValueError,
            match=expected_message,
        ):
            verify()


def test_m94q_rereview_reused_evidence_lineage_mismatch_rejected():
    """REUSED Study evidence must match its source RunAttempt."""
    catalog = CatalogStub()

    source_attempt = catalog.attempts["attempt-reused"]
    source_attempt.evidence_id = "evidence-reused"

    original_job = catalog.jobs[REUSED_TRIAL_ID][0]

    tampered_job = SimpleNamespace(
        **vars(original_job),
    )
    tampered_job.reused_evidence_id = "evidence-wrong"

    catalog.jobs[REUSED_TRIAL_ID] = (
        tampered_job,
    )

    with pytest.raises(
        StudyAggregationError,
        match="evidence|lineage",
    ):
        StudyAggregationService(
            catalog_store=catalog,
            artifact_store=ArtifactStoreStub(),
        ).aggregate_revision(
            REVISION_ID
        )


def test_m94q_rereview_aggregation_rejects_registered_population_denominator_drift(
    tmp_path,
):
    """Study aggregation must preserve the registered Trial denominator."""
    import runpy
    import sqlite3
    from pathlib import Path

    queue_ns = runpy.run_path(
        str(
            Path(__file__).with_name(
                "test_m94c_research_job_queue.py"
            )
        )
    )

    (
        catalog,
        registration,
        _queue,
        definition,
        snapshot,
    ) = queue_ns["_environment"](
        tmp_path
    )

    population = queue_ns["_register"](
        registration,
        definition,
        snapshot,
        intent="aggregation denominator integrity",
        registered_at=queue_ns["MAR"],
    )

    revision_id = (
        population.revision.study_revision_id
    )

    service = StudyAggregationService(
        catalog_store=catalog,
        artifact_store=ArtifactStoreStub(),
    )

    baseline = service.aggregate_revision(
        revision_id
    )

    assert baseline.total_registered_trials == 6
    assert baseline.pending_trials == 6

    victim = population.trials[0]

    with sqlite3.connect(
        catalog.database_path
    ) as connection:
        connection.execute(
            """
            DELETE FROM trial_disposition_events
            WHERE trial_id = ?
            """,
            (victim.trial_id,),
        )
        connection.execute(
            """
            DELETE FROM trials
            WHERE trial_id = ?
            """,
            (victim.trial_id,),
        )
        connection.commit()

    assert len(
        catalog.list_trials_for_revision(
            revision_id
        )
    ) == 5

    with pytest.raises(
        StudyAggregationError,
        match="population|denominator|proof",
    ):
        service.aggregate_revision(
            revision_id
        )
