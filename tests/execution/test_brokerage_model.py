from core.execution.brokerage_model import (
    BrokerageModel,
)


def test_brokerage_model_calculates_costs():

    model = BrokerageModel()

    result = model.calculate(
        turnover=100000,
    )

    assert result is not None

    assert result.brokerage >= 0

    assert result.taxes >= 0

    assert result.total_cost >= 0

    assert result.total_cost == result.brokerage + result.taxes
