from fastapi import APIRouter

router = APIRouter()


@router.get("/config")
async def get_backtest_config():
    return {
        "markets": [
            {
                "id": "NSE",
                "name": "NSE",
            },
            {
                "id": "BSE",
                "name": "BSE",
            },
        ],
        "symbols": [
            {
                "symbol": "RELIANCE",
                "exchange": "NSE",
            },
            {
                "symbol": "TCS",
                "exchange": "NSE",
            },
        ],
        "timeframes": [
            {
                "id": "5m",
                "label": "5 Minutes",
            },
            {
                "id": "15m",
                "label": "15 Minutes",
            },
        ],
        "strategies": [
            {
                "id": "sma_crossover",
                "name": "SMA Crossover",
            },
            {
                "id": "camarilla",
                "name": "Camarilla",
            },
        ],
    }


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
