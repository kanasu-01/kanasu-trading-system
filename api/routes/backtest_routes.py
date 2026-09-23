from fastapi import APIRouter

from api.application_catalog import (
    backtest_config_payload,
)

from api.models.backtest_models import (
    BacktestConfigResponse,
)

router = APIRouter()


@router.get(
    "/config",
    response_model=BacktestConfigResponse,
)
async def get_backtest_config(
) -> BacktestConfigResponse:
    return BacktestConfigResponse.model_validate(
        backtest_config_payload()
    )


@router.post("/run")
async def run_backtest(
    payload: dict,
):
    return {
        "run_id": "bt_mock_001",
        "status": "completed",
        "summary": {
            "total_trades": 6,
            "win_rate": 50.0,
            "net_pnl": -2500,
            "max_drawdown": 6.13,
            "expectancy": -0.59,
        },
        "equity_curve": [],
        "trades": [],
        "replay_available": True,
    }
